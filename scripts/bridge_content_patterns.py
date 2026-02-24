#!/usr/bin/env python3
"""
Bridge semops-docs content entities to the pattern layer in PostgreSQL.

HITL (human-in-the-loop) workflow:
 1. --extract: Extract concepts from detected_edges, match against patterns,
 generate mapping YAML for human review
 2. Human reviews and edits config/mappings/concept-pattern-map.yaml
 3. --apply: Create PostgreSQL edges + register new patterns from mapping
 4. --verify: Report on bridging results and governance impact

Usage:
 python scripts/bridge_content_patterns.py --extract
 python scripts/bridge_content_patterns.py --extract --dry-run
 python scripts/bridge_content_patterns.py --apply
 python scripts/bridge_content_patterns.py --apply --dry-run
 python scripts/bridge_content_patterns.py --verify
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path

import psycopg
import yaml
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection

console = Console

DEFAULT_MAPPING_PATH = Path(__file__).parent.parent / "config" / "mappings" / "concept-pattern-map.yaml"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ConceptInfo:
 """Aggregated info about a unique concept across all detected_edges."""
 concept_id: str
 occurrences: int = 0
 entities: list[str] = field(default_factory=list)
 predicates: list[str] = field(default_factory=list)
 max_strength: float = 0.0
 sample_rationale: str = ""


@dataclass
class MatchResult:
 """Result of matching a concept against the pattern table."""
 match_type: str # exact | alt_label | none
 pattern_id: str | None = None
 pattern_label: str | None = None


# ---------------------------------------------------------------------------
# Extract: query entities and collect concepts
# ---------------------------------------------------------------------------

def extract_detected_edges(conn: psycopg.Connection, corpus: str | None = None) -> list[dict]:
 """Query all content entities with detected_edges in metadata.

 Args:
 conn: Database connection
 corpus: Optional corpus filter (e.g., 'core_kb')

 Returns:
 List of {id, title, corpus, detected_edges} dicts
 """
 cursor = conn.cursor
 query = """
 SELECT id, title, metadata
 FROM entity
 WHERE entity_type = 'content'
 AND metadata->'detected_edges' IS NOT NULL
 AND jsonb_array_length(metadata->'detected_edges') > 0
 """
 params: list = []
 if corpus:
 query += " AND metadata->>'corpus' = %s"
 params.append(corpus)
 query += " ORDER BY id"

 cursor.execute(query, params)
 results = []
 for row in cursor.fetchall:
 entity_id, title, metadata = row
 metadata = metadata or {}
 results.append({
 "id": entity_id,
 "title": title,
 "corpus": metadata.get("corpus", ""),
 "primary_concept": metadata.get("primary_concept", ""),
 "detected_edges": metadata.get("detected_edges", []),
 })
 return results


def collect_unique_concepts(entities: list[dict]) -> dict[str, ConceptInfo]:
 """Aggregate detected_edges across entities into unique concepts.

 Returns:
 {concept_id: ConceptInfo} sorted by occurrence count descending
 """
 concepts: dict[str, ConceptInfo] = {}

 for entity in entities:
 for edge in entity.get("detected_edges", []):
 concept_id = edge.get("target_concept", "").strip
 if not concept_id:
 continue

 if concept_id not in concepts:
 concepts[concept_id] = ConceptInfo(concept_id=concept_id)

 info = concepts[concept_id]
 info.occurrences += 1
 if entity["id"] not in info.entities:
 info.entities.append(entity["id"])

 predicate = edge.get("predicate", "related_to")
 if predicate not in info.predicates:
 info.predicates.append(predicate)

 strength = edge.get("strength", 0.0)
 if strength > info.max_strength:
 info.max_strength = strength
 info.sample_rationale = edge.get("rationale", "")

 # Sort by occurrence count descending
 return dict(sorted(concepts.items, key=lambda x: -x[1].occurrences))


def get_registered_patterns(conn: psycopg.Connection) -> dict[str, dict]:
 """Load all registered patterns with their alt_labels.

 Returns:
 {pattern_id: {preferred_label, alt_labels, provenance}}
 """
 cursor = conn.cursor
 cursor.execute("""
 SELECT id, preferred_label, alt_labels, provenance
 FROM pattern
 ORDER BY id
 """)
 patterns = {}
 for row in cursor.fetchall:
 pattern_id, label, alt_labels, provenance = row
 patterns[pattern_id] = {
 "preferred_label": label,
 "alt_labels": alt_labels or [],
 "provenance": provenance,
 }
 return patterns


def match_concept_to_pattern(
 concept_id: str,
 patterns: dict[str, dict],
) -> MatchResult:
 """Try to match a concept to a registered pattern.

 Resolution order:
 1. Exact match: concept_id == pattern.id
 2. Alt-label match: concept_id in any pattern's alt_labels
 3. No match

 Args:
 concept_id: LLM-generated concept identifier
 patterns: Registered patterns from get_registered_patterns

 Returns:
 MatchResult with match_type and pattern_id
 """
 # 1. Exact match
 if concept_id in patterns:
 return MatchResult(
 match_type="exact",
 pattern_id=concept_id,
 pattern_label=patterns[concept_id]["preferred_label"],
 )

 # 2. Alt-label match
 for pid, pdata in patterns.items:
 if concept_id in (pdata.get("alt_labels") or []):
 return MatchResult(
 match_type="alt_label",
 pattern_id=pid,
 pattern_label=pdata["preferred_label"],
 )

 # 3. No match
 return MatchResult(match_type="none")


def generate_mapping_file(
 concepts: dict[str, ConceptInfo],
 matches: dict[str, MatchResult],
 entities: list[dict],
 output_path: Path,
) -> None:
 """Write concept-pattern-map.yaml for human review.

 Args:
 concepts: Unique concepts with occurrence info
 matches: Match results per concept
 entities: Source entities (for context)
 output_path: Where to write the YAML
 """
 now = datetime.now(UTC).isoformat

 matched = sum(1 for m in matches.values if m.match_type != "none")
 unmatched = len(matches) - matched

 # Build the mapping structure
 mapping = {
 "version": "1.0",
 "status": "pending_review",
 "generated_at": now,
 "entity_count": len(entities),
 "concept_count": len(concepts),
 "matched_count": matched,
 "unmatched_count": unmatched,
 "concepts": {},
 }

 for concept_id, info in concepts.items:
 match = matches[concept_id]

 entry: dict = {
 "occurrences": info.occurrences,
 "max_strength": round(info.max_strength, 2),
 "predicates": info.predicates,
 "entities": info.entities,
 "sample_rationale": info.sample_rationale,
 }

 if match.match_type != "none":
 entry["action"] = "map"
 entry["pattern_id"] = match.pattern_id
 entry["match_type"] = match.match_type
 entry["pattern_label"] = match.pattern_label
 entry["add_as_alt_label"] = match.match_type != "exact"
 entry["set_primary"] = False
 else:
 entry["action"] = "review"
 entry["pattern_id"] = None
 entry["match_type"] = "none"
 entry["note"] = ""

 mapping["concepts"][concept_id] = entry

 output_path.parent.mkdir(parents=True, exist_ok=True)
 with open(output_path, "w") as f:
 f.write("# Concept-to-Pattern Mapping for semops-docs content entities\n")
 f.write(f"# Generated: {now} by bridge_content_patterns.py --extract\n")
 f.write("#\n")
 f.write("# WORKFLOW:\n")
 f.write("# 1. Review each concept below\n")
 f.write("# 2. Set action to: map | register | dismiss\n")
 f.write("# 3. For 'map': set pattern_id to an existing pattern\n")
 f.write("# 4. For 'register': add a 'register' block with new pattern fields\n")
 f.write("# 5. For 'dismiss': optionally add a note explaining why\n")
 f.write("# 6. Change status to 'reviewed' when done\n")
 f.write("# 7. Run: python scripts/bridge_content_patterns.py --apply\n")
 f.write("#\n")
 f.write("# REGISTER EXAMPLE:\n")
 f.write("# some-concept:\n")
 f.write("# action: register\n")
 f.write("# register:\n")
 f.write("# id: some-concept\n")
 f.write("# preferred_label: \"Some Concept\"\n")
 f.write("# definition: \"A brief definition...\"\n")
 f.write("# provenance: \"1p\"\n")
 f.write("# set_primary: true\n")
 f.write("# ...\n")
 f.write("#\n\n")
 yaml.dump(mapping, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

 console.print(f"\n[green]Mapping file written:[/green] {output_path}")
 console.print(f" Concepts: {len(concepts)} ({matched} matched, {unmatched} unmatched)")
 console.print(f" Entities: {len(entities)}")
 console.print(f"\n[yellow]Next step:[/yellow] Review the YAML, set actions, change status to 'reviewed', then run --apply")


def run_extract(args: argparse.Namespace) -> int:
 """Extract mode: query entities, match concepts, generate mapping."""
 console.print
 console.print("[bold]Bridge Content→Pattern: Extract[/bold]")
 console.print("=" * 50)

 conn = get_db_connection

 # 1. Query entities with detected_edges
 console.print("\n[bold]Querying entities with detected_edges...[/bold]")
 entities = extract_detected_edges(conn)
 console.print(f" Found {len(entities)} entities with detected edges")

 if not entities:
 console.print("[yellow]No entities with detected_edges found.[/yellow]")
 conn.close
 return 0

 # 2. Collect unique concepts
 concepts = collect_unique_concepts(entities)
 console.print(f" Unique concepts: {len(concepts)}")

 total_edges = sum(c.occurrences for c in concepts.values)
 console.print(f" Total edge references: {total_edges}")

 # 3. Load registered patterns
 console.print("\n[bold]Loading registered patterns...[/bold]")
 patterns = get_registered_patterns(conn)
 console.print(f" Registered patterns: {len(patterns)}")

 # 4. Match concepts to patterns
 console.print("\n[bold]Matching concepts to patterns...[/bold]")
 matches: dict[str, MatchResult] = {}
 for concept_id in concepts:
 matches[concept_id] = match_concept_to_pattern(concept_id, patterns)

 # 5. Print summary table
 table = Table(title="Concept Match Results")
 table.add_column("Concept", style="cyan", max_width=35)
 table.add_column("Count", justify="right")
 table.add_column("Strength", justify="right")
 table.add_column("Match", style="green")
 table.add_column("Pattern", style="magenta")

 for concept_id, info in concepts.items:
 match = matches[concept_id]
 match_display = match.match_type if match.match_type != "none" else "[red]none[/red]"
 pattern_display = match.pattern_id or "-"
 table.add_row(
 concept_id,
 str(info.occurrences),
 f"{info.max_strength:.2f}",
 match_display,
 pattern_display,
 )

 console.print
 console.print(table)

 # 6. Generate mapping file
 if not args.dry_run:
 generate_mapping_file(concepts, matches, entities, args.mapping_file)
 else:
 matched = sum(1 for m in matches.values if m.match_type != "none")
 console.print(f"\n[yellow]DRY RUN:[/yellow] Would write mapping file to {args.mapping_file}")
 console.print(f" {matched} auto-matched, {len(matches) - matched} need review")

 conn.close
 return 0


# ---------------------------------------------------------------------------
# Apply: read mapping, create edges and register patterns
# ---------------------------------------------------------------------------

def load_mapping(mapping_path: Path) -> dict:
 """Load and validate the human-reviewed mapping file.

 Args:
 mapping_path: Path to concept-pattern-map.yaml

 Returns:
 Parsed mapping dict

 Raises:
 SystemExit: If file is missing, invalid, or not reviewed
 """
 if not mapping_path.exists:
 console.print(f"[red]Mapping file not found:[/red] {mapping_path}")
 console.print("Run --extract first to generate it.")
 sys.exit(1)

 with open(mapping_path) as f:
 mapping = yaml.safe_load(f)

 if not mapping or not isinstance(mapping, dict):
 console.print("[red]Invalid mapping file format[/red]")
 sys.exit(1)

 if mapping.get("status") != "reviewed":
 console.print(f"[red]Mapping file status is '{mapping.get('status', 'unknown')}' — must be 'reviewed'[/red]")
 console.print("Review the mapping file and change status to 'reviewed' before applying.")
 sys.exit(1)

 concepts = mapping.get("concepts", {})
 if not concepts:
 console.print("[yellow]No concepts in mapping file[/yellow]")
 sys.exit(1)

 # Validate actions
 valid_actions = {"map", "register", "dismiss"}
 for concept_id, entry in concepts.items:
 action = entry.get("action", "")
 if action not in valid_actions:
 console.print(f"[red]Invalid action '{action}' for concept '{concept_id}'[/red]")
 console.print(f" Valid actions: {', '.join(sorted(valid_actions))}")
 sys.exit(1)
 if action == "map" and not entry.get("pattern_id"):
 console.print(f"[red]Concept '{concept_id}' has action 'map' but no pattern_id[/red]")
 sys.exit(1)
 if action == "register" and not entry.get("register"):
 console.print(f"[red]Concept '{concept_id}' has action 'register' but no register block[/red]")
 sys.exit(1)

 return mapping


# Predicate mapping: LLM predicate → edge table predicate
PREDICATE_MAP = {
 "derived_from": "documents",
 "cites": "documents",
 "extends": "documents",
 "related_to": "related_to",
 "contradicts": "related_to",
}


def register_pattern(
 pattern_data: dict,
 cursor: psycopg.cursor.Cursor,
 dry_run: bool = False,
) -> bool:
 """Register a new pattern (roadmap or otherwise).

 Args:
 pattern_data: Dict with id, preferred_label, definition, provenance
 cursor: DB cursor
 dry_run: If True, don't write

 Returns:
 True if successful
 """
 pattern_id = pattern_data["id"]
 label = pattern_data["preferred_label"]
 definition = pattern_data["definition"]
 provenance = pattern_data.get("provenance", "1p")

 metadata = {
 "$schema": "pattern_registry_v1",
 "lifecycle_stage": pattern_data.get("lifecycle_stage", "proposed"),
 "registered_by": "bridge_content_patterns.py",
 }

 status = "[DRY]" if dry_run else " +"
 console.print(f" {status} register pattern: {pattern_id} ({provenance})")

 if dry_run:
 return True

 try:
 cursor.execute(
 """
 INSERT INTO pattern (id, preferred_label, definition, provenance, metadata)
 VALUES (%s, %s, %s, %s, %s)
 ON CONFLICT (id) DO UPDATE SET
 preferred_label = EXCLUDED.preferred_label,
 definition = EXCLUDED.definition,
 metadata = EXCLUDED.metadata,
 updated_at = now
 """,
 (pattern_id, label, definition, provenance, json.dumps(metadata)),
 )
 return True
 except Exception as e:
 console.print(f"[red]Pattern register error ({pattern_id}): {e}[/red]")
 return False


def create_documents_edge(
 entity_id: str,
 pattern_id: str,
 strength: float,
 edge_metadata: dict,
 cursor: psycopg.cursor.Cursor,
 dry_run: bool = False,
) -> bool:
 """Create entity→pattern documents edge using upsert.

 Args:
 entity_id: Source content entity
 pattern_id: Target pattern
 strength: Relationship strength 0.0-1.0
 edge_metadata: Traceability metadata
 cursor: DB cursor
 dry_run: If True, don't write

 Returns:
 True if successful
 """
 if dry_run:
 return True

 predicate = edge_metadata.pop("_predicate", "documents")

 try:
 cursor.execute(
 """
 INSERT INTO edge (src_type, src_id, dst_type, dst_id, predicate, strength, metadata)
 VALUES ('entity', %s, 'pattern', %s, %s, %s, %s)
 ON CONFLICT (src_type, src_id, dst_type, dst_id, predicate) DO UPDATE SET
 strength = EXCLUDED.strength,
 metadata = EXCLUDED.metadata
 """,
 (entity_id, pattern_id, predicate, strength, json.dumps(edge_metadata)),
 )
 return True
 except Exception as e:
 console.print(f"[red]Edge error ({entity_id} → {pattern_id}): {e}[/red]")
 return False


def set_primary_pattern(
 entity_id: str,
 pattern_id: str,
 cursor: psycopg.cursor.Cursor,
 dry_run: bool = False,
) -> bool:
 """Set primary_pattern_id on entity (only if currently NULL).

 Args:
 entity_id: Entity to update
 pattern_id: Pattern to set as primary
 cursor: DB cursor
 dry_run: If True, don't write

 Returns:
 True if updated (was NULL), False if already set
 """
 if dry_run:
 return True

 try:
 cursor.execute(
 """
 UPDATE entity
 SET primary_pattern_id = %s, updated_at = now
 WHERE id = %s AND primary_pattern_id IS NULL
 """,
 (pattern_id, entity_id),
 )
 return cursor.rowcount > 0
 except Exception as e:
 console.print(f"[red]Primary pattern error ({entity_id}): {e}[/red]")
 return False


def add_alt_label(
 pattern_id: str,
 alt_label: str,
 cursor: psycopg.cursor.Cursor,
 dry_run: bool = False,
) -> bool:
 """Add a concept as alt_label on a pattern (if not already present).

 Args:
 pattern_id: Pattern to update
 alt_label: Alt label to add
 cursor: DB cursor
 dry_run: If True, don't write

 Returns:
 True if successful
 """
 if dry_run:
 return True

 try:
 cursor.execute(
 """
 UPDATE pattern
 SET alt_labels = array_append(alt_labels, %s)
 WHERE id = %s AND NOT (%s = ANY(alt_labels))
 """,
 (alt_label, pattern_id, alt_label),
 )
 return True
 except Exception as e:
 console.print(f"[red]Alt label error ({pattern_id}): {e}[/red]")
 return False


def run_apply(args: argparse.Namespace) -> int:
 """Apply mode: read mapping, create edges, register patterns."""
 console.print
 console.print("[bold]Bridge Content→Pattern: Apply[/bold]")
 console.print("=" * 50)

 if args.dry_run:
 console.print("[yellow]DRY RUN — no database changes[/yellow]")

 # Load and validate mapping
 mapping = load_mapping(args.mapping_file)
 concepts = mapping.get("concepts", {})

 # Tally actions
 action_counts = {"map": 0, "register": 0, "dismiss": 0}
 for entry in concepts.values:
 action_counts[entry["action"]] += 1

 console.print(f"\n Concepts: {len(concepts)}")
 console.print(f" Map: {action_counts['map']}, Register: {action_counts['register']}, Dismiss: {action_counts['dismiss']}")

 # Load entities with detected_edges (to get per-entity edge details)
 conn = get_db_connection
 conn.autocommit = False
 cursor = conn.cursor

 # Build entity→edges lookup from DB
 entities = extract_detected_edges(conn)
 entity_edges: dict[str, list[dict]] = {}
 for entity in entities:
 entity_edges[entity["id"]] = entity.get("detected_edges", [])

 # Verify pattern references exist
 registered = get_registered_patterns(conn)

 now = datetime.now(UTC).isoformat
 stats = {
 "edges_created": 0,
 "patterns_registered": 0,
 "primary_set": 0,
 "alt_labels_added": 0,
 "dismissed": 0,
 "errors": 0,
 }

 try:
 # Pass 1: Register new patterns first (so edges can reference them)
 console.print("\n[bold]Pass 1: Register new patterns[/bold]")
 for concept_id, entry in concepts.items:
 if entry["action"] != "register":
 continue
 reg = entry["register"]
 ok = register_pattern(reg, cursor, dry_run=args.dry_run)
 if ok:
 stats["patterns_registered"] += 1
 # Add to registered set so edges can reference it
 registered[reg["id"]] = {
 "preferred_label": reg["preferred_label"],
 "alt_labels": [],
 "provenance": reg.get("provenance", "1p"),
 }
 else:
 stats["errors"] += 1

 if stats["patterns_registered"] > 0 or args.dry_run:
 console.print(f" Registered: {stats['patterns_registered']}")

 # Pass 2: Create edges for map + register actions
 console.print("\n[bold]Pass 2: Create documents edges[/bold]")
 for concept_id, entry in concepts.items:
 if entry["action"] == "dismiss":
 stats["dismissed"] += 1
 continue

 # Determine target pattern
 if entry["action"] == "map":
 pattern_id = entry["pattern_id"]
 elif entry["action"] == "register":
 pattern_id = entry["register"]["id"]
 else:
 continue

 # Verify pattern exists
 if pattern_id not in registered:
 console.print(f" [red]Pattern not found: {pattern_id} (concept: {concept_id})[/red]")
 stats["errors"] += 1
 continue

 # Create edge for each entity that references this concept
 entity_ids = entry.get("entities", [])
 for entity_id in entity_ids:
 # Find the original detected_edge for this entity+concept
 edges_for_entity = entity_edges.get(entity_id, [])
 original_edge = next(
 (e for e in edges_for_entity if e.get("target_concept") == concept_id),
 None,
 )

 original_predicate = (original_edge or {}).get("predicate", "related_to")
 strength = (original_edge or {}).get("strength", 0.5)
 mapped_predicate = PREDICATE_MAP.get(original_predicate, "documents")

 edge_metadata = {
 "source": "bridge_content_patterns",
 "original_predicate": original_predicate,
 "original_concept": concept_id,
 "mapped_at": now,
 "_predicate": mapped_predicate,
 }

 status = "[DRY]" if args.dry_run else " +"
 console.print(
 f" {status} edge: {entity_id} --{mapped_predicate}--> {pattern_id}"
 f" (str={strength:.2f})"
 )

 ok = create_documents_edge(
 entity_id, pattern_id, strength, edge_metadata,
 cursor, dry_run=args.dry_run,
 )
 if ok:
 stats["edges_created"] += 1
 else:
 stats["errors"] += 1

 # Set primary_pattern_id if requested
 if entry.get("set_primary", False):
 for entity_id in entity_ids:
 ok = set_primary_pattern(entity_id, pattern_id, cursor, dry_run=args.dry_run)
 if ok:
 stats["primary_set"] += 1
 status = "[DRY]" if args.dry_run else " ="
 console.print(f" {status} primary: {entity_id} → {pattern_id}")

 # Add alt_label if requested (for 'map' action with non-exact match)
 if entry.get("add_as_alt_label", False) and entry["action"] == "map":
 ok = add_alt_label(pattern_id, concept_id, cursor, dry_run=args.dry_run)
 if ok:
 stats["alt_labels_added"] += 1

 # Commit
 if not args.dry_run:
 conn.commit
 console.print("\n[green]Transaction committed.[/green]")
 else:
 conn.rollback

 except Exception as e:
 conn.rollback
 console.print(f"\n[red]Error: {e}[/red]")
 import traceback
 traceback.print_exc
 return 1
 finally:
 conn.close

 # Summary
 console.print
 table = Table(title="Apply Summary")
 table.add_column("Metric", style="cyan")
 table.add_column("Count", justify="right")
 table.add_row("Edges created", str(stats["edges_created"]))
 table.add_row("Patterns registered", str(stats["patterns_registered"]))
 table.add_row("Primary pattern set", str(stats["primary_set"]))
 table.add_row("Alt labels added", str(stats["alt_labels_added"]))
 table.add_row("Dismissed", str(stats["dismissed"]))
 table.add_row("Errors", str(stats["errors"]))
 console.print(table)

 if args.dry_run:
 console.print("\n[yellow]DRY RUN — no changes made[/yellow]")

 return 0 if stats["errors"] == 0 else 1


# ---------------------------------------------------------------------------
# Verify: report on bridging results
# ---------------------------------------------------------------------------

def run_verify(args: argparse.Namespace) -> int:
 """Verify mode: report on bridging results and governance impact."""
 console.print
 console.print("[bold]Bridge Content→Pattern: Verify[/bold]")
 console.print("=" * 50)

 conn = get_db_connection
 cursor = conn.cursor

 # 1. Documents edges created by this script
 console.print("\n[bold]Documents edges (bridge_content_patterns)[/bold]")
 cursor.execute("""
 SELECT
 e.src_id AS entity_id,
 e.dst_id AS pattern_id,
 e.predicate,
 e.strength,
 p.preferred_label
 FROM edge e
 JOIN pattern p ON e.dst_id = p.id
 WHERE e.src_type = 'entity'
 AND e.dst_type = 'pattern'
 AND e.predicate IN ('documents', 'related_to')
 AND e.metadata->>'source' = 'bridge_content_patterns'
 ORDER BY e.dst_id, e.src_id
 """)
 bridge_edges = cursor.fetchall

 if bridge_edges:
 table = Table(title=f"Bridge Edges ({len(bridge_edges)} total)")
 table.add_column("Entity", style="cyan", max_width=35)
 table.add_column("Predicate")
 table.add_column("Pattern", style="magenta")
 table.add_column("Label")
 table.add_column("Strength", justify="right")
 for row in bridge_edges:
 table.add_row(row[0], row[2], row[1], row[4], f"{row[3]:.2f}")
 console.print(table)
 else:
 console.print(" [yellow]No bridge edges found. Run --apply first.[/yellow]")

 # 2. Pattern coverage with edge-based content
 console.print("\n[bold]Pattern coverage (content via FK + documents edges)[/bold]")
 cursor.execute("""
 SELECT
 p.id,
 p.preferred_label,
 p.provenance,
 COUNT(DISTINCT fk.id) AS fk_content,
 COUNT(DISTINCT ed.src_id) AS edge_content,
 COUNT(DISTINCT COALESCE(fk.id, ed.src_id)) AS total_content
 FROM pattern p
 LEFT JOIN entity fk ON fk.primary_pattern_id = p.id AND fk.entity_type = 'content'
 LEFT JOIN edge ed ON ed.dst_type = 'pattern' AND ed.dst_id = p.id
 AND ed.src_type = 'entity' AND ed.predicate IN ('documents', 'related_to')
 GROUP BY p.id, p.preferred_label, p.provenance
 HAVING COUNT(DISTINCT fk.id) > 0 OR COUNT(DISTINCT ed.src_id) > 0
 ORDER BY COUNT(DISTINCT COALESCE(fk.id, ed.src_id)) DESC
 """)
 rows = cursor.fetchall

 if rows:
 table = Table(title="Pattern Coverage (content entities)")
 table.add_column("Pattern", style="cyan")
 table.add_column("Label")
 table.add_column("FK", justify="right", style="dim")
 table.add_column("Edge", justify="right", style="green")
 table.add_column("Total", justify="right", style="bold")
 for row in rows:
 table.add_row(row[0], row[1], str(row[3]), str(row[4]), str(row[5]))
 console.print(table)
 else:
 console.print(" [yellow]No patterns with content coverage[/yellow]")

 # 3. Remaining orphans (content with no pattern link)
 console.print("\n[bold]Remaining orphan content entities[/bold]")
 cursor.execute("""
 SELECT e.id, e.title, e.metadata->>'corpus' AS corpus
 FROM entity e
 WHERE e.entity_type = 'content'
 AND e.primary_pattern_id IS NULL
 AND NOT EXISTS (
 SELECT 1 FROM edge ed
 WHERE ed.src_type = 'entity' AND ed.src_id = e.id
 AND ed.dst_type = 'pattern'
 AND ed.predicate IN ('documents', 'related_to')
 )
 ORDER BY e.id
 """)
 orphans = cursor.fetchall
 console.print(f" Orphan entities: {len(orphans)}")
 if orphans and args.verbose:
 for row in orphans:
 console.print(f" {row[0]} | {row[1]} | {row[2]}")

 # 4. Summary counts
 console.print("\n[bold]Summary[/bold]")
 cursor.execute("SELECT count(*) FROM edge WHERE metadata->>'source' = 'bridge_content_patterns'")
 console.print(f" Bridge edges: {cursor.fetchone[0]}")

 cursor.execute("""
 SELECT count(*) FROM pattern
 WHERE metadata->>'registered_by' = 'bridge_content_patterns.py'
 """)
 console.print(f" Registered patterns: {cursor.fetchone[0]}")

 cursor.execute("""
 SELECT count(*) FROM entity
 WHERE entity_type = 'content' AND primary_pattern_id IS NOT NULL
 """)
 console.print(f" Content with primary_pattern_id: {cursor.fetchone[0]}")

 cursor.execute("""
 SELECT count(*) FROM entity
 WHERE entity_type = 'content' AND primary_pattern_id IS NULL
 """)
 console.print(f" Content without primary_pattern_id: {cursor.fetchone[0]}")

 conn.close
 console.print
 return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main -> int:
 parser = argparse.ArgumentParser(
 description="Bridge semops-docs content entities to pattern layer (HITL workflow)"
 )
 group = parser.add_mutually_exclusive_group(required=True)
 group.add_argument("--extract", action="store_true",
 help="Extract concepts and generate mapping YAML")
 group.add_argument("--apply", action="store_true",
 help="Apply reviewed mapping (create edges, register patterns)")
 group.add_argument("--verify", action="store_true",
 help="Report on bridging results")

 parser.add_argument("--dry-run", action="store_true",
 help="Show what would be done without writing")
 parser.add_argument("--mapping-file", type=Path, default=DEFAULT_MAPPING_PATH,
 help=f"Mapping file path (default: {DEFAULT_MAPPING_PATH})")
 parser.add_argument("-v", "--verbose", action="store_true",
 help="Show detailed output")

 args = parser.parse_args

 if args.extract:
 return run_extract(args)
 elif args.apply:
 return run_apply(args)
 elif args.verify:
 return run_verify(args)

 return 0


if __name__ == "__main__":
 sys.exit(main)
