# ADR-0008: Unified Ingestion and Retrieval Pipeline

> **Status:** Complete
> **Date:** 2026-02-02
> **Related Issue:** [](https://github.com/semops-ai/semops-core/issues/114)
> **Related ADRs:** ADR-0005 (Ingestion Strategy and Corpus Architecture), ADR-0007 (Concept/Content Value Objects)

## Executive Summary

The knowledge base has three storage layers (entity, chunk, graph) served by three independent pipelines with different source configs, embedding models, and no cross-references. This ADR unifies them into a single ingestion pipeline that populates all layers from the same source configuration, using a single embedding model, with foreign key links between layers.

## Context

### Current State (as of 2026-02-02)

| Store | Pipeline | Config | Embedding | Count |
|-------|----------|--------|-----------|-------|
| Entity (Supabase pgvector) | `ingest_from_source.py` | Source YAML configs | OpenAI `text-embedding-3-small` (1536d) | 131 entities |
| Chunk (Supabase pgvector) | `chunk_markdown_docs.py` | Hardcoded directory arg | Ollama `nomic-embed-text` (768d) | 103 chunks from 5 files |
| Graph (Neo4j) | Manual / unknown | None | N/A | 19 nodes, 14 edges |

**Problems:**
1. Chunks come from a deprecated repo (`project-ike-private`), not current sources
2. Graph has 19 nodes when 131+ entities exist with hundreds of detected edges in metadata
3. No FK between chunks and entities — hybrid retrieval impossible
4. Two embedding models with different dimensions — no vector space alignment
5. Chunk search and entity search return results from different content

### Cross-Repo Dependency: semops-data

semops-data's research pipeline uses `text-embedding-3-small` (1536d) with Qdrant for its research corpus. Future lineage scoring (, Phase 4) will measure `coherence_score` — alignment between agent episodes and knowledge patterns. This requires the same embedding model across both repos.

| Component | Model | Dimensions | Store |
|-----------|-------|-----------|-------|
| semops-core entities | `text-embedding-3-small` | 1536 | Supabase pgvector |
| semops-core chunks | `nomic-embed-text` | 768 | Supabase pgvector |
| semops-data research | `text-embedding-3-small` | 1536 | Qdrant |

The chunk pipeline's use of `nomic-embed-text` is the outlier.

## Decision

### D1: Single Embedding Model — OpenAI `text-embedding-3-small`

Use `text-embedding-3-small` (1536d) for all vector embeddings across the system:
- Entity embeddings (existing, no change)
- Chunk embeddings (change from `nomic-embed-text`)
- semops-data research embeddings (existing, no change)

**Rationale:** Same vector space enables cross-layer similarity (entity ↔ chunk), cross-repo coherence scoring, and eliminates the need for alignment or reranking between incompatible spaces. The cost difference is negligible at current scale (~$0.02/M tokens).

**Tradeoff:** Dependency on OpenAI API. If local-only operation is needed, define a migration path later (e.g., re-embed with a local model). Don't optimize for this now.

### D2: Chunk-Entity Linking via `entity_id` FK

Add `entity_id` column to `document_chunk` table:

```sql
ALTER TABLE document_chunk ADD COLUMN entity_id TEXT REFERENCES entity(id);
CREATE INDEX idx_document_chunk_entity_id ON document_chunk(entity_id);
```

When a file is ingested as an entity, its chunks reference back via `entity_id`. This enables:
- Given an entity, retrieve its chunks: `SELECT * FROM document_chunk WHERE entity_id = ?`
- Given a chunk, look up its parent entity metadata
- Hybrid query: entity search → chunk retrieval within top-N entities

### D3: Chunking Integrated into Entity Ingestion

Extend `ingest_from_source.py` to chunk each file during ingestion:

1. Fetch file content (existing)
2. Build entity (existing)
3. Chunk content by markdown headings (port from `chunk_markdown_docs.py`)
4. Generate chunk embeddings (OpenAI, same model as entity)
5. Upsert chunks with `entity_id` FK
6. Upsert entity (existing)

Chunk metadata inherits from entity: `corpus`, `content_type`, `lifecycle_stage`, `source_id`.

**Chunking strategy:** Heading-based (current approach) with max token limit and overlap for large sections. This preserves document structure and enables section-level retrieval with heading hierarchy context.

### D4: Graph Materialization from Detected Edges

Add a post-ingestion step that writes `metadata.detected_edges` to Neo4j:

1. For each entity with `detected_edges`:
 - Create/update a node for the entity (label from `content_type`, properties from metadata)
 - For each detected edge, create/update the target concept node and relationship

```cypher
MERGE (source:Entity {id: $source_id})
SET source.title = $title, source.corpus = $corpus, source.content_type = $content_type
MERGE (target:Concept {id: $target_concept})
MERGE (source)-[r:EXTENDS {strength: $strength}]->(target)
SET r.rationale = $rationale
```

**Trigger:** Run after each ingestion batch (not per-entity, to batch Neo4j writes). Also provide `scripts/materialize_graph.py` for backfill.

### D5: Query Architecture — Three Modes

1. **Entity search** (existing) — semantic search over entity embeddings, returns document-level results with metadata
2. **Chunk search** (fix) — semantic search over chunk embeddings, returns passage-level results with heading context
3. **Hybrid search** (new) — entity search to find top-N documents, then chunk search within those entities for best passages

Extend the Query API (`api/query.py`) with:
- `POST /search` — entity search (existing)
- `POST /search/chunks` — chunk search (new)
- `POST /search/hybrid` — entity → chunk two-stage (new)
- `GET /graph/neighbors/{entity_id}` — graph traversal (new)

MCP server gets corresponding tools.

## Consequences

### Positive

- Single source of truth for content: one ingestion populates all layers
- Hybrid retrieval enables precise passage citation in RAG responses
- Graph becomes usable for concept navigation and relationship discovery
- Same embedding space across all layers and repos enables coherence scoring
- Chunks inherit entity metadata (corpus, lifecycle_stage) automatically

### Negative

- OpenAI API dependency for all embeddings (no local fallback)
- Ingestion becomes slower (chunking + more embeddings per file)
- More storage (chunk embeddings at 1536d vs current 768d)

### Risks

- Neo4j `detected_edges` reference `target_concept` IDs that may not correspond to actual entity IDs (they're concept slugs, not file-derived entity IDs). Need a concept resolution strategy.
- Re-embedding existing 103 chunks with OpenAI changes their vectors — existing chunk search results will differ

## Implementation Plan

- [x] Schema migration: add `entity_id` FK to `document_chunk`, re-create with 1536d vector column
- [x] Port chunking logic from `chunk_markdown_docs.py` into ingestion pipeline (`scripts/chunker.py`)
- [x] Switch chunk embeddings to OpenAI `text-embedding-3-small`
- [x] Add chunk upsert to `ingest_from_source.py` post-entity-build
- [x] Create `scripts/materialize_graph.py` for Neo4j backfill from existing entity edges
- [x] Add graph materialization step to ingestion pipeline
- [x] Extend Query API with `/search/chunks`, `/search/hybrid`, `/graph/neighbors`
- [x] Update MCP server with chunk search and graph tools
- [x] Re-ingest all sources to populate chunks and graph (184 entities, 3,664 chunks, 446 nodes, 553+ edges)
- [x] Deprecate standalone `chunk_markdown_docs.py` and `search_chunks.py` Ollama path (deleted)
- [x] Update USER_GUIDE.md with new query modes

## Session Log

### 2026-02-02

- Discovered three-layer sync gap during query capability testing
- Fixed `search_chunks.py` container name bug (`supabase-db` → `semops-hub-pg`)
- Confirmed: chunks from deprecated `project-ike-private` (5 files), Neo4j has 19/131 nodes
- Confirmed embedding model alignment: semops entities + semops-data both use `text-embedding-3-small`; chunks are the outlier with `nomic-embed-text`
- semops-data lineage scoring (Phase 4, #31) not yet implemented but will need same embedding space
- Created issue #114, wrote this ADR

## References

- [ADR-0005: Ingestion Strategy and Corpus Architecture](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/decisions/ADR-0005-ingestion-strategy-corpus-architecture.md)
- [: Unify chunk and entity ingestion pipelines](https://github.com/semops-ai/semops-core/issues/114)
- [: Ingestion v2](https://github.com/semops-ai/semops-core/issues/101)
- [: Agent provenance extension](https://github.com/semops-ai/semops-data/issues/31)
- [USER_GUIDE.md](../USER_GUIDE.md) — Current query documentation
