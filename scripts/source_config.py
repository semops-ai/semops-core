#!/usr/bin/env python3
"""
Source configuration loader for Project SemOps ingestion pipeline.

Loads and validates YAML source configurations from config/sources/*.yaml
using Pydantic models.

Usage:
 from source_config import load_source_config, list_sources

 config = load_source_config("semops-docs")
 sources = list_sources
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator

__all__ = [
 "SourceConfig",
 "load_source_config",
 "list_sources",
]


# Known corpus and content_type values (from UBIQUITOUS_LANGUAGE.md v7.2.0)
# Corpus: exact matches + research_* and ephemeral_* prefixes
KNOWN_CORPUS_VALUES = {"core_kb", "deployment", "published"}
CORPUS_PREFIXES = ("research_", "ephemeral_")

# Content types used in routing configs (non-exhaustive; LLM may produce others)
KNOWN_CONTENT_TYPES = {
 "concept", "pattern", "architecture", "adr", "article", "session_note",
}

# Lifecycle stages for entity knowledge lifecycle (distinct from delivery.approval_status)
# 5-stage model adopted from 3P patterns (CI/CD promotion, Backstage catalog, DDD aggregate).
# See issue #112 for design rationale and governance model.
# - draft: pre-delivery, unvalidated. Ideas, open issues, WIP. Forecast zone for coherence.
# - active: validated, operational. Merged, deployed, in use. Measured for coherence.
# - stable: trusted coherence baseline. Semantic anchor for classifiers and scoring.
# - deprecated: signaled for retirement. Still visible, consumers should migrate.
# - archived: removed from operational system. Retained for lineage/provenance only.
KNOWN_LIFECYCLE_STAGES = {"draft", "active", "stable", "deprecated", "archived"}


# Default config directory relative to repo root
CONFIG_DIR = Path(__file__).parent.parent / "config" / "sources"


class GitHubConfig(BaseModel):
 """GitHub repository configuration."""

 owner: str
 repo: str
 branch: str = "main"
 base_path: str = ""
 include_directories: list[str] = Field(default_factory=list)
 exclude_patterns: list[str] = Field(default_factory=list)
 file_extensions: list[str] = Field(default_factory=lambda: [".md"])


class EntityDefaults(BaseModel):
 """Default values for entities from this source."""

 asset_type: str = "file"
 version: str = "1.0"


class AttributionTemplate(BaseModel):
 """Attribution template for entities from this source."""

 schema_version: str = Field(default="attribution_v2", alias="$schema")
 creator: list[str] = Field(default_factory=list)
 rights: str = ""
 organization: str = ""
 platform: str = ""
 channel: str = ""
 epistemic_status: str = ""

 class Config:
 populate_by_name = True


class LLMClassifyConfig(BaseModel):
 """LLM classification configuration."""

 enabled: bool = True
 model: str = "claude-opus-4-5-20251101"
 fields: list[str] = Field(default_factory=list)


def _validate_corpus(v: str) -> str:
 """Validate corpus against known values or allowed prefixes."""
 if not v:
 return v
 if v in KNOWN_CORPUS_VALUES or any(v.startswith(p) for p in CORPUS_PREFIXES):
 return v
 raise ValueError(
 f"Unknown corpus '{v}'. Known: {sorted(KNOWN_CORPUS_VALUES)} "
 f"or prefixed with {CORPUS_PREFIXES}"
 )


def _validate_content_type(v: str) -> str:
 """Validate content_type against known values (warning-level; non-exhaustive)."""
 if not v:
 return v
 if v not in KNOWN_CONTENT_TYPES:
 import warnings
 warnings.warn(
 f"Content type '{v}' not in known set {sorted(KNOWN_CONTENT_TYPES)}. "
 f"This may be intentional (LLM-classified values are non-exhaustive).",
 stacklevel=2,
 )
 return v


def _validate_lifecycle_stage(v: str) -> str:
 """Validate lifecycle_stage against known values."""
 if not v:
 return v
 if v not in KNOWN_LIFECYCLE_STAGES:
 raise ValueError(
 f"Unknown lifecycle_stage '{v}'. Known: {sorted(KNOWN_LIFECYCLE_STAGES)}"
 )
 return v


class CorpusRoute(BaseModel):
 """A single corpus routing rule: path pattern → corpus + content_type + lifecycle_stage."""

 path_pattern: str
 corpus: str
 content_type: str = ""
 lifecycle_stage: str = ""

 @field_validator("corpus")
 @classmethod
 def check_corpus(cls, v: str) -> str:
 return _validate_corpus(v)

 @field_validator("content_type")
 @classmethod
 def check_content_type(cls, v: str) -> str:
 return _validate_content_type(v)

 @field_validator("lifecycle_stage")
 @classmethod
 def check_lifecycle_stage(cls, v: str) -> str:
 return _validate_lifecycle_stage(v)


class CorpusRoutingConfig(BaseModel):
 """Corpus routing configuration with ordered rules and a default."""

 rules: list[CorpusRoute] = Field(default_factory=list)
 default_corpus: str = ""
 default_content_type: str = ""
 default_lifecycle_stage: str = "active"

 @field_validator("default_corpus")
 @classmethod
 def check_default_corpus(cls, v: str) -> str:
 return _validate_corpus(v)

 @field_validator("default_content_type")
 @classmethod
 def check_default_content_type(cls, v: str) -> str:
 return _validate_content_type(v)

 @field_validator("default_lifecycle_stage")
 @classmethod
 def check_default_lifecycle_stage(cls, v: str) -> str:
 return _validate_lifecycle_stage(v)

 def resolve(self, file_path: str) -> tuple[str, str, str]:
 """
 Match file_path against rules in order, return (corpus, content_type, lifecycle_stage).

 Uses fnmatch-style glob patterns.
 """
 from fnmatch import fnmatch

 for rule in self.rules:
 if fnmatch(file_path, rule.path_pattern):
 return (
 rule.corpus,
 rule.content_type,
 rule.lifecycle_stage or self.default_lifecycle_stage,
 )
 return self.default_corpus, self.default_content_type, self.default_lifecycle_stage


class SourceConfig(BaseModel):
 """Complete source configuration."""

 source_id: str
 surface_id: str
 name: str
 github: GitHubConfig
 defaults: EntityDefaults = Field(default_factory=EntityDefaults)
 attribution: AttributionTemplate = Field(default_factory=AttributionTemplate)
 llm_classify: LLMClassifyConfig = Field(default_factory=LLMClassifyConfig)
 corpus_routing: CorpusRoutingConfig = Field(default_factory=CorpusRoutingConfig)

 @field_validator("source_id")
 @classmethod
 def validate_source_id(cls, v: str) -> str:
 """Validate source_id is kebab-case."""
 if not v or not all(c.isalnum or c == "-" for c in v):
 raise ValueError("source_id must be kebab-case alphanumeric")
 return v

 def resolve_corpus(self, repo_relative_path: str) -> tuple[str, str, str]:
 """
 Resolve corpus, content_type, and lifecycle_stage for a file path.

 Accepts a repo-relative path (e.g. "RESEARCH/FOUNDATIONS/foo.md")
 and prepends github.base_path before matching against routing rules.
 This eliminates caller dependency on knowing the path format
 that routing patterns expect.

 Returns:
 (corpus, content_type, lifecycle_stage) tuple
 """
 if self.github.base_path:
 full_path = f"{self.github.base_path}/{repo_relative_path}"
 else:
 full_path = repo_relative_path
 return self.corpus_routing.resolve(full_path)


def load_source_config(
 source_name: str, config_dir: Optional[Path] = None
) -> SourceConfig:
 """
 Load and validate a source configuration.

 Args:
 source_name: Name of the source (filename without .yaml)
 config_dir: Optional path to config directory

 Returns:
 Validated SourceConfig

 Raises:
 FileNotFoundError: If config file doesn't exist
 ValueError: If config validation fails
 """
 config_path = (config_dir or CONFIG_DIR) / f"{source_name}.yaml"

 if not config_path.exists:
 raise FileNotFoundError(f"Source config not found: {config_path}")

 with open(config_path) as f:
 data = yaml.safe_load(f)

 return SourceConfig.model_validate(data)


def list_sources(config_dir: Optional[Path] = None) -> list[str]:
 """
 List available source configurations.

 Args:
 config_dir: Optional path to config directory

 Returns:
 List of source names (filename stems)
 """
 search_dir = config_dir or CONFIG_DIR

 if not search_dir.exists:
 return []

 return sorted(f.stem for f in search_dir.glob("*.yaml"))


if __name__ == "__main__":
 # Simple test/demo
 print("Available sources:")
 for source in list_sources:
 print(f" - {source}")

 if list_sources:
 source_name = list_sources[0]
 print(f"\nLoading '{source_name}':")
 config = load_source_config(source_name)
 print(f" Name: {config.name}")
 print(f" GitHub: {config.github.owner}/{config.github.repo}")
 print(
 f" LLM Classification: {'enabled' if config.llm_classify.enabled else 'disabled'}"
 )
 print(f" Fields: {', '.join(config.llm_classify.fields)}")
