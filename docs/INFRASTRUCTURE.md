# Infrastructure

> **Repo:** `semops-core`
> **Owner:** This repo owns and operates these services
> **Version:** 2.0.0
> **Last Updated:** 2026-02-13
> **Related:** [ARCHITECTURE.md](ARCHITECTURE.md) (system design), [SEARCH_GUIDE.md](SEARCH_GUIDE.md) (usage), [INGESTION_GUIDE.md](INGESTION_GUIDE.md) (ingestion)

---

## Services

### Always-On (Docker Compose)

These services run via Docker Compose and are consumed by all SemOps repos.

| Service | Description |
|---------|-------------|
| Supabase Studio | Database UI, admin interface |
| PostgreSQL (pooler) | Supavisor connection pooler (Supabase internals) |
| PostgreSQL (direct) | Direct DB access — scripts and agents use this connection |
| PostgREST | Auto-generated REST API |
| n8n | Workflow automation |
| Qdrant REST | Vector database (REST interface) |
| Qdrant gRPC | Vector database (gRPC interface) |
| Neo4j HTTP | Graph DB browser/API |
| Neo4j Bolt | Graph DB connection protocol |
| Ollama | Local LLM inference |
| Docling | Document processing |

### Application Services (Run On Demand)

These are Python processes started manually when needed.

| Service | Command | Purpose |
|---------|---------|---------|
| Query API | `uvicorn api.query:app` | REST endpoints for semantic search |
| MCP Server | `python -m api.mcp_server` | Agent KB access (managed by Claude Code) |

**Query API** provides REST endpoints for entity search, chunk search, hybrid search, graph neighbors, and corpus listing. See [SEARCH_GUIDE.md](SEARCH_GUIDE.md) for endpoint details.

**MCP Server** runs as a stdio subprocess managed by Claude Code. It's registered in `~/.claude.json` (global) and `.mcp.json` (project-level):

```json
{
  "semops-kb": {
    "command": "python",
    "args": ["-m", "api.mcp_server"],
    "cwd": "/path/to/semops-core"
  }
}
```

The MCP server exposes three tools: `search_knowledge_base` (entity search), `search_chunks` (passage search), and `list_corpora`. See [SEARCH_GUIDE.md](SEARCH_GUIDE.md) for usage.

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
| `SEMOPS_DB_PORT` | Database port | Yes |
| `SEMOPS_DB_NAME` | Database name (default: `postgres`) | Yes |
| `SEMOPS_DB_USER` | Database user (default: `postgres`) | Yes |
| `SEMOPS_DB_PASSWORD` | Database password | Yes |
| `OPENAI_API_KEY` | OpenAI API key for embeddings and search | Yes |

Scripts load these from `.env` via `scripts/db_utils.py`. The `get_db_connection()` function is the single point of connection configuration — do not duplicate connection logic.

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

**Connection:** Scripts connect to PostgreSQL directly using the configured `SEMOPS_DB_HOST` and `SEMOPS_DB_PORT`. The pooler connection is used by Supabase internals only.

**Key extensions:** `pgvector` (vector similarity search with HNSW indexes), `pg_trgm` (trigram matching).

**Schema:** See [SCHEMA_REFERENCE.md](../schemas/SCHEMA_REFERENCE.md) for column specs, [phase2-schema.sql](../schemas/phase2-schema.sql) for DDL.

### Neo4j

Graph database for relationship traversal between entities and concepts.

**Access:** HTTP API and Bolt protocol. No authentication configured for local development.

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

Routing rules are defined per-source in `config/sources/*.yaml`. See [INGESTION_GUIDE.md](INGESTION_GUIDE.md) for source config format and routing details.

---

## Health Checks

Each service exposes a health endpoint. Verify infrastructure readiness by checking:

- **PostgreSQL** — `pg_isready` confirms the database is accepting connections
- **Supabase Studio** — API health endpoint confirms the Studio and Kong gateway are running
- **Qdrant** — Health endpoint confirms the vector database is responsive
- **n8n** — Health endpoint confirms the workflow engine is running
- **Neo4j** — HTTP endpoint confirms the graph database is available
- **Query API** (when running) — Health endpoint confirms the search API is responsive

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

**Symptoms:** `start_services.py` hangs waiting for PostgreSQL, database port not responding.

**Cause:** Previous container didn't shut down cleanly, or port conflict with local PostgreSQL.

**Fix:**
```bash
# Check for processes using the PostgreSQL port
sudo lsof -i :<your-db-port>
docker compose down -v
docker compose up -d
```

### Supabase Studio 500 error

**Symptoms:** Supabase Studio returns 500, loads but shows errors.

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

**Symptoms:** Vector operations fail, Qdrant not responding.

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
- [INGESTION_GUIDE.md](INGESTION_GUIDE.md) — Ingestion pipeline and source configs
- [GLOBAL_ARCHITECTURE.md](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/GLOBAL_ARCHITECTURE.md) — System landscape
