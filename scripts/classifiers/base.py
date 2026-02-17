"""
Base classifier interface for semantic coherence evaluation.

All classifiers inherit from BaseClassifier and implement the classify() method.
Results are written to the classification table for audit and promotion workflow.
"""

import hashlib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration from environment variables."""

    semops_db_host: str = "localhost"
    semops_db_port: int = 5434
    semops_db_name: str = "postgres"
    semops_db_user: str = "postgres"
    semops_db_password: str = "postgres"

    # OpenAI for embeddings
    openai_api_key: str = ""

    # Anthropic for LLM classification
    anthropic_api_key: str = ""

    # Ollama for local embeddings/LLM
    ollama_host: str = "http://localhost:11434"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_llm_model: str = "mistral"

    class Config:
        env_file = ".env"
        extra = "ignore"


@dataclass
class ClassificationResult:
    """Result of a classification operation."""

    target_type: str  # 'concept' or 'entity'
    target_id: str
    classifier_id: str
    classifier_version: str
    scores: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    rationale: str | None = None
    input_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "classifier_id": self.classifier_id,
            "classifier_version": self.classifier_version,
            "scores": self.scores,
            "labels": self.labels,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "input_hash": self.input_hash,
        }


class BaseClassifier(ABC):
    """
    Base class for all classifiers.

    Subclasses must implement:
        - classifier_id: Unique identifier for this classifier
        - classifier_version: Semantic version
        - classify(): The classification logic
    """

    def __init__(self) -> None:
        self.settings = Settings()
        self._conn: psycopg.Connection | None = None

    @property
    @abstractmethod
    def classifier_id(self) -> str:
        """Unique identifier for this classifier (e.g., 'rule-completeness-v1')."""
        pass

    @property
    @abstractmethod
    def classifier_version(self) -> str:
        """Semantic version (e.g., '1.0.0')."""
        pass

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

    def close(self) -> None:
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

    def compute_input_hash(self, content: str) -> str:
        """Compute SHA256 hash of input for reproducibility."""
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    @abstractmethod
    def classify(
        self, target_type: str, target_id: str, content: dict[str, Any]
    ) -> ClassificationResult:
        """
        Classify a concept or entity.

        Args:
            target_type: 'concept' or 'entity'
            target_id: ID of the item to classify
            content: Dictionary containing the item's data

        Returns:
            ClassificationResult with scores, labels, and rationale
        """
        pass

    def save_result(self, result: ClassificationResult) -> str:
        """
        Save classification result to database.

        Returns:
            The generated classification ID
        """
        import json

        classification_id = str(uuid.uuid4())

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO classification (
                    id, target_type, target_id, classifier_id, classifier_version,
                    scores, labels, confidence, rationale, input_hash
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    classification_id,
                    result.target_type,
                    result.target_id,
                    result.classifier_id,
                    result.classifier_version,
                    json.dumps(result.scores),
                    json.dumps(result.labels),
                    result.confidence,
                    result.rationale,
                    result.input_hash,
                ),
            )
        self.conn.commit()

        return classification_id

    def classify_and_save(
        self, target_type: str, target_id: str, content: dict[str, Any]
    ) -> str:
        """Classify and save result in one step."""
        result = self.classify(target_type, target_id, content)
        return self.save_result(result)

    def get_pending_concepts(self) -> list[dict[str, Any]]:
        """Get all pending concepts for classification."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, preferred_label, definition, provenance, alt_labels,
                       metadata, created_at
                FROM concept
                WHERE approval_status = 'pending'
                ORDER BY created_at
            """)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_pending_entities(self) -> list[dict[str, Any]]:
        """Get all pending entities for classification."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, asset_type, visibility, primary_concept_id,
                       filespec, attribution, metadata, created_at
                FROM entity
                WHERE approval_status = 'pending'
                ORDER BY created_at
            """)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def classify_pending_concepts(self, limit: int | None = None) -> list[str]:
        """
        Classify all pending concepts.

        Args:
            limit: Maximum number to classify (None = all)

        Returns:
            List of classification IDs
        """
        concepts = self.get_pending_concepts()
        if limit:
            concepts = concepts[:limit]

        classification_ids = []
        for concept in concepts:
            try:
                cid = self.classify_and_save("concept", concept["id"], concept)
                classification_ids.append(cid)
                print(f"Classified concept: {concept['id']}")
            except Exception as e:
                print(f"Error classifying {concept['id']}: {e}")

        return classification_ids

    def classify_pending_entities(self, limit: int | None = None) -> list[str]:
        """
        Classify all pending entities.

        Args:
            limit: Maximum number to classify (None = all)

        Returns:
            List of classification IDs
        """
        entities = self.get_pending_entities()
        if limit:
            entities = entities[:limit]

        classification_ids = []
        for entity in entities:
            try:
                cid = self.classify_and_save("entity", entity["id"], entity)
                classification_ids.append(cid)
                print(f"Classified entity: {entity['id']}")
            except Exception as e:
                print(f"Error classifying {entity['id']}: {e}")

        return classification_ids
