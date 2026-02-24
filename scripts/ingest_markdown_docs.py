#!/usr/bin/env python3
"""
Lightweight markdown ingestion script for Project Ike knowledge base.

Ingests markdown files from into the Entity table.

Supports two modes:
1. Explicit metadata via YAML frontmatter (takes precedence)
2. Auto-derived attributes from file structure and content (fallback)

Frontmatter Format:
---
entity_id: custom-id-here
title: My Custom Title
description: Optional custom description
category: first-principles
tags: [dikw, knowledge-ops, semantic-operations]
content_type: framework
provenance: 1p
visibility: internal
approval_status: approved
relationships:
 - predicate: documents
 target_id: semantic-operations-intro
 strength: 1.0
 - predicate: cites
 target_file: DIKW.md
 strength: 0.8
---

Usage:
 uv run python scripts/ingest_markdown_docs.py [--dry-run] [--path PATH]
"""

import argparse
import json
import re
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional
from uuid import uuid4

import os
import psycopg

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection
import yaml


# Default docs path
DEFAULT_DOCS_PATH = ""

# Category mapping from directory names
CATEGORY_MAP = {
 "AI_TRANSFORMATION": "ai-transformation",
 "FIRST_PRINCIPLES": "first-principles",
 "SEMANTIC_OPERATIONS": "semantic-operations",
 "GLOBAL_ARCHITECTURE": "architecture",
 "REAL_DATA": "data-systems",
 "examples-analogies": "examples",
}


def parse_frontmatter(content: str) -> tuple[Optional[dict], str]:
 """
 Parse YAML frontmatter from markdown content.

 Args:
 content: Full markdown file content

 Returns:
 Tuple of (frontmatter_dict, content_without_frontmatter)
 If no frontmatter found, returns (None, original_content)
 """
 # Check for YAML frontmatter (--- at start)
 if not content.startswith("---"):
 return None, content

 # Find closing ---
 parts = content.split("---", 2)
 if len(parts) < 3:
 return None, content

 try:
 frontmatter = yaml.safe_load(parts[1])
 content_body = parts[2].lstrip
 return frontmatter, content_body
 except yaml.YAMLError as e:
 print(f"Warning: Failed to parse YAML frontmatter: {e}", file=sys.stderr)
 return None, content


def extract_title(content: str, filename: str) -> str:
 """
 Extract title from markdown content.

 First tries to find H1 header, falls back to filename.

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


def extract_description(content: str, max_length: int = 500) -> Optional[str]:
 """
 Extract description from first paragraph after title.

 Args:
 content: Markdown file content
 max_length: Maximum description length

 Returns:
 First paragraph as description, or None
 """
 # Remove frontmatter if present
 content_no_frontmatter = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)

 # Remove H1 title
 content_no_title = re.sub(r"^#\s+.+$", "", content_no_frontmatter, count=1, flags=re.MULTILINE)

 # Find first non-empty paragraph
 paragraphs = [p.strip for p in content_no_title.split("\n\n") if p.strip]
 if paragraphs:
 desc = paragraphs[0]
 # Remove markdown formatting
 desc = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", desc) # Links
 desc = re.sub(r"\*\*([^\*]+)\*\*", r"\1", desc) # Bold
 desc = re.sub(r"\*([^\*]+)\*", r"\1", desc) # Italic
 desc = re.sub(r"`([^`]+)`", r"\1", desc) # Code

 if len(desc) > max_length:
 desc = desc[:max_length].rsplit(" ", 1)[0] + "..."
 return desc
 return None


def extract_tags(content: str, directory: str) -> list[str]:
 """
 Extract tags from content and directory.

 Args:
 content: Markdown file content
 directory: Parent directory name

 Returns:
 List of tags
 """
 tags = []

 # Add directory-based tag
 if directory in CATEGORY_MAP:
 tags.append(CATEGORY_MAP[directory])

 # Extract common conceptual keywords from content (simple heuristic)
 keywords = ["DIKW", "DDD", "Knowledge", "Semantic", "AI", "Data", "Domain"]
 content_upper = content.upper
 for keyword in keywords:
 if keyword.upper in content_upper:
 tags.append(keyword.lower)

 return list(set(tags)) # Deduplicate


def build_filespec(file_path: Path) -> dict:
 """
 Build filespec_v1 JSONB object.

 Args:
 file_path: Path to markdown file

 Returns:
 Filespec dictionary
 """
 stat = file_path.stat
 return {
 "filename": file_path.name,
 "extension": file_path.suffix,
 "size_bytes": stat.st_size,
 "mime_type": "text/markdown",
 "storage_path": str(file_path),
 }


def build_content_metadata(content: str) -> dict:
 """
 Build content_metadata_v1 JSONB object.

 Args:
 content: Markdown file content

 Returns:
 Content metadata dictionary
 """
 word_count = len(re.findall(r"\w+", content))
 return {
 "word_count": word_count,
 "format": "markdown",
 "language": "en",
 }


def ingest_markdown_file(
 file_path: Path,
 cursor: psycopg.Cursor,
 dry_run: bool = False,
 entity_id_map: Optional[dict] = None,
) -> dict:
 """
 Ingest a single markdown file into Entity table.

 Merges frontmatter metadata with auto-derived attributes.
 Frontmatter takes precedence when present.

 Args:
 file_path: Path to markdown file
 cursor: Database cursor
 dry_run: If True, don't insert into database
 entity_id_map: Dict mapping filenames to entity_ids for relationship resolution

 Returns:
 Dictionary of derived attributes for logging
 """
 # Read content
 content = file_path.read_text(encoding="utf-8")

 # Parse frontmatter
 frontmatter, content_body = parse_frontmatter(content)

 # Derive attributes from file structure
 relative_path = file_path.relative_to(DEFAULT_DOCS_PATH)
 directory = relative_path.parts[0] if len(relative_path.parts) > 1 else ""
 filename_stem = file_path.stem

 # Auto-derive (fallback values)
 auto_title = extract_title(content_body, filename_stem)
 auto_description = extract_description(content_body)
 auto_tags = extract_tags(content_body, directory)
 auto_category = CATEGORY_MAP.get(directory, "uncategorized")

 # Build JSONB objects
 filespec = build_filespec(file_path)
 content_metadata = build_content_metadata(content_body)

 # Merge frontmatter with auto-derived (frontmatter wins)
 if frontmatter:
 entity_id = frontmatter.get("entity_id", str(uuid4))
 title = frontmatter.get("title", auto_title)
 description = frontmatter.get("description", auto_description)
 category = frontmatter.get("category", auto_category)
 tags = frontmatter.get("tags", auto_tags)
 provenance = frontmatter.get("provenance", "1p")
 visibility = frontmatter.get("visibility", "internal")
 approval_status = frontmatter.get("approval_status", "approved")
 content_type = frontmatter.get("content_type", "article")
 relationships = frontmatter.get("relationships", [])
 else:
 entity_id = str(uuid4)
 title = auto_title
 description = auto_description
 category = auto_category
 tags = auto_tags
 provenance = "1p"
 visibility = "internal"
 approval_status = "approved"
 content_type = "article"
 relationships = []

 # Prepare timestamps
 now = datetime.now(UTC)

 entity_data = {
 "entity_id": entity_id,
 "title": title,
 "description": description,
 "provenance": provenance,
 "visibility": visibility,
 "approval_status": approval_status,
 "content_type": content_type,
 "category": category,
 "tags": tags,
 "filespec": json.dumps(filespec),
 "content_metadata": json.dumps(content_metadata),
 "created_at": now,
 "updated_at": now,
 "approved_at": now if approval_status == "approved" else None,
 }

 if not dry_run:
 # Insert entity into database
 cursor.execute(
 """
 INSERT INTO entity (
 entity_id, title, description, provenance, visibility,
 approval_status, content_type, category, tags,
 filespec, content_metadata,
 created_at, updated_at, approved_at
 ) VALUES (
 %(entity_id)s, %(title)s, %(description)s, %(provenance)s, %(visibility)s,
 %(approval_status)s, %(content_type)s, %(category)s, %(tags)s,
 %(filespec)s::jsonb, %(content_metadata)s::jsonb,
 %(created_at)s, %(updated_at)s, %(approved_at)s
 )
 """,
 entity_data,
 )

 return {
 "file": str(relative_path),
 "title": title,
 "category": category,
 "tags": tags,
 "entity_id": str(entity_id),
 "relationships": relationships,
 "has_frontmatter": frontmatter is not None,
 }


def create_edge_relationships(
 relationships: list[dict],
 source_entity_id: str,
 cursor: psycopg.Cursor,
 entity_id_map: dict,
 dry_run: bool = False,
) -> int:
 """
 Create Edge relationships from frontmatter relationship definitions.

 Args:
 relationships: List of relationship dicts from frontmatter
 source_entity_id: Source entity ID
 cursor: Database cursor
 entity_id_map: Map of filenames to entity IDs
 dry_run: If True, don't insert

 Returns:
 Number of edges created
 """
 edges_created = 0

 for rel in relationships:
 predicate = rel.get("predicate")
 strength = rel.get("strength", 0.5)

 # Resolve target entity
 target_id = rel.get("target_id")
 target_file = rel.get("target_file")

 if target_id:
 destination_id = target_id
 elif target_file:
 destination_id = entity_id_map.get(target_file)
 if not destination_id:
 print(
 f" Warning: Cannot resolve target_file '{target_file}' to entity_id",
 file=sys.stderr,
 )
 continue
 else:
 print(f" Warning: Relationship missing target_id or target_file", file=sys.stderr)
 continue

 if not dry_run:
 edge_id = uuid4
 cursor.execute(
 """
 INSERT INTO edge (
 edge_id, source_id, destination_id, predicate, strength
 ) VALUES (
 %s, %s, %s, %s, %s
 )
 ON CONFLICT DO NOTHING
 """,
 (edge_id, source_entity_id, destination_id, predicate, strength),
 )
 edges_created += 1

 return edges_created


def main:
 """Main ingestion workflow."""
 parser = argparse.ArgumentParser(description="Ingest markdown docs into knowledge base")
 parser.add_argument(
 "--dry-run",
 action="store_true",
 help="Print what would be ingested without inserting into database",
 )
 parser.add_argument(
 "--path",
 type=str,
 default=DEFAULT_DOCS_PATH,
 help=f"Path to docs directory (default: {DEFAULT_DOCS_PATH})",
 )
 args = parser.parse_args

 docs_path = Path(args.path)
 if not docs_path.exists:
 print(f"Error: Path does not exist: {docs_path}", file=sys.stderr)
 sys.exit(1)

 # Find all markdown files
 md_files = sorted(docs_path.rglob("*.md"))
 print(f"Found {len(md_files)} markdown files in {docs_path}\n")

 if args.dry_run:
 print("DRY RUN MODE - No database changes will be made\n")

 # Connect to database (only if not dry-run)
 conn = None
 if not args.dry_run:
 try:
 conn = get_db_connection
 conn.autocommit = False
 except Exception as e:
 print(f"Error connecting to database: {e}", file=sys.stderr)
 sys.exit(1)

 try:
 cursor = conn.cursor if conn else None

 # PASS 1: Ingest all entities
 print("=== PASS 1: Ingesting Entities ===\n")
 entity_id_map = {} # filename -> entity_id
 entity_relationships = {} # entity_id -> relationships
 ingested_count = 0

 for md_file in md_files:
 try:
 result = ingest_markdown_file(md_file, cursor, dry_run=args.dry_run)

 # Track entity ID by filename for relationship resolution
 entity_id_map[md_file.name] = result["entity_id"]
 if result["relationships"]:
 entity_relationships[result["entity_id"]] = result["relationships"]

 # Display result
 frontmatter_indicator = " [frontmatter]" if result["has_frontmatter"] else ""
 print(f"✓ {result['file']}{frontmatter_indicator}")
 print(f" Title: {result['title']}")
 print(f" Category: {result['category']}")
 print(f" Tags: {', '.join(result['tags'])}")
 print(f" Entity ID: {result['entity_id']}")
 if result["relationships"]:
 print(f" Relationships: {len(result['relationships'])} defined")
 print
 ingested_count += 1
 except Exception as e:
 print(f"✗ Error processing {md_file}: {e}", file=sys.stderr)
 continue

 # PASS 2: Create relationships
 if entity_relationships:
 print(f"\n=== PASS 2: Creating Relationships ===\n")
 total_edges = 0

 for entity_id, relationships in entity_relationships.items:
 edges_created = create_edge_relationships(
 relationships,
 entity_id,
 cursor,
 entity_id_map,
 dry_run=args.dry_run,
 )
 if edges_created > 0:
 print(f"✓ Created {edges_created} edges for entity {entity_id}")
 total_edges += edges_created

 print(f"\nTotal edges created: {total_edges}")

 # Commit transaction
 if conn and not args.dry_run:
 conn.commit
 print(f"\n✓ Successfully ingested {ingested_count} files")
 else:
 print(f"\n✓ Would ingest {ingested_count} files")

 except Exception as e:
 if conn:
 conn.rollback
 print(f"Error during ingestion: {e}", file=sys.stderr)
 sys.exit(1)
 finally:
 if conn:
 conn.close


if __name__ == "__main__":
 main
