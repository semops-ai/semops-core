"""
Episode-Centric Provenance for Semantic Operations.

This module provides instrumentation for tracking lineage of all DDD-touching
operations. Inspired by OpenLineage's automatic event emission model.

Usage:
    from lineage import LineageTracker, emit_lineage, OperationType

    # Context manager for runs
    with LineageTracker(source_name="my-source") as tracker:
        # Episodes are automatically tracked
        result = tracker.track_episode(
            operation=OperationType.INGEST,
            target_type="entity",
            target_id="my-entity-id",
            func=my_ingest_function,
            args=(arg1, arg2),
        )

    # Or use decorator for simple cases
    @emit_lineage(operation=OperationType.CLASSIFY)
    def classify_entity(entity_id: str) -> ClassificationResult:
        ...
"""

from .tracker import LineageTracker
from .episode import Episode, OperationType
from .decorators import emit_lineage

__all__ = [
    "LineageTracker",
    "Episode",
    "OperationType",
    "emit_lineage",
]
