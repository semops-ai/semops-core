"""
SemOps MCP Server — Corpus-aware knowledge base access for Claude Code agents.

Exposes semantic search and corpus listing as MCP tools so agents
in any repo can query the Project SemOps knowledge base.

Usage (stdio transport — Claude Code manages lifecycle):
 python -m api.mcp_server

Configuration in .mcp.json or ~/.claude.json:
 {
 "semops-kb": {
 "command": "python",
 "args": ["-m", "api.mcp_server"],
 "cwd": ""
 }
 }
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from openai import OpenAI

# Shared utilities (after sys.path setup)
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import schema_queries as _schema # noqa: E402
import search as _search # noqa: E402
from db_utils import get_db_connection, load_env # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_env

_openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
_conn = get_db_connection(autocommit=True)

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("semops-kb")


@mcp.tool
def search_knowledge_base(
 query: str,
 corpus: list[str] | None = None,
 content_type: list[str] | None = None,
 limit: int = 10,
) -> str:
 """Search the Project SemOps knowledge base using semantic similarity.

 Args:
 query: Natural language search query
 corpus: Filter by corpus
 (e.g. ["core_kb", "deployment", "published", "research_ai"])
 content_type: Filter by content type
 (e.g. ["concept", "pattern", "adr", "article", "architecture"])
 limit: Max results (default 10, max 50)

 Returns:
 JSON array of matching entities with similarity scores, titles,
 corpus, content_type, and filespec URIs.
 """
 limit = min(limit, 50)

 resp = _openai.embeddings.create(
 model=_search.EMBEDDING_MODEL,
 input=query,
 dimensions=_search.EMBEDDING_DIMENSIONS,
 )
 query_embedding = resp.data[0].embedding

 results = _search.search_entities(
 _conn,
 query_embedding,
 limit=limit,
 corpus=corpus,
 content_type=content_type,
 )

 return json.dumps(
 [
 {
 "id": r["id"],
 "title": r["title"],
 "corpus": r["corpus"],
 "content_type": r["content_type"],
 "summary": r["summary"],
 "similarity": r["similarity"],
 "uri": r["uri"],
 }
 for r in results
 ],
 indent=2,
 )


@mcp.tool
def search_chunks(
 query: str,
 corpus: list[str] | None = None,
 limit: int = 10,
) -> str:
 """Search document chunks (passages) in the knowledge base using semantic similarity.

 Returns passage-level results with heading hierarchy context, linked to parent entities.

 Args:
 query: Natural language search query
 corpus: Filter by corpus (e.g. ["core_kb", "deployment"])
 limit: Max results (default 10, max 50)

 Returns:
 JSON array of matching chunks with content, heading hierarchy,
 similarity, and entity_id.
 """
 limit = min(limit, 50)

 resp = _openai.embeddings.create(
 model=_search.EMBEDDING_MODEL,
 input=query,
 dimensions=_search.EMBEDDING_DIMENSIONS,
 )
 query_embedding = resp.data[0].embedding

 results = _search.search_chunks(
 _conn,
 query_embedding,
 limit=limit,
 corpus=corpus,
 content_max_chars=500,
 )

 return json.dumps(results, indent=2)


@mcp.tool
def list_corpora -> str:
 """List available corpora in the knowledge base with entity counts.

 Returns:
 JSON array of {corpus, count} objects.
 """
 return json.dumps(_search.list_corpora(_conn), indent=2)


# ---------------------------------------------------------------------------
# DDD Schema Query Tools (structured ACL lookups — no embeddings needed)
# ---------------------------------------------------------------------------


@mcp.tool
def list_patterns(
 provenance: list[str] | None = None,
 include_coverage: bool = True,
) -> str:
 """List registered patterns with optional provenance filter.

 Args:
 provenance: Filter by provenance
 (e.g. ["3p"] for third-party standards, ["1p"] for proprietary)
 include_coverage: Include usage statistics (content, capability,
 repo counts). Default True.

 Returns:
 JSON array of patterns with id, preferred_label, definition,
 provenance, and coverage statistics.
 """
 results = _schema.list_patterns(
 _conn,
 provenance=provenance,
 include_coverage=include_coverage,
 )
 return json.dumps(results, indent=2)


@mcp.tool
def get_pattern(pattern_id: str) -> str:
 """Get detailed information about a single pattern.

 Returns the pattern with its SKOS relationships (broader/narrower/related),
 adoption edges (adopts/extends/modifies), and coverage statistics.

 Args:
 pattern_id: Pattern identifier (e.g. "ddd", "skos", "semantic-coherence")

 Returns:
 JSON object with pattern details, edges, and coverage.
 Returns null if not found.
 """
 result = _schema.get_pattern(_conn, pattern_id)
 return json.dumps(result, indent=2)


@mcp.tool
def search_patterns(
 query: str,
 provenance: list[str] | None = None,
 limit: int = 10,
) -> str:
 """Search patterns using semantic similarity on pattern definitions.

 Unlike search_knowledge_base (which searches content entities), this
 searches the pattern registry directly.

 Args:
 query: Natural language search query
 provenance: Filter by provenance (e.g. ["3p"])
 limit: Max results (default 10, max 50)

 Returns:
 JSON array of patterns with similarity scores and coverage.
 """
 limit = min(limit, 50)

 resp = _openai.embeddings.create(
 model=_search.EMBEDDING_MODEL,
 input=query,
 dimensions=_search.EMBEDDING_DIMENSIONS,
 )
 query_embedding = resp.data[0].embedding

 results = _schema.search_patterns(
 _conn,
 query_embedding,
 limit=limit,
 provenance=provenance,
 )
 return json.dumps(results, indent=2)


@mcp.tool
def list_capabilities(
 domain_classification: list[str] | None = None,
) -> str:
 """List system capabilities with coherence signals.

 Shows each capability with its pattern count and repo delivery count
 from the capability_coverage view (ADR-0009 coherence signal).

 Args:
 domain_classification: Filter by domain
 (e.g. ["core", "supporting", "generic"])

 Returns:
 JSON array of capabilities with pattern/repo counts.
 """
 results = _schema.list_capabilities(
 _conn,
 domain_classification=domain_classification,
 )
 return json.dumps(results, indent=2)


@mcp.tool
def get_capability_impact(capability_id: str) -> str:
 """Get full impact analysis for a capability.

 Answers: "What patterns does this implement, which repos deliver it,
 and what are their integration relationships?"

 Args:
 capability_id: Capability entity ID
 (e.g. "ingestion-pipeline", "domain-data-model")

 Returns:
 JSON object with patterns, repos, and integration dependencies.
 Returns null if capability not found.
 """
 result = _schema.get_capability_details(_conn, capability_id)
 return json.dumps(result, indent=2)


@mcp.tool
def query_integration_map(
 source_repo: str | None = None,
 target_repo: str | None = None,
) -> str:
 """Query repository integration relationships (DDD context map).

 Shows integration patterns between repos: shared-kernel, conformist,
 customer-supplier, etc. with direction and shared artifacts.

 Args:
 source_repo: Filter by source repository ID
 target_repo: Filter by target repository ID

 Returns:
 JSON array of integration edges with DDD patterns and rationale.
 """
 results = _schema.query_integration_map(
 _conn,
 source_repo=source_repo,
 target_repo=target_repo,
 )
 return json.dumps(results, indent=2)


@mcp.tool
def run_fitness_checks(
 severity: list[str] | None = None,
) -> str:
 """Run schema fitness functions and return violations.

 Database-level governance checks complementing /arch-sync
 (document-level). Validates capability-pattern coverage, edge
 referential integrity, integration metadata, and more.

 Args:
 severity: Filter by severity level
 (e.g. ["CRITICAL", "HIGH"]). Default returns all.

 Returns:
 JSON array of violations with check_name, entity_id, issue,
 and severity. Empty array means all checks pass.
 """
 results = _schema.run_fitness_checks(
 _conn,
 severity=severity,
 )
 return json.dumps(results, indent=2)


if __name__ == "__main__":
 mcp.run(transport="stdio")
