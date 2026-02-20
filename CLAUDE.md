# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Role in Global Architecture

**Repo:** `semops-core`
**Role:** Schema owner and infrastructure provider
**Location:** `.`

**Owns:**
- Global schema definitions (entity, edge, surface, delivery)
- Domain language ([schemas/UBIQUITOUS_LANGUAGE.md](schemas/UBIQUITOUS_LANGUAGE.md))
- Infrastructure services (Supabase, n8n, Qdrant, Neo4j)
- Knowledge graph and RAG pipelines

**Does NOT own (consumed from semops-dx-orchestrator):**
- Process documentation
- Global architecture docs
- Cross-repo coordination patterns

**Key Insight:** This repo owns *model* (what we know) and *infrastructure* (services), while `semops-dx-orchestrator` owns *process* (how we work).

## Core Schema

**Schema changes are high-impact** - they affect all connected Project SemOps repositories.

| File | Purpose |
|------|---------|
| [schemas/UBIQUITOUS_LANGUAGE.md](schemas/UBIQUITOUS_LANGUAGE.md) | Domain definitions and business rules |
| [schemas/SCHEMA_REFERENCE.md](schemas/SCHEMA_REFERENCE.md) | Column specs, JSONB schemas, constraints |
| [schemas/phase2-schema.sql](schemas/phase2-schema.sql) | PostgreSQL implementation |
| [schemas/SCHEMA_CHANGELOG.md](schemas/SCHEMA_CHANGELOG.md) | Schema evolution history |

**Before schema changes:**
1. Read UBIQUITOUS_LANGUAGE.md and SCHEMA_REFERENCE.md
2. Review phase2-schema.sql
3. Create GitHub issue for discussion
4. Update SCHEMA_CHANGELOG.md

## Infrastructure

**Services (Docker Compose):**

| Service | Port | Purpose |
|---------|------|---------|
| Supabase Studio | 8000 | Database UI |
| PostgreSQL (direct) | 5434 | Primary DB — scripts/agents use this port |
| Supavisor (pooler) | 5432 | Connection pooler — Supabase internals only |
| n8n | 5678 | Workflow automation |
| Qdrant | 6333 | Vector DB |
| Neo4j | 7474/7687 | Graph DB |

**Starting services:**
```bash
python start_services.py --skip-clone
```

**Environment:** Create `.env` from `.env.example`. Key vars:

| Variable      | Purpose                                                   |
|---------------|-----------------------------------------------------------|
| `SEMOPS_DB_*` | Application connection (scripts, agents, consuming repos)  |
| `POSTGRES_*`  | Supabase infrastructure (docker-compose internals)         |

Scripts use `SEMOPS_DB_HOST=localhost`, `SEMOPS_DB_PORT=5434` by default via `scripts/db_utils.py`.
All scripts import `from db_utils import get_db_connection` — do not duplicate connection logic.

## Key Commands

```bash
# Schema
python scripts/init_schema.py          # Initialize schema
python scripts/setup_supabase.py       # Setup Supabase env

# Data ingestion
python scripts/ingest_from_source.py --source <name>  # Source-based ingestion (LLM classification)
python scripts/ingest_architecture.py                  # Architecture layer (repos, capabilities, edges)
python scripts/ingest_markdown_docs.py                 # Ingest markdown to entities (legacy)
python scripts/sheets_to_entities.py                   # Import from Google Sheets
python scripts/manage_lineage.py                       # Manage entity edges
```

## Data Model

**Pattern as Aggregate Root** (ADR-0004, ADR-0009): Three-layer architecture.

| Layer | Tables | Purpose |
|-------|--------|---------|
| **Pattern** (WHY) | `pattern`, `pattern_edge` | SKOS concept taxonomy, adoption relationships |
| **Architecture** (WHAT/WHERE) | `entity` (capability, repository), `edge` | Capabilities, repos, integration patterns |
| **Content** (artifacts) | `entity` (content), `edge`, `surface`, `delivery` | Publishing artifacts, PROV-O relationships |

The `entity` table uses `entity_type` discriminator (`content`, `capability`, `repository`).

**Strategic views:** `pattern_coverage`, `capability_coverage`, `repo_capabilities`, `integration_map`, `orphan_entities`

**Fitness functions:** `schemas/fitness-functions.sql` — database-level governance checks (10 functions)

**JSONB conventions:** All JSONB fields include `$schema` versioning (e.g., `filespec_v1`, `content_metadata_v1`)

## Repository Structure

## MCP Server (Cross-Repo Agent Access)

The MCP server exposes 10 tools across two query surfaces for cross-repo agent access.

**Semantic search** (content discovery via embeddings):

| Tool | Description |
|------|-------------|
| `search_knowledge_base` | Entity-level semantic search with corpus/content_type filters |
| `search_chunks` | Passage-level search with heading hierarchy context |
| `list_corpora` | List available corpora with counts |

**ACL queries** (deterministic architectural lookups):

| Tool | Description |
|------|-------------|
| `list_patterns` | Pattern registry with optional provenance filter and coverage stats |
| `get_pattern` | Single pattern with SKOS edges, adoption relationships, coverage |
| `search_patterns` | Semantic search over pattern embeddings |
| `list_capabilities` | Capability coverage view with domain classification filter |
| `get_capability_impact` | Full impact analysis: patterns, repos, integration dependencies |
| `query_integration_map` | DDD context map: repo integration edges with patterns and artifacts |
| `run_fitness_checks` | Database-level governance checks with severity filter |

**Key files:**
- `api/mcp_server.py` — MCP tool definitions (FastMCP, stdio transport)
- `scripts/search.py` — Shared semantic search module
- `scripts/schema_queries.py` — Shared ACL query module

**Configuration:** Registered in `~/.claude.json` as `semops-kb`.

## Repository Structure

```
semops-core/
├── api/                  # MCP server and Query API
│   ├── mcp_server.py     # MCP server (10 tools)
│   └── query.py          # REST Query API (:8101)
├── schemas/              # DDD schema definitions
│   ├── UBIQUITOUS_LANGUAGE.md  # Domain language (business rules)
│   ├── SCHEMA_REFERENCE.md     # Data dictionary (column specs)
│   ├── phase2-schema.sql
│   └── fitness-functions.sql
├── scripts/              # Data transformation and query modules
│   ├── search.py         # Semantic search (shared module)
│   ├── schema_queries.py # ACL queries (shared module)
│   ├── db_utils.py       # Database connection
│   └── ...               # Ingestion, embedding, lineage scripts
├── config/sources/       # Source configurations for ingestion
├── docs/                 # Documentation and ADRs
│   └── decisions/
├── n8n/backup/           # Workflow definitions
└── docker-compose.yml
```

**Note:** This is a schema and data operations repository - not a typical application with `src/` and `tests/`.

## Python Environment

```bash
source .venv/bin/activate    # or: uv run <script>
python scripts/init_schema.py
```

## Related Documentation

- [GLOBAL_ARCHITECTURE.md](docs/GLOBAL_ARCHITECTURE.md) - System landscape
- [INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) - Services, operations, troubleshooting
- [SEARCH_GUIDE.md](docs/SEARCH_GUIDE.md) - Search and retrieval (CLI, API, MCP)
- [USER_GUIDE.md](docs/USER_GUIDE.md) - Ingestion pipeline
