"""
Embedding-based classifier for semantic similarity.

This classifier uses pgvector embeddings to evaluate:
- Coherence: How similar is this concept to its related concepts
- Duplicate detection: Find near-duplicates
- Orphan detection: Distance to nearest approved concept

Requires embeddings to be populated in the concept.embedding column.
"""

from typing import Any

from openai import OpenAI

from .base import BaseClassifier, ClassificationResult


class EmbeddingClassifier(BaseClassifier):
    """
    Embedding-based classifier using pgvector.

    Scores:
        - coherence: Average similarity to related concepts (0.0-1.0)
        - nearest_approved_distance: Distance to nearest approved concept
        - duplicate_similarity: Highest similarity to another concept
        - promotion_ready: boolean

    Labels:
        - nearest_approved: ID of nearest approved concept
        - potential_duplicate: ID if similarity > 0.95
    """

    # Thresholds
    COHERENCE_THRESHOLD = 0.6  # Min avg similarity to related concepts
    DUPLICATE_THRESHOLD = 0.95  # Above this, flag as potential duplicate
    ORPHAN_THRESHOLD = 0.7  # If nearest approved is below this, flag as orphan

    @property
    def classifier_id(self) -> str:
        return "embedding-coherence-v1"

    @property
    def classifier_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self._openai_client: OpenAI | None = None

    @property
    def openai_client(self) -> OpenAI:
        """Lazy OpenAI client."""
        if self._openai_client is None:
            self._openai_client = OpenAI(api_key=self.settings.openai_api_key)
        return self._openai_client

    def get_embedding(self, text: str) -> list[float]:
        """Get embedding for text using OpenAI."""
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def ensure_embedding(self, concept_id: str, content: dict[str, Any]) -> bool:
        """
        Ensure concept has an embedding, generate if missing.

        Returns True if embedding exists or was created.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT embedding IS NOT NULL FROM concept WHERE id = %s",
                (concept_id,),
            )
            result = cur.fetchone()
            if result and result[0]:
                return True

        # Generate embedding
        label = content.get("preferred_label", "")
        definition = content.get("definition", "")
        text = f"{label}: {definition}"

        try:
            embedding = self.get_embedding(text)
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE concept SET embedding = %s WHERE id = %s",
                    (embedding, concept_id),
                )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error generating embedding for {concept_id}: {e}")
            return False

    def classify(
        self, target_type: str, target_id: str, content: dict[str, Any]
    ) -> ClassificationResult:
        """Run embedding-based classification."""
        if target_type != "concept":
            # For now, only concepts have embeddings
            return ClassificationResult(
                target_type=target_type,
                target_id=target_id,
                classifier_id=self.classifier_id,
                classifier_version=self.classifier_version,
                scores={"skipped": True},
                labels={"reason": "Embedding classification only supports concepts"},
                confidence=None,
                rationale="Entity embedding classification not implemented",
            )

        # Ensure embedding exists
        if not self.ensure_embedding(target_id, content):
            return ClassificationResult(
                target_type=target_type,
                target_id=target_id,
                classifier_id=self.classifier_id,
                classifier_version=self.classifier_version,
                scores={"error": True},
                labels={"reason": "Could not generate embedding"},
                confidence=None,
                rationale="Failed to generate embedding for concept",
            )

        return self._classify_concept(target_id, content)

    def _classify_concept(
        self, concept_id: str, content: dict[str, Any]
    ) -> ClassificationResult:
        """Classify concept using embeddings."""

        # 1. Coherence: Average similarity to related concepts
        coherence_score, related_count = self._compute_coherence(concept_id)

        # 2. Nearest approved: Find closest approved 1p concept
        nearest_approved_id, nearest_distance = self._find_nearest_approved(concept_id)

        # 3. Duplicate detection: Find most similar concept
        duplicate_id, duplicate_similarity = self._find_potential_duplicate(concept_id)

        # Compute scores
        is_coherent = coherence_score >= self.COHERENCE_THRESHOLD if coherence_score else True
        is_potential_duplicate = duplicate_similarity >= self.DUPLICATE_THRESHOLD
        is_orphan_by_embedding = (
            nearest_distance is not None
            and nearest_distance < self.ORPHAN_THRESHOLD
        )

        promotion_ready = (
            is_coherent
            and not is_potential_duplicate
            and not is_orphan_by_embedding
        )

        scores = {
            "coherence": round(coherence_score, 3) if coherence_score else None,
            "related_concept_count": related_count,
            "nearest_approved_similarity": round(nearest_distance, 3) if nearest_distance else None,
            "duplicate_similarity": round(duplicate_similarity, 3) if duplicate_similarity else None,
            "is_coherent": is_coherent,
            "is_potential_duplicate": is_potential_duplicate,
            "promotion_ready": promotion_ready,
        }

        labels: dict[str, Any] = {}
        if nearest_approved_id:
            labels["nearest_approved"] = nearest_approved_id
        if is_potential_duplicate and duplicate_id:
            labels["potential_duplicate"] = duplicate_id

        # Build rationale
        rationale_parts = []
        if coherence_score is not None:
            rationale_parts.append(
                f"Coherence with {related_count} related concepts: {coherence_score:.2f}"
            )
        if is_potential_duplicate:
            rationale_parts.append(
                f"Potential duplicate of '{duplicate_id}' (similarity: {duplicate_similarity:.2f})"
            )
        if is_orphan_by_embedding:
            rationale_parts.append(
                f"Low similarity to approved concepts (nearest: {nearest_distance:.2f})"
            )
        if not rationale_parts:
            rationale_parts.append("Embedding analysis complete, no issues found")

        input_text = f"{content.get('preferred_label', '')}|{content.get('definition', '')}"

        return ClassificationResult(
            target_type="concept",
            target_id=concept_id,
            classifier_id=self.classifier_id,
            classifier_version=self.classifier_version,
            scores=scores,
            labels=labels,
            confidence=0.85,  # Embedding similarity is probabilistic
            rationale="; ".join(rationale_parts),
            input_hash=self.compute_input_hash(input_text),
        )

    def _compute_coherence(self, concept_id: str) -> tuple[float | None, int]:
        """
        Compute average similarity to related concepts.

        Returns (coherence_score, related_count)
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                WITH related AS (
                    SELECT DISTINCT
                        CASE WHEN src_id = %s THEN dst_id ELSE src_id END as related_id
                    FROM concept_edge
                    WHERE src_id = %s OR dst_id = %s
                )
                SELECT
                    AVG(1 - (c.embedding <=> related_c.embedding)) as avg_similarity,
                    COUNT(*) as count
                FROM concept c
                CROSS JOIN related r
                JOIN concept related_c ON related_c.id = r.related_id
                WHERE c.id = %s
                  AND c.embedding IS NOT NULL
                  AND related_c.embedding IS NOT NULL
                """,
                (concept_id, concept_id, concept_id, concept_id),
            )
            result = cur.fetchone()
            if result and result[0]:
                return float(result[0]), int(result[1])
            return None, 0

    def _find_nearest_approved(self, concept_id: str) -> tuple[str | None, float | None]:
        """
        Find nearest approved 1p concept.

        Returns (concept_id, similarity)
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    approved.id,
                    1 - (target.embedding <=> approved.embedding) as similarity
                FROM concept target
                CROSS JOIN concept approved
                WHERE target.id = %s
                  AND approved.id != %s
                  AND approved.approval_status = 'approved'
                  AND approved.provenance = '1p'
                  AND target.embedding IS NOT NULL
                  AND approved.embedding IS NOT NULL
                ORDER BY target.embedding <=> approved.embedding
                LIMIT 1
                """,
                (concept_id, concept_id),
            )
            result = cur.fetchone()
            if result:
                return result[0], float(result[1])
            return None, None

    def _find_potential_duplicate(self, concept_id: str) -> tuple[str | None, float]:
        """
        Find most similar concept (potential duplicate).

        Returns (concept_id, similarity)
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    other.id,
                    1 - (target.embedding <=> other.embedding) as similarity
                FROM concept target
                CROSS JOIN concept other
                WHERE target.id = %s
                  AND other.id != %s
                  AND target.embedding IS NOT NULL
                  AND other.embedding IS NOT NULL
                ORDER BY target.embedding <=> other.embedding
                LIMIT 1
                """,
                (concept_id, concept_id),
            )
            result = cur.fetchone()
            if result:
                return result[0], float(result[1])
            return None, 0.0
