"""
Decorators for automatic lineage emission.

These decorators instrument functions to automatically emit lineage episodes.
Inspired by OpenLineage's automatic event emission model.

Usage:
    @emit_lineage(operation=OperationType.CLASSIFY)
    def classify_entity(entity_id: str, patterns: list[str]) -> ClassificationResult:
        # The decorator will:
        # 1. Create an episode before the function runs
        # 2. Capture the result and any context
        # 3. Complete the episode after the function returns
        return result
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from .episode import Episode, OperationType, TargetType
from .tracker import LineageTracker, create_standalone_episode

F = TypeVar("F", bound=Callable[..., Any])


class LineageContext:
    """
    Thread-local context for lineage tracking.

    Allows nested operations to share a tracker and add context to episodes.
    """

    _current_tracker: LineageTracker | None = None
    _current_episode: Episode | None = None

    @classmethod
    def set_tracker(cls, tracker: LineageTracker) -> None:
        """Set the current tracker for this thread."""
        cls._current_tracker = tracker

    @classmethod
    def get_tracker(cls) -> LineageTracker | None:
        """Get the current tracker for this thread."""
        return cls._current_tracker

    @classmethod
    def set_episode(cls, episode: Episode) -> None:
        """Set the current episode for this thread."""
        cls._current_episode = episode

    @classmethod
    def get_episode(cls) -> Episode | None:
        """Get the current episode for this thread."""
        return cls._current_episode

    @classmethod
    def clear(cls) -> None:
        """Clear the current context."""
        cls._current_tracker = None
        cls._current_episode = None


def emit_lineage(
    operation: OperationType,
    target_type: TargetType | str = TargetType.ENTITY,
    target_id_param: str = "entity_id",
    agent_name: str | None = None,
    agent_version: str | None = None,
    extract_context: Callable[[Any], dict[str, Any]] | None = None,
) -> Callable[[F], F]:
    """
    Decorator that emits lineage episodes for function calls.

    Args:
        operation: Type of operation being performed
        target_type: Type of target being modified (default: entity)
        target_id_param: Name of the parameter containing the target ID
        agent_name: Name of the agent (defaults to function name)
        agent_version: Version of the agent
        extract_context: Optional function to extract context from the result

    Returns:
        Decorated function

    Example:
        @emit_lineage(
            operation=OperationType.CLASSIFY,
            target_id_param="entity_id",
            agent_name="llm_classifier",
        )
        def classify_entity(entity_id: str, content: str) -> ClassificationResult:
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get target_id from args/kwargs
            target_id = _extract_param(func, target_id_param, args, kwargs)
            if target_id is None:
                # If we can't find the target_id, just run the function without tracking
                return func(*args, **kwargs)

            # Get or create tracker
            tracker = LineageContext.get_tracker()

            if tracker is not None:
                # Use existing tracker from context
                with tracker.track_operation(
                    operation=operation,
                    target_type=target_type,
                    target_id=target_id,
                ) as episode:
                    # Set agent info
                    episode.set_agent_info(
                        name=agent_name or func.__name__,
                        version=agent_version,
                    )

                    # Make episode available in context
                    LineageContext.set_episode(episode)

                    try:
                        result = func(*args, **kwargs)

                        # Extract context from result if function provided
                        if extract_context and result is not None:
                            context = extract_context(result)
                            for pattern_id in context.get("pattern_ids", []):
                                episode.add_context_pattern(pattern_id)
                            for entity_id in context.get("entity_ids", []):
                                episode.add_context_entity(entity_id)
                            if "coherence_score" in context:
                                episode.coherence_score = context["coherence_score"]
                            if "detected_edges" in context:
                                for edge in context["detected_edges"]:
                                    episode.add_detected_edge(**edge)

                        return result
                    finally:
                        LineageContext.set_episode(None)
            else:
                # Create standalone episode
                episode = Episode(
                    operation=operation,
                    target_type=(
                        TargetType(target_type)
                        if isinstance(target_type, str)
                        else target_type
                    ),
                    target_id=target_id,
                )
                episode.set_agent_info(
                    name=agent_name or func.__name__,
                    version=agent_version,
                )

                LineageContext.set_episode(episode)

                try:
                    result = func(*args, **kwargs)

                    # Extract context from result
                    if extract_context and result is not None:
                        context = extract_context(result)
                        for pattern_id in context.get("pattern_ids", []):
                            episode.add_context_pattern(pattern_id)
                        for entity_id in context.get("entity_ids", []):
                            episode.add_context_entity(entity_id)
                        if "coherence_score" in context:
                            episode.coherence_score = context["coherence_score"]
                        if "detected_edges" in context:
                            for edge in context["detected_edges"]:
                                episode.add_detected_edge(**edge)

                    # Persist standalone episode
                    create_standalone_episode(
                        operation=operation,
                        target_type=target_type,
                        target_id=target_id,
                        agent_name=episode.agent_name,
                        agent_version=episode.agent_version,
                        context_pattern_ids=episode.context_pattern_ids,
                        context_entity_ids=episode.context_entity_ids,
                        coherence_score=episode.coherence_score,
                        detected_edges=episode.detected_edges,
                    )

                    return result
                except Exception as e:
                    episode.error_message = str(e)
                    create_standalone_episode(
                        operation=operation,
                        target_type=target_type,
                        target_id=target_id,
                        agent_name=episode.agent_name,
                        error_message=episode.error_message,
                    )
                    raise
                finally:
                    LineageContext.set_episode(None)

        return wrapper  # type: ignore

    return decorator


def _extract_param(
    func: Callable, param_name: str, args: tuple, kwargs: dict
) -> Any | None:
    """Extract a parameter value from function arguments."""
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Check kwargs first
    if param_name in kwargs:
        return kwargs[param_name]

    # Check positional args
    if param_name in params:
        idx = params.index(param_name)
        if idx < len(args):
            return args[idx]

    return None


def add_context_pattern(pattern_id: str) -> None:
    """
    Add a pattern to the current episode's context.

    Call this from within a function decorated with @emit_lineage
    to record which patterns were used during the operation.

    Example:
        @emit_lineage(operation=OperationType.CLASSIFY)
        def classify_entity(entity_id: str) -> ClassificationResult:
            patterns = retrieve_patterns(entity_id)
            for p in patterns:
                add_context_pattern(p.id)  # Record which patterns were considered
            return classify(entity_id, patterns)
    """
    episode = LineageContext.get_episode()
    if episode:
        episode.add_context_pattern(pattern_id)


def add_context_entity(entity_id: str) -> None:
    """
    Add an entity to the current episode's context.

    Call this from within a function decorated with @emit_lineage
    to record which entities were used during the operation.
    """
    episode = LineageContext.get_episode()
    if episode:
        episode.add_context_entity(entity_id)


def set_coherence_score(score: float) -> None:
    """
    Set the coherence score for the current episode.

    Call this from within a function decorated with @emit_lineage.
    """
    episode = LineageContext.get_episode()
    if episode:
        episode.coherence_score = score


def add_detected_edge(
    predicate: str,
    target_id: str,
    strength: float = 1.0,
    rationale: str | None = None,
) -> None:
    """
    Add a detected edge to the current episode.

    Call this from within a function decorated with @emit_lineage
    to record relationships detected by the agent.
    """
    episode = LineageContext.get_episode()
    if episode:
        episode.add_detected_edge(predicate, target_id, strength, rationale)


def set_token_usage(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int | None = None,
) -> None:
    """
    Set token usage for the current episode.

    Call this from within a function decorated with @emit_lineage
    to record LLM token consumption.
    """
    episode = LineageContext.get_episode()
    if episode:
        episode.set_token_usage(prompt_tokens, completion_tokens, total_tokens)
