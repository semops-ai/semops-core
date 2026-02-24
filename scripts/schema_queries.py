"""
Structured schema queries for the DDD architecture layer.

All query functions accept a database connection and return plain dicts.
Consumers (MCP, API, CLI) handle error handling and response formatting.

These are deterministic SQL lookups against the ACL (Anti-Corruption Layer) —
the authoritative source of truth for architectural queries. No embeddings
needed except for search_patterns.

Used by:
 - api/mcp_server.py (MCP tools for Claude Code agents)
 - api/query.py (FastAPI endpoints — future)
"""

from __future__ import annotations

import psycopg

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_pattern_where(
 *,
 provenance: list[str] | None = None,
) -> tuple[str, list]:
 """Build WHERE clause and params for pattern table queries."""
 conditions = ["TRUE"]
 params: list = []

 if provenance:
 placeholders = ", ".join(["%s"] * len(provenance))
 conditions.append(f"p.provenance IN ({placeholders})")
 params.extend(provenance)

 return " AND ".join(conditions), params


def _build_capability_where(
 *,
 domain_classification: list[str] | None = None,
) -> tuple[str, list]:
 """Build WHERE clause and params for capability_coverage view queries."""
 conditions = ["TRUE"]
 params: list = []

 if domain_classification:
 placeholders = ", ".join(["%s"] * len(domain_classification))
 conditions.append(f"cc.domain_classification IN ({placeholders})")
 params.extend(domain_classification)

 return " AND ".join(conditions), params


# ---------------------------------------------------------------------------
# Pattern queries
# ---------------------------------------------------------------------------


def list_patterns(
 conn: psycopg.Connection,
 *,
 provenance: list[str] | None = None,
 include_coverage: bool = True,
) -> list[dict]:
 """List patterns with optional provenance filter and coverage stats.

 Returns dicts with: id, preferred_label, definition, alt_labels,
 provenance, and optionally coverage (content_count, capability_count,
 repo_count).
 """
 where_clause, params = _build_pattern_where(provenance=provenance)

 if include_coverage:
 sql = f"""
 SELECT
 p.id, p.preferred_label, p.definition, p.alt_labels,
 p.provenance,
 COALESCE(pc.content_count, 0) AS content_count,
 COALESCE(pc.capability_count, 0) AS capability_count,
 COALESCE(pc.repo_count, 0) AS repo_count
 FROM pattern p
 LEFT JOIN pattern_coverage pc ON p.id = pc.pattern_id
 WHERE {where_clause}
 ORDER BY p.preferred_label
 """
 else:
 sql = f"""
 SELECT
 p.id, p.preferred_label, p.definition, p.alt_labels,
 p.provenance
 FROM pattern p
 WHERE {where_clause}
 ORDER BY p.preferred_label
 """

 cursor = conn.cursor
 cursor.execute(sql, params)

 if include_coverage:
 return [
 {
 "id": row[0],
 "preferred_label": row[1],
 "definition": row[2],
 "alt_labels": row[3] or [],
 "provenance": row[4],
 "coverage": {
 "content_count": row[5],
 "capability_count": row[6],
 "repo_count": row[7],
 },
 }
 for row in cursor.fetchall
 ]
 else:
 return [
 {
 "id": row[0],
 "preferred_label": row[1],
 "definition": row[2],
 "alt_labels": row[3] or [],
 "provenance": row[4],
 }
 for row in cursor.fetchall
 ]


def get_pattern(
 conn: psycopg.Connection,
 pattern_id: str,
) -> dict | None:
 """Get a single pattern with its edges and coverage stats.

 Returns dict with: id, preferred_label, definition, alt_labels,
 provenance, edges (grouped by predicate), and coverage stats.
 Returns None if pattern not found.
 """
 cursor = conn.cursor

 # Base pattern + coverage
 cursor.execute(
 """
 SELECT
 p.id, p.preferred_label, p.definition, p.alt_labels,
 p.provenance,
 COALESCE(pc.content_count, 0),
 COALESCE(pc.capability_count, 0),
 COALESCE(pc.repo_count, 0)
 FROM pattern p
 LEFT JOIN pattern_coverage pc ON p.id = pc.pattern_id
 WHERE p.id = %s
 """,
 [pattern_id],
 )
 row = cursor.fetchone
 if not row:
 return None

 result = {
 "id": row[0],
 "preferred_label": row[1],
 "definition": row[2],
 "alt_labels": row[3] or [],
 "provenance": row[4],
 "coverage": {
 "content_count": row[5],
 "capability_count": row[6],
 "repo_count": row[7],
 },
 "edges": [],
 }

 # Pattern edges (both directions)
 cursor.execute(
 """
 SELECT
 pe.src_id, pe.dst_id, pe.predicate, pe.strength,
 CASE WHEN pe.src_id = %s THEN dst.preferred_label
 ELSE src.preferred_label END AS related_label
 FROM pattern_edge pe
 JOIN pattern src ON pe.src_id = src.id
 JOIN pattern dst ON pe.dst_id = dst.id
 WHERE pe.src_id = %s OR pe.dst_id = %s
 ORDER BY pe.predicate, related_label
 """,
 [pattern_id, pattern_id, pattern_id],
 )
 result["edges"] = [
 {
 "src_id": r[0],
 "dst_id": r[1],
 "predicate": r[2],
 "strength": float(r[3]) if r[3] is not None else 1.0,
 "related_label": r[4],
 }
 for r in cursor.fetchall
 ]

 return result


def search_patterns(
 conn: psycopg.Connection,
 query_embedding: list[float],
 *,
 limit: int = 10,
 provenance: list[str] | None = None,
) -> list[dict]:
 """Semantic search over pattern embeddings.

 Returns dicts with: id, preferred_label, definition, provenance,
 similarity, and coverage stats.
 """
 where_clause, where_params = _build_pattern_where(provenance=provenance)
 # Add embedding filter
 where_clause += " AND p.embedding IS NOT NULL"

 params: list = [query_embedding] + where_params + [query_embedding, limit]

 cursor = conn.cursor
 cursor.execute(
 f"""
 SELECT
 p.id, p.preferred_label, p.definition, p.provenance,
 1 - (p.embedding <=> %s::vector) AS similarity,
 COALESCE(pc.content_count, 0),
 COALESCE(pc.capability_count, 0),
 COALESCE(pc.repo_count, 0)
 FROM pattern p
 LEFT JOIN pattern_coverage pc ON p.id = pc.pattern_id
 WHERE {where_clause}
 ORDER BY p.embedding <=> %s::vector
 LIMIT %s
 """,
 params,
 )

 return [
 {
 "id": row[0],
 "preferred_label": row[1],
 "definition": row[2],
 "provenance": row[3],
 "similarity": round(row[4], 4),
 "coverage": {
 "content_count": row[5],
 "capability_count": row[6],
 "repo_count": row[7],
 },
 }
 for row in cursor.fetchall
 ]


# ---------------------------------------------------------------------------
# Capability queries
# ---------------------------------------------------------------------------


def list_capabilities(
 conn: psycopg.Connection,
 *,
 domain_classification: list[str] | None = None,
) -> list[dict]:
 """List capabilities with coherence stats from capability_coverage view.

 Returns dicts with: capability_id, capability_name, domain_classification,
 primary_pattern_id, primary_pattern_label, pattern_count, repo_count.
 """
 where_clause, params = _build_capability_where(
 domain_classification=domain_classification,
 )

 cursor = conn.cursor
 cursor.execute(
 f"""
 SELECT
 cc.capability_id, cc.capability_name, cc.domain_classification,
 cc.primary_pattern_id, cc.primary_pattern_label,
 cc.pattern_count, cc.repo_count
 FROM capability_coverage cc
 WHERE {where_clause}
 ORDER BY cc.capability_name
 """,
 params,
 )

 return [
 {
 "capability_id": row[0],
 "capability_name": row[1],
 "domain_classification": row[2],
 "primary_pattern_id": row[3],
 "primary_pattern_label": row[4],
 "pattern_count": row[5],
 "repo_count": row[6],
 }
 for row in cursor.fetchall
 ]


def get_capability_details(
 conn: psycopg.Connection,
 capability_id: str,
) -> dict | None:
 """Get a single capability with its patterns, repos, and integrations.

 Returns dict with: capability info, implemented patterns, delivering repos,
 and upstream/downstream integration edges for those repos.
 Returns None if capability not found.
 """
 cursor = conn.cursor

 # Base capability from capability_coverage view
 cursor.execute(
 """
 SELECT
 cc.capability_id, cc.capability_name, cc.domain_classification,
 cc.primary_pattern_id, cc.primary_pattern_label,
 cc.pattern_count, cc.repo_count
 FROM capability_coverage cc
 WHERE cc.capability_id = %s
 """,
 [capability_id],
 )
 row = cursor.fetchone
 if not row:
 return None

 result = {
 "capability_id": row[0],
 "capability_name": row[1],
 "domain_classification": row[2],
 "primary_pattern_id": row[3],
 "primary_pattern_label": row[4],
 "pattern_count": row[5],
 "repo_count": row[6],
 "patterns": [],
 "repos": [],
 "integrations": [],
 }

 # Patterns this capability implements (via edge table)
 cursor.execute(
 """
 SELECT e.dst_id, p.preferred_label, p.provenance, e.strength
 FROM edge e
 JOIN pattern p ON e.dst_id = p.id
 WHERE e.src_type = 'entity' AND e.src_id = %s
 AND e.dst_type = 'pattern' AND e.predicate = 'implements'
 ORDER BY p.preferred_label
 """,
 [capability_id],
 )
 result["patterns"] = [
 {
 "pattern_id": r[0],
 "preferred_label": r[1],
 "provenance": r[2],
 "strength": float(r[3]) if r[3] is not None else 1.0,
 }
 for r in cursor.fetchall
 ]

 # Repos that deliver this capability (via edge table)
 cursor.execute(
 """
 SELECT e.dst_id, repo.title, repo.metadata->>'role' AS repo_role
 FROM edge e
 JOIN entity repo ON e.dst_id = repo.id AND repo.entity_type = 'repository'
 WHERE e.src_type = 'entity' AND e.src_id = %s
 AND e.dst_type = 'entity' AND e.predicate = 'delivered_by'
 ORDER BY repo.title
 """,
 [capability_id],
 )
 repos = [{"repo_id": r[0], "repo_name": r[1], "repo_role": r[2]} for r in cursor.fetchall]
 result["repos"] = repos

 # Integration edges for those repos
 if repos:
 repo_ids = [r["repo_id"] for r in repos]
 placeholders = ", ".join(["%s"] * len(repo_ids))
 cursor.execute(
 f"""
 SELECT
 source_repo_id, source_repo_name,
 target_repo_id, target_repo_name,
 integration_pattern, shared_artifact, direction, rationale
 FROM integration_map
 WHERE source_repo_id IN ({placeholders})
 OR target_repo_id IN ({placeholders})
 ORDER BY source_repo_name, target_repo_name
 """,
 repo_ids + repo_ids,
 )
 result["integrations"] = [
 {
 "source_repo_id": r[0],
 "source_repo_name": r[1],
 "target_repo_id": r[2],
 "target_repo_name": r[3],
 "integration_pattern": r[4],
 "shared_artifact": r[5],
 "direction": r[6],
 "rationale": r[7],
 }
 for r in cursor.fetchall
 ]

 return result


# ---------------------------------------------------------------------------
# Repository queries
# ---------------------------------------------------------------------------


def list_repositories(
 conn: psycopg.Connection,
) -> list[dict]:
 """List repositories with their capability delivery counts.

 Returns dicts with: repo_id, repo_name, repo_role, capability_count.
 """
 cursor = conn.cursor
 cursor.execute(
 """
 SELECT
 repo.id AS repo_id,
 repo.title AS repo_name,
 repo.metadata->>'role' AS repo_role,
 COUNT(DISTINCT rc.capability_id) AS capability_count
 FROM entity repo
 LEFT JOIN repo_capabilities rc ON repo.id = rc.repo_id
 WHERE repo.entity_type = 'repository'
 GROUP BY repo.id, repo.title, repo.metadata->>'role'
 ORDER BY repo.title
 """
 )

 return [
 {
 "repo_id": row[0],
 "repo_name": row[1],
 "repo_role": row[2],
 "capability_count": row[3],
 }
 for row in cursor.fetchall
 ]


# ---------------------------------------------------------------------------
# Integration queries
# ---------------------------------------------------------------------------


def query_integration_map(
 conn: psycopg.Connection,
 *,
 source_repo: str | None = None,
 target_repo: str | None = None,
) -> list[dict]:
 """Query repo-to-repo integration relationships from integration_map view.

 Returns dicts with: source/target repo info, integration_pattern,
 shared_artifact, direction, rationale.
 """
 conditions = ["TRUE"]
 params: list = []

 if source_repo:
 conditions.append("source_repo_id = %s")
 params.append(source_repo)

 if target_repo:
 conditions.append("target_repo_id = %s")
 params.append(target_repo)

 where_clause = " AND ".join(conditions)

 cursor = conn.cursor
 cursor.execute(
 f"""
 SELECT
 source_repo_id, source_repo_name,
 target_repo_id, target_repo_name,
 integration_pattern, shared_artifact, direction, rationale
 FROM integration_map
 WHERE {where_clause}
 ORDER BY source_repo_name, target_repo_name
 """,
 params,
 )

 return [
 {
 "source_repo_id": row[0],
 "source_repo_name": row[1],
 "target_repo_id": row[2],
 "target_repo_name": row[3],
 "integration_pattern": row[4],
 "shared_artifact": row[5],
 "direction": row[6],
 "rationale": row[7],
 }
 for row in cursor.fetchall
 ]


# ---------------------------------------------------------------------------
# Fitness checks
# ---------------------------------------------------------------------------


def run_fitness_checks(
 conn: psycopg.Connection,
 *,
 severity: list[str] | None = None,
) -> list[dict]:
 """Execute schema fitness functions and return violations.

 Calls run_all_fitness_functions from fitness-functions.sql.
 Optionally filters by severity: CRITICAL, HIGH, MEDIUM, LOW.

 Returns dicts with: check_name, entity_id, issue, severity.
 """
 cursor = conn.cursor
 cursor.execute("SELECT * FROM run_all_fitness_functions")

 rows = cursor.fetchall

 results = [
 {
 "check_name": row[0],
 "entity_id": row[1],
 "issue": row[2],
 "severity": row[3],
 }
 for row in rows
 ]

 if severity:
 severity_upper = [s.upper for s in severity]
 results = [r for r in results if r["severity"] in severity_upper]

 return results
