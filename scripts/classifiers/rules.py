"""
Rule-based classifier for deterministic validation.

This classifier checks concepts and entities against validation rules:
- Completeness: Required fields present
- Format: Definition length, structure
- Relationships: Has SKOS connections

Fast and deterministic - runs first in the classification pipeline.
"""

from typing import Any

from .base import BaseClassifier, ClassificationResult


class RuleBasedClassifier(BaseClassifier):
 """
 Deterministic rule-based classifier.

 Scores:
 - completeness: 0.0-1.0 based on required fields
 - format_valid: boolean
 - has_relationships: boolean
 - promotion_ready: boolean (all rules pass)

 Labels:
 - issues: list of validation issues found
 """

 @property
 def classifier_id(self) -> str:
 return "rule-completeness-v1"

 @property
 def classifier_version(self) -> str:
 return "1.0.0"

 def classify(
 self, target_type: str, target_id: str, content: dict[str, Any]
 ) -> ClassificationResult:
 """Run rule-based validation."""
 if target_type == "concept":
 return self._classify_concept(target_id, content)
 elif target_type == "entity":
 return self._classify_entity(target_id, content)
 else:
 raise ValueError(f"Unknown target_type: {target_type}")

 def _classify_concept(
 self, concept_id: str, content: dict[str, Any]
 ) -> ClassificationResult:
 """Validate a concept against rules."""
 issues: list[str] = []
 scores: dict[str, Any] = {}

 # Check required fields
 definition = content.get("definition", "")
 preferred_label = content.get("preferred_label", "")

 completeness_score = 0.0
 if preferred_label:
 completeness_score += 0.3
 else:
 issues.append("Missing preferred_label")

 if definition:
 completeness_score += 0.4
 else:
 issues.append("Missing definition")

 # Check definition quality
 format_valid = True
 if definition:
 if len(definition) < 20:
 issues.append("Definition too short (<20 chars)")
 format_valid = False
 if len(definition) > 2000:
 issues.append("Definition too long (>2000 chars)")
 format_valid = False
 # Check if it's just a synonym/circular definition
 if preferred_label.lower in definition.lower[:50]:
 # Definition starts with the term itself - might be circular
 if len(definition) < 50:
 issues.append("Definition may be circular (starts with term)")
 format_valid = False

 # Check for relationships
 has_relationships = self._check_relationships(concept_id)
 if has_relationships:
 completeness_score += 0.3
 else:
 issues.append("No SKOS relationships (broader, narrower, related)")

 # Determine if promotion ready
 promotion_ready = (
 completeness_score >= 0.7
 and format_valid
 and len(issues) <= 1 # Allow one minor issue
 )

 scores = {
 "completeness": round(completeness_score, 2),
 "format_valid": format_valid,
 "has_relationships": has_relationships,
 "promotion_ready": promotion_ready,
 }

 # Build rationale
 if issues:
 rationale = f"Issues found: {'; '.join(issues)}"
 else:
 rationale = "All validation rules passed"

 input_text = f"{preferred_label}|{definition}"

 return ClassificationResult(
 target_type="concept",
 target_id=concept_id,
 classifier_id=self.classifier_id,
 classifier_version=self.classifier_version,
 scores=scores,
 labels={"issues": issues},
 confidence=1.0, # Rule-based is deterministic
 rationale=rationale,
 input_hash=self.compute_input_hash(input_text),
 )

 def _classify_entity(
 self, entity_id: str, content: dict[str, Any]
 ) -> ClassificationResult:
 """Validate an entity against rules."""
 issues: list[str] = []

 # Check required fields
 title = content.get("title", "")
 asset_type = content.get("asset_type", "")
 primary_concept_id = content.get("primary_concept_id")
 filespec = content.get("filespec", {})
 attribution = content.get("attribution", {})

 completeness_score = 0.0

 if title:
 completeness_score += 0.2
 else:
 issues.append("Missing title")

 if asset_type:
 completeness_score += 0.1
 else:
 issues.append("Missing asset_type")

 if primary_concept_id:
 completeness_score += 0.3
 else:
 issues.append("Orphan entity (no primary_concept_id)")

 # Check filespec
 if filespec and filespec.get("uri"):
 completeness_score += 0.2
 else:
 issues.append("Missing filespec.uri")

 # Check attribution
 if attribution and attribution.get("creator"):
 completeness_score += 0.2
 else:
 issues.append("Missing attribution.creator")

 # Determine if promotion ready
 promotion_ready = (
 completeness_score >= 0.7
 and primary_concept_id is not None # Must not be orphan
 )

 scores = {
 "completeness": round(completeness_score, 2),
 "is_orphan": primary_concept_id is None,
 "has_filespec": bool(filespec and filespec.get("uri")),
 "has_attribution": bool(attribution and attribution.get("creator")),
 "promotion_ready": promotion_ready,
 }

 if issues:
 rationale = f"Issues found: {'; '.join(issues)}"
 else:
 rationale = "All validation rules passed"

 input_text = f"{title}|{asset_type}|{primary_concept_id}"

 return ClassificationResult(
 target_type="entity",
 target_id=entity_id,
 classifier_id=self.classifier_id,
 classifier_version=self.classifier_version,
 scores=scores,
 labels={"issues": issues},
 confidence=1.0,
 rationale=rationale,
 input_hash=self.compute_input_hash(input_text),
 )

 def _check_relationships(self, concept_id: str) -> bool:
 """Check if concept has any SKOS relationships."""
 with self.conn.cursor as cur:
 cur.execute(
 """
 SELECT EXISTS (
 SELECT 1 FROM concept_edge
 WHERE src_id = %s OR dst_id = %s
 )
 """,
 (concept_id, concept_id),
 )
 result = cur.fetchone
 return result[0] if result else False
