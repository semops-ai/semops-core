"""
Local embedding-based classifier using Ollama.

Uses nomic-embed-text via Ollama for semantic similarity evaluation.
Works with embedding_local column (768 dimensions).
"""

import json
import subprocess
from typing import Any

from .base import BaseClassifier, ClassificationResult


class LocalEmbeddingClassifier(BaseClassifier):
    """
    Local embedding classifier using Ollama + nomic-embed-text.

    Evaluates:
        - coherence: Average similarity to related concepts
        - duplicate_similarity: Highest similarity to another concept
        - nearest_approved_distance: Distance to nearest approved concept

    Uses embedding_local column (768 dims) instead of embedding (1536 dims).
    """

    # Thresholds
    COHERENCE_THRESHOLD = 0.6
    DUPLICATE_THRESHOLD = 0.95
    ORPHAN_THRESHOLD = 0.7

    @property
    def classifier_id(self) -> str:
        return "embedding-local-v1"

    @property
    def classifier_version(self) -> str:
        return "1.0.0"

    def get_embedding(self, text: str) -> list[float] | None:
        """Generate embedding using Ollama."""
        try:
            result = subprocess.run(
                [
                    "curl", "-s", f"{self.settings.ollama_host}/api/embeddings",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps({
                        "model": self.settings.ollama_embedding_model,
                        "prompt": text
                    })
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return None

            response = json.loads(result.stdout)
            return response.get("embedding")

        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return None

    def ensure_embedding(self, concept_id: str, content: dict[str, Any]) -> bool:
        """Ensure concept has a local embedding, generate if missing."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT embedding_local IS NOT NULL FROM concept WHERE id = %s",
                (concept_id,),
            )
            result = cur.fetchone()
            if result and result[0]:
                return True

            # Generate embedding
            label = content.get("preferred_label", "")
            definition = content.get("definition", "")
            text = f"{label}: {definition}"

            embedding = self.get_embedding(text)
            if embedding is None:
                return False

            # Update database
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            cur.execute(
                "UPDATE concept SET embedding_local = %s::vector WHERE id = %s",
                (embedding_str, concept_id),
            )
            self.conn.commit()
            return True

    def get_coherence_score(self, concept_id: str) -> tuple[float, list[str]]:
        """
        Calculate coherence as average similarity to related concepts.

        Returns: (coherence_score, list of related concept IDs)
        """
        with self.conn.cursor() as cur:
            # Get related concepts via concept_edge
            cur.execute(
                """
                SELECT DISTINCT
                    CASE WHEN src_id = %s THEN dst_id ELSE src_id END as related_id
                FROM concept_edge
                WHERE (src_id = %s OR dst_id = %s)
                  AND predicate IN ('broader', 'narrower', 'related')
                """,
                (concept_id, concept_id, concept_id),
            )
            related_ids = [row[0] for row in cur.fetchall()]

            if not related_ids:
                return 0.5, []  # Default for isolated concepts

            # Calculate average similarity
            placeholders = ",".join(["%s"] * len(related_ids))
            cur.execute(
                f"""
                SELECT AVG(1 - (c1.embedding_local <=> c2.embedding_local))
                FROM concept c1, concept c2
                WHERE c1.id = %s
                  AND c2.id IN ({placeholders})
                  AND c1.embedding_local IS NOT NULL
                  AND c2.embedding_local IS NOT NULL
                """,
                [concept_id] + related_ids,
            )
            result = cur.fetchone()
            coherence = result[0] if result and result[0] else 0.0

            return float(coherence), related_ids

    def get_duplicate_similarity(self, concept_id: str) -> tuple[float, str | None]:
        """
        Find highest similarity to any other concept.

        Returns: (similarity, potential_duplicate_id)
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c2.id,
                    1 - (c1.embedding_local <=> c2.embedding_local) as similarity
                FROM concept c1, concept c2
                WHERE c1.id = %s
                  AND c2.id != %s
                  AND c1.embedding_local IS NOT NULL
                  AND c2.embedding_local IS NOT NULL
                ORDER BY c1.embedding_local <=> c2.embedding_local
                LIMIT 1
                """,
                (concept_id, concept_id),
            )
            result = cur.fetchone()
            if result:
                return float(result[1]), result[0]
            return 0.0, None

    def get_nearest_approved(self, concept_id: str) -> tuple[float, str | None]:
        """
        Find nearest approved concept.

        Returns: (similarity, nearest_id)
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c2.id,
                    1 - (c1.embedding_local <=> c2.embedding_local) as similarity
                FROM concept c1, concept c2
                WHERE c1.id = %s
                  AND c2.id != %s
                  AND c2.approval_status = 'approved'
                  AND c1.embedding_local IS NOT NULL
                  AND c2.embedding_local IS NOT NULL
                ORDER BY c1.embedding_local <=> c2.embedding_local
                LIMIT 1
                """,
                (concept_id, concept_id),
            )
            result = cur.fetchone()
            if result:
                return float(result[1]), result[0]
            return 0.0, None

    def classify(
        self, target_type: str, target_id: str, content: dict[str, Any]
    ) -> ClassificationResult:
        """Classify a concept using local embeddings."""

        if target_type != "concept":
            raise ValueError("LocalEmbeddingClassifier only supports concepts")

        # Ensure embedding exists
        if not self.ensure_embedding(target_id, content):
            return ClassificationResult(
                target_type=target_type,
                target_id=target_id,
                classifier_id=self.classifier_id,
                classifier_version=self.classifier_version,
                scores={"error": "Could not generate embedding"},
                labels={"status": "error"},
                confidence=0.0,
                rationale="Failed to generate or retrieve embedding",
            )

        # Calculate scores
        coherence, related_ids = self.get_coherence_score(target_id)
        dup_similarity, dup_id = self.get_duplicate_similarity(target_id)
        nearest_sim, nearest_id = self.get_nearest_approved(target_id)

        # Determine labels
        labels = {}
        if dup_similarity > self.DUPLICATE_THRESHOLD:
            labels["potential_duplicate"] = dup_id
        if nearest_sim < self.ORPHAN_THRESHOLD:
            labels["orphan_candidate"] = True
        if nearest_id:
            labels["nearest_approved"] = nearest_id

        # Determine promotion readiness
        promotion_ready = (
            coherence >= self.COHERENCE_THRESHOLD
            and dup_similarity < self.DUPLICATE_THRESHOLD
            and nearest_sim >= self.ORPHAN_THRESHOLD
        )

        scores = {
            "coherence": coherence,
            "duplicate_similarity": dup_similarity,
            "nearest_approved_similarity": nearest_sim,
            "promotion_ready": promotion_ready,
            "related_count": len(related_ids),
        }

        # Build rationale
        rationale_parts = []
        if coherence < self.COHERENCE_THRESHOLD:
            rationale_parts.append(
                f"Low coherence ({coherence:.2f}) with related concepts"
            )
        if dup_similarity > self.DUPLICATE_THRESHOLD:
            rationale_parts.append(
                f"Potential duplicate of {dup_id} ({dup_similarity:.2f})"
            )
        if nearest_sim < self.ORPHAN_THRESHOLD:
            rationale_parts.append(
                f"Orphan candidate - low similarity to approved concepts ({nearest_sim:.2f})"
            )
        if not rationale_parts:
            rationale_parts.append("Meets all embedding-based criteria")

        input_text = f"{content.get('preferred_label', '')}: {content.get('definition', '')}"

        return ClassificationResult(
            target_type=target_type,
            target_id=target_id,
            classifier_id=self.classifier_id,
            classifier_version=self.classifier_version,
            scores=scores,
            labels=labels,
            confidence=coherence,  # Use coherence as confidence
            rationale="; ".join(rationale_parts),
            input_hash=self.compute_input_hash(input_text),
        )
