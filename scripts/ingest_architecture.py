#!/usr/bin/env python3
"""
Architecture layer ingestion for Project SemOps.

Parses structured architecture sources (REPOS.yaml, STRATEGIC_DDD.md) and
creates repository entities, capability entities, and typed edges (implements,
delivered_by, integration) in the entity catalog.

This is a deterministic parser — no LLM classification needed. The architecture
data is already structured in YAML and markdown tables.

Usage:
 python scripts/ingest_architecture.py # Full ingestion
 python scripts/ingest_architecture.py --dry-run # Parse only, no DB
 python scripts/ingest_architecture.py --verify # Ingest + test queries
 python scripts/ingest_architecture.py --skip-neo4j # Skip Neo4j sync
 python scripts/ingest_architecture.py --dry-run -v # Verbose dry run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
import yaml
from rich.console import Console
from rich.table import Table

console = Console

# ---------------------------------------------------------------------------
# Source file locations
# ---------------------------------------------------------------------------
REPOS_YAML = Path.home / "GitHub" / "semops-dx-orchestrator" / "docs" / "REPOS.yaml"
STRATEGIC_DDD_MD = Path(__file__).parent.parent / "docs" / "STRATEGIC_DDD.md"

# Repos outside the SemOps bounded context
SKIP_REPOS = {"motorsport-consulting"}

# All SemOps repos (for expanding "all repos" in integration map)
SEMOPS_REPOS = {
 "semops-dx-orchestrator",
 "semops-core",
 "semops-publisher",
 "semops-docs",
 "semops-data",
 "semops-sites",
 "semops-backoffice",
}

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection

NEO4J_URL = os.environ.get("NEO4J_URL", "http://localhost:7474")


# ---------------------------------------------------------------------------
# Neo4j utilities (reused from materialize_graph.py)
# ---------------------------------------------------------------------------
def neo4j_escape(s: str) -> str:
 """Escape string for Cypher."""
 return s.replace("\\", "\\\\").replace("'", "\\'")


def run_cypher(cypher: str) -> dict | None:
 """Execute Cypher statement via Neo4j HTTP API."""
 try:
 result = subprocess.run(
 [
 "curl", "-s",
 "-H", "Content-Type: application/json",
 "-d", json.dumps({"statements": [{"statement": cypher}]}),
 f"{NEO4J_URL}/db/neo4j/tx/commit",
 ],
 capture_output=True,
 text=True,
 timeout=10,
 )
 return json.loads(result.stdout) if result.returncode == 0 else None
 except Exception:
 return None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def parse_repos(yaml_path: Path) -> list[dict]:
 """Parse REPOS.yaml into repository entity dicts."""
 with open(yaml_path) as f:
 data = yaml.safe_load(f)

 repos = []
 for entry in data.get("repos", []):
 name = entry.get("name", "")
 if name in SKIP_REPOS:
 continue
 if entry.get("status") != "active":
 continue

 now = datetime.now(timezone.utc).isoformat
 repos.append({
 "id": name,
 "entity_type": "repository",
 "asset_type": None,
 "title": name,
 "version": "1.0",
 "filespec": json.dumps({
 "$schema": "filespec_v1",
 "uri": f"github://timjmitchell/{name}",
 "platform": "github",
 }),
 "attribution": json.dumps({
 "$schema": "attribution_v2",
 "creator": ["Tim Mitchell"],
 "organization": "TJMConsulting",
 "platform": "github",
 }),
 "metadata": {
 "$schema": "repository_metadata_v1",
 "role": entry.get("role", ""),
 "context": entry.get("context", ""),
 "github_url": f"https://github.com/timjmitchell/{name}",
 "delivers_capabilities": [], # populated after capability parsing
 "status": "active",
 },
 "created_at": now,
 "updated_at": now,
 "_raw": entry, # keep for cross-referencing
 })

 return repos


def _parse_capability_table(text: str, domain_classification: str) -> list[dict]:
 """Parse a single capability markdown table into capability dicts.

 Handles 5-column table format (added Status column in Issue #146):
 | ID | Capability | Status | Implements Patterns | Delivered By |
 """
 capabilities = []
 # Match rows: | `id` | Name | Status | `pat1`, `pat2` | repo1, repo2 |
 row_re = re.compile(
 r"^\|\s*`([^`]+)`\s*\|" # ID in backticks
 r"\s*([^|]+?)\s*\|" # Capability name
 r"\s*([^|]+?)\s*\|" # Status (planned/draft/in_progress/active/retired)
 r"\s*([^|]+?)\s*\|" # Implements patterns
 r"\s*([^|]+?)\s*\|", # Delivered by
 re.MULTILINE,
 )

 for match in row_re.finditer(text):
 cap_id = match.group(1).strip
 cap_name = match.group(2).strip
 status_raw = match.group(3).strip
 patterns_raw = match.group(4).strip
 repos_raw = match.group(5).strip

 # Parse pattern IDs: `ddd`, `skos`, `prov-o` → ["ddd", "skos", "prov-o"]
 pattern_ids = [
 p.strip.strip("`")
 for p in patterns_raw.split(",")
 if p.strip.strip("`")
 ]

 # Parse repo IDs: semops-core, semops-dx-orchestrator → ["semops-core", "semops-dx-orchestrator"]
 repo_ids = [
 r.strip
 for r in repos_raw.split(",")
 if r.strip
 ]

 now = datetime.now(timezone.utc).isoformat
 capabilities.append({
 "id": cap_id,
 "entity_type": "capability",
 "asset_type": None,
 "title": cap_name,
 "version": "1.0",
 "filespec": json.dumps({}),
 "attribution": json.dumps({
 "$schema": "attribution_v2",
 "creator": ["Tim Mitchell"],
 "organization": "TJMConsulting",
 }),
 "metadata": {
 "$schema": "capability_metadata_v1",
 "domain_classification": domain_classification,
 "implements_patterns": pattern_ids,
 "delivered_by_repos": repo_ids,
 "status": status_raw,
 },
 "created_at": now,
 "updated_at": now,
 })

 return capabilities


def parse_capabilities(md_path: Path) -> list[dict]:
 """Parse STRATEGIC_DDD.md capability tables into capability entity dicts."""
 content = md_path.read_text

 capabilities = []

 # Split by section headers to find each capability table
 # Stop at any heading (## or ###) or end-of-string
 section_end = r"(?=\n##[# ]|\Z)"

 # Core Domain Capabilities
 core_match = re.search(
 r"### Core Domain Capabilities\b(.*?)" + section_end,
 content, re.DOTALL,
 )
 if core_match:
 capabilities.extend(_parse_capability_table(core_match.group(1), "core"))

 # Supporting Domain Capabilities
 supporting_match = re.search(
 r"### Supporting Domain Capabilities\b(.*?)" + section_end,
 content, re.DOTALL,
 )
 if supporting_match:
 capabilities.extend(
 _parse_capability_table(supporting_match.group(1), "supporting")
 )

 # Generic Domain Capabilities
 generic_match = re.search(
 r"### Generic Domain Capabilities\b(.*?)" + section_end,
 content, re.DOTALL,
 )
 if generic_match:
 capabilities.extend(
 _parse_capability_table(generic_match.group(1), "generic")
 )

 return capabilities


def parse_repo_capability_map(md_path: Path) -> dict[str, list[str]]:
 """Parse the Repository Registry table → {repo_id: [capability_ids]}."""
 content = md_path.read_text

 repo_map: dict[str, list[str]] = {}
 registry_match = re.search(
 r"## Repository Registry\b(.*?)(?=\n---|\n## |\Z)",
 content, re.DOTALL,
 )
 if not registry_match:
 return repo_map

 # Match rows: | `repo-id` | repo | role | `cap1`, `cap2` |
 row_re = re.compile(
 r"^\|\s*`([^`]+)`\s*\|" # ID
 r"\s*[^|]+?\s*\|" # Repo name
 r"\s*[^|]+?\s*\|" # Role
 r"\s*([^|]+?)\s*\|", # Delivers capabilities
 re.MULTILINE,
 )

 for match in row_re.finditer(registry_match.group(1)):
 repo_id = match.group(1).strip
 caps_raw = match.group(2).strip
 cap_ids = [
 c.strip.strip("`")
 for c in caps_raw.split(",")
 if c.strip.strip("`")
 ]
 repo_map[repo_id] = cap_ids

 return repo_map


def parse_integration_edges(md_path: Path) -> list[dict]:
 """Parse integration map table → edge dicts."""
 content = md_path.read_text

 edges = []
 integration_match = re.search(
 r"### Current Integration Map\b(.*?)(?=\n###|\n---|\n## |\Z)",
 content, re.DOTALL,
 )
 if not integration_match:
 return edges

 # Match rows: | source | target | **Pattern** | shared | direction |
 row_re = re.compile(
 r"^\|\s*(\S+)\s*\|" # Source repo
 r"\s*([^|]+?)\s*\|" # Target repo
 r"\s*\*\*([^*]+)\*\*\s*\|" # DDD pattern (bold)
 r"\s*([^|]+?)\s*\|" # What's shared
 r"\s*([^|]+?)\s*\|", # Direction
 re.MULTILINE,
 )

 for match in row_re.finditer(integration_match.group(1)):
 src = match.group(1).strip
 dst = match.group(2).strip
 pattern = match.group(3).strip
 shared = match.group(4).strip
 direction = match.group(5).strip.lower

 # Normalize pattern to kebab-case
 pattern_kebab = pattern.lower.replace(" ", "-")

 # Expand "all repos" to individual edges
 if dst.lower == "all repos":
 for repo in sorted(SEMOPS_REPOS - {src}):
 edges.append({
 "src_type": "entity",
 "src_id": src,
 "dst_type": "entity",
 "dst_id": repo,
 "predicate": "integration",
 "strength": 1.0,
 "metadata": {
 "integration_pattern": pattern_kebab,
 "shared_artifact": shared,
 "direction": direction,
 },
 })
 else:
 edges.append({
 "src_type": "entity",
 "src_id": src,
 "dst_type": "entity",
 "dst_id": dst,
 "predicate": "integration",
 "strength": 1.0,
 "metadata": {
 "integration_pattern": pattern_kebab,
 "shared_artifact": shared,
 "direction": direction,
 },
 })

 return edges


def derive_lifecycle_stages(
 capabilities: list[dict],
 repos: list[dict],
 implements_edges: list[dict],
 delivered_by_edges: list[dict],
) -> None:
 """Set lifecycle_stage for capabilities and repos.

 Lifecycle evolution model (Issue #146):
 v1 (current): Human-declared status from STRATEGIC_DDD.md Status column.
 Capabilities use the 5-state model: planned → draft → in_progress → active → retired.
 Repos use lifecycle_stage from REPOS.yaml (defaulting to 'active').
 v2 (future): System validates declared vs edge-derived, reports delta.
 v3 (future): Computed becomes primary, declared becomes override.

 Sets lifecycle_stage in entity.metadata (JSONB), consistent with how
 source_config.py / entity_builder.py set it for content entities.
 """
 # v1: Use declared status from parsed table (stored in metadata.status)
 valid_states = {"planned", "draft", "in_progress", "active", "retired"}

 for cap in capabilities:
 declared = cap["metadata"].get("status", "draft")
 cap["metadata"]["lifecycle_stage"] = declared if declared in valid_states else "draft"

 # Repos: use status from REPOS.yaml parse (defaults to 'active')
 for repo in repos:
 declared = repo["metadata"].get("status", "active")
 repo["metadata"]["lifecycle_stage"] = declared if declared in valid_states else "active"


def build_delivered_by_edges(capabilities: list[dict]) -> list[dict]:
 """Build delivered_by edges from capability metadata."""
 edges = []
 for cap in capabilities:
 meta = cap["metadata"]
 for repo_id in meta.get("delivered_by_repos", []):
 edges.append({
 "src_type": "entity",
 "src_id": cap["id"],
 "dst_type": "entity",
 "dst_id": repo_id,
 "predicate": "delivered_by",
 "strength": 1.0,
 "metadata": {},
 })
 return edges


def build_implements_edges(
 capabilities: list[dict], registered_patterns: set[str]
) -> tuple[list[dict], list[str]]:
 """Build implements edges for patterns that exist in DB.

 Returns (edges, warnings) where warnings lists unregistered pattern IDs.
 """
 edges = []
 unregistered: set[str] = set

 for cap in capabilities:
 meta = cap["metadata"]
 for pattern_id in meta.get("implements_patterns", []):
 if pattern_id in registered_patterns:
 edges.append({
 "src_type": "entity",
 "src_id": cap["id"],
 "dst_type": "pattern",
 "dst_id": pattern_id,
 "predicate": "implements",
 "strength": 1.0,
 "metadata": {},
 })
 else:
 unregistered.add(pattern_id)

 return edges, sorted(unregistered)


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------
def upsert_entity(entity: dict, cursor: Any) -> bool:
 """Insert or update an entity."""
 try:
 cursor.execute(
 """
 INSERT INTO entity (
 id, entity_type, asset_type, title, version,
 filespec, attribution, metadata,
 created_at, updated_at
 ) VALUES (
 %(id)s, %(entity_type)s, %(asset_type)s, %(title)s, %(version)s,
 %(filespec)s, %(attribution)s, %(metadata)s,
 %(created_at)s, %(updated_at)s
 )
 ON CONFLICT (id) DO UPDATE SET
 entity_type = EXCLUDED.entity_type,
 title = EXCLUDED.title,
 filespec = EXCLUDED.filespec,
 attribution = EXCLUDED.attribution,
 metadata = EXCLUDED.metadata,
 updated_at = EXCLUDED.updated_at
 """,
 {
 "id": entity["id"],
 "entity_type": entity["entity_type"],
 "asset_type": entity["asset_type"],
 "title": entity["title"],
 "version": entity["version"],
 "filespec": entity["filespec"] if isinstance(entity["filespec"], str)
 else json.dumps(entity["filespec"]),
 "attribution": entity["attribution"] if isinstance(entity["attribution"], str)
 else json.dumps(entity["attribution"]),
 "metadata": json.dumps(entity["metadata"]),
 "created_at": entity["created_at"],
 "updated_at": entity["updated_at"],
 },
 )
 return True
 except Exception as e:
 console.print(f"[red]Entity upsert error ({entity['id']}): {e}[/red]")
 return False


def upsert_edge(edge: dict, cursor: Any) -> bool:
 """Insert or update an edge."""
 try:
 cursor.execute(
 """
 INSERT INTO edge (
 src_type, src_id, dst_type, dst_id, predicate,
 strength, metadata
 ) VALUES (
 %(src_type)s, %(src_id)s, %(dst_type)s, %(dst_id)s, %(predicate)s,
 %(strength)s, %(metadata)s
 )
 ON CONFLICT (src_type, src_id, dst_type, dst_id, predicate) DO UPDATE SET
 strength = EXCLUDED.strength,
 metadata = EXCLUDED.metadata
 """,
 {
 "src_type": edge["src_type"],
 "src_id": edge["src_id"],
 "dst_type": edge["dst_type"],
 "dst_id": edge["dst_id"],
 "predicate": edge["predicate"],
 "strength": edge["strength"],
 "metadata": json.dumps(edge["metadata"]),
 },
 )
 return True
 except Exception as e:
 console.print(
 f"[red]Edge upsert error ({edge['src_id']} "
 f"-[{edge['predicate']}]-> {edge['dst_id']}): {e}[/red]"
 )
 return False


def get_registered_patterns(cursor: Any) -> set[str]:
 """Query existing pattern IDs from the pattern table."""
 cursor.execute("SELECT id FROM pattern")
 return {row[0] for row in cursor.fetchall}


# ---------------------------------------------------------------------------
# Neo4j materialization
# ---------------------------------------------------------------------------
def materialize_neo4j(
 repos: list[dict],
 capabilities: list[dict],
 delivered_by_edges: list[dict],
 implements_edges: list[dict],
 integration_edges: list[dict],
 verbose: bool = False,
) -> dict[str, int]:
 """Materialize architecture layer to Neo4j graph."""
 counts = {"nodes": 0, "relationships": 0}

 # Check connectivity
 health = run_cypher("RETURN 1")
 if health is None:
 console.print(f"[yellow]Cannot connect to Neo4j at {NEO4J_URL} — skipping[/yellow]")
 return counts

 # Constraints
 run_cypher(
 "CREATE CONSTRAINT repository_id IF NOT EXISTS "
 "FOR (r:Repository) REQUIRE r.id IS UNIQUE"
 )
 run_cypher(
 "CREATE CONSTRAINT capability_id IF NOT EXISTS "
 "FOR (c:Capability) REQUIRE c.id IS UNIQUE"
 )

 # Repository nodes
 for repo in repos:
 meta = repo["metadata"]
 cypher = (
 f"MERGE (r:Repository {{id: '{neo4j_escape(repo['id'])}'}}) "
 f"SET r.title = '{neo4j_escape(repo['title'])}', "
 f"r.role = '{neo4j_escape(meta.get('role', ''))}'"
 )
 run_cypher(cypher)
 counts["nodes"] += 1

 # Capability nodes
 for cap in capabilities:
 meta = cap["metadata"]
 cypher = (
 f"MERGE (c:Capability {{id: '{neo4j_escape(cap['id'])}'}}) "
 f"SET c.title = '{neo4j_escape(cap['title'])}', "
 f"c.domain = '{neo4j_escape(meta.get('domain_classification', ''))}'"
 )
 run_cypher(cypher)
 counts["nodes"] += 1

 # DELIVERED_BY relationships
 for edge in delivered_by_edges:
 cypher = (
 f"MATCH (c:Capability {{id: '{neo4j_escape(edge['src_id'])}'}}) "
 f"MATCH (r:Repository {{id: '{neo4j_escape(edge['dst_id'])}'}}) "
 f"MERGE (c)-[:DELIVERED_BY]->(r)"
 )
 run_cypher(cypher)
 counts["relationships"] += 1

 # IMPLEMENTS relationships
 for edge in implements_edges:
 cypher = (
 f"MATCH (c:Capability {{id: '{neo4j_escape(edge['src_id'])}'}}) "
 f"MERGE (p:Pattern {{id: '{neo4j_escape(edge['dst_id'])}'}}) "
 f"MERGE (c)-[:IMPLEMENTS]->(p)"
 )
 run_cypher(cypher)
 counts["relationships"] += 1

 # INTEGRATION relationships
 for edge in integration_edges:
 meta = edge["metadata"]
 cypher = (
 f"MATCH (s:Repository {{id: '{neo4j_escape(edge['src_id'])}'}}) "
 f"MATCH (t:Repository {{id: '{neo4j_escape(edge['dst_id'])}'}}) "
 f"MERGE (s)-[r:INTEGRATION]->(t) "
 f"SET r.pattern = '{neo4j_escape(meta.get('integration_pattern', ''))}', "
 f"r.direction = '{neo4j_escape(meta.get('direction', ''))}', "
 f"r.shared_artifact = '{neo4j_escape(meta.get('shared_artifact', ''))}'"
 )
 run_cypher(cypher)
 counts["relationships"] += 1

 return counts


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def run_verification(conn: psycopg.Connection) -> None:
 """Run test queries from Issue #117."""
 cursor = conn.cursor
 console.print
 console.print("[bold]Verification Queries[/bold]")
 console.print("=" * 60)

 # Test Query 2: "Which repo owns the Pattern model?"
 console.print
 console.print("[bold]Query 2:[/bold] Which repo owns the Pattern model?")
 cursor.execute(
 """
 SELECT repo_id, repo_name, repo_role, capability_id, capability_name
 FROM repo_capabilities
 WHERE capability_id = 'domain-data-model'
 """
 )
 rows = cursor.fetchall
 if rows:
 for row in rows:
 console.print(f" [green]{row[0]}[/green] ({row[2]}) delivers {row[4]}")
 else:
 console.print(" [yellow]No results — domain-data-model not found[/yellow]")

 # Test Query 3: "How does content flow from semops-docs to semops-sites?"
 console.print
 console.print("[bold]Query 3:[/bold] How does content flow from semops-docs to semops-sites?")
 cursor.execute(
 """
 SELECT source_repo_id, target_repo_id, integration_pattern,
 shared_artifact, direction
 FROM integration_map
 WHERE source_repo_id IN ('semops-docs', 'semops-sites')
 OR target_repo_id IN ('semops-docs', 'semops-sites')
 """
 )
 rows = cursor.fetchall
 if rows:
 for row in rows:
 console.print(
 f" [green]{row[0]}[/green] -> [green]{row[1]}[/green] "
 f"({row[2]}, {row[4]}): {row[3]}"
 )
 else:
 console.print(" [yellow]No integration edges involving semops-docs or semops-sites[/yellow]")

 # Capability coverage
 console.print
 console.print("[bold]Capability Coverage (coherence signal):[/bold]")
 cursor.execute(
 """
 SELECT capability_id, capability_name, domain_classification,
 pattern_count, repo_count
 FROM capability_coverage
 ORDER BY domain_classification, capability_name
 """
 )
 rows = cursor.fetchall
 tbl = Table(title="Capability Coverage")
 tbl.add_column("ID")
 tbl.add_column("Name")
 tbl.add_column("Domain")
 tbl.add_column("Patterns", justify="right")
 tbl.add_column("Repos", justify="right")
 for row in rows:
 tbl.add_row(row[0], row[1], row[2] or "", str(row[3]), str(row[4]))
 console.print(tbl)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def print_dry_run(
 repos: list[dict],
 capabilities: list[dict],
 delivered_by: list[dict],
 implements: list[dict],
 integration: list[dict],
 unregistered: list[str],
 verbose: bool = False,
) -> None:
 """Print what would be created."""
 console.print
 console.print("[bold]Dry Run Summary[/bold]")
 console.print("=" * 60)

 # Entities
 tbl = Table(title="Entities")
 tbl.add_column("Type")
 tbl.add_column("Count", justify="right")
 tbl.add_row("Repository", str(len(repos)))
 tbl.add_row("Capability", str(len(capabilities)))
 tbl.add_row("[bold]Total[/bold]", f"[bold]{len(repos) + len(capabilities)}[/bold]")
 console.print(tbl)

 # Edges
 tbl = Table(title="Edges")
 tbl.add_column("Predicate")
 tbl.add_column("Count", justify="right")
 tbl.add_row("delivered_by", str(len(delivered_by)))
 tbl.add_row("implements", str(len(implements)))
 tbl.add_row("integration", str(len(integration)))
 total = len(delivered_by) + len(implements) + len(integration)
 tbl.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
 console.print(tbl)

 if unregistered:
 console.print
 console.print(
 f"[yellow]Unregistered patterns ({len(unregistered)}) — "
 f"implements edges skipped:[/yellow]"
 )
 for p in unregistered:
 console.print(f" - {p}")

 if verbose:
 console.print
 console.print("[bold]Repository Entities:[/bold]")
 for r in repos:
 meta = r["metadata"]
 console.print(
 f" {r['id']} — {meta['role']} "
 f"({len(meta['delivers_capabilities'])} capabilities)"
 )

 console.print
 console.print("[bold]Capability Entities:[/bold]")
 for c in capabilities:
 meta = c["metadata"]
 console.print(
 f" {c['id']} [{meta['domain_classification']}] — "
 f"{c['title']} "
 f"(patterns: {', '.join(meta['implements_patterns'])})"
 )

 console.print
 console.print("[bold]Integration Edges:[/bold]")
 for e in integration:
 m = e["metadata"]
 console.print(
 f" {e['src_id']} -> {e['dst_id']} "
 f"({m['integration_pattern']}, {m['direction']})"
 )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main -> int:
 parser = argparse.ArgumentParser(
 description="Ingest architecture layer (repos, capabilities, integration edges)"
 )
 parser.add_argument(
 "--dry-run", action="store_true",
 help="Parse and show what would be created, without writing to DB",
 )
 parser.add_argument(
 "--skip-neo4j", action="store_true",
 help="Skip Neo4j graph materialization",
 )
 parser.add_argument(
 "--verify", action="store_true",
 help="Run test queries after ingestion",
 )
 parser.add_argument(
 "-v", "--verbose", action="store_true",
 help="Show detailed output",
 )
 args = parser.parse_args

 console.print
 console.print("[bold]Architecture Layer Ingestion[/bold]")
 console.print("=" * 60)

 # ------------------------------------------------------------------
 # 1. Validate source files
 # ------------------------------------------------------------------
 if not REPOS_YAML.exists:
 console.print(f"[red]Source not found: {REPOS_YAML}[/red]")
 return 1
 if not STRATEGIC_DDD_MD.exists:
 console.print(f"[red]Source not found: {STRATEGIC_DDD_MD}[/red]")
 return 1

 console.print(f"Sources: {REPOS_YAML.name}, {STRATEGIC_DDD_MD.name}")

 # ------------------------------------------------------------------
 # 2. Parse sources
 # ------------------------------------------------------------------
 console.print("Parsing sources...")

 # Parse capabilities first (need repo→capability map for repo metadata)
 capabilities = parse_capabilities(STRATEGIC_DDD_MD)
 repo_cap_map = parse_repo_capability_map(STRATEGIC_DDD_MD)

 # Parse repos and inject delivers_capabilities from STRATEGIC_DDD.md
 repos = parse_repos(REPOS_YAML)
 for repo in repos:
 repo["metadata"]["delivers_capabilities"] = repo_cap_map.get(repo["id"], [])
 # Remove internal tracking field
 repo.pop("_raw", None)

 # Build edges
 delivered_by_edges = build_delivered_by_edges(capabilities)
 integration_edges = parse_integration_edges(STRATEGIC_DDD_MD)

 # For implements edges, check which patterns exist (need DB for live run)
 if args.dry_run:
 # In dry-run, assume seed patterns only
 seed_patterns = {"ddd", "skos", "prov-o", "dublin-core", "dam"}
 implements_edges, unregistered = build_implements_edges(
 capabilities, seed_patterns
 )
 else:
 conn = get_db_connection
 conn.autocommit = False
 cursor = conn.cursor
 registered = get_registered_patterns(cursor)
 conn.commit # clear transaction state from SELECT
 implements_edges, unregistered = build_implements_edges(
 capabilities, registered
 )

 console.print(
 f"Parsed: {len(repos)} repos, {len(capabilities)} capabilities, "
 f"{len(delivered_by_edges) + len(implements_edges) + len(integration_edges)} edges"
 )

 # ------------------------------------------------------------------
 # 2b. Derive lifecycle_stage from edge coverage (ADR-0011)
 # ------------------------------------------------------------------
 derive_lifecycle_stages(
 capabilities, repos, implements_edges, delivered_by_edges
 )

 # Count capabilities by lifecycle stage
 from collections import Counter
 cap_stages = Counter(c["metadata"].get("lifecycle_stage", "draft") for c in capabilities)
 stage_parts = [f"{count} {stage}" for stage, count in sorted(cap_stages.items)]
 console.print(f"Capability lifecycle: {', '.join(stage_parts)}")

 repo_stages = Counter(r["metadata"].get("lifecycle_stage", "active") for r in repos)
 stage_parts = [f"{count} {stage}" for stage, count in sorted(repo_stages.items)]
 console.print(f"Repo lifecycle: {', '.join(stage_parts)}")

 # ------------------------------------------------------------------
 # 3. Dry run — just print
 # ------------------------------------------------------------------
 if args.dry_run:
 print_dry_run(
 repos, capabilities,
 delivered_by_edges, implements_edges, integration_edges,
 unregistered, args.verbose,
 )
 return 0

 # ------------------------------------------------------------------
 # 4. Ingest to PostgreSQL
 # ------------------------------------------------------------------
 console.print
 console.print("Ingesting to PostgreSQL...")

 try:
 # Upsert repository entities
 repo_ok = 0
 for repo in repos:
 if upsert_entity(repo, cursor):
 repo_ok += 1
 console.print(f" Repositories: {repo_ok}/{len(repos)}")

 # Upsert capability entities
 cap_ok = 0
 for cap in capabilities:
 if upsert_entity(cap, cursor):
 cap_ok += 1
 console.print(f" Capabilities: {cap_ok}/{len(capabilities)}")

 # Upsert delivered_by edges
 db_ok = 0
 for edge in delivered_by_edges:
 if upsert_edge(edge, cursor):
 db_ok += 1
 console.print(f" delivered_by edges: {db_ok}/{len(delivered_by_edges)}")

 # Upsert implements edges
 impl_ok = 0
 for edge in implements_edges:
 if upsert_edge(edge, cursor):
 impl_ok += 1
 console.print(f" implements edges: {impl_ok}/{len(implements_edges)}")

 if unregistered:
 console.print(
 f" [yellow]Skipped {len(unregistered)} unregistered patterns: "
 f"{', '.join(unregistered)}[/yellow]"
 )

 # Upsert integration edges
 intg_ok = 0
 for edge in integration_edges:
 if upsert_edge(edge, cursor):
 intg_ok += 1
 console.print(f" integration edges: {intg_ok}/{len(integration_edges)}")

 conn.commit
 console.print("[green]PostgreSQL commit successful[/green]")

 except Exception as e:
 conn.rollback
 console.print(f"[red]Transaction rolled back: {e}[/red]")
 return 1

 # ------------------------------------------------------------------
 # 5. Neo4j materialization
 # ------------------------------------------------------------------
 if not args.skip_neo4j:
 console.print
 console.print("Materializing to Neo4j...")
 counts = materialize_neo4j(
 repos, capabilities,
 delivered_by_edges, implements_edges, integration_edges,
 args.verbose,
 )
 console.print(
 f" Neo4j: {counts['nodes']} nodes, "
 f"{counts['relationships']} relationships"
 )

 # ------------------------------------------------------------------
 # 6. Verification
 # ------------------------------------------------------------------
 if args.verify:
 run_verification(conn)

 # ------------------------------------------------------------------
 # Summary
 # ------------------------------------------------------------------
 console.print
 total_entities = len(repos) + len(capabilities)
 total_edges = len(delivered_by_edges) + len(implements_edges) + len(integration_edges)
 console.print(f"[bold green]Done:[/bold green] {total_entities} entities, {total_edges} edges")
 console.print

 conn.close
 return 0


if __name__ == "__main__":
 sys.exit(main)
