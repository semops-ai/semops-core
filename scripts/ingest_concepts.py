#!/usr/bin/env python3
"""
Ingest concepts from COMPOSABLE_CONCEPTS markdown files into PostgreSQL.

Reads YAML frontmatter from markdown files and inserts into the concept table.
This is Phase 1+3 combined: inventory directly to database.

Usage:
 python scripts/ingest_concepts.py [--dry-run] [--source PATH]
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

import psycopg
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection

# Default source path
DEFAULT_SOURCE = ""


def parse_frontmatter(content: str) -> dict[str, Any] | None:
 """Extract YAML frontmatter from markdown content."""
 # Match YAML between --- markers (skip HTML comments first)
 # Remove HTML comments that might precede frontmatter
 content = re.sub(r"<!--[\s\S]*?-->", "", content).strip

 match = re.match(r"^---\s*\n([\s\S]*?)\n---", content)
 if not match:
 return None

 try:
 return yaml.safe_load(match.group(1))
 except yaml.YAMLError as e:
 print(f" YAML parse error: {e}")
 return None


def extract_concept_data(frontmatter: dict[str, Any], filepath: Path) -> dict[str, Any] | None:
 """Extract concept fields from frontmatter."""
 metadata = frontmatter.get("metadata", {})
 attribution = frontmatter.get("attribution", {})

 # Get concept ID - prefer primary_concept, fall back to entity_id, then filename
 concept_id = (
 metadata.get("primary_concept")
 or frontmatter.get("entity_id")
 or filepath.stem
 )

 # Get definition - required field
 definition = metadata.get("definition")
 if not definition:
 return None

 # Get preferred label
 preferred_label = metadata.get("preferred_label", concept_id.replace("-", " ").title)

 # Get provenance from concept_ownership
 ownership = attribution.get("concept_ownership", "1p")
 provenance_map = {"1p": "1p", "2p": "2p", "3p": "3p"}
 provenance = provenance_map.get(ownership, "1p")

 # Get alt labels
 alt_labels = metadata.get("alt_labels", [])
 if isinstance(alt_labels, str):
 alt_labels = [alt_labels]

 # Build metadata JSONB
 concept_metadata = {
 "source_file": str(filepath),
 "content_type": metadata.get("content_type"),
 "subject_area": metadata.get("subject_area", []),
 "quality_score": metadata.get("quality_score"),
 "epistemic_status": attribution.get("epistemic_status"),
 }
 # Remove None values
 concept_metadata = {k: v for k, v in concept_metadata.items if v is not None}

 # Build attribution JSONB
 concept_attribution = {
 "$schema": attribution.get("$schema", "attribution_v2"),
 "authors": attribution.get("authors", []),
 }
 if attribution.get("organization"):
 concept_attribution["organization"] = attribution["organization"]
 if attribution.get("license"):
 concept_attribution["license"] = attribution["license"]

 return {
 "id": concept_id,
 "preferred_label": preferred_label,
 "definition": definition,
 "alt_labels": alt_labels,
 "provenance": provenance,
 "approval_status": "pending",
 "attribution": concept_attribution,
 "metadata": concept_metadata,
 }


def extract_edges(frontmatter: dict[str, Any], concept_id: str) -> list[dict[str, Any]]:
 """Extract concept edges from frontmatter."""
 metadata = frontmatter.get("metadata", {})
 edges = []

 # SKOS broader (this concept IS NARROWER THAN target)
 for broader in metadata.get("broader_concepts", []):
 if broader:
 edges.append({
 "src_id": concept_id,
 "dst_id": broader,
 "predicate": "broader",
 "strength": 1.0,
 })

 # SKOS narrower (this concept IS BROADER THAN target)
 for narrower in metadata.get("narrower_concepts", []):
 if narrower:
 edges.append({
 "src_id": concept_id,
 "dst_id": narrower,
 "predicate": "narrower",
 "strength": 1.0,
 })

 # SKOS related
 for related in metadata.get("related_concepts", []):
 if related:
 edges.append({
 "src_id": concept_id,
 "dst_id": related,
 "predicate": "related",
 "strength": 0.7,
 })

 return edges


def ingest_file(filepath: Path, conn: psycopg.Connection, dry_run: bool = False) -> tuple[bool, list]:
 """Process a single markdown file."""
 content = filepath.read_text(encoding="utf-8")

 frontmatter = parse_frontmatter(content)
 if not frontmatter:
 return False, []

 concept_data = extract_concept_data(frontmatter, filepath)
 if not concept_data:
 return False, []

 edges = extract_edges(frontmatter, concept_data["id"])

 if dry_run:
 print(f" Would insert: {concept_data['id']} ({concept_data['provenance']})")
 print(f" Label: {concept_data['preferred_label']}")
 print(f" Definition: {concept_data['definition'][:80]}...")
 print(f" Edges: {len(edges)}")
 return True, edges

 # Insert concept
 try:
 with conn.cursor as cur:
 cur.execute(
 """
 INSERT INTO concept (
 id, preferred_label, definition, alt_labels,
 provenance, approval_status, attribution, metadata
 )
 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
 ON CONFLICT (id) DO UPDATE SET
 preferred_label = EXCLUDED.preferred_label,
 definition = EXCLUDED.definition,
 alt_labels = EXCLUDED.alt_labels,
 provenance = EXCLUDED.provenance,
 attribution = EXCLUDED.attribution,
 metadata = EXCLUDED.metadata,
 updated_at = now
 """,
 (
 concept_data["id"],
 concept_data["preferred_label"],
 concept_data["definition"],
 concept_data["alt_labels"],
 concept_data["provenance"],
 concept_data["approval_status"],
 psycopg.types.json.Json(concept_data["attribution"]),
 psycopg.types.json.Json(concept_data["metadata"]),
 ),
 )
 return True, edges
 except Exception as e:
 print(f" Error inserting {concept_data['id']}: {e}")
 return False, []


def insert_edges(edges: list[dict], conn: psycopg.Connection, dry_run: bool = False) -> int:
 """Insert concept edges, skipping those with missing targets."""
 if dry_run:
 return len(edges)

 inserted = 0
 with conn.cursor as cur:
 # Get all existing concept IDs
 cur.execute("SELECT id FROM concept")
 existing_ids = {row[0] for row in cur.fetchall}

 for edge in edges:
 # Only insert if both source and destination exist
 if edge["src_id"] in existing_ids and edge["dst_id"] in existing_ids:
 try:
 cur.execute(
 """
 INSERT INTO concept_edge (src_id, dst_id, predicate, strength)
 VALUES (%s, %s, %s, %s)
 ON CONFLICT (src_id, dst_id, predicate) DO UPDATE SET
 strength = EXCLUDED.strength
 """,
 (edge["src_id"], edge["dst_id"], edge["predicate"], edge["strength"]),
 )
 inserted += 1
 except Exception as e:
 print(f" Edge error {edge['src_id']} -> {edge['dst_id']}: {e}")

 return inserted


def main:
 parser = argparse.ArgumentParser(description="Ingest concepts from markdown files")
 parser.add_argument("--dry-run", action="store_true", help="Parse files but don't insert")
 parser.add_argument("--source", default=DEFAULT_SOURCE, help="Source directory path")
 args = parser.parse_args

 source_path = Path(args.source)
 if not source_path.exists:
 print(f"Error: Source path does not exist: {source_path}")
 sys.exit(1)

 # Find all markdown files
 md_files = list(source_path.glob("*.md"))
 print(f"Found {len(md_files)} markdown files in {source_path}")

 if args.dry_run:
 print("\n=== DRY RUN MODE ===\n")
 conn = None
 else:
 # Connect to database
 try:
 conn = get_db_connection(autocommit=True)
 print("Connected to PostgreSQL")
 except Exception as e:
 print(f"Database connection failed: {e}")
 sys.exit(1)

 # Process files
 success_count = 0
 all_edges = []

 for filepath in sorted(md_files):
 print(f"\nProcessing: {filepath.name}")
 success, edges = ingest_file(filepath, conn, args.dry_run)
 if success:
 success_count += 1
 all_edges.extend(edges)
 else:
 print(f" Skipped (no definition or parse error)")

 # Insert edges (second pass to ensure all concepts exist first)
 print(f"\n\nInserting {len(all_edges)} edges...")
 edge_count = insert_edges(all_edges, conn, args.dry_run)

 print(f"\n=== Summary ===")
 print(f"Concepts ingested: {success_count}/{len(md_files)}")
 print(f"Edges inserted: {edge_count}/{len(all_edges)}")

 if conn:
 conn.close


if __name__ == "__main__":
 main
