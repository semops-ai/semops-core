# semops-core Architecture

> **Repo:** `semops-core`
> **Role:** Schema/Infrastructure — Schema owner, knowledge base, and retrieval services for SemOps
> **Version:** 3.0.0
> **Last Updated:** 2026-02-13
> **Related:** [INFRASTRUCTURE.md](INFRASTRUCTURE.md) (services), [SEARCH_GUIDE.md](SEARCH_GUIDE.md) (usage), [INGESTION_GUIDE.md](INGESTION_GUIDE.md) (ingestion)

---

## What This Repo Does

This repo owns two things: the **domain model** (Pattern as aggregate root, entity schema) and the **retrieval pipeline** (how content becomes searchable knowledge). The retrieval pipeline is the core architecture — it determines what agents across all repos can find and how precisely they can find it.

```
Source repos          semops-core                        Consumers
(semops-docs,     ┌─────────────────────────────────┐
 semops-publisher, │                                 │    CLI
 semops-dx-        │   Ingestion                     │    (semantic_search.py)
 orchestrator)     │   ├── Entity + metadata          │
     │            │   ├── Chunks + content           │    Query API
     │  GitHub    │   ├── Embeddings (OpenAI)        │
     └──────────► │   └── Graph edges (Neo4j)        │
        fetch     │                                 │    MCP Server
                  │   Retrieval                     │    (cross-repo agents)
                  │   ├── Entity search (topics)     │───►  semops-publisher
                  │   ├── Chunk search (passages)    │───►  semops-data
                  │   └── Hybrid search (both)       │───►  semops-dx-orchestrator
                  │                                 │───►  semops-docs
                  └─────────────────────────────────┘
```

---

## Retrieval Pipeline

The retrieval pipeline is a single flow from source file to searchable content. Each document passes through four stages, producing two searchable layers (entity + chunks) plus a graph layer.

### Stage 1: Ingestion

`ingest_from_source.py` fetches files from GitHub repos using YAML source configs. Each file becomes an **entity** (the document record) with metadata assigned by corpus routing rules and optionally enriched by LLM classification.

**Key decision:** Corpus and content type are assigned at ingestion time based on file path, not inferred at query time. This means filtering is a metadata lookup, not a semantic operation.

### Stage 2: Chunking

During ingestion, each file is split into **chunks** by markdown headings. Sections exceeding 512 tokens are split with 50-token overlap. Each chunk is stored in `document_chunk` with an `entity_id` foreign key back to its parent entity, inheriting `corpus` and `content_type`.

The heading hierarchy is preserved (e.g., `["Architecture", "Entities", "Attributes"]`), enabling section-level context in search results without re-parsing the source.

**Key decision:** Chunking is heading-based, not token-window-based. This preserves document structure and produces semantically coherent passages aligned with how authors organize their content. The tradeoff is uneven chunk sizes.

### Stage 3: Embedding

Two different embedding strategies produce two searchable layers:

**Entity embeddings** are built from structured metadata — not the full document content. The `build_embedding_text()` function in `generate_embeddings.py` assembles:

```
Title: Schema Reference
Summary: Column specifications for the entity table...
Type: architecture
Concept: database-schema
Subject areas: data-modeling, postgresql
Broader concepts: domain-driven-design, data-architecture
Narrower concepts: entity-table, document-chunk-table
```

This makes entity search effective for **topic discovery** — finding documents about a concept even when the query terms don't appear in the document text.

**Chunk embeddings** are built from actual passage content during ingestion. This makes chunk search effective for **precise retrieval** — finding the specific paragraph that answers a question.

**Key decision:** Using different source text for entity vs chunk embeddings is the defining architectural choice. It creates a two-layer retrieval system where the same query can find different things at each layer. Entity search for "embeddings" returns `schema-reference.md` (metadata topic match); chunk search returns the specific paragraph explaining the embedding column (content match). This is what enables the hybrid search pattern.

**Model:** OpenAI `text-embedding-3-small` (1536 dimensions) is used at both ingestion and query time. During ingestion, it embeds entity metadata and chunk content into stored vectors. At search time, it embeds the query string into the same vector space so cosine similarity scores are meaningful. The same model across all layers and repos ensures vector space alignment for cross-layer similarity and future coherence scoring with semops-data (ADR-0008: Unified Ingestion and Retrieval, D1).

### Stage 4: Graph Materialization

LLM classification during ingestion detects relationships between entities and concepts (e.g., "semantic-operations EXTENDS domain-driven-design"). These are stored as `detected_edges` in entity metadata and materialized to Neo4j as typed graph edges.

The graph enables **relationship traversal** — a fundamentally different retrieval mode from vector similarity. After finding an entity via semantic search, agents can traverse the graph to discover related concepts, parent patterns, or downstream implementations.

**Key decision:** Graph materialization is decoupled from vector search. The graph answers "what is related to X?" while vector search answers "what is similar to my query?" These are complementary, not competing, retrieval strategies.

#### Graph as Edge Discovery Pipeline

The graph layer connects to the core DDD schema through a promotion pipeline. The domain model has two formal edge tables — `pattern_edge` (SKOS relationships between patterns) and `edge` (typed relationships between entities, patterns, and surfaces using PROV-O and strategic DDD predicates). These are the committed domain model, schema-enforced with constrained predicates.

Neo4j serves as the **discovery and exploration layer** between LLM detection and formal edge commitment:

```
LLM Classification          Neo4j Graph              PostgreSQL Schema
(detection)                 (exploration)            (committed model)

detected_edges ──────────► Entity→Concept ·········► edge table
  in metadata                 nodes + rels              (PROV-O, DDD predicates)
  (per-entity)               (traversable)

                           Pattern nodes  ◄────────── pattern_edge table
                             + SKOS rels               (SKOS, adoption)
```

The flow works in both directions:

- **Forward (detection → commitment):** During ingestion, the LLM proposes relationships as `detected_edges`. These are materialized to Neo4j where they can be explored via graph traversal. Validated relationships are promoted to the `edge` table as formal predicates — `derived_from`, `cites`, `implements`, `documents`, etc. The graph drives which predicate edges get committed to the domain model.

- **Reverse (schema → graph):** The `pattern` and `pattern_edge` tables (the SKOS taxonomy) are synced to Neo4j via `sync_neo4j.py`, making the formal pattern hierarchy available for graph algorithms (community detection, centrality, orphan detection).

This parallels the **stable core / flexible edge** pattern from the domain model:

| Layer | Role | Governance |
|-------|------|------------|
| `pattern_edge` | SKOS taxonomy between patterns | Curated, schema-enforced |
| `edge` | Typed predicates between entities | Committed, predicate-constrained |
| Neo4j `detected_edges` | LLM-proposed relationships | Exploratory, awaiting promotion |

Detected edges in Neo4j are the **flexible edge** — model-proposed relationships that may be wrong, incomplete, or use free-form predicates. The `edge` table is the **stable core** — committed relationships with constrained predicates (`derived_from`, `cites`, `version_of`, `part_of`, `documents`, `depends_on`, `related_to`, `implements`, `delivered_by`, `integration`). Graph traversal and human review are the promotion gate between them.

---

## Two-Layer Retrieval Architecture

The pipeline above produces a hybrid search system decomposed into independent stages. This is the standard RAG pattern, but split so each stage can be used independently or combined.

### Three Search Modes

| Mode | What it searches | Embedding source | Best for |
|------|-----------------|-----------------|----------|
| **Entity search** | `entity.embedding` | Structured metadata | Topic discovery, document relevance |
| **Chunk search** | `document_chunk.embedding` | Passage content | Precise answers, specific citations |
| **Hybrid search** | Both (two-stage) | Both | Grounded generation with document context |

**Hybrid search** runs entity search first (find top-N relevant documents), then chunk search within those entities (find best passages per document). This answers "which documents are relevant, and where specifically within them?" — the standard retrieval pattern for RAG with precise citations.

### Why This Decomposition Matters

Keeping entity and chunk search as independent operations (rather than always running hybrid) gives consumers flexibility and agent efficiency — agentic processes retrieve only what they need rather than paying the cost of a full hybrid pipeline on every query:

- **Agentic composition** — agents efficiently and deterministically retrieve the right artifacts with metadata, then use LLMs for higher reasoning tasks like document composition, classification, or coherence scoring. Entity search finds relevant material; chunk search retrieves specific passages to cite.
- **Agent-driven classification** uses entity search alone to find pattern context without retrieving passage content
- **CLI diagnostic queries** default to chunk search for direct answers
- **RAG pipelines** use hybrid search for grounded generation
- **Graph exploration** starts from an entity found via search, then traverses relationships


The shared search module (`scripts/search.py`) implements all three modes as pure functions accepting a database connection and pre-computed embedding. The three transport layers (MCP server, Query API, CLI) are thin wrappers handling embedding generation and response formatting.

---

## Cross-Repo Agent Integration

The MCP server (`api/mcp_server.py`) exposes search to Claude Code agents in any repo. This is the primary cross-repo integration surface.

```
┌──────────────────┐  ┌──────────────┐  ┌──────────────────────┐
│ semops-publisher │  │ semops-data  │  │ semops-dx-           │
│                  │  │              │  │   orchestrator       │
│ Claude Code      │  │ Claude Code  │  │ Claude Code          │
│   agent          │  │   agent      │  │   agent              │
└──────┬───────────┘  └──────┬───────┘  └──────┬───────────────┘
       │                     │                  │
       │     MCP (stdio)     │                  │
       └─────────────┬───────┘──────────────────┘
                     │
           ┌─────────▼──────────┐
           │   semops-kb MCP    │
           │                    │
           │ search_knowledge_  │     ┌──────────────────┐
           │   base (entities)  │────►│                  │
           │ search_chunks      │     │  PostgreSQL +    │
           │   (passages)       │────►│  pgvector        │
           │ list_corpora       │     │                  │
           └────────────────────┘     └──────────────────┘
```

**Registered in:** `~/.claude.json` (global) and `.mcp.json` (project-level)

Agents choose search modes based on their task:
- `search_knowledge_base` for topic discovery and document-level context
- `search_chunks` for passage-level retrieval and precise citations
- Corpus filtering narrows results to relevant knowledge domains

---

## Domain Model

### Aggregate Root: Pattern

**Pattern** is the aggregate root for the semantic operations model — an applied unit of meaning with a business purpose, measured for semantic coherence and optimization.

Patterns have provenance tiers:
- **3p (Third-party):** External standards we adopt (SKOS, PROV-O, DDD, Dublin Core, DAM)
- **2p (Collaborative):** Shared with partners
- **1p (First-party):** Our innovations that derive from 3p patterns

1p patterns **adopt**, **extend**, or **modify** 3p patterns via `pattern_edge` relationships. This is the Semantic Optimization Loop: adopt standards, innovate on top.

### Core Tables

| Table | Purpose |
|-------|---------|
| `pattern` | Aggregate root — semantic units with SKOS properties |
| `pattern_edge` | Pattern relationships (adopts, extends, modifies) |
| `entity` | Content items (files, links) with embeddings and metadata |
| `document_chunk` | Passages within entities, with embeddings and heading hierarchy |
| `edge` | Entity relationships (PROV-O predicates) |
| `surface` | Publication/ingestion destinations |
| `delivery` | Entity-to-surface publishing with per-surface governance |
| `brand` | Schema.org Person/Organization/Brand |
| `product` | Schema.org Product |
| `ingestion_episode` | Provenance tracking for DDD operations |

Schema definitions: [UBIQUITOUS_LANGUAGE.md](../schemas/UBIQUITOUS_LANGUAGE.md), [SCHEMA_REFERENCE.md](../schemas/SCHEMA_REFERENCE.md), [phase2-schema.sql](../schemas/phase2-schema.sql)

---

## Episode-Centric Provenance

Ingestion tracks operations with episode-level provenance via the `ingestion_episode` table.

An Episode represents one meaningful operation that modifies the DDD layer (INGEST, CLASSIFY, DECLARE_PATTERN, PUBLISH, EMBED). Each episode captures:
- Which patterns were in context during the operation
- What model/agent made the decision
- Token usage and prompt hashes for reproducibility
- Coherence score (quality signal)
- Detected edges (model-identified relationships)

This answers "why was this classified this way?" — critical for a system where LLM classification shapes what agents can find via search.

**Location:** `scripts/lineage/`

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/search.py` | Shared search module — single source of truth for all search logic |
| `scripts/generate_embeddings.py` | Entity embedding generation (`build_embedding_text()` defines what entities are embedded from) |
| `scripts/ingest_from_source.py` | Unified ingestion: entity + chunks + graph in one pass |
| `api/mcp_server.py` | MCP server for cross-repo agent KB access |
| `api/query.py` | Query API (REST endpoints) |
| `scripts/lineage/` | Episode-centric provenance system |
| `schemas/UBIQUITOUS_LANGUAGE.md` | Domain definitions and business rules |
| `schemas/phase2-schema.sql` | PostgreSQL schema implementation |
| `docker-compose.yml` | Infrastructure stack |

---

## Dependencies

None — this is the foundation layer.

## Depended On By

| Repo | What it uses |
|------|--------------|
| `semops-dx-orchestrator` | Schema definitions, UBIQUITOUS_LANGUAGE.md |
| `semops-publisher` | Patterns, entities, knowledge base, MCP server |
| `semops-docs` | Schema definitions, patterns |
| `semops-data` | Docker services (pgvector), Query API, same embedding model for coherence scoring |
| `semops-sites` | Supabase data |

---

## Related Documents

- [SEARCH_GUIDE.md](SEARCH_GUIDE.md) — Search modes, CLI usage, API endpoints, MCP tools
- [INGESTION_GUIDE.md](INGESTION_GUIDE.md) — Ingestion pipeline, source configs, embedding generation
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) — Services, ports, troubleshooting, health checks
- ADR-0008: Unified Ingestion and Retrieval — Unified ingestion and retrieval pipeline
- ADR-0004: Pattern as Aggregate Root — Pattern as aggregate root
- [GLOBAL_ARCHITECTURE.md](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/GLOBAL_ARCHITECTURE.md) — System landscape
