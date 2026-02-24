# Issue #62: Source-Based Ingestion Pipeline with RAG

> **Status:** Complete
> **Date:** 2025-12-03
> **Related Issue:** 
> **PR:** 
> **Builds On:** [ADR-0001](./ADR-0001.md), [ISSUE-48-FOUNDATION-CATALOG](./ISSUE-48-FOUNDATION-CATALOG.md)

---

## Executive Summary

Implemented source-based ingestion for the Project Ike knowledgebase. This enables automated ingestion from configured sources (GitHub repos) with LLM classification for semantic metadata, vector embeddings for RAG retrieval, and an n8n chat interface for querying the knowledge base.

---

## Context

The Project Ike knowledge base needed a way to:
1. Ingest content from owned surfaces (GitHub, WordPress, LinkedIn)
2. Apply consistent attribution and metadata
3. Classify content semantically (concept ownership, content type, relationships)
4. Enable semantic search and RAG-based Q&A

Previous manual approaches didn't scale. We needed an automated pipeline that could:
- Define sources via configuration (not code changes)
- Apply LLM classification for nuanced metadata
- Support incremental updates via content hashing
- Provide multiple query interfaces

---

## Decision

### Architecture

**Source Configuration (YAML)**
- Sources defined in `config/sources/*.yaml`
- Specifies: GitHub repo, include/exclude patterns, file extensions
- Provides: default attribution, LLM classification fields

**Ingestion Pipeline**
- Dockerized Python scripts for portability
- GitHub file fetching via `gh` CLI (authenticated)
- LLM classification via Anthropic Claude Sonnet 4
- Entity storage in PostgreSQL with JSONB metadata

**Vector Search (pgvector)**
- Embeddings via OpenAI `text-embedding-3-small` (1536 dimensions)
- HNSW index for fast similarity search
- Single database for structured + vector data (no sync issues)

**RAG Interface (n8n)**
- Webhook-based workflow for API access
- Chat Trigger workflow for UI-based queries
- Context assembly from top-5 similar entities
- Response generation via GPT-4o-mini

### Why pgvector over Qdrant?

| Factor | pgvector | Qdrant |
|--------|----------|--------|
| Data locality | Same DB as entities | Separate service |
| Sync complexity | None | Requires sync |
| Joins | Yes | No |
| HNSW index | Yes | Yes |
| Production scale | Sufficient | Overkill for now |

**Decision:** Use pgvector. Keep Qdrant in docker-compose for potential future chunk-level search.

### LLM Classification Fields

| Field | Source | Purpose |
|-------|--------|---------|
| `concept_ownership` | LLM | 1p (coined) / 2p (adapted) / 3p (industry) |
| `content_type` | LLM | article, guide, framework, principle, pattern, definition |
| `primary_concept` | LLM | Main concept as kebab-case ID |
| `broader_concepts` | LLM | Parent concept IDs |
| `narrower_concepts` | LLM | Child concept IDs |
| `subject_area` | LLM | Domain areas array |
| `summary` | LLM | Brief abstract |

---

## Consequences

**Positive:**
- Automated ingestion from GitHub (120 docs processed)
- Semantic search working (114 entities with embeddings)
- RAG chat interface functional
- Unified database (no sync complexity)
- LLM classification provides rich metadata

**Negative:**
- LLM classification adds cost (~$0.01/doc with Claude)
- Some classifications may need manual review
- Docling document processing not yet tested
- No diff-based updates implemented yet

---

## Implementation

### Files Created

```
config/sources/project-ike-private.yaml # Source configuration
scripts/source_config.py # Pydantic config loader
scripts/github_fetcher.py # GitHub file fetcher
scripts/entity_builder.py # Entity construction
scripts/llm_classifier.py # Anthropic classification
scripts/ingest_from_source.py # Main CLI orchestrator
scripts/generate_embeddings.py # OpenAI embedding generation
scripts/semantic_search.py # CLI vector search
scripts/docling_ingest.py # Document processing (ready)
scripts/Dockerfile.ingestion # Docker container
scripts/sql/seed_surfaces.sql # Surface records
n8n/backup/workflows/rag-chat.json # Webhook workflow
n8n/backup/workflows/Ike RAG Chat UI.json # UI workflow
```

### Stack

| Service | Port | Purpose |
|---------|------|---------|
| Supabase Studio | 8000 | Database UI |
| PostgreSQL + pgvector | 5432 | Data + vectors |
| n8n | 5678 | Workflow automation |
| Docling | 5001 | Document processing |
| Qdrant | 6333 | (Reserved for chunks) |

### Usage

```bash
# Ingestion
docker build -t ike-ingestion -f scripts/Dockerfile.ingestion .
docker run --network ike_default \
 -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=... \
 -e ANTHROPIC_API_KEY=... \
 ike-ingestion --source project-ike-private

# Embeddings
python scripts/generate_embeddings.py

# Search
python scripts/semantic_search.py "What is semantic coherence?"

# RAG (n8n must be running)
curl -X POST http://localhost:5678/webhook/rag-chat \
 -H "Content-Type: application/json" \
 -d '{"query": "What is semantic coherence?"}'
```

---

## Next Steps

### Issue #69: Classification Refinement
- Review classification accuracy via SQL queries
- Implement manual overrides or prompt improvements
- Add diff-based re-ingestion

### Issue #70: Advanced Retrieval
- Hybrid search (vector + full-text)
- Test Docling with PDFs
- Evaluate graph relationships
- Local model options (Ollama)

---

## Session Log

### 2025-12-03: Full Implementation

**Status:** Completed
**Tracking Issue:** 

**Completed:**
- Created source configuration schema and YAML loader
- Implemented GitHub fetcher using `gh` CLI
- Built entity construction with derived + LLM-classified attributes
- Integrated Anthropic Claude for classification
- Containerized pipeline with Dockerfile
- Added pgvector extension and embedding column
- Generated embeddings for 114 entities
- Created n8n RAG chat workflows (webhook + UI)
- Added Docling service to docker-compose
- Tested full pipeline: ingestion → embeddings → RAG query

**Key Decisions:**
- pgvector over Qdrant for simplicity
- OpenAI embeddings (text-embedding-3-small)
- Claude Sonnet 4 for classification
- n8n for chat interface (vs custom API)

**Experiment Results (LLM Classification):**
- 100% consistency across 3 runs per document
- semantic-operations.md: 1p ✅
- first-principles.md: 2p (expected 1p, but reasonable)
- domain-driven-design.md: 3p ✅
- Average latency ~4s per classification

---

## References

- 
- 
- 
- [ottomator-agents docling-rag-agent](https://github.com/coleam00/ottomator-agents/tree/main/docling-rag-agent) (reference implementation)

---

**End of Document**
