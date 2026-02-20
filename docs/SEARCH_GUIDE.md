# User Guide: Search & Retrieval

> **Version:** 2.0.0 | **Last Updated:** 2026-02-16
> **Related Issues:** #109 (query API), #131 (shared search module), #133 (ACL query tools)
> **See also:** [INGESTION_GUIDE.md](INGESTION_GUIDE.md) for ingesting content into the knowledge base

---

## Quick Reference

| Task | Command |
|------|---------|
| CLI search (chunks) | `python scripts/semantic_search.py "query"` |
| CLI search (entities) | `python scripts/semantic_search.py "query" --mode entities` |
| CLI search (hybrid) | `python scripts/semantic_search.py "query" --mode hybrid` |
| Start query API | `uvicorn api.query:app --port 8101` |
| Check entity count | `docker exec semops-hub-pg psql -U postgres -d postgres -c "SELECT count(*) FROM entity;"` |
| Check chunk count | `docker exec semops-hub-pg psql -U postgres -d postgres -c "SELECT count(*) FROM document_chunk;"` |
| Corpus distribution | `docker exec semops-hub-pg psql -U postgres -d postgres -c "SELECT metadata->>'corpus', count(*) FROM entity GROUP BY 1 ORDER BY 2 DESC;"` |

**Note:** All Python commands assume `source .venv/bin/activate` (or use `uv run`) and `OPENAI_API_KEY` is set (loaded from `.env`).

---

## Prerequisites

1. **Docker services running** — `python start_services.py --skip-clone`
2. **Python venv activated** — `source .venv/bin/activate` (or use `uv run`)
3. **`.env` file** with `OPENAI_API_KEY` and `POSTGRES_PASSWORD`
4. **Database connection** — Scripts connect automatically via `SEMOPS_DB_*` env vars configured in `.env`. Direct PostgreSQL access is available on port 5434.
5. **Content ingested** — At least one source ingested with embeddings generated. See [INGESTION_GUIDE.md](INGESTION_GUIDE.md).

---

## How Search Works

The knowledge base implements **hybrid semantic search** — the standard RAG pattern of combining document-level retrieval with passage-level retrieval to get both broad relevance and precise answers. The system decomposes this into two independent stages that you can run separately or together:

1. **Entity search** — finds *which documents* are relevant (document retrieval)
2. **Chunk search** — finds *which passages* answer your question (passage retrieval)
3. **Hybrid search** — runs both stages together: find top documents, then retrieve best passages within each

All search is **purely semantic**. Your query is converted into a 1536-dimensional embedding vector (OpenAI `text-embedding-3-small`), then compared against pre-computed embeddings using pgvector cosine similarity. There is no keyword or full-text search component — a query like "database connectivity" matches content about "PostgreSQL connection pooling" because the meaning is similar.

### The Two Retrieval Layers

Each ingested document exists at two levels in the knowledge base:

**Entities** represent whole documents. Each entity's embedding is built from structured metadata — title, summary, content type, primary concept, and broader/narrower concept tags. This makes entity search effective for topic discovery: "find me documents about domain-driven design."

**Chunks** represent passages within documents. During ingestion, each file is split by markdown headings (~512 tokens per section), and each chunk's embedding is built from its actual content text. This makes chunk search effective for precise retrieval: "find the paragraph that explains the embedding column."

```text
Entity: "schema-reference.md"
  embedding from: title + summary + concept tags (metadata)
  |
  +-- Chunk 0: "## Entity Table\nThe entity table is the..."
  |   embedding from: actual section text
  |
  +-- Chunk 1: "## Document Chunk Table\nChunks store..."
  |   embedding from: actual section text
  |
  +-- Chunk 2: "## Edge Table\nRelationships between..."
      embedding from: actual section text
```

Because entity and chunk embeddings are built from different text, the same query can surface different results at each layer. Entity search for "embeddings" returns `schema-reference.md` (metadata topic match), while chunk search for "embeddings" returns the specific paragraph explaining the embedding column (content match).

### Three Search Modes

**Chunk search** (`--mode chunks`, default) — the passage retrieval stage. Searches `document_chunk` embeddings built from actual content. Best for finding specific answers.

Results include: similarity score (0.0-1.0), entity ID (parent document), heading hierarchy (section breadcrumbs like "Architecture > Entities > Attributes"), content preview (truncated to 500 chars in CLI/MCP), and chunk position (e.g., "3 of 7" within that entity).

**Entity search** (`--mode entities`) — the document retrieval stage. Searches `entity` embeddings built from structured metadata. Best for topic discovery and document-level relevance.

Results include: similarity score (based on metadata match, not full document content), title, corpus, content type, LLM-generated summary, and concept ownership (first-party vs. third-party).

**Hybrid search** (`--mode hybrid`) — the full two-stage pipeline. First finds the top-N relevant entities, then retrieves the best-matching chunks *within each entity*. This answers "which documents are relevant, and where specifically within them?" — the standard RAG retrieval pattern for grounded generation with precise citations.

### Similarity Scores

Scores range from 0.0 (completely unrelated) to 1.0 (identical meaning):

| Score Range | Interpretation |
| ----------- | -------------- |
| 0.80+ | Strong match — content directly addresses the query |
| 0.60-0.80 | Related — content is topically relevant but may not be a direct answer |
| Below 0.60 | Weak — try rephrasing the query or broadening terms |

Chunk searches typically produce higher scores than entity searches because chunks match against actual content, while entities match against metadata summaries.

### Graph Traversal (Separate)

The Neo4j knowledge graph tracks **relationships between concepts** (e.g., "semantic-operations EXTENDS domain-driven-design"). Graph traversal is completely separate from vector search — it doesn't rank by similarity, it follows typed edges between entities.

The graph is accessed via `GET /graph/neighbors/{entity_id}` in the Query API. It returns direct neighbors (not transitive paths) with relationship types and directions. Agents typically use this to explore related concepts after finding a starting point via semantic search.

### Filtering

All search modes support **corpus filtering** (`--corpus core_kb research_ai`) to restrict results to specific knowledge domains. Entity search additionally supports **content type** (`--content-type adr pattern`) and **lifecycle stage** (`--lifecycle-stage active draft`) filters. Filters are applied before vector ranking — they narrow the candidate set, not the similarity calculation.

### Available Corpus Types

| Corpus | Description |
|--------|-------------|
| `core_kb` | Curated knowledge: patterns, theory, schema |
| `deployment` | Operational artifacts: ADRs, session notes, architecture docs |
| `published` | Published content: blog posts, public docs |
| `research_ai` | AI/ML research: AI foundations, cognitive science |
| `research_general` | General research: ad-hoc, unsorted, triage |

### Available Content Types

| Content Type | Description |
|-------------|-------------|
| `concept` | Theoretical/conceptual document |
| `pattern` | Domain pattern documentation |
| `architecture` | Architecture docs, topology |
| `adr` | Architecture Decision Record |
| `article` | General prose, blog post |
| `session_note` | Work log, decision provenance |

---

## CLI Search

The CLI defaults to **chunk search** (passage-level retrieval), which is the most useful mode for most queries. Use `--mode` to switch between search modes.

```bash
# Chunk search (default) — passage-level retrieval
python scripts/semantic_search.py "What is semantic coherence?"

# Entity search — document-level results
python scripts/semantic_search.py "domain patterns" --mode entities

# Hybrid search — top entities with best chunks per entity
python scripts/semantic_search.py "semantic flywheel" --mode hybrid

# Filter by corpus
python scripts/semantic_search.py \
  "publication workflow" --corpus core_kb published

# Filter by content type (entity mode)
python scripts/semantic_search.py \
  "architecture decisions" --mode entities --content-type adr

# Filter by lifecycle stage (entity mode only)
python scripts/semantic_search.py \
  "draft concepts" --mode entities --lifecycle-stage draft

# Combine filters with limit and verbose output
python scripts/semantic_search.py \
  "provenance" --corpus core_kb --limit 5 --verbose
```

**Search modes:**

| Mode | Flag | Description |
| ------ | ------ | ------------- |
| Chunks | `--mode chunks` (default) | Passage-level results from `document_chunk` table |
| Entities | `--mode entities` | Document-level results from `entity` table |
| Hybrid | `--mode hybrid` | Top entities with best-matching chunks per entity |

---

## FastAPI Query API

**Start the server:**

```bash
uvicorn api.query:app --port 8101
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/search` | Entity-level semantic search with filters |
| `POST` | `/search/chunks` | Chunk (passage) level semantic search |
| `POST` | `/search/hybrid` | Two-stage: entity search then chunk retrieval within top entities |
| `GET` | `/graph/neighbors/{entity_id}` | Graph traversal — related concepts and entities |
| `GET` | `/corpora` | List corpora with entity counts |
| `GET` | `/health` | Health check |

**Entity search** (document-level):

```bash
curl -s http://localhost:8101/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is semantic coherence?",
    "corpus": ["core_kb"],
    "content_type": ["concept", "pattern"],
    "limit": 5
  }' | python3 -m json.tool
```

**Response fields:** `id`, `title`, `corpus`, `content_type`, `summary`, `similarity`, `filespec`, `metadata`

**Chunk search** (passage-level):

```bash
curl -s http://localhost:8101/search/chunks \
  -H "Content-Type: application/json" \
  -d '{
    "query": "semantic compression in DDD",
    "corpus": ["core_kb"],
    "limit": 5
  }' | python3 -m json.tool
```

**Response fields:** `chunk_id`, `entity_id`, `source_file`, `heading_hierarchy`, `content`, `corpus`, `content_type`, `similarity`, `chunk_index`, `total_chunks`

**Hybrid search** (entity then chunk two-stage):

```bash
curl -s http://localhost:8101/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "semantic flywheel pattern",
    "corpus": ["core_kb"],
    "limit": 5,
    "chunks_per_entity": 3
  }' | python3 -m json.tool
```

Returns top entities with their best-matching chunks inlined.

**Graph neighbors:**

```bash
curl -s http://localhost:8101/graph/neighbors/semantic-flywheel | python3 -m json.tool
```

Returns related entities and concepts from the Neo4j knowledge graph with relationship types and directions.

**List corpora:**

```bash
curl -s http://localhost:8101/corpora | python3 -m json.tool
```

---

## MCP Server (Cross-Repo Agent Access)

The MCP server exposes 10 tools across two query surfaces, allowing Claude Code agents in any repo to query the knowledge base.

**Configuration:** Already registered in `~/.claude.json` as `semops-kb`. Also configured in `.mcp.json` for project-level access.

### Semantic Search Tools (Content Discovery)

These use pgvector embeddings for probabilistic matching — best for finding relevant content.

| Tool | Description |
|------|-------------|
| `search_knowledge_base` | Entity-level semantic search with corpus/content_type filters |
| `search_chunks` | Chunk (passage) level semantic search with heading hierarchy context |
| `list_corpora` | List available corpora with counts |

**Usage:**

```
Use the search_knowledge_base tool to find entities about "semantic coherence"
in the core_kb corpus.

Use the search_chunks tool to find specific passages about "anti-corruption layer"
for precise citation in a document.
```

### ACL Query Tools (Architectural Truth)

These are deterministic SQL lookups against the DDD schema — exact results from committed edges and the pattern registry. Use these when you need architecturally-aligned answers, not probabilistic matches.

| Tool | Description |
|------|-------------|
| `list_patterns` | Pattern registry with optional provenance filter (`1p`, `3p`) and coverage statistics (capability/repo/content counts) |
| `get_pattern` | Single pattern with all SKOS edges (broader/narrower/related), adoption relationships (adopts/extends/modifies), and coverage |
| `search_patterns` | Semantic search over pattern embeddings — finds patterns by meaning, not just ID |
| `list_capabilities` | Capabilities from the `capability_coverage` view with optional domain classification filter (`core`, `supporting`, `generic`) |
| `get_capability_impact` | Full impact analysis for a capability: implementing patterns, delivering repos, and integration dependencies between those repos |
| `query_integration_map` | DDD context map — integration edges between repos with patterns (shared-kernel, conformist, customer-supplier, ACL), direction, and shared artifacts |
| `run_fitness_checks` | Database-level governance checks (10 functions). Returns violations with severity (CRITICAL/HIGH/MEDIUM/LOW). Optional severity filter |

**Usage:**

```
Use the list_patterns tool with provenance ["3p"] to see all adopted third-party patterns.

Use the get_capability_impact tool with capability_id "ingestion-pipeline" to see
what patterns it implements, which repos deliver it, and integration dependencies.

Use the run_fitness_checks tool to check for schema governance violations.
```

### Key Files

| File | Purpose |
|------|---------|
| `api/mcp_server.py` | MCP tool definitions (FastMCP, stdio transport) |
| `scripts/search.py` | Shared semantic search module (entity, chunk, hybrid) |
| `scripts/schema_queries.py` | Shared ACL query module (patterns, capabilities, integrations, fitness) |

**Requires:** Docker services running and `SEMOPS_DB_*` env vars configured in `.env`.

---

## Troubleshooting

### Database Connection

Scripts connect automatically via `SEMOPS_DB_*` env vars configured in `.env`. Direct PostgreSQL access is available on port 5434.

**Error:** `connection refused`
**Cause:** Docker services not running, or `.env` missing `SEMOPS_DB_*` variables.
**Fix:** Start services with `python start_services.py --skip-clone` and verify `.env` has the `SEMOPS_DB_*` connection settings.

### Embedding Generation

**Error:** `OPENAI_API_KEY not set in environment`
**Fix:** The `.env` file has the key, but the script's `.env` loader may not pick it up. Export it explicitly:

```bash
export $(grep OPENAI_API_KEY .env)
```

### MCP Server

**Server won't start:**
**Check:** Verify Docker services are running and `.env` has correct `SEMOPS_DB_*` connection settings. Direct PostgreSQL access is on port 5434.
