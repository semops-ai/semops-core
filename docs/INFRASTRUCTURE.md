# Infrastructure

> **Repo:** `semops-core`
> **Owner:** This repo owns and operates these services
> **Version:** 2.1.0
> **Last Updated:** 2026-02-16
> **Related:** [ARCHITECTURE.md](ARCHITECTURE.md) (system design), [SEARCH_GUIDE.md](SEARCH_GUIDE.md) (usage), [USER_GUIDE.md](USER_GUIDE.md) (ingestion)

---

## Services

### Always-On (Docker Compose)

These services run via Docker Compose and are consumed by all Project Ike repos.

| Service | Port | Purpose |
|---------|------|---------|
| Supabase Studio | 8000 | Database UI, admin interface |
| PostgreSQL (pooler) | 5432 | Supavisor connection pooler (Supabase internals) |
| PostgreSQL (direct) | 5434 | Direct DB access — scripts and agents use this port |
| PostgREST | 3000 | Auto-generated REST API |
| n8n | 5678 | Workflow automation |
| Qdrant REST | 6333 | Vector database |
| Qdrant gRPC | 6334 | Vector database (gRPC) |
| Neo4j HTTP | 7474 | Graph DB browser/API |
| Neo4j Bolt | 7687 | Graph DB connection protocol |
| Ollama | 11434 | Local LLM inference |
| Docling | 5001 | Document processing |

### Application Services (Run On Demand)

These are Python processes started manually when needed.

| Service | Port | Command | Purpose |
|---------|------|---------|---------|
| Query API | 8101 | `uvicorn api.query:app --port 8101` | REST endpoints for semantic search |
| MCP Server | stdio | `python -m api.mcp_server` | Agent KB access (managed by Claude Code) |

**Query API** provides REST endpoints for entity search, chunk search, hybrid search, graph neighbors, and corpus listing. See [SEARCH_GUIDE.md](SEARCH_GUIDE.md) for endpoint details.

**MCP Server** runs as a stdio subprocess managed by Claude Code. It's registered in `~/.claude.json` (global) and `.mcp.json` (project-level):

```json
{
 "semops-kb": {
 "command": "python",
 "args": ["-m", "api.mcp_server"],
 "cwd": ""
 }
}
```

The MCP server exposes 10 tools in two categories:

**Semantic search** (content discovery via embeddings):

| Tool | Purpose |
|------|---------|
| `search_knowledge_base` | Entity-level semantic search |
| `search_chunks` | Passage-level semantic search |
| `list_corpora` | List available corpora with counts |

**ACL queries** (deterministic architectural lookups):

| Tool | Purpose |
|------|---------|
| `list_patterns` | Pattern registry with provenance filter and coverage |
| `get_pattern` | Single pattern with SKOS edges and coverage |
| `search_patterns` | Semantic search scoped to pattern definitions |
| `list_capabilities` | Capabilities with coherence signals |
| `get_capability_impact` | Dependency graph: patterns, repos, integrations |
| `query_integration_map` | DDD context map (repo-to-repo relationships) |
| `run_fitness_checks` | Database-level governance validation |

See [SEARCH_GUIDE.md](SEARCH_GUIDE.md) for usage.

---

## Starting Services

```bash
# Recommended method
python start_services.py --skip-clone

# Direct Docker Compose
docker compose up -d
```

The `start_services.py` script:
1. Clones/updates Supabase repository (unless `--skip-clone`)
2. Copies `.env` to `supabase/docker/.env`
3. Starts Supabase stack first
4. Waits for PostgreSQL readiness
5. Starts additional services (n8n, Qdrant, Neo4j)

## Stopping Services

```bash
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

---

## Environment Variables

### Application (scripts, agents, consuming repos)

| Variable | Purpose | Required |
|----------|---------|----------|
| `SEMOPS_DB_HOST` | Database host (default: `localhost`) | Yes |
| `SEMOPS_DB_PORT` | Database port (default: `5434`) | Yes |
| `SEMOPS_DB_NAME` | Database name (default: `postgres`) | Yes |
| `SEMOPS_DB_USER` | Database user (default: `postgres`) | Yes |
| `SEMOPS_DB_PASSWORD` | Database password | Yes |
| `OPENAI_API_KEY` | OpenAI API key for embeddings and search | Yes |

Scripts load these from `.env` via `scripts/db_utils.py`. The `get_db_connection` function is the single point of connection configuration — do not duplicate connection logic.

### Supabase Infrastructure (Docker Compose internals)

| Variable | Purpose | Required |
|----------|---------|----------|
| `POSTGRES_PASSWORD` | Supabase DB password | Yes |
| `JWT_SECRET` | Supabase JWT signing | Yes |
| `ANON_KEY` | Supabase anonymous key | Yes |
| `SERVICE_ROLE_KEY` | Supabase service role | Yes |
| `N8N_ENCRYPTION_KEY` | n8n credential encryption | Yes |

**Setup:** Create `.env` from `.env.example` and fill values.

---

## Database

### PostgreSQL + pgvector

Primary data store. All entities, chunks, embeddings, edges, and metadata live here.

**Connection:** Port 5434 (direct), port 5432 (pooler — Supabase internals only). Scripts use port 5434 by default.

**Key extensions:** `pgvector` (vector similarity search with HNSW indexes), `pg_trgm` (trigram matching).

**Schema:** See [SCHEMA_REFERENCE.md](../schemas/SCHEMA_REFERENCE.md) for column specs, [phase2-schema.sql](../schemas/phase2-schema.sql) for DDL.

### Neo4j

Graph database for relationship traversal between entities and concepts.

**Access:** HTTP API on port 7474, Bolt protocol on port 7687. No authentication configured for local development.

**Populated by:** `scripts/materialize_graph.py` (backfill) and automatic graph writes during ingestion. Pattern taxonomy synced from `pattern_edge` table via `scripts/sync_neo4j.py`.

**Queried by:** `GET /graph/neighbors/{entity_id}` endpoint in the Query API.

**Notes:** Graph data persists in Docker volume.

### Qdrant

Vector database used by `semops-data` for research corpus. Not used directly by semops-core scripts (which use pgvector for all vector operations).

**Notes:** No auth by default in dev mode (API key required in production). Collections persist in Docker volume. Large embeddings can exhaust memory on small machines.

---

## Corpus Routing

Knowledge is organized into corpora for filtered retrieval. Corpus assignment happens at ingestion time via source config routing rules.

| Corpus | Content |
|--------|---------|
| `core_kb` | Core SemOps concepts, patterns, and domain knowledge |
| `deployment` | Infrastructure, ADRs, session notes, architecture docs |
| `published` | Published content (blog posts, articles) |
| `research_ai` | AI/ML research and experiments |
| `research_general` | General research and explorations |

Routing rules are defined per-source in `config/sources/*.yaml`. See [USER_GUIDE.md](USER_GUIDE.md) for source config format and routing details.

---

## Connection Patterns

How this repo's scripts connect to shared infrastructure:

| Service | Method | Details |
| --- | --- | --- |
| PostgreSQL | `localhost:5434` | Via `SEMOPS_DB_*` env vars. Shared module: `scripts/db_utils.py` |
| Qdrant | `localhost:6333` | Via REST API. Used by semops-data; semops-core uses pgvector |
| Neo4j | `localhost:7474` / `:7687` | HTTP + Bolt. No auth in dev |
| MCP Server | stdio | Registered in `~/.claude.json` (global) and `.mcp.json` (project) |

---

## Docker Configuration

### Network

| Network | Services | Purpose |
| --- | --- | --- |
| `semops-network` | All Docker Compose services | Internal container communication |

> **Convention:** Cross-repo access uses `localhost` port mapping, not Docker internal networking. See [GLOBAL_INFRASTRUCTURE.md](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/GLOBAL_INFRASTRUCTURE.md#how-repos-connect).

---

## Python Stack

| Property | Value |
| --- | --- |
| **Python version** | `>=3.12` |
| **Package manager** | `uv` with `pyproject.toml` |
| **Virtual environment** | `.venv/` |
| **Linter/formatter** | `ruff` |
| **Test framework** | `pytest` |

### Key Dependencies

| Library | Purpose | Shared With |
| --- | --- | --- |
| `psycopg[binary]` | PostgreSQL driver (primary) | — |
| `fastapi` / `uvicorn` | Query API, MCP server hosting | — |
| `mcp` | MCP server protocol (FastMCP) | — |
| `openai` | Embeddings (`text-embedding-3-small`) | semops-data |
| `anthropic` | LLM classification (Claude) | semops-publisher |
| `neo4j` | Graph DB driver | — |
| `pydantic` / `pydantic-settings` | Data models, settings, env loading | publisher, data |
| `httpx` | HTTP client (Docling integration) | backoffice |
| `pyyaml` | YAML parsing (source configs, patterns) | all repos |
| `click` | CLI scaffolding | publisher, data |
| `rich` | CLI output formatting | publisher |
| `ulid-py` | ULID generation for entity IDs | — |

### Setup

```bash
uv venv && source .venv/bin/activate && uv sync
```

---

## Health Checks

```bash
# PostgreSQL (direct port)
pg_isready -h localhost -p 5434

# Supabase Studio
curl -s http://localhost:8000/api/health

# Qdrant
curl -s http://localhost:6333/health

# n8n
curl -s http://localhost:5678/healthz

# Neo4j
curl -s http://localhost:7474

# Query API (when running)
curl -s http://localhost:8101/health
```

---

## Local Development Setup

```bash
# Clone and setup
git clone https://github.com/semops-ai/semops-core.git
cd semops-core

# Create Python environment
uv venv
source .venv/bin/activate
uv sync

# Setup environment
cp supabase/docker/.env.example .env
# Edit .env with your values

# Start services
python start_services.py

# Initialize schema
python scripts/init_schema.py
```

---

## Troubleshooting

### PostgreSQL won't start

**Symptoms:** `start_services.py` hangs waiting for PostgreSQL, port 5434 not responding.

**Cause:** Previous container didn't shut down cleanly, or port conflict with local PostgreSQL.

**Fix:**
```bash
sudo lsof -i :5434
docker compose down -v
docker compose up -d
```

### Supabase Studio 500 error

**Symptoms:** `http://localhost:8000` returns 500, Studio loads but shows errors.

**Cause:** Missing or incorrect environment variables, or database not initialized.

**Fix:**
```bash
# Verify .env exists and has values
cat .env | grep -E "^(POSTGRES|JWT|ANON|SERVICE)"

# Reinitialize if needed
docker compose down -v
python start_services.py --skip-clone
```

### Qdrant connection refused

**Symptoms:** Vector operations fail, port 6333 not responding.

**Fix:**
```bash
docker compose logs qdrant
docker compose restart qdrant
```

---

## Service Notes

### Supabase

- Uses JWT tokens defined in `.env` (`ANON_KEY` for public, `SERVICE_ROLE_KEY` for admin)
- Studio requires all Kong/GoTrue services running
- pgvector extension must be enabled manually on fresh install
- Row Level Security (RLS) disabled by default in dev
- If migrations fail, check `supabase/docker/volumes/db/` for state

### n8n

- First-time setup creates admin account
- Credentials encrypted with `N8N_ENCRYPTION_KEY` — changing the key invalidates all stored credentials
- Webhook URLs change if container recreated without persistent storage

---

## Consumed By

| Repo | Services Used |
|------|---------------|
| `semops-publisher` | PostgreSQL (entities, knowledge base), MCP server |
| `semops-data` | Qdrant (vectors), Docling (doc processing), PostgreSQL, same embedding model |
| `semops-sites` | Supabase Cloud (production mirror) |
| `semops-docs` | Schema definitions (read-only) |
| `semops-dx-orchestrator` | MCP server (knowledge base access) |

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Retrieval pipeline and system design
- [SEARCH_GUIDE.md](SEARCH_GUIDE.md) — Search modes, API endpoints, MCP tools
- [USER_GUIDE.md](USER_GUIDE.md) — Ingestion pipeline and source configs
- [GLOBAL_ARCHITECTURE.md](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/GLOBAL_ARCHITECTURE.md) — System landscape
- [PORTS.md](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/PORTS.md) — Full port registry across all repos
