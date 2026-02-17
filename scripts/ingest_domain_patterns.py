#!/usr/bin/env python3
"""
Domain pattern ingestion for Project SemOps (Phase B of ADR-0005).

Ingests patterns from the DX hub schemas/pattern_v1.yaml into the pattern table,
creates pattern_edge relationships (SKOS hierarchy), ingests domain pattern
markdown files as content entities, and materializes to Neo4j.

Usage:
    python scripts/ingest_domain_patterns.py --dry-run     # Parse only, no DB
    python scripts/ingest_domain_patterns.py               # Full ingestion
    python scripts/ingest_domain_patterns.py --verify      # Ingest + test queries
    python scripts/ingest_domain_patterns.py --skip-neo4j  # Skip Neo4j sync
    python scripts/ingest_domain_patterns.py --cleanup          # Upsert + remove stale rows
    python scripts/ingest_domain_patterns.py --patterns-only
    python scripts/ingest_domain_patterns.py --docs-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

import psycopg
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DX_HUB_PATH = Path(os.environ.get("DX_HUB_PATH", "../semops-dx-orchestrator"))
PATTERN_REGISTRY = DX_HUB_PATH / "schemas" / "pattern_v1.yaml"
DOMAIN_PATTERNS_DIR = DX_HUB_PATH / "docs" / "domain-patterns"
SKIP_FILES = {"README.md", "_TEMPLATE.md"}

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection

NEO4J_URL = os.environ.get("NEO4J_URL", "http://localhost:7474")


# ---------------------------------------------------------------------------
# Neo4j utilities (same pattern as ingest_architecture.py)
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
# Registry loading
# ---------------------------------------------------------------------------
def load_pattern_registry() -> list[dict]:
    """Load patterns from pattern_v1.yaml."""
    with open(PATTERN_REGISTRY) as f:
        data = yaml.safe_load(f)
    return data.get("patterns", [])


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------
def extract_title(content: str, filename: str) -> str:
    """Extract H1 title from markdown, fallback to filename."""
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return filename.replace("-", " ").replace("_", " ").title()


def extract_description(content: str) -> Optional[str]:
    """Extract first blockquote or paragraph after title as description."""
    bq_match = re.search(r"^>\s+(.+)$", content, re.MULTILINE)
    if bq_match:
        desc = bq_match.group(1).strip()
        if len(desc) > 20:
            return desc[:500]

    lines = content.split("\n")
    collecting = False
    paragraph = []
    for line in lines:
        if line.startswith("# "):
            collecting = True
            continue
        if collecting:
            stripped = line.strip()
            if stripped and not stripped.startswith(">") and not stripped.startswith("---"):
                paragraph.append(stripped)
            elif paragraph:
                break
    if paragraph:
        return " ".join(paragraph)[:500]
    return None


def map_doc_to_pattern(patterns: list[dict]) -> dict[str, str]:
    """Build mapping from doc filename to pattern ID."""
    doc_to_pattern = {}
    for p in patterns:
        doc = p.get("documentation", {})
        primary = doc.get("primary", "")
        if "domain-patterns/" in primary:
            filename = primary.split("domain-patterns/")[-1]
            doc_to_pattern[filename] = p["id"]
        for related in doc.get("related", []):
            if "domain-patterns/" in related:
                filename = related.split("domain-patterns/")[-1]
                if filename not in doc_to_pattern:
                    doc_to_pattern[filename] = p["id"]
    return doc_to_pattern


# ---------------------------------------------------------------------------
# Step 1: Pattern registry → pattern table
# ---------------------------------------------------------------------------
def ingest_patterns(conn: Optional[psycopg.Connection], patterns: list[dict], dry_run: bool = False) -> int:
    """Upsert patterns from registry into pattern table."""
    count = 0
    cur = conn.cursor() if conn else None

    try:
        for p in patterns:
            pattern_id = p["id"]
            name = p["name"]
            provenance = p.get("provenance", "1p")

            source = p.get("source")
            if source and isinstance(source, dict) and source.get("org"):
                definition = f"{name} ({source['org']})"
            else:
                definition = name

            metadata = {
                "$schema": "pattern_registry_v1",
                "pattern_type": p.get("pattern_type", "domain"),
                "implementations": p.get("implementations", []),
                "documentation": p.get("documentation", {}),
            }
            if source and isinstance(source, dict):
                metadata["source"] = {k: v for k, v in source.items() if v}

            print(f"  {'[DRY]' if dry_run else '  ✓'} pattern: {pattern_id} ({provenance})")

            if cur:
                cur.execute(
                    """
                    INSERT INTO pattern (id, preferred_label, definition, provenance, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        preferred_label = EXCLUDED.preferred_label,
                        definition = EXCLUDED.definition,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                    """,
                    (pattern_id, name, definition, provenance, json.dumps(metadata)),
                )
            count += 1
    finally:
        if cur:
            cur.close()

    if conn:
        conn.commit()
    return count


# ---------------------------------------------------------------------------
# Step 2: Pattern edges (SKOS hierarchy)
# ---------------------------------------------------------------------------
def create_pattern_edges(conn: Optional[psycopg.Connection], patterns: list[dict], dry_run: bool = False) -> int:
    """Create pattern_edge relationships from derives_from."""
    count = 0
    pattern_ids = {p["id"] for p in patterns}
    cur = conn.cursor() if conn else None

    try:
        for p in patterns:
            derives_from = p.get("derives_from", [])
            if not derives_from:
                continue

            for parent_id in derives_from:
                if parent_id not in pattern_ids:
                    print(f"  ⚠ skipping edge {p['id']} -> {parent_id} (unknown target)")
                    continue

                predicate = "extends" if p.get("provenance") == "1p" else "adopts"

                print(f"  {'[DRY]' if dry_run else '  ✓'} edge: {p['id']} --{predicate}--> {parent_id}")

                if cur:
                    cur.execute(
                        """
                        INSERT INTO pattern_edge (src_id, dst_id, predicate, metadata)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (src_id, dst_id, predicate) DO NOTHING
                        """,
                        (p["id"], parent_id, predicate, json.dumps({"source": "pattern_v1.yaml"})),
                    )
                count += 1
    finally:
        if cur:
            cur.close()

    if conn:
        conn.commit()
    return count


# ---------------------------------------------------------------------------
# Step 3: Domain pattern docs → content entities
# ---------------------------------------------------------------------------
def ingest_doc_entities(
    conn: Optional[psycopg.Connection],
    doc_to_pattern: dict[str, str],
    dry_run: bool = False,
) -> int:
    """Ingest domain pattern markdown files as content entities."""
    count = 0

    if not DOMAIN_PATTERNS_DIR.exists():
        print(f"  ⚠ Domain patterns directory not found: {DOMAIN_PATTERNS_DIR}")
        return 0

    md_files = sorted(DOMAIN_PATTERNS_DIR.glob("*.md"))
    cur = conn.cursor() if conn else None

    try:
        for md_file in md_files:
            if md_file.name in SKIP_FILES:
                continue

            content = md_file.read_text(encoding="utf-8")
            title = extract_title(content, md_file.stem)
            description = extract_description(content)

            entity_id = f"dp-{md_file.stem}"
            pattern_id = doc_to_pattern.get(md_file.name)

            # Detect provenance from content
            provenance = "1p"
            content_lower = content.lower()
            if any(kw in content_lower for kw in ["3p", "w3c", "industry", "external standard"]):
                if re.search(r"provenance.*3p|3p.*standard", content_lower):
                    provenance = "3p"

            stat = md_file.stat()
            filespec = {
                "$schema": "filespec_v1",
                "filename": md_file.name,
                "extension": ".md",
                "size_bytes": stat.st_size,
                "mime_type": "text/markdown",
                "storage_path": f"semops-dx-orchestrator/docs/domain-patterns/{md_file.name}",
                "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
            }

            word_count = len(re.findall(r"\w+", content))
            metadata = {
                "$schema": "content_metadata_v1",
                "content_type": "domain-pattern",
                "corpus": "core_kb",
                "lifecycle_stage": "active",
                "word_count": word_count,
                "format": "markdown",
                "description": description,
                "source_repo": "semops-dx-orchestrator",
            }

            attribution = {
                "$schema": "attribution_v1",
                "provenance": provenance,
                "ingested_by": "ingest_domain_patterns.py",
                "ingested_at": datetime.now(UTC).isoformat(),
            }

            status = "[DRY]" if dry_run else "  ✓"
            pattern_info = f" → pattern:{pattern_id}" if pattern_id else ""
            print(f"  {status} entity: {entity_id} | {title[:50]}{pattern_info}")

            if cur:
                cur.execute(
                    """
                    INSERT INTO entity (
                        id, entity_type, asset_type, title, primary_pattern_id,
                        filespec, attribution, metadata
                    ) VALUES (%s, 'content', %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        primary_pattern_id = EXCLUDED.primary_pattern_id,
                        filespec = EXCLUDED.filespec,
                        attribution = EXCLUDED.attribution,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                    """,
                    (
                        entity_id,
                        "file",
                        title,
                        pattern_id,
                        json.dumps(filespec),
                        json.dumps(attribution),
                        json.dumps(metadata),
                    ),
                )
            count += 1
    finally:
        if cur:
            cur.close()

    if conn:
        conn.commit()
    return count


# ---------------------------------------------------------------------------
# Step 4: Neo4j materialization
# ---------------------------------------------------------------------------
def materialize_neo4j(
    patterns: list[dict],
    pattern_edges: list[tuple[str, str, str]],
) -> dict[str, int]:
    """Materialize Pattern nodes and SKOS edges to Neo4j."""
    counts = {"nodes": 0, "relationships": 0}

    health = run_cypher("RETURN 1")
    if health is None:
        print(f"  ⚠ Cannot connect to Neo4j at {NEO4J_URL} — skipping")
        return counts

    # Constraint
    run_cypher(
        "CREATE CONSTRAINT pattern_id IF NOT EXISTS "
        "FOR (p:Pattern) REQUIRE p.id IS UNIQUE"
    )

    # Pattern nodes
    for p in patterns:
        cypher = (
            f"MERGE (p:Pattern {{id: '{neo4j_escape(p['id'])}'}}) "
            f"SET p.name = '{neo4j_escape(p['name'])}', "
            f"p.provenance = '{neo4j_escape(p.get('provenance', '1p'))}', "
            f"p.pattern_type = '{neo4j_escape(p.get('pattern_type', 'domain'))}'"
        )
        run_cypher(cypher)
        counts["nodes"] += 1

    # SKOS edges (extends/adopts)
    for src_id, dst_id, predicate in pattern_edges:
        rel_type = predicate.upper()
        cypher = (
            f"MATCH (s:Pattern {{id: '{neo4j_escape(src_id)}'}}) "
            f"MATCH (t:Pattern {{id: '{neo4j_escape(dst_id)}'}}) "
            f"MERGE (s)-[:{rel_type}]->(t)"
        )
        run_cypher(cypher)
        counts["relationships"] += 1

    return counts


# ---------------------------------------------------------------------------
# Cleanup: remove rows no longer in source
# ---------------------------------------------------------------------------
def cleanup_stale_rows(
    conn: psycopg.Connection,
    patterns: list[dict],
    doc_to_pattern: dict[str, str],
    dry_run: bool = False,
    patterns_only: bool = False,
    docs_only: bool = False,
) -> dict[str, int]:
    """Delete DB rows that no longer exist in the source YAML/files.

    Order: entities → edges → patterns (FK safety).
    Each delete is scoped by metadata markers to avoid touching rows from other scripts.
    Requires a DB connection even in dry-run mode (reads current state to diff).
    """
    deleted = {"entities": 0, "edges": 0, "patterns": 0}
    cur = conn.cursor()

    try:
        # 1. Entities: content_type='domain-pattern' not in current doc set
        if not patterns_only:
            current_entity_ids = set()
            if DOMAIN_PATTERNS_DIR.exists():
                for md_file in DOMAIN_PATTERNS_DIR.glob("*.md"):
                    if md_file.name not in SKIP_FILES:
                        current_entity_ids.add(f"dp-{md_file.stem}")

            cur.execute(
                "SELECT id FROM entity "
                "WHERE metadata->>'content_type' = 'domain-pattern'"
            )
            db_entity_ids = {row[0] for row in cur.fetchall()}

            stale_entities = db_entity_ids - current_entity_ids
            for eid in sorted(stale_entities):
                print(f"  {'[DRY]' if dry_run else '  ✗'} delete entity: {eid}")
                if not dry_run:
                    cur.execute("DELETE FROM entity WHERE id = %s", (eid,))
                deleted["entities"] += 1

        # 2. Pattern edges: source='pattern_v1.yaml' not in current derives_from
        if not docs_only:
            current_edges = set()
            pattern_ids = {p["id"] for p in patterns}
            for p in patterns:
                for parent_id in p.get("derives_from", []):
                    if parent_id in pattern_ids:
                        predicate = "extends" if p.get("provenance") == "1p" else "adopts"
                        current_edges.add((p["id"], parent_id, predicate))

            cur.execute(
                "SELECT src_id, dst_id, predicate FROM pattern_edge "
                "WHERE metadata->>'source' = 'pattern_v1.yaml'"
            )
            db_edges = {(row[0], row[1], row[2]) for row in cur.fetchall()}

            stale_edges = db_edges - current_edges
            for src, dst, pred in sorted(stale_edges):
                print(f"  {'[DRY]' if dry_run else '  ✗'} delete edge: {src} --{pred}--> {dst}")
                if not dry_run:
                    cur.execute(
                        "DELETE FROM pattern_edge "
                        "WHERE src_id = %s AND dst_id = %s AND predicate = %s",
                        (src, dst, pred),
                    )
                deleted["edges"] += 1

        # 3. Patterns: schema='pattern_registry_v1' not in current YAML
        if not docs_only:
            current_pattern_ids = {p["id"] for p in patterns}

            cur.execute(
                "SELECT id FROM pattern "
                "WHERE metadata->>'$schema' = 'pattern_registry_v1'"
            )
            db_pattern_ids = {row[0] for row in cur.fetchall()}

            stale_patterns = db_pattern_ids - current_pattern_ids
            for pid in sorted(stale_patterns):
                print(f"  {'[DRY]' if dry_run else '  ✗'} delete pattern: {pid}")
                if not dry_run:
                    cur.execute("DELETE FROM pattern WHERE id = %s", (pid,))
                deleted["patterns"] += 1

    finally:
        cur.close()

    if not dry_run:
        conn.commit()
    return deleted


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def run_verification(conn: psycopg.Connection) -> None:
    """Run ADR-0005 test queries."""
    cursor = conn.cursor()
    print()
    print("=" * 60)
    print("Verification Queries")
    print("=" * 60)

    # Pattern coverage
    print("\nPattern Coverage:")
    cursor.execute("""
        SELECT p.id, p.preferred_label, p.provenance,
               COUNT(DISTINCT e.id) AS entity_count
        FROM pattern p
        LEFT JOIN entity e ON e.primary_pattern_id = p.id
        GROUP BY p.id, p.preferred_label, p.provenance
        ORDER BY entity_count DESC, p.id
    """)
    for row in cursor.fetchall():
        marker = "✓" if row[3] > 0 else "○"
        print(f"  {marker} {row[0]:30s} ({row[2]}) — {row[3]} docs")

    # Unmapped docs
    print("\nUnmapped domain pattern docs (no primary_pattern_id):")
    cursor.execute("""
        SELECT id, title FROM entity
        WHERE entity_type = 'content'
          AND metadata->>'content_type' = 'domain-pattern'
          AND primary_pattern_id IS NULL
        ORDER BY id
    """)
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  ○ {row[0]} — {row[1]}")
    else:
        print("  (none — all docs mapped)")

    # ADR-0005 Test Query 2: "What patterns apply to blog post creation?"
    print("\nADR-0005 Query 2: What patterns apply to blog post creation?")
    cursor.execute("""
        SELECT p.id, p.preferred_label, c.id AS capability
        FROM pattern p
        JOIN edge e ON e.dst_type = 'pattern' AND e.dst_id = p.id AND e.predicate = 'implements'
        JOIN entity c ON e.src_type = 'entity' AND e.src_id = c.id AND c.entity_type = 'capability'
        WHERE c.id IN ('content-pipeline', 'content-management', 'publishing-pipeline')
        ORDER BY p.id
    """)
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  ✓ {row[0]:30s} (via {row[2]})")
    else:
        print("  (no results — capabilities may not have implements edges yet)")

    # Summary counts
    print("\nSummary:")
    cursor.execute("SELECT count(*) FROM pattern")
    print(f"  Patterns: {cursor.fetchone()[0]}")
    cursor.execute("SELECT count(*) FROM pattern_edge")
    print(f"  Pattern edges: {cursor.fetchone()[0]}")
    cursor.execute("SELECT count(*) FROM entity WHERE entity_type = 'content' AND metadata->>'content_type' = 'domain-pattern'")
    print(f"  Domain pattern entities: {cursor.fetchone()[0]}")
    cursor.execute("SELECT count(*) FROM entity WHERE entity_type = 'content' AND primary_pattern_id IS NOT NULL")
    print(f"  Entities with pattern link: {cursor.fetchone()[0]}")


def run_governance_audit(conn: psycopg.Connection) -> None:
    """Layer 2 governance audit: cross-check coverage views for drift.

    Per ADR-0011 governance model, ingestion time is an audit opportunity.
    This checks for mismatches between declared architecture (edges) and
    documentation coverage (primary_pattern_id).

    Findings are reported but not auto-fixed — human reviews and acts.
    """
    cursor = conn.cursor()
    print()
    print("=" * 60)
    print("Governance Audit (Layer 2)")
    print("=" * 60)

    findings = []

    # 1. Patterns with capabilities but no documentation
    cursor.execute("""
        SELECT pattern_id, preferred_label, capability_count, content_count
        FROM pattern_coverage
        WHERE capability_count > 0 AND content_count = 0
        ORDER BY capability_count DESC
    """)
    rows = cursor.fetchall()
    if rows:
        print(f"\n  [HIGH] {len(rows)} patterns have capabilities but no documentation:")
        for r in rows:
            print(f"    {r[0]:40s} cap={r[2]} docs=0  | {r[1]}")
            findings.append(("HIGH", f"{r[0]}: has {r[2]} capabilities but no dp-* doc"))

    # 2. Patterns with documentation but no capabilities
    cursor.execute("""
        SELECT pattern_id, preferred_label, content_count, capability_count
        FROM pattern_coverage
        WHERE content_count > 0 AND capability_count = 0
        ORDER BY content_count DESC
    """)
    rows = cursor.fetchall()
    if rows:
        print(f"\n  [INFO] {len(rows)} patterns have documentation but no capabilities:")
        for r in rows:
            print(f"    {r[0]:40s} docs={r[2]} cap=0  | {r[1]}")
            findings.append(("INFO", f"{r[0]}: has {r[2]} docs but no implementing capability"))

    # 3. Capabilities with no pattern justification (missing implements edges)
    cursor.execute("""
        SELECT capability_id, capability_name, pattern_count, repo_count
        FROM capability_coverage
        WHERE pattern_count = 0
        ORDER BY capability_name
    """)
    rows = cursor.fetchall()
    if rows:
        print(f"\n  [HIGH] {len(rows)} capabilities have no pattern justification:")
        for r in rows:
            print(f"    {r[0]:30s} patterns=0 repos={r[3]}  | {r[1]}")
            findings.append(("HIGH", f"{r[0]}: no implements edges (WHY missing)"))

    # 4. Content entities with NULL lifecycle_stage
    cursor.execute("""
        SELECT COUNT(*) FROM entity
        WHERE entity_type = 'content'
          AND (metadata->>'lifecycle_stage' IS NULL OR metadata->>'lifecycle_stage' = '')
    """)
    null_count = cursor.fetchone()[0]
    if null_count:
        print(f"\n  [MEDIUM] {null_count} content entities have no lifecycle_stage in metadata")
        findings.append(("MEDIUM", f"{null_count} content entities missing lifecycle_stage"))

    # 5. Architecture entities with NULL lifecycle_stage
    cursor.execute("""
        SELECT id, entity_type FROM entity
        WHERE entity_type IN ('capability', 'repository')
          AND (metadata->>'lifecycle_stage' IS NULL OR metadata->>'lifecycle_stage' = '')
        ORDER BY entity_type, id
    """)
    rows = cursor.fetchall()
    if rows:
        print(f"\n  [HIGH] {len(rows)} architecture entities have no lifecycle_stage:")
        for r in rows:
            print(f"    {r[1]:12s} {r[0]}")
            findings.append(("HIGH", f"{r[0]} ({r[1]}): no lifecycle_stage"))

    # Summary
    high = sum(1 for f in findings if f[0] == "HIGH")
    medium = sum(1 for f in findings if f[0] == "MEDIUM")
    info = sum(1 for f in findings if f[0] == "INFO")
    print(f"\n  Audit complete: {high} HIGH, {medium} MEDIUM, {info} INFO findings")
    if high == 0 and medium == 0:
        print("  All governance checks passed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Ingest domain patterns (Phase B of ADR-0005)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--patterns-only", action="store_true", help="Only ingest pattern registry")
    parser.add_argument("--docs-only", action="store_true", help="Only ingest doc entities")
    parser.add_argument("--skip-neo4j", action="store_true", help="Skip Neo4j materialization")
    parser.add_argument("--cleanup", action="store_true", help="Remove stale rows no longer in source")
    parser.add_argument("--verify", action="store_true", help="Run test queries after ingestion")
    parser.add_argument("--audit", action="store_true", help="Run governance audit (Layer 2 cross-check)")
    args = parser.parse_args()

    print("=" * 60)
    print("Phase B: Domain Pattern Ingestion")
    print("=" * 60)

    # Load registry
    if not PATTERN_REGISTRY.exists():
        print(f"Error: Pattern registry not found: {PATTERN_REGISTRY}")
        return 1

    patterns = load_pattern_registry()
    print(f"\nLoaded {len(patterns)} patterns from registry")

    doc_to_pattern = map_doc_to_pattern(patterns)
    print(f"Mapped {len(doc_to_pattern)} docs to patterns")

    if args.dry_run:
        print("\n*** DRY RUN — no database changes ***\n")

    conn = None
    if not args.dry_run:
        conn = get_db_connection()
        conn.autocommit = False

    # Track pattern edges for Neo4j
    neo4j_edges: list[tuple[str, str, str]] = []

    try:
        # Step 1: Patterns
        if not args.docs_only:
            print("\n--- Patterns ---")
            pattern_count = ingest_patterns(conn, patterns, dry_run=args.dry_run)
            print(f"\n  Patterns: {pattern_count}")

            print("\n--- Pattern Edges ---")
            edge_count = create_pattern_edges(conn, patterns, dry_run=args.dry_run)
            print(f"\n  Edges: {edge_count}")

            # Collect edges for Neo4j
            pattern_ids = {p["id"] for p in patterns}
            for p in patterns:
                for parent_id in p.get("derives_from", []):
                    if parent_id in pattern_ids:
                        predicate = "extends" if p.get("provenance") == "1p" else "adopts"
                        neo4j_edges.append((p["id"], parent_id, predicate))

        # Step 2: Doc entities
        if not args.patterns_only:
            print("\n--- Domain Pattern Documents ---")
            entity_count = ingest_doc_entities(conn, doc_to_pattern, dry_run=args.dry_run)
            print(f"\n  Entities: {entity_count}")

        if conn and not args.dry_run:
            conn.commit()

        # Cleanup stale rows (needs DB connection even in dry-run for reads)
        if args.cleanup:
            print("\n--- Cleanup ---")
            cleanup_conn = conn
            if cleanup_conn is None:
                cleanup_conn = get_db_connection()
            cleaned = cleanup_stale_rows(
                cleanup_conn, patterns, doc_to_pattern,
                dry_run=args.dry_run,
                patterns_only=args.patterns_only,
                docs_only=args.docs_only,
            )
            if cleanup_conn is not conn:
                cleanup_conn.close()
            total = sum(cleaned.values())
            if total:
                print(f"\n  Removed: {cleaned['entities']} entities, "
                      f"{cleaned['edges']} edges, {cleaned['patterns']} patterns")
            else:
                print("\n  Nothing to clean up")

        # Step 3: Neo4j
        if not args.dry_run and not args.skip_neo4j and not args.docs_only:
            print("\n--- Neo4j Materialization ---")
            counts = materialize_neo4j(patterns, neo4j_edges)
            print(f"\n  Neo4j: {counts['nodes']} nodes, {counts['relationships']} relationships")

        # Step 4: Verification
        if args.verify and conn:
            run_verification(conn)

        # Step 5: Governance audit (Layer 2 cross-check per ADR-0011)
        if args.audit and conn:
            run_governance_audit(conn)

        print(f"\n{'DRY RUN complete' if args.dry_run else 'Ingestion complete'}")
        return 0

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
