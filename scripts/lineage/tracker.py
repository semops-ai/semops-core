"""
LineageTracker - Main interface for Episode-Centric Provenance.

Usage:
    with LineageTracker(source_name="my-source") as tracker:
        # Track an operation
        episode = tracker.start_episode(
            operation=OperationType.INGEST,
            target_type=TargetType.ENTITY,
            target_id="my-entity-id",
        )

        # ... do the work ...

        # Add context
        episode.add_context_pattern("pattern-used")
        episode.coherence_score = 0.85

        # Complete the episode
        tracker.complete_episode(episode)
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Generator

import psycopg
import ulid
from pydantic_settings import BaseSettings

from .episode import Episode, OperationType, TargetType


class TrackerSettings(BaseSettings):
    """Configuration from environment variables (ADR-0010)."""

    semops_db_host: str = "localhost"
    semops_db_port: int = 5434
    semops_db_name: str = "postgres"
    semops_db_user: str = "postgres"
    semops_db_password: str = "postgres"

    class Config:
        env_file = ".env"
        extra = "ignore"


class LineageTracker:
    """
    Tracks ingestion runs and their episodes.

    Use as a context manager for automatic run lifecycle management:

        with LineageTracker(source_name="my-source") as tracker:
            episode = tracker.start_episode(...)
            # ... do work ...
            tracker.complete_episode(episode)

    Episodes are persisted to the database for lineage audits.
    """

    def __init__(
        self,
        source_name: str | None = None,
        run_type: str = "manual",
        agent_name: str | None = None,
        source_config: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ):
        """
        Initialize a lineage tracker.

        Args:
            source_name: Name of the source being ingested
            run_type: 'manual', 'scheduled', or 'agent'
            agent_name: Name of the agent/script running the ingestion
            source_config: Configuration snapshot for reproducibility
            conn: Optional existing database connection
        """
        self.source_name = source_name
        self.run_type = run_type
        self.agent_name = agent_name
        self.source_config = source_config or {}

        self.settings = TrackerSettings()
        self._conn = conn
        self._owns_conn = conn is None

        self.run_id: str | None = None
        self.started_at: datetime | None = None
        self._episodes: list[Episode] = []
        self._metrics: dict[str, int] = {
            "entities_created": 0,
            "entities_updated": 0,
            "patterns_created": 0,
            "edges_created": 0,
            "errors": 0,
        }

    @property
    def conn(self) -> psycopg.Connection:
        """Lazy database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(
                host=self.settings.semops_db_host,
                port=self.settings.semops_db_port,
                dbname=self.settings.semops_db_name,
                user=self.settings.semops_db_user,
                password=self.settings.semops_db_password,
            )
        return self._conn

    def __enter__(self) -> LineageTracker:
        """Start a new ingestion run."""
        self.run_id = str(ulid.new())
        self.started_at = datetime.now()

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_run (
                    id, run_type, agent_name, source_name, started_at, status, source_config
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self.run_id,
                    self.run_type,
                    self.agent_name,
                    self.source_name,
                    self.started_at,
                    "running",
                    json.dumps(self.source_config),
                ),
            )
        self.conn.commit()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Complete the ingestion run."""
        status = "failed" if exc_type else "completed"

        if exc_type:
            self._metrics["errors"] += 1

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_run
                SET completed_at = %s, status = %s, metrics = %s
                WHERE id = %s
                """,
                (
                    datetime.now(),
                    status,
                    json.dumps(self._metrics),
                    self.run_id,
                ),
            )
        self.conn.commit()

        if self._owns_conn and self._conn:
            self._conn.close()

    def start_episode(
        self,
        operation: OperationType,
        target_type: TargetType | str,
        target_id: str,
        **kwargs: Any,
    ) -> Episode:
        """
        Start a new episode.

        Args:
            operation: Type of operation being performed
            target_type: Type of target being modified
            target_id: ID of the target
            **kwargs: Additional Episode fields

        Returns:
            Episode instance to be populated during the operation
        """
        if isinstance(target_type, str):
            target_type = TargetType(target_type)

        episode = Episode(
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            run_id=self.run_id,
            **kwargs,
        )

        self._episodes.append(episode)
        return episode

    def complete_episode(self, episode: Episode) -> str:
        """
        Complete and persist an episode.

        Args:
            episode: The episode to complete

        Returns:
            The episode ID
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_episode (
                    id, run_id, operation, target_type, target_id,
                    context_pattern_ids, context_entity_ids, coherence_score,
                    agent_name, agent_version, model_name, prompt_hash, token_usage,
                    detected_edges, input_hash, error_message, metadata, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    episode.id,
                    episode.run_id,
                    episode.operation.value,
                    episode.target_type.value,
                    episode.target_id,
                    episode.context_pattern_ids,
                    episode.context_entity_ids,
                    episode.coherence_score,
                    episode.agent_name,
                    episode.agent_version,
                    episode.model_name,
                    episode.prompt_hash,
                    json.dumps(episode.token_usage),
                    json.dumps([e.to_dict() for e in episode.detected_edges]),
                    episode.input_hash,
                    episode.error_message,
                    json.dumps(episode.metadata),
                    episode.created_at,
                ),
            )
        self.conn.commit()

        # Update metrics
        self._update_metrics(episode)

        return episode.id

    def fail_episode(self, episode: Episode, error: str) -> str:
        """
        Mark an episode as failed and persist it.

        Args:
            episode: The episode that failed
            error: Error message

        Returns:
            The episode ID
        """
        episode.error_message = error
        self._metrics["errors"] += 1
        return self.complete_episode(episode)

    def _update_metrics(self, episode: Episode) -> None:
        """Update run-level metrics based on episode."""
        if episode.error_message:
            return  # Don't count errors as successes

        if episode.operation == OperationType.INGEST:
            self._metrics["entities_created"] += 1
        elif episode.operation == OperationType.DECLARE_PATTERN:
            self._metrics["patterns_created"] += 1
        elif episode.operation == OperationType.CREATE_EDGE:
            self._metrics["edges_created"] += 1

    def increment_metric(self, metric: str, count: int = 1) -> None:
        """Manually increment a metric."""
        if metric in self._metrics:
            self._metrics[metric] += count
        else:
            self._metrics[metric] = count

    @contextmanager
    def track_operation(
        self,
        operation: OperationType,
        target_type: TargetType | str,
        target_id: str,
        **kwargs: Any,
    ) -> Generator[Episode, None, None]:
        """
        Context manager for tracking an operation.

        Usage:
            with tracker.track_operation(OperationType.INGEST, "entity", "my-id") as episode:
                # Do the work
                episode.add_context_pattern("pattern-used")
                episode.coherence_score = 0.85
            # Episode is automatically completed

        Args:
            operation: Type of operation
            target_type: Type of target
            target_id: ID of target
            **kwargs: Additional Episode fields

        Yields:
            Episode instance
        """
        episode = self.start_episode(operation, target_type, target_id, **kwargs)
        try:
            yield episode
            self.complete_episode(episode)
        except Exception as e:
            self.fail_episode(episode, str(e))
            raise


def create_standalone_episode(
    operation: OperationType,
    target_type: TargetType | str,
    target_id: str,
    conn: psycopg.Connection | None = None,
    **kwargs: Any,
) -> Episode:
    """
    Create and persist a standalone episode (not part of a run).

    Useful for one-off operations that don't need run-level tracking.

    Args:
        operation: Type of operation
        target_type: Type of target
        target_id: ID of target
        conn: Optional database connection
        **kwargs: Additional Episode fields

    Returns:
        The created Episode
    """
    settings = TrackerSettings()

    if conn is None:
        conn = psycopg.connect(
            host=settings.semops_db_host,
            port=settings.semops_db_port,
            dbname=settings.semops_db_name,
            user=settings.semops_db_user,
            password=settings.semops_db_password,
        )
        owns_conn = True
    else:
        owns_conn = False

    if isinstance(target_type, str):
        target_type = TargetType(target_type)

    episode = Episode(
        operation=operation,
        target_type=target_type,
        target_id=target_id,
        **kwargs,
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_episode (
                    id, run_id, operation, target_type, target_id,
                    context_pattern_ids, context_entity_ids, coherence_score,
                    agent_name, agent_version, model_name, prompt_hash, token_usage,
                    detected_edges, input_hash, error_message, metadata, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    episode.id,
                    episode.run_id,
                    episode.operation.value,
                    episode.target_type.value,
                    episode.target_id,
                    episode.context_pattern_ids,
                    episode.context_entity_ids,
                    episode.coherence_score,
                    episode.agent_name,
                    episode.agent_version,
                    episode.model_name,
                    episode.prompt_hash,
                    json.dumps(episode.token_usage),
                    json.dumps([e.to_dict() for e in episode.detected_edges]),
                    episode.input_hash,
                    episode.error_message,
                    json.dumps(episode.metadata),
                    episode.created_at,
                ),
            )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()

    return episode
