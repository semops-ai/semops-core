"""
Episode model for Episode-Centric Provenance.

An Episode represents one meaningful operation that modifies the DDD layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import hashlib
import ulid


class OperationType(str, Enum):
    """Types of operations that create episodes."""

    INGEST = "ingest"  # new entity created from source
    CLASSIFY = "classify"  # entity gets primary_pattern_id
    DECLARE_PATTERN = "declare_pattern"  # new pattern created from synthesis
    PUBLISH = "publish"  # delivery created (original)
    SYNTHESIZE = "synthesize"  # research → pattern emergence
    CREATE_EDGE = "create_edge"  # relationship established
    EMBED = "embed"  # embedding generated


class TargetType(str, Enum):
    """Types of targets that can be modified."""

    ENTITY = "entity"
    PATTERN = "pattern"
    EDGE = "edge"
    DELIVERY = "delivery"


@dataclass
class DetectedEdge:
    """A relationship detected/proposed by an agent."""

    predicate: str  # derived_from, cites, related_to, etc.
    target_id: str  # ID of the related artifact
    strength: float = 1.0  # 0.0-1.0
    rationale: str | None = None  # Why the agent thinks this relationship exists

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicate": self.predicate,
            "target_id": self.target_id,
            "strength": self.strength,
            "rationale": self.rationale,
        }


@dataclass
class Episode:
    """
    An episode in the provenance chain.

    Episodes are created automatically when DDD-touching operations execute.
    They capture the full context needed for "why was this classified this way?" audits.
    """

    # Required fields
    operation: OperationType
    target_type: TargetType
    target_id: str

    # Auto-generated
    id: str = field(default_factory=lambda: str(ulid.new()))
    created_at: datetime = field(default_factory=datetime.now)

    # Run context (set by LineageTracker)
    run_id: str | None = None

    # Context used (for classification/declaration audits)
    context_pattern_ids: list[str] = field(default_factory=list)
    context_entity_ids: list[str] = field(default_factory=list)

    # Quality signals
    coherence_score: float | None = None

    # Agent info
    agent_name: str | None = None
    agent_version: str | None = None
    model_name: str | None = None
    prompt_hash: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)

    # Detected edges
    detected_edges: list[DetectedEdge] = field(default_factory=list)

    # Metadata
    input_hash: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_input_hash(self, content: str) -> str:
        """Compute SHA256 hash of input for deduplication."""
        self.input_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
        return self.input_hash

    def add_context_pattern(self, pattern_id: str) -> None:
        """Add a pattern to the context (retrieved/considered during operation)."""
        if pattern_id not in self.context_pattern_ids:
            self.context_pattern_ids.append(pattern_id)

    def add_context_entity(self, entity_id: str) -> None:
        """Add an entity to the context (used during operation)."""
        if entity_id not in self.context_entity_ids:
            self.context_entity_ids.append(entity_id)

    def add_detected_edge(
        self,
        predicate: str,
        target_id: str,
        strength: float = 1.0,
        rationale: str | None = None,
    ) -> None:
        """Add a model-detected relationship."""
        self.detected_edges.append(
            DetectedEdge(
                predicate=predicate,
                target_id=target_id,
                strength=strength,
                rationale=rationale,
            )
        )

    def set_agent_info(
        self,
        name: str,
        version: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
    ) -> None:
        """Set agent metadata for reproducibility."""
        self.agent_name = name
        self.agent_version = version
        self.model_name = model
        self.prompt_hash = prompt_hash

    def set_token_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int | None = None,
    ) -> None:
        """Record token usage for cost tracking."""
        self.token_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens or (prompt_tokens + completion_tokens),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "operation": self.operation.value,
            "target_type": self.target_type.value,
            "target_id": self.target_id,
            "context_pattern_ids": self.context_pattern_ids,
            "context_entity_ids": self.context_entity_ids,
            "coherence_score": self.coherence_score,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "model_name": self.model_name,
            "prompt_hash": self.prompt_hash,
            "token_usage": self.token_usage,
            "detected_edges": [e.to_dict() for e in self.detected_edges],
            "input_hash": self.input_hash,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
