#!/usr/bin/env python3
"""
Generate SQL INSERT statements for concepts from COMPOSABLE_CONCEPTS markdown files.

Reads YAML frontmatter and outputs SQL that can be piped to psql.

Usage:
 python scripts/ingest_concepts_sql.py | docker exec -i supabase-db psql -U postgres -d postgres

Or dry run:
 python scripts/ingest_concepts_sql.py --dry-run
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


# Default source path
DEFAULT_SOURCE = ""


def parse_frontmatter(content: str) -> dict[str, Any] | None:
 """Extract YAML frontmatter from markdown content."""
 # Remove HTML comments that might precede frontmatter
 content = re.sub(r"<!--[\s\S]*?-->", "", content).strip

 match = re.match(r"^---\s*\n([\s\S]*?)\n---", content)
 if not match:
 return None

 try:
 return yaml.safe_load(match.group(1))
 except yaml.YAMLError as e:
 print(f"-- YAML parse error: {e}", file=sys.stderr)
 return None


def escape_sql(s: str) -> str:
 """Escape string for SQL."""
 if s is None:
 return "NULL"
 return "'" + s.replace("'", "''") + "'"


def array_to_sql(arr: list) -> str:
 """Convert Python list to PostgreSQL array literal."""
 if not arr:
 return "'{}'::text[]"
 escaped = [s.replace("'", "''").replace('"', '\\"') for s in arr if s]
 return "ARRAY[" + ", ".join(f"'{s}'" for s in escaped) + "]"


def extract_concept(frontmatter: dict[str, Any], filepath: Path) -> dict[str, Any] | None:
 """Extract concept fields from frontmatter."""
 metadata = frontmatter.get("metadata", {})
 attribution = frontmatter.get("attribution", {})

 # Get concept ID
 concept_id = (
 metadata.get("primary_concept")
 or frontmatter.get("entity_id")
 or filepath.stem
 )

 # Get definition - required
 definition = metadata.get("definition")
 if not definition:
 return None

 # Get preferred label
 preferred_label = metadata.get("preferred_label", concept_id.replace("-", " ").title)

 # Get provenance
 ownership = attribution.get("concept_ownership", "1p")
 provenance = ownership if ownership in ("1p", "2p", "3p") else "1p"

 # Alt labels
 alt_labels = metadata.get("alt_labels", [])
 if isinstance(alt_labels, str):
 alt_labels = [alt_labels]

 # Build metadata
 concept_metadata = {
 "source_file": str(filepath),
 "subject_area": metadata.get("subject_area", []),
 }
 if metadata.get("quality_score"):
 concept_metadata["quality_score"] = metadata["quality_score"]
 if attribution.get("epistemic_status"):
 concept_metadata["epistemic_status"] = attribution["epistemic_status"]

 # Build attribution
 concept_attribution = {
 "$schema": "attribution_v2",
 "authors": attribution.get("authors", []),
 }

 return {
 "id": concept_id,
 "preferred_label": preferred_label,
 "definition": definition,
 "alt_labels": alt_labels,
 "provenance": provenance,
 "attribution": concept_attribution,
 "metadata": concept_metadata,
 "broader_concepts": metadata.get("broader_concepts", []),
 "narrower_concepts": metadata.get("narrower_concepts", []),
 "related_concepts": metadata.get("related_concepts", []),
 }


def generate_concept_sql(concept: dict) -> str:
 """Generate INSERT statement for a concept."""
 return f"""INSERT INTO concept (id, preferred_label, definition, alt_labels, provenance, approval_status, attribution, metadata)
VALUES (
 {escape_sql(concept['id'])},
 {escape_sql(concept['preferred_label'])},
 {escape_sql(concept['definition'])},
 {array_to_sql(concept['alt_labels'])},
 {escape_sql(concept['provenance'])},
 'pending',
 {escape_sql(json.dumps(concept['attribution']))}::jsonb,
 {escape_sql(json.dumps(concept['metadata']))}::jsonb
)
ON CONFLICT (id) DO UPDATE SET
 preferred_label = EXCLUDED.preferred_label,
 definition = EXCLUDED.definition,
 alt_labels = EXCLUDED.alt_labels,
 provenance = EXCLUDED.provenance,
 attribution = EXCLUDED.attribution,
 metadata = EXCLUDED.metadata,
 updated_at = now;
"""


def generate_edge_sql(src_id: str, dst_id: str, predicate: str) -> str:
 """Generate INSERT statement for an edge (will be run after all concepts exist)."""
 return f"""INSERT INTO concept_edge (src_id, dst_id, predicate)
SELECT {escape_sql(src_id)}, {escape_sql(dst_id)}, {escape_sql(predicate)}
WHERE EXISTS (SELECT 1 FROM concept WHERE id = {escape_sql(src_id)})
 AND EXISTS (SELECT 1 FROM concept WHERE id = {escape_sql(dst_id)})
ON CONFLICT (src_id, dst_id, predicate) DO NOTHING;
"""


def main:
 parser = argparse.ArgumentParser(description="Generate SQL for concept ingestion")
 parser.add_argument("--dry-run", action="store_true", help="Print summary instead of SQL")
 parser.add_argument("--source", default=DEFAULT_SOURCE, help="Source directory path")
 args = parser.parse_args

 source_path = Path(args.source)
 if not source_path.exists:
 print(f"-- Error: Source path does not exist: {source_path}", file=sys.stderr)
 sys.exit(1)

 md_files = list(source_path.glob("*.md"))
 print(f"-- Found {len(md_files)} markdown files", file=sys.stderr)

 concepts = []
 edges = []

 for filepath in sorted(md_files):
 content = filepath.read_text(encoding="utf-8")
 frontmatter = parse_frontmatter(content)

 if not frontmatter:
 print(f"-- Skipped {filepath.name}: no frontmatter", file=sys.stderr)
 continue

 concept = extract_concept(frontmatter, filepath)
 if not concept:
 print(f"-- Skipped {filepath.name}: no definition", file=sys.stderr)
 continue

 concepts.append(concept)

 # Collect edges
 for broader in concept.get("broader_concepts", []) or []:
 if broader:
 edges.append((concept["id"], broader, "broader"))
 for narrower in concept.get("narrower_concepts", []) or []:
 if narrower:
 edges.append((concept["id"], narrower, "narrower"))
 for related in concept.get("related_concepts", []) or []:
 if related:
 edges.append((concept["id"], related, "related"))

 if args.dry_run:
 print(f"\n=== DRY RUN ===")
 print(f"Would insert {len(concepts)} concepts:")
 for c in concepts:
 print(f" {c['id']} ({c['provenance']}): {c['preferred_label']}")
 print(f"\nWould insert {len(edges)} edges")
 return

 # Output SQL
 print("-- Concept ingestion from COMPOSABLE_CONCEPTS")
 print("-- Generated by ingest_concepts_sql.py")
 print("-- BEGIN;") # Commented out to see all errors
 print

 print("-- Insert concepts")
 for concept in concepts:
 print(generate_concept_sql(concept))

 print
 print("-- Insert edges (only where both concepts exist)")
 for src_id, dst_id, predicate in edges:
 print(generate_edge_sql(src_id, dst_id, predicate))

 print
 print("-- COMMIT;")
 print
 print(f"-- Inserted {len(concepts)} concepts and {len(edges)} edges", file=sys.stderr)


if __name__ == "__main__":
 main
