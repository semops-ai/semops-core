# semops-core Architecture

> **Repo:** `semops-core`
> **Role:** Schema/Infrastructure — Schema owner, knowledge base, and retrieval services for SemOps
> **Status:** ACTIVE
> **Version:** 3.2.0
> **Last Updated:** 2026-02-19
> **Infrastructure:** [INFRASTRUCTURE.md](INFRASTRUCTURE.md)
> **Related:** [SEARCH_GUIDE.md](SEARCH_GUIDE.md) (usage), [USER_GUIDE.md](USER_GUIDE.md) (ingestion)

## Role

This repo owns two things: the **domain model** (Pattern + Coherence as co-equal core aggregates, entity schema) and the **retrieval pipeline** (how content becomes searchable knowledge). The retrieval pipeline is the core architecture — it determines what agents across all repos can find and how precisely they can find it.

**Key distinction:** This repo owns *model* (what we know) and *infrastructure* (services), while `semops-dx-orchestrator` owns *process* (how we work).

## DDD Classification

> Source: [REPOS.yaml](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/REPOS.yaml)

| Property | Value |
| --- | --- |
| **Layer** | `semops-core` |
| **Context Type** | `core` |
| **Integration Patterns** | `shared-kernel` |
| **Subdomains** | `semantic-operations`, `knowledge-management` |

## Capabilities

> Source: [STRATEGIC_DDD.md](STRATEGIC_DDD.md) (authoritative capability registry)

| Capability | Description |
| --- | --- |
| Domain Data Model | Pattern schema, SKOS taxonomy, entity/edge tables, strategic views |
| Internal Knowledge Access | Semantic search (entity, chunk, hybrid), MCP server, Query API |
| Ingestion Pipeline | Source-based ingestion with LLM classification, chunking, embedding, graph |
| Agentic Lineage | Episode-centric provenance tracking for DDD operations |
| Pattern Management | Pattern registration, SKOS edge management, pattern coverage views |
| Coherence Scoring | Fitness functions, coverage views, coherence signal infrastructure |

Every capability traces to at least one registered pattern (coherence signal). See [STRATEGIC_DDD.md § Capability-Pattern Coverage](STRATEGIC_DDD.md#capability-pattern-coverage).

## Ownership

**Owns (source of truth for):**

- Global schema definitions (entity, edge, surface, delivery, pattern, brand)
- Domain language ([UBIQUITOUS_LANGUAGE.md](../schemas/UBIQUITOUS_LANGUAGE.md))
- Infrastructure services (Supabase, n8n, Qdrant, Neo4j)
- Knowledge graph and RAG pipelines
- MCP server and Query API for cross-repo agent access
- Strategic DDD model ([STRATEGIC_DDD.md](STRATEGIC_DDD.md))

**Does NOT own (consumed from elsewhere):**

- Process documentation (semops-dx-orchestrator)
- Global architecture docs (semops-dx-orchestrator)
- Cross-repo coordination patterns (semops-dx-orchestrator)
- Pattern YAML registry (semops-dx-orchestrator: `schemas/pattern_v1.yaml`)

**Ubiquitous Language conformance:** This repo is the owner of [UBIQUITOUS_LANGUAGE.md](../schemas/UBIQUITOUS_LANGUAGE.md). All domain terms in code and docs must match.

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

**Entity embeddings** are built from structured metadata — not the full document content. The `build_embedding_text` function in `generate_embeddings.py` assembles:

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

**Model:** OpenAI `text-embedding-3-small` (1536 dimensions) is used at both ingestion and query time. During ingestion, it embeds entity metadata and chunk content into stored vectors. At search time, it embeds the query string into the same vector space so cosine similarity scores are meaningful. The same model across all layers and repos ensures vector space alignment for cross-layer similarity and future coherence scoring with semops-data (ADR-0008, D1).

### Stage 4: Graph Materialization

LLM classification during ingestion detects relationships between entities and concepts (e.g., "semantic-operations EXTENDS domain-driven-design"). These are stored as `detected_edges` in entity metadata and materialized to Neo4j as typed graph edges.

The graph enables **relationship traversal** — a fundamentally different retrieval mode from vector similarity. After finding an entity via semantic search, agents can traverse the graph to discover related concepts, parent patterns, or downstream implementations.

**Key decision:** Graph materialization is decoupled from vector search. The graph answers "what is related to X?" while vector search answers "what is similar to my query?" These are complementary, not competing, retrieval strategies.

#### Graph as Edge Discovery Pipeline

The graph layer connects to the core DDD schema through a promotion pipeline. The domain model has two formal edge tables — `pattern_edge` (SKOS relationships between patterns) and `edge` (typed relationships between entities, patterns, and surfaces using PROV-O and strategic DDD predicates). These are the committed domain model, schema-enforced with constrained predicates.

Neo4j serves as the **discovery and exploration layer** between LLM detection and formal edge commitment:

```
LLM Classification Neo4j Graph PostgreSQL Schema
(detection) (exploration) (committed model)

detected_edges ──────────► Entity→Concept ·········► edge table
 in metadata nodes + rels (PROV-O, DDD predicates)
 (per-entity) (traversable)

 Pattern nodes ◄────────── pattern_edge table
 + SKOS rels (SKOS, adoption)
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

The MCP server (`api/mcp_server.py`) exposes two query surfaces to Claude Code agents in any repo: **semantic search** (content discovery via embeddings) and **ACL queries** (deterministic architectural lookups against the DDD schema).

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ semops-publisher │ │ semops-data │ │ semops-dx-orchestrator │
│ │ │ │ │ │
│ Claude Code │ │ Claude Code │ │ Claude Code │
│ agent │ │ agent │ │ agent │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
 │ │ │
 │ MCP (stdio) │ │
 └────────────┬───────┘────────────────────┘
 │
 ┌─────────▼──────────┐
 │ semops-kb MCP │
 │ │
 │ Semantic Search │ ┌──────────────────┐
 │ search_knowledge_ │ │ │
 │ base (entities) │────►│ PostgreSQL + │
 │ search_chunks │ │ pgvector │
 │ (passages) │ │ │
 │ list_corpora │ │ entity │
 │ │────►│ document_chunk │
 │ ACL Queries │ │ pattern │
 │ list_patterns │ │ pattern_edge │
 │ get_pattern │────►│ edge │
 │ search_patterns │ │ views: │
 │ list_capabilities │ │ capability_ │
 │ get_capability_ │ │ coverage │
 │ impact │ │ integration_ │
 │ query_integration │ │ map │
 │ _map │ │ repo_ │
 │ run_fitness_ │ │ capabilities │
 │ checks │ │ │
 └────────────────────┘ └──────────────────┘
```

**Registered in:** `~/.claude.json` (global) and `.mcp.json` (project-level)

### Two Query Surfaces for Two Purposes

| Query Type | Source of Truth | Purpose | Example |
|-----------|----------------|---------|---------|
| **Semantic (pgvector)** | Entity/chunk embeddings | Content discovery | "Find docs about semantic coherence" |
| **Structured (SQL)** | DDD tables — the ACL | Architectural truth | "Which patterns does this capability implement?" |

**Semantic search tools** (content discovery):
- `search_knowledge_base` for topic discovery and document-level context
- `search_chunks` for passage-level retrieval and precise citations
- `list_corpora` for available knowledge domains

**ACL query tools** (architectural truth — deterministic, same query = same answer):
- `list_patterns` — pattern registry with provenance filter and coverage stats
- `get_pattern` — single pattern with SKOS edges and coverage
- `search_patterns` — semantic search scoped to pattern definitions
- `list_capabilities` — capabilities with coherence signals (ADR-0009)
- `get_capability_impact` — full dependency graph: patterns → repos → integrations
- `query_integration_map` — DDD context map (repo-to-repo relationships)
- `run_fitness_checks` — database-level governance validation

The ACL tools query the strategic views (`pattern_coverage`, `capability_coverage`, `repo_capabilities`, `integration_map`) and base tables (`pattern`, `pattern_edge`, `edge`) directly. The shared query module (`scripts/schema_queries.py`) follows the same thin-wrapper pattern as `scripts/search.py`.

---

## Domain Model

### Core Aggregates: Pattern + Coherence

The SemOps domain model has two core aggregates that form the **Semantic Optimization Loop** (ADR-0012):

- **Pattern** (prescriptive) — what we should look like. An applied unit of meaning with a business purpose, organized via SKOS taxonomy with provenance tiers (1p/2p/3p) and adoption lineage (adopts/extends/modifies).
- **Coherence Assessment** (evaluative/directive) — how well reality matches intent, and what to do about it. Cross-cutting measurement that audits the Pattern → Capability → Script chain and drives pattern evolution, reversal, or realignment.

Pattern without Coherence is documentation. Coherence without Pattern is measurement without a reference. Together they are the Semantic Optimization Loop: Pattern pushes, Coherence aligns.

Patterns have provenance tiers:
- **3p (Third-party):** External standards we adopt (SKOS, PROV-O, DDD, Dublin Core, DAM)
- **2p (Collaborative):** Shared with partners
- **1p (First-party):** Our innovations that derive from 3p patterns

1p patterns **adopt**, **extend**, or **modify** 3p patterns via `pattern_edge` relationships.

**Capabilities** are Entities (DDD building block) — produced by Pattern decisions, audited by Coherence, implementing multiple patterns. They exist in the space between both core aggregates.

**Repositories** are Value Objects — identity doesn't matter, role and delivery mapping do. Repos can be reorganized without changing the domain model.

See [STRATEGIC_DDD.md](STRATEGIC_DDD.md) for the full aggregate map and DDD building block classifications.

### Core Tables

| Table | Purpose |
|-------|---------|
| `pattern` | Pattern Aggregate root — semantic units with SKOS properties |
| `pattern_edge` | Pattern relationships (SKOS + adopts, extends, modifies) |
| `entity` | Content, Capability, and Repository records (type discriminator) |
| `document_chunk` | Passages within entities, with embeddings and heading hierarchy |
| `edge` | Typed relationships (PROV-O, DDD predicates) |
| `surface` | Surface Aggregate root — publication/ingestion destinations |
| `delivery` | Content Aggregate child — entity-to-surface publishing with per-surface governance |
| `brand` | Brand Aggregate root — Schema.org Person/Organization/Brand |
| `product` | Brand Aggregate child — Schema.org Product |
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

## Key Components

### Scripts

Scripts are capability implementations — small, focused, independently runnable. Each traces to a capability listed in the [Capabilities](#capabilities) section above.

| Script | Capability | Purpose |
| --- | --- | --- |
| `scripts/ingest_from_source.py` | Ingestion Pipeline | Unified ingestion: entity + chunks + graph in one pass |
| `scripts/entity_builder.py` | Ingestion Pipeline | Merge source defaults + LLM classification into entity dicts |
| `scripts/source_config.py` | Ingestion Pipeline | YAML source config parser and routing rules |
| `scripts/chunker.py` | Ingestion Pipeline | Heading-aware markdown chunking with overlap |
| `scripts/classifiers/llm.py` | Ingestion Pipeline | LLM classification (content_type, concepts, edges) |
| `scripts/classifiers/rules.py` | Ingestion Pipeline | Rule-based classification (corpus routing) |
| `scripts/generate_embeddings.py` | Ingestion Pipeline | Entity embedding generation (`build_embedding_text`) |
| `scripts/docling_ingest.py` | Ingestion Pipeline | PDF/DOCX ingestion via Docling API |
| `scripts/github_fetcher.py` | Ingestion Pipeline | GitHub repo file fetching |
| `scripts/search.py` | Internal Knowledge Access | Shared search module (entity, chunk, hybrid) |
| `scripts/schema_queries.py` | Internal Knowledge Access | Shared ACL query module (patterns, capabilities, integrations) |
| `scripts/semantic_search.py` | Internal Knowledge Access | CLI for semantic search |
| `scripts/materialize_graph.py` | Internal Knowledge Access | Backfill detected_edges to Neo4j |
| `api/mcp_server.py` | Internal Knowledge Access | MCP server for cross-repo agent KB access (10 tools) |
| `api/query.py` | Internal Knowledge Access | Query API (REST endpoints, port 8101) |
| `scripts/init_schema.py` | Domain Data Model | Initialize PostgreSQL schema from phase2-schema.sql |
| `scripts/ingest_architecture.py` | Domain Data Model | Parse STRATEGIC_DDD.md → capability/repo entities + edges |
| `scripts/sync_neo4j.py` | Domain Data Model | Sync pattern/pattern_edge to Neo4j graph |
| `scripts/ingest_domain_patterns.py` | Pattern Management | Register patterns from pattern_v1.yaml |
| `scripts/bridge_content_patterns.py` | Pattern Management | HITL: extract detected_edges → human review → register |
| `scripts/lineage/tracker.py` | Agentic Lineage | LineageTracker context manager for ingestion runs |
| `scripts/lineage/episode.py` | Agentic Lineage | Episode model (operation, context, coherence_score) |
| `scripts/db_utils.py` | *(shared utility)* | Database connection (`get_db_connection`) |

### Other Components

| Component | Purpose |
| --- | --- |
| `schemas/UBIQUITOUS_LANGUAGE.md` | Domain definitions and business rules |
| `schemas/SCHEMA_REFERENCE.md` | Column specs, JSONB schemas, constraints |
| `schemas/phase2-schema.sql` | PostgreSQL schema implementation |
| `schemas/fitness-functions.sql` | Database-level governance checks (10 functions) |
| `config/sources/*.yaml` | Source configurations for ingestion routing |
| `docker-compose.yml` | Infrastructure stack |

---

## Dependencies

| Repo | What We Consume |
| --- | --- |
| *(none)* | This is the foundation layer |

| Repo | What Consumes Us |
| --- | --- |
| `semops-dx-orchestrator` | Schema definitions, UBIQUITOUS_LANGUAGE.md, MCP server |
| `semops-publisher` | Patterns, entities, knowledge base, MCP server |
| `semops-docs` | Schema definitions, patterns |
| `semops-data` | Docker services (pgvector), Query API, same embedding model for coherence scoring |
| `semops-sites` | Supabase data |

## Data Flows

```text
Source repos semops-core Consumers
(semops-docs, ┌─────────────────────────────────┐
 semops-publisher, │ │ CLI
 semops-dx-orchestrator) │ Ingestion │ (semantic_search.py)
 │ │ ├── Entity + metadata │
 │ GitHub │ ├── Chunks + content │ Query API
 └──────────► │ ├── Embeddings (OpenAI) │ (localhost:8101)
 fetch │ └── Graph edges (Neo4j) │
 │ │ MCP Server
 │ Retrieval │ (cross-repo agents)
 │ ├── Entity search (topics) │───► semops-publisher
 │ ├── Chunk search (passages) │───► semops-data
 │ └── Hybrid search (both) │───► semops-dx-orchestrator
 │ │───► semops-docs
 └─────────────────────────────────┘
```

---

## Related Documentation

- [SEARCH_GUIDE.md](SEARCH_GUIDE.md) — Search modes, CLI usage, API endpoints, MCP tools
- [USER_GUIDE.md](USER_GUIDE.md) — Ingestion pipeline, source configs, embedding generation
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) — Services, ports, troubleshooting, health checks
- [ADR-0008](decisions/ADR-0008-unified-ingestion-and-retrieval.md) — Unified ingestion and retrieval pipeline
- [ADR-0004](decisions/ADR-0004-schema-phase2-pattern-aggregate-root.md) — Pattern as aggregate root (partially superseded by ADR-0012)
- [ADR-0012](decisions/ADR-0012-pattern-coherence-co-equal-aggregates.md) — Pattern + Coherence as co-equal core aggregates
- [GLOBAL_ARCHITECTURE.md](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/GLOBAL_ARCHITECTURE.md) — System landscape
- [DIAGRAMS.md](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/DIAGRAMS.md) — Visual diagrams (context map, data flows, DDD model)
- [REPOS.yaml](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/REPOS.yaml) — Structured repo registry
- `docs/decisions/` — Architecture Decision Records for this repo

---

## Versioning Notes

**Status values:**

- `ACTIVE` — Current implemented state (one per doc type)
- `PLANNED-A`, `PLANNED-B`, `PLANNED-C` — Alternative future states

**When to create a PLANNED version:**

- Significant architectural changes under consideration
- Alternative approaches being evaluated
- Future state design for upcoming work
