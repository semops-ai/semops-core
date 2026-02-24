#!/usr/bin/env python3
"""
Entity builder for Project Ike ingestion pipeline.

Constructs entity dictionaries from source files using:
1. Derived attributes from file content (title, word_count, etc.)
2. Fixed defaults from source configuration
3. LLM-classified semantic attributes (optional)

Usage:
 from entity_builder import EntityBuilder

 builder = EntityBuilder(source_config)
 entity = builder.build(fetched_file, classification=llm_result)
"""

from __future__ import annotations

import re
import yaml
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from github_fetcher import FetchedFile
from source_config import SourceConfig


@dataclass
class LLMClassification:
 """Result of LLM classification."""

 content_type: str = ""
 primary_concept: str = ""
 broader_concepts: list[str] | None = None
 narrower_concepts: list[str] | None = None
 subject_area: list[str] | None = None
 summary: str = ""
 concept_ownership: str = ""
 detected_edges: list[dict] | None = None

 def to_dict(self) -> dict[str, Any]:
 """Convert to dictionary, excluding empty values."""
 result = {}
 if self.content_type:
 result["content_type"] = self.content_type
 if self.primary_concept:
 result["primary_concept"] = self.primary_concept
 if self.broader_concepts:
 result["broader_concepts"] = self.broader_concepts
 if self.narrower_concepts:
 result["narrower_concepts"] = self.narrower_concepts
 if self.subject_area:
 result["subject_area"] = self.subject_area
 if self.summary:
 result["summary"] = self.summary
 if self.concept_ownership:
 result["concept_ownership"] = self.concept_ownership
 if self.detected_edges:
 result["detected_edges"] = self.detected_edges
 return result


class EntityBuilder:
 """Builds entity dictionaries from source files."""

 def __init__(self, config: SourceConfig):
 """
 Initialize builder with source configuration.

 Args:
 config: Source configuration with defaults and templates
 """
 self.config = config

 def derive_entity_id(self, file_path: str) -> str:
 """
 Derive entity ID from file path.

 Converts file path to kebab-case ID. For generic filenames like
 README.md or index.md, uses the parent directory name instead to
 avoid duplicate IDs across directories.

 Args:
 file_path: Path like "docs/SEMANTIC_OPERATIONS/semantic-operations.md"

 Returns:
 Entity ID like "semantic-operations"
 """
 path = Path(file_path)
 filename = path.stem
 # For generic filenames, use the parent directory name
 if filename.lower in ("readme", "index"):
 filename = path.parent.name or filename
 # Convert to lowercase kebab-case
 entity_id = filename.lower.replace("_", "-").replace(" ", "-")
 # Remove consecutive hyphens
 entity_id = re.sub(r"-+", "-", entity_id)
 return entity_id

 def extract_title(self, content: str, filename: str) -> str:
 """
 Extract title from markdown content.

 Tries to find H1 header, falls back to filename.

 Args:
 content: Markdown file content
 filename: Original filename without extension

 Returns:
 Extracted title
 """
 # Try to find H1 header (# Title)
 h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
 if h1_match:
 return h1_match.group(1).strip

 # Fallback: clean up filename
 title = filename.replace("-", " ").replace("_", " ")
 return title.title

 @staticmethod
 def parse_frontmatter(content: str) -> dict[str, Any]:
 """Parse YAML frontmatter from markdown content.

 Returns empty dict if no frontmatter found.
 """
 if not content.startswith("---"):
 return {}
 end = content.find("---", 3)
 if end == -1:
 return {}
 try:
 return yaml.safe_load(content[3:end]) or {}
 except yaml.YAMLError:
 return {}

 def count_words(self, content: str) -> int:
 """Count words in content."""
 return len(re.findall(r"\w+", content))

 def build_filespec(self, fetched: FetchedFile) -> dict[str, Any]:
 """
 Build filespec_v1 JSONB object.

 Args:
 fetched: Fetched file with content and metadata

 Returns:
 Filespec dictionary
 """
 return {
 "$schema": "filespec_v1",
 "uri": f"github://{self.config.github.owner}/{self.config.github.repo}/{fetched.metadata.path}",
 "format": "markdown",
 "hash": f"sha256:{fetched.metadata.content_hash}",
 "size_bytes": fetched.metadata.size_bytes,
 "platform": "github",
 "accessible": True,
 "last_checked": datetime.now(timezone.utc).isoformat,
 }

 def build_attribution(
 self, classification: Optional[LLMClassification] = None
 ) -> dict[str, Any]:
 """
 Build attribution_v2 JSONB object.

 Args:
 classification: Optional LLM classification for concept_ownership

 Returns:
 Attribution dictionary
 """
 attr = self.config.attribution
 result: dict[str, Any] = {"$schema": "attribution_v2"}

 if attr.creator:
 result["creator"] = attr.creator
 if attr.rights:
 result["rights"] = attr.rights
 if attr.organization:
 result["organization"] = attr.organization
 if attr.platform:
 result["platform"] = attr.platform
 if attr.channel:
 result["channel"] = attr.channel
 if attr.epistemic_status:
 result["epistemic_status"] = attr.epistemic_status

 # Add concept_ownership from LLM classification if available
 if classification and classification.concept_ownership:
 result["concept_ownership"] = classification.concept_ownership

 return result

 def build_metadata(
 self,
 content: str,
 classification: Optional[LLMClassification] = None,
 ) -> dict[str, Any]:
 """
 Build content_metadata_v1 JSONB object.

 Combines derived attributes with LLM classification.

 Args:
 content: File content for word count
 classification: Optional LLM classification results

 Returns:
 Content metadata dictionary
 """
 word_count = self.count_words(content)
 reading_time = max(1, word_count // 200)

 result: dict[str, Any] = {
 "$schema": "content_metadata_v1",
 "media_type": "text",
 "language": "en",
 "word_count": word_count,
 "reading_time_minutes": reading_time,
 }

 # Add LLM-classified fields
 if classification:
 llm_dict = classification.to_dict
 # Remove concept_ownership (it goes in attribution)
 llm_dict.pop("concept_ownership", None)
 result.update(llm_dict)

 return result

 def build(
 self,
 fetched: FetchedFile,
 classification: Optional[LLMClassification] = None,
 ) -> dict[str, Any]:
 """
 Build complete entity dictionary from fetched file.

 Args:
 fetched: Fetched file with content and metadata
 classification: Optional LLM classification results

 Returns:
 Entity dictionary ready for database insertion
 """
 filename_stem = Path(fetched.metadata.path).stem
 entity_id = self.derive_entity_id(fetched.metadata.path)
 title = self.extract_title(fetched.content, filename_stem)

 now = datetime.now(timezone.utc)
 defaults = self.config.defaults

 metadata = self.build_metadata(fetched.content, classification)

 # Apply corpus routing from source config (ADR-0005, #112)
 corpus, routed_content_type, lifecycle_stage = self.config.corpus_routing.resolve(
 fetched.metadata.path
 )
 if corpus:
 metadata["corpus"] = corpus
 # Use routed content_type as fallback if LLM didn't provide one
 if routed_content_type and "content_type" not in metadata:
 metadata["content_type"] = routed_content_type
 if lifecycle_stage:
 metadata["lifecycle_stage"] = lifecycle_stage

 # Extract pattern_type from YAML frontmatter if present (#115)
 frontmatter = self.parse_frontmatter(fetched.content)
 fm_metadata = frontmatter.get("metadata", {})
 if isinstance(fm_metadata, dict) and fm_metadata.get("pattern_type"):
 metadata["pattern_type"] = fm_metadata["pattern_type"]

 return {
 "id": entity_id,
 "entity_type": "content",
 "asset_type": defaults.asset_type,
 "title": title,
 "version": defaults.version,
 "filespec": self.build_filespec(fetched),
 "attribution": self.build_attribution(classification),
 "metadata": metadata,
 "created_at": now.isoformat,
 "updated_at": now.isoformat,
 # Track source for re-ingestion
 "_source": {
 "source_id": self.config.source_id,
 "file_path": fetched.metadata.path,
 "github_sha": fetched.metadata.sha,
 "content_hash": fetched.metadata.content_hash,
 },
 }


if __name__ == "__main__":
 # Simple test/demo
 from source_config import load_source_config

 config = load_source_config("project-ike-private")
 builder = EntityBuilder(config)

 # Create a mock fetched file for testing
 mock_metadata = type(
 "FileMetadata",
 {
 "path": "docs/SEMANTIC_OPERATIONS/semantic-operations.md",
 "size_bytes": 5000,
 "sha": "abc123",
 "content_hash": "def456",
 },
 )

 mock_fetched = type(
 "FetchedFile",
 {
 "content": "# Semantic Operations\n\nThis is a test document about semantic operations...",
 "metadata": mock_metadata,
 },
 )

 mock_classification = LLMClassification(
 content_type="framework",
 primary_concept="semantic-operations",
 broader_concepts=["knowledge-management"],
 narrower_concepts=["semantic-coherence", "semantic-drift"],
 subject_area=["Knowledge Management", "AI/ML"],
 summary="A systematic approach to managing knowledge as operational infrastructure.",
 concept_ownership="1p",
 )

 entity = builder.build(mock_fetched, mock_classification)

 import json

 print(json.dumps(entity, indent=2, default=str))
