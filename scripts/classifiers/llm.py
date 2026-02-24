"""
LLM-based classifier for semantic quality evaluation.

This classifier uses Claude to evaluate:
- Definition quality: Is the definition clear, complete, and well-formed?
- Semantic fit: Does this concept belong in the knowledge base?
- Naming quality: Is the preferred_label appropriate?
- Scope assessment: Is this concept appropriately scoped (not too broad/narrow)?

The LLM provides both scores and natural language rationale.
"""

import json
from typing import Any

from anthropic import Anthropic

from .base import BaseClassifier, ClassificationResult


CONCEPT_EVALUATION_PROMPT = """You are evaluating a concept for inclusion in a semantic knowledge base.

The knowledge base follows these principles:
- Concepts represent stable semantic units (ideas, principles, methodologies)
- First-party (1p) concepts are core intellectual property that operates in this system
- Third-party (3p) concepts are external references from industry/academia
- Concepts should be well-defined, appropriately scoped, and clearly named

Evaluate this concept:

**ID:** {concept_id}
**Preferred Label:** {preferred_label}
**Definition:** {definition}
**Provenance:** {provenance}
**Alternative Labels:** {alt_labels}
**Related Concepts:** {related_concepts}

Score each dimension from 0.0 to 1.0:

1. **definition_quality** - Is the definition clear, complete, and well-formed?
 - 0.0-0.3: Missing, vague, or circular
 - 0.4-0.6: Adequate but could be improved
 - 0.7-1.0: Clear, precise, and complete

2. **naming_quality** - Is the preferred_label appropriate and descriptive?
 - 0.0-0.3: Misleading, unclear, or inappropriate
 - 0.4-0.6: Acceptable but not ideal
 - 0.7-1.0: Clear, concise, and accurately descriptive

3. **scope_appropriateness** - Is the concept appropriately scoped?
 - 0.0-0.3: Too broad (should be split) or too narrow (should be merged)
 - 0.4-0.6: Scope is acceptable but boundaries could be clearer
 - 0.7-1.0: Well-scoped with clear boundaries

4. **semantic_fit** - Does this concept belong in a knowledge base?
 - 0.0-0.3: Not a concept (task, action, specific instance)
 - 0.4-0.6: Borderline - might be better as entity or merged with another concept
 - 0.7-1.0: Clearly a stable semantic unit worth preserving

Respond in JSON format:
{{
 "scores": {{
 "definition_quality": <float>,
 "naming_quality": <float>,
 "scope_appropriateness": <float>,
 "semantic_fit": <float>
 }},
 "labels": {{
 "needs_work": [<list of dimensions that need improvement>],
 "suggested_improvements": [<list of specific suggestions>]
 }},
 "rationale": "<2-3 sentence summary of the evaluation>",
 "promotion_ready": <boolean - true if all scores >= 0.6>
}}
"""

ENTITY_EVALUATION_PROMPT = """You are evaluating a content entity for a digital asset management system.

Entities represent content artifacts (blog posts, videos, documents) that:
- Must be connected to concepts in the knowledge base
- Have clear attribution and provenance
- Follow content quality standards

Evaluate this entity:

**ID:** {entity_id}
**Title:** {title}
**Asset Type:** {asset_type}
**Primary Concept:** {primary_concept}
**Visibility:** {visibility}
**Metadata:** {metadata}

Score each dimension from 0.0 to 1.0:

1. **title_quality** - Is the title clear and descriptive?
 - 0.0-0.3: Missing, vague, or misleading
 - 0.4-0.6: Acceptable but could be improved
 - 0.7-1.0: Clear, engaging, and accurately descriptive

2. **concept_alignment** - Does the content align with its primary concept?
 - 0.0-0.3: Misaligned or unrelated
 - 0.4-0.6: Loosely related
 - 0.7-1.0: Strongly aligned and supports the concept

3. **metadata_completeness** - Is the metadata sufficient?
 - 0.0-0.3: Missing critical fields
 - 0.4-0.6: Basic metadata present
 - 0.7-1.0: Comprehensive metadata

4. **content_value** - Does this content add value to the knowledge base?
 - 0.0-0.3: Duplicate, outdated, or low quality
 - 0.4-0.6: Acceptable but not distinctive
 - 0.7-1.0: Valuable, unique contribution

Respond in JSON format:
{{
 "scores": {{
 "title_quality": <float>,
 "concept_alignment": <float>,
 "metadata_completeness": <float>,
 "content_value": <float>
 }},
 "labels": {{
 "needs_work": [<list of dimensions that need improvement>],
 "suggested_improvements": [<list of specific suggestions>]
 }},
 "rationale": "<2-3 sentence summary of the evaluation>",
 "promotion_ready": <boolean - true if all scores >= 0.6>
}}
"""


class LLMClassifier(BaseClassifier):
 """
 LLM-based classifier using Claude for quality evaluation.

 Provides nuanced scoring with natural language rationale.
 More expensive but better for edge cases and subjective quality.

 Scores:
 - definition_quality / title_quality: Clarity and completeness
 - naming_quality / concept_alignment: Appropriateness
 - scope_appropriateness / metadata_completeness: Structure
 - semantic_fit / content_value: Overall worth
 - promotion_ready: boolean aggregate
 """

 MODEL = "claude-sonnet-4-20250514"

 @property
 def classifier_id(self) -> str:
 return "llm-quality-v1"

 @property
 def classifier_version(self) -> str:
 return "1.0.0"

 def __init__(self) -> None:
 super.__init__
 self._anthropic_client: Anthropic | None = None

 @property
 def anthropic_client(self) -> Anthropic:
 """Lazy Anthropic client."""
 if self._anthropic_client is None:
 self._anthropic_client = Anthropic(api_key=self.settings.anthropic_api_key)
 return self._anthropic_client

 def _get_related_concepts(self, concept_id: str) -> list[str]:
 """Get labels of related concepts for context."""
 with self.conn.cursor as cur:
 cur.execute(
 """
 SELECT DISTINCT c.preferred_label
 FROM concept_edge ce
 JOIN concept c ON (
 (ce.src_id = %s AND c.id = ce.dst_id) OR
 (ce.dst_id = %s AND c.id = ce.src_id)
 )
 WHERE ce.src_id = %s OR ce.dst_id = %s
 LIMIT 10
 """,
 (concept_id, concept_id, concept_id, concept_id),
 )
 return [row[0] for row in cur.fetchall if row[0]]

 def _evaluate_with_llm(self, prompt: str) -> dict[str, Any]:
 """Call Claude and parse JSON response."""
 message = self.anthropic_client.messages.create(
 model=self.MODEL,
 max_tokens=1024,
 messages=[{"role": "user", "content": prompt}],
 )

 response_text = message.content[0].text

 # Extract JSON from response (handle markdown code blocks)
 if "```json" in response_text:
 json_str = response_text.split("```json")[1].split("```")[0]
 elif "```" in response_text:
 json_str = response_text.split("```")[1].split("```")[0]
 else:
 json_str = response_text

 return json.loads(json_str.strip)

 def classify(
 self, target_type: str, target_id: str, content: dict[str, Any]
 ) -> ClassificationResult:
 """Run LLM-based classification."""
 if target_type == "concept":
 return self._classify_concept(target_id, content)
 elif target_type == "entity":
 return self._classify_entity(target_id, content)
 else:
 return ClassificationResult(
 target_type=target_type,
 target_id=target_id,
 classifier_id=self.classifier_id,
 classifier_version=self.classifier_version,
 scores={"error": True},
 labels={"reason": f"Unknown target type: {target_type}"},
 confidence=None,
 rationale=f"LLM classification not supported for {target_type}",
 )

 def _classify_concept(
 self, concept_id: str, content: dict[str, Any]
 ) -> ClassificationResult:
 """Classify a concept using LLM evaluation."""
 related_concepts = self._get_related_concepts(concept_id)

 prompt = CONCEPT_EVALUATION_PROMPT.format(
 concept_id=concept_id,
 preferred_label=content.get("preferred_label", ""),
 definition=content.get("definition", ""),
 provenance=content.get("provenance", "unknown"),
 alt_labels=", ".join(content.get("alt_labels", []) or []),
 related_concepts=", ".join(related_concepts) if related_concepts else "None",
 )

 try:
 result = self._evaluate_with_llm(prompt)

 scores = result.get("scores", {})
 scores["promotion_ready"] = result.get("promotion_ready", False)

 input_text = (
 f"{content.get('preferred_label', '')}|{content.get('definition', '')}"
 )

 return ClassificationResult(
 target_type="concept",
 target_id=concept_id,
 classifier_id=self.classifier_id,
 classifier_version=self.classifier_version,
 scores=scores,
 labels=result.get("labels", {}),
 confidence=0.75, # LLM evaluation has inherent uncertainty
 rationale=result.get("rationale", "LLM evaluation complete"),
 input_hash=self.compute_input_hash(input_text),
 )
 except Exception as e:
 return ClassificationResult(
 target_type="concept",
 target_id=concept_id,
 classifier_id=self.classifier_id,
 classifier_version=self.classifier_version,
 scores={"error": True},
 labels={"error_message": str(e)},
 confidence=None,
 rationale=f"LLM evaluation failed: {e}",
 )

 def _classify_entity(
 self, entity_id: str, content: dict[str, Any]
 ) -> ClassificationResult:
 """Classify an entity using LLM evaluation."""
 metadata = content.get("metadata", {})
 if isinstance(metadata, str):
 try:
 metadata = json.loads(metadata)
 except json.JSONDecodeError:
 metadata = {}

 prompt = ENTITY_EVALUATION_PROMPT.format(
 entity_id=entity_id,
 title=content.get("title", ""),
 asset_type=content.get("asset_type", "unknown"),
 primary_concept=content.get("primary_concept_id", "None"),
 visibility=content.get("visibility", "unknown"),
 metadata=json.dumps(metadata, indent=2) if metadata else "None",
 )

 try:
 result = self._evaluate_with_llm(prompt)

 scores = result.get("scores", {})
 scores["promotion_ready"] = result.get("promotion_ready", False)

 input_text = f"{content.get('title', '')}|{content.get('asset_type', '')}"

 return ClassificationResult(
 target_type="entity",
 target_id=entity_id,
 classifier_id=self.classifier_id,
 classifier_version=self.classifier_version,
 scores=scores,
 labels=result.get("labels", {}),
 confidence=0.75,
 rationale=result.get("rationale", "LLM evaluation complete"),
 input_hash=self.compute_input_hash(input_text),
 )
 except Exception as e:
 return ClassificationResult(
 target_type="entity",
 target_id=entity_id,
 classifier_id=self.classifier_id,
 classifier_version=self.classifier_version,
 scores={"error": True},
 labels={"error_message": str(e)},
 confidence=None,
 rationale=f"LLM evaluation failed: {e}",
 )
