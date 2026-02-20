# Strategic DDD: Capabilities, Repos, and Integration

> **Version:** 1.2.0
> **Last Updated:** 2026-02-19
> **Status:** Draft (ADR-0009, ADR-0012)
> **Related:** [ADR-0009](decisions/ADR-0009-strategic-tactical-ddd-refactor.md) | [ADR-0012](decisions/ADR-0012-pattern-coherence-co-equal-aggregates.md) | [Issue #122](https://github.com/semops-ai/semops-core/issues/122) | [Issue #142](https://github.com/semops-ai/semops-core/issues/142)

This document formalizes the Strategic DDD layer for SemOps. It defines **capabilities** (what the system delivers), **repositories** (where implementation lives), and **integration patterns** (how repos relate).

These concepts were previously captured only in GLOBAL_ARCHITECTURE.md prose. This document makes them structured, queryable, and traceable to patterns.

---

## Principles

1. **Repos are functionally aligned to model organizational roles** and manage agent boundaries and context.
2. **Repos are recognizable nodes in an "Agentic Enterprise"** — each scopes what an AI agent needs to do useful work, simulating team structure.
3. **Every capability traces to >=1 pattern.** If it can't, either a pattern is missing or the capability lacks domain justification.
4. **Data flows are emergent** from shared capability participation, not explicitly modeled.
5. **Integration relationships are first-class** — rich edges with DDD integration pattern typing.
6. **SemOps has one bounded context** with a single ubiquitous language.
7. **Capabilities decompose into scripts** — small, focused, identifiable files rather than buried in large applications (anti-monolith). Each script is a bounded piece of executable functionality that can be replaced and audited independently.

### Repos, Bounded Contexts, and the DDD Repository Pattern

Three uses of "repository" coexist in SemOps — understanding the distinction is important for reading this document and for DDD alignment:

1. **Git repositories (repos)** — the physical code boundaries listed in the [Repository Registry](#repository-registry) below. These are **agent role boundaries**, not bounded contexts. Each repo scopes what an AI agent (or human) needs in context to do useful work, simulating team structure in a one-person operation. Repos can be reorganized — merged, split, renamed — without changing the domain model. When that happens, the `repository` entity mappings in this document update, but `capability` and `pattern` entities don't.

2. **Bounded Contexts** — the semantic boundaries where a particular domain model and ubiquitous language apply. SemOps has a layered context structure described in [SYSTEM_LANDSCAPE.md](SYSTEM_LANDSCAPE.md): **SemOps Core** (semops-dx-orchestrator, semops-core, semops-data) is the product — always present regardless of domain. **Domain applications** (Content: semops-publisher, semops-docs, semops-sites; Operations: semops-backoffice) are pluggable contexts that consume Core but own their own domain logic. The key boundary rule: Core never depends on a domain application. Domain applications depend on Core.

3. **DDD Repository pattern** — the data access abstraction that mediates between the domain model and the transactional data layer (OLTP), responsible for retrieving and persisting Aggregates. Currently this lives in **semops-core** — the ingestion scripts, entity builders, and edge creation logic that persist domain objects to PostgreSQL. This is distinct from **semops-data**, which is the analytics/research layer (OLAP) — it reads from the domain model for coherence scoring, Research RAG, and profiling, but doesn't persist aggregates. The Repository pattern handles concerns like tenant isolation at the infrastructure layer, keeping the domain model unaware of which tenant or deployment context it operates within.

This OLTP/OLAP distinction maps to the [Four Data System Types](https://github.com/semops-ai/semops-docs/blob/main/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/STRATEGIC_DATA/four-data-system-types.md) framework: semops-core is the **Application Data System** (transactional, DDD-governed), semops-data is the **Analytics Data System** (read-heavy, dimensional). GitHub issues, projects, and session notes are the **Enterprise Work System** (unstructured knowledge artifacts). semops-backoffice's financial pipeline is an **Enterprise Record System** (canonical truth, double-entry constraints). Each system type has different scaling physics, governance approaches, and integration patterns — understanding which type you're operating in determines which DDD patterns apply.

The relationship between these three is itself a [Scale Projection](https://github.com/semops-ai/semops-docs/blob/main/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/EXPLICIT_ARCHITECTURE/scale-projection.md) proof: because the mapping from domain model (capabilities, patterns) to physical boundaries (repos) is explicit and queryable in this document, changing the physical structure is an infrastructure decision. The architecture — what this document captures — remains stable.

---

## Domain Model: Aggregates and Building Blocks

The SemOps domain model contains multiple aggregates, each with its own root, lifecycle, and invariants (ADR-0012). The two **core aggregates** form the Semantic Optimization Loop — the feedback cycle that makes SemOps more than a knowledge graph.

### Core Aggregates

| Aggregate | Root | Children / Value Objects | Invariants |
| --- | --- | --- | --- |
| **Pattern** | `pattern` | `pattern_edge` | Valid SKOS hierarchy, provenance rules, unique preferred_label |
| **Coherence Assessment** | *(deferred — schema when operational)* | measurements, gaps, actions | Must reference >=1 pattern, lifecycle state machine |

**Pattern** is the prescriptive force — what we should look like. It defines stable meaning via SKOS taxonomy, provenance tiers (1P/2P/3P), and adoption lineage (adopts/extends/modifies).

**Coherence Assessment** is the evaluative/directive force — how well reality matches intent, and what to do about it. It audits the Pattern → Capability → Script chain across all aggregates and can drive pattern evolution, reversal, or realignment. Coherence is audit by default, not a gate — the flexible edge is free to exist. Aggregate root invariants protect the stable core. See ADR-0012 §3 for details.

Three modes of coherence: **Governance** (something exists without justification), **Discovery** (something aligns but isn't tracked — the most valuable mode, compounds over time), **Regression** (something that was coherent broke).

### Supporting Aggregates

Each supporting aggregate traces to a 3P pattern that prescribes its structure.

| Aggregate | Root | Children | 3P Pattern |
| --- | --- | --- | --- |
| **Content** (DAM) | `entity` (content) | `delivery` (publication records), edges | DAM, Dublin Core |
| **Surface** | `surface` | `surface_address` | DAM (channels) |
| **Brand** (PIM/CRM) | `brand` | `product`, `brand_relationship` | Schema.org, PIM *(unregistered)* |

### DDD Building Block Classifications

| Concept | DDD Building Block | Rationale |
| --- | --- | --- |
| **Capability** | Entity | Has identity and lifecycle. Produced by Pattern decisions, audited by Coherence. Implements multiple patterns — can't be a child of any single Pattern. Exists in the space between both core aggregates, owned by neither. |
| **Repository** | Value Object | Identity doesn't matter — role and delivery mapping do. Repos can be reorganized (merged, split, renamed) without changing the domain model. |

### The Semantic Optimization Loop

```text
Pattern ──produces──→ Capability
   ↑                      ↓
   └──── Coherence ←──audits──┘
         (informs)

Pattern pushes. Coherence aligns.
```

When `semantic-optimization` becomes operational, coherence scoring becomes the objective function — Pattern sets the target, Coherence measures the gap, the optimization loop minimizes the gap. The existing agentic lineage system (episodes with `coherence_score` fields) provides the telemetry layer. See ADR-0012 §10.

---

## Capability Registry

A **capability** is what the system delivers. It implements one or more Patterns. It is delivered by one or more repos. Capability-to-pattern coverage is a measurable coherence signal.

### Core Domain Capabilities

These are the differentiating capabilities aligned with the [Semantic Operations Framework](https://github.com/semops-ai/semops-docs/blob/main/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/README.md).— what makes SemOps unique.

| ID | Capability | Implements Patterns | Delivered By |
|----|-----------|-------------------|--------------|
| `domain-data-model` | Domain Data Model | `ddd`, `skos`, `prov-o`, `explicit-architecture` | semops-core |
| `internal-knowledge-access` | Internal Knowledge Access | `agentic-rag` | semops-core |
| `coherence-scoring` | Coherence Scoring | `semantic-coherence` | semops-data, semops-core |
| `ingestion-pipeline` | Ingestion Pipeline | `semantic-ingestion`, `etl`, `medallion-architecture`, `mlops` | semops-core |
| `agentic-lineage` | Agentic Lineage | `agentic-lineage`, `open-lineage`, `episode-provenance` | semops-core, semops-data |
| `research` | Research | `semantic-ingestion`, `raptor` | semops-data |
| `pattern-management` | Pattern Management | `semantic-object-pattern`, `knowledge-organization-systems`, `pattern-language`, `explicit-architecture` | semops-core, semops-dx-orchestrator |
| `orchestration` | Orchestration | `explicit-enterprise`, `platform-engineering`, `explicit-architecture` | semops-dx-orchestrator |
| `context-engineering` | Context Engineering | `explicit-enterprise`, `context-engineering` | semops-dx-orchestrator |
| `autonomous-execution` | Autonomous Execution | `scale-projection`, `ci-cd`, `containerization` | semops-dx-orchestrator |

#### Ingestion Pipeline Detail

The ingestion pipeline orchestrates multiple 3P patterns (ETL, Medallion Architecture, MLOps) into a unified flow where every semantic byproduct is a first-class knowledge artifact. The innovation (`semantic-ingestion`, 1P) is that intermediate results — classifications, detected edges, coherence scores, embeddings — are all captured and queryable, not discarded.

```text
Sources (multi-source extraction)
┌─────────────────────────────────────────────────────────────────┐
│  Domain patterns    Architecture specs   Research & standards   │
│  & theory (MD)      & ADRs (markdown)    (PDF/DOCX)            │
│                                                                 │
│  config/sources/    GitHub repos          Docling API           │
│  *.yaml                                                         │
└────────────┬──────────────┬───────────────────┬─────────────────┘
             │              │                   │
             ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  EXTRACT — Source-specific fetchers produce raw content         │
│  [ETL: Extract]                                                 │
│                                                                 │
│  • GitHubFetcher: clone/API → markdown files                   │
│  • Docling: PDF/DOCX → structured markdown                     │
│  • Sheets: Google Sheets API → entity dicts                    │
│  • Frontmatter parsing (YAML metadata extraction)              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  CLASSIFY — LLM-powered semantic classification                │
│  [MLOps: LLM classification pipeline]                          │
│                                                                 │
│  • LLMClassifier (Claude): content_type, primary_concept,      │
│    broader/narrower concepts, concept_ownership (1p/2p/3p),    │
│    detected_edges, subject_area, summary                       │
│  • Corpus routing: path-pattern rules → corpus + content_type  │
│  • Lifecycle stage assignment (draft/active/stable/deprecated/archived) │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  BUILD — Entity construction                                    │
│  [ETL: Transform] + [Medallion: Bronze→Silver enrichment]      │
│                                                                 │
│  • EntityBuilder: merge source defaults + derived attributes   │
│    + LLM classification → entity dict                          │
│  • Filespec (source URI, hash, size)                           │
│  • Attribution (creator, rights, organization)                 │
│  • Metadata (content_type, corpus, lifecycle_stage, etc.)      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  LOAD — Multi-target persistence                                │
│  [ETL: Load] + [MLOps: embedding generation]                   │
│                                                                 │
│  • PostgreSQL: entity upsert, edge creation                    │
│  • Chunking: markdown → heading-aware chunks (for RAG)         │
│  • Embeddings: OpenAI text-embedding-3-small → document_chunk  │
│  • Qdrant: vector index for semantic search                    │
│  • Neo4j: graph sync (pattern/entity relationships)            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  SCORE — Coherence measurement                                  │
│  [MLOps: MLflow experiment tracking]                           │
│                                                                 │
│  • Coherence scoring against pattern taxonomy                  │
│  • MLflow: experiment tracking, model comparison               │
│  • Feedback into pattern-management (gap detection)            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  LINEAGE — Episode tracking (agentic-lineage capability)       │
│                                                                 │
│  • Every operation wrapped in LineageTracker episodes          │
│  • Operations: ingest, classify, embed, create_edge, publish   │
│  • Captures: inputs, context patterns, outputs, quality        │
└─────────────────────────────────────────────────────────────────┘
```

**Key innovation (semantic-ingestion):** A traditional ETL pipeline discards intermediate results. A traditional RAG pipeline only keeps chunks + embeddings. Semantic ingestion captures *every byproduct* — LLM classifications, detected edges, coherence scores, concept ownership signals — as first-class knowledge artifacts that feed back into the domain model.

### Supporting Domain Capabilities

These are capabilities used to create the published content that is the marketing product of SemOps. They are based on standard (3p) domain patterns. They are used as examples and showcase of the core domain as part of the SemOps project, but are not necessary to define the Semantic Operations Framework, nor are they unique to SemOps.

| ID | Capability | Implements Patterns | Delivered By |
|----|-----------|-------------------|--------------|
| `publishing-pipeline` | Publishing Pipeline | `dam`, `dublin-core` | semops-publisher |
| `surface-deployment` | Surface Deployment | `dam` | semops-sites |
| `agentic-composition` | Agentic Composition | `semantic-ingestion`, `agentic-rag`, `zettelkasten` | semops-publisher |
| `style-learning` | Style Capture | `scale-projection`, `rlhf`, `seci` | semops-publisher |
| `synthesis-simulation` | Synthesis and Simulation | `scale-projection`, `semops-dataofiling`, `data-lineage`, `data-modeling`, `synthetic-data` | semops-data |
| `concept-documentation` | Concept Documentation | `ddd` | semops-docs |

**Publishing Pipeline** consolidates content creation, MDX transformation, and style governance into a single DAM capability in semops-publisher.

**Agentic Composition** is the general pattern of compose-from-structured-data: pattern identification → corpus building → structure definition → fit matching → agent assembly. Uses hybrid search (SQL entities + vector chunks) from `internal-knowledge-access` to treat entities and chunks as composable atoms. Resume composition is the current implementation; the pattern generalizes to any structured-data-to-composed-output workflow. Implements `zettelkasten` (3P — atomic interconnected knowledge units), `agentic-rag` (3P — hybrid retrieval), and `semantic-ingestion` (1P — ingestion creates the composable atoms).

> **Bounded context candidate:** Agentic composition applied to domain-specific outputs (e.g., resume composition, [motorsport-consulting](https://github.com/semops-ai/motorsport-consulting) proposals) may warrant a **second bounded context**. These use SemOps infrastructure and patterns but serve a different domain with its own ubiquitous language (STAR bullets, job fit, industry naming for resumes; consulting proposals for motorsport). This would challenge ADR-0009 decision #6 ("SemOps has one bounded context") — the integration pattern would be Customer-Supplier, with SemOps providing composable atoms and the domain context consuming them with its own interpretation.

**Surface Deployment** covers web publishing and content delivery — the semops-sites side of the DAM pipeline.

> **Gap noted:** semops-sites also manages visual design governance — font management, per-brand Mermaid diagram styles, and other design system concerns with agentic elements. This likely warrants a separate `design-system` capability (3P: design systems/design tokens; possible Scale Projection 1P for the agentic progression). To be formalized in a future review.

**Style Learning** (`/capture-on`, `/capture-off`, `/capture-edits`) is a HITL feedback loop that captures editorial edits with intent, building structured YAML training data. Implements **Scale Projection** (1P) — an intentional progression from manual slash-command HITL (Level 1) through structured sidecar events (Level 2) to eventual RLHF model training (Level 5). See [semops-dx-orchestrator#96](https://github.com/semops-ai/semops-dx-orchestrator/issues/96) for the Scale Projection framework.

**Synthesis and Simulation** covers synthetic data generation (SDV, Faker), stack simulation (S3 → Delta Lake → Snowflake), data profiling, and scenario modeling (e.g., Plumbus product data — BOM, ERP, PIM, SKU). Implements **Scale Projection** (1P) — intentionally building from simple local scenarios to production-scale data engineering. The 3P foundations are standard data engineering patterns: data profiling, data lineage, data modeling, and AI-driven synthetic data generation.

---

### Capability Traceability

The system enforces a full traceability chain from stable meaning to executable code:

```text
Pattern → Capability → Script
(why)      (what)       (where it runs)
```

- **Pattern → Capability** — every capability must trace to at least one pattern. Gaps indicate missing patterns or unjustified capabilities. Tracked in this document (Capability Registry above).
- **Capability → Script** — capabilities decompose into small, focused scripts (Principle 7). Each script is a bounded piece of executable functionality that can be identified, replaced, and audited independently. Tracked in per-repo `ARCHITECTURE.md` "Key Components" sections.
- **Lineage** — git provides the change history for scripts. Comments and docstrings provide intent. No separate registry is needed at current scale.

This chain is the primary audit domain of Coherence Assessment (ADR-0012 §6). Every break in the chain is a coherence finding — the fix can go in either direction (create a capability, delete a script, or discover that a script is already part of an existing capability). See [Coherence Signals](#coherence-signals) for how this is measured today.

> **Capability registry:** This document (above)
> **Per-repo script inventory:** Each repo's `ARCHITECTURE.md` § Key Components
> **Library → Capability crosswalk:** [GLOBAL_INFRASTRUCTURE.md § Stack Ecosystem](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/GLOBAL_INFRASTRUCTURE.md#stack-ecosystem)
> **Audit:** `/arch-sync` Step 5 (per-repo), `/global-arch-sync` Step 4e (cross-repo)

---

### Generic Domain Capabilities

These are capabilities adopted to run various operation components for Semops, but not necessarily differentiating. Some may be promoted if unique alignment with Semops evolves.

| ID | Capability | Implements Patterns | Delivered By |
|----|-----------|-------------------|--------------|
| `attention-management` | Attention Management | `explicit-enterprise`, `task-management` | semops-backoffice |
| `financial-pipeline` | Financial Pipeline | `explicit-enterprise`, `accounting-system` | semops-backoffice |

Generic capabilities implement **`explicit-enterprise`** (1P) — the principle that enterprise systems treat architecture, data, and AI as first class, with humble tools (email, calendars, accounting) becoming agent-addressable signal streams rather than applications. Each capability's 3P pattern is the primitive enterprise equivalent it replaces. See [explicit-enterprise](https://github.com/semops-ai/semops-docs/blob/main/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/EXPLICIT_ARCHITECTURE/explicit-enterprise.md).

---

## Repository Registry

A **repository** is where implementation lives. Repos deliver capabilities.

| ID | Repo | Role | Delivers Capabilities |
|----|------|------|----------------------|
| `semops-core` | semops-core | Schema/Infrastructure | `domain-data-model`, `internal-knowledge-access`, `ingestion-pipeline`, `agentic-lineage`, `pattern-management`, `coherence-scoring` |
| `semops-dx-orchestrator` | semops-dx-orchestrator | Platform/DX | `orchestration`, `context-engineering`, `autonomous-execution`, `pattern-management` |
| `semops-publisher` | semops-publisher | Publishing | `publishing-pipeline`, `agentic-composition`, `style-learning` |
| `semops-docs` | semops-docs | Documents | `concept-documentation` |
| `semops-data` | semops-data | Product/Data | `research`, `coherence-scoring`, `agentic-lineage`, `synthesis-simulation` |
| `semops-sites` | semops-sites | Frontend | `surface-deployment` |
| `semops-backoffice` | semops-backoffice | Operations | `attention-management`, `financial-pipeline` |

---

## Integration Patterns

Repos interact through DDD integration patterns. These describe how repos relate to the **domain model**, not the database.

### Current Integration Map

| Source Repo | Target Repo | DDD Pattern | What's Shared | Direction |
|-------------|-------------|-------------|---------------|-----------|
| semops-core | semops-publisher | **Shared Kernel** | UBIQUITOUS_LANGUAGE.md, Pattern/Entity schema | Bidirectional |
| semops-core | semops-docs | **Shared Kernel** | UBIQUITOUS_LANGUAGE.md, Pattern/Entity schema | Bidirectional |
| semops-dx-orchestrator | all repos | **Published Language** | GLOBAL_ARCHITECTURE.md, process docs, ADR templates | Downstream reads |
| semops-core | semops-data | **Customer-Supplier** | Qdrant, Docling, Supabase services | Upstream provides |
| semops-core | semops-sites | **Customer-Supplier** | Supabase data, API access | Upstream provides |
| semops-publisher | semops-core | **Conformist** | Adopts Pattern/Entity model as-is | Downstream conforms |
| semops-docs | semops-core | **Conformist** | Adopts Pattern/Entity model as-is | Downstream conforms |
| semops-backoffice | semops-core | **Anti-Corruption Layer** | Translates shared PostgreSQL to financial domain | ACL at boundary |
| semops-publisher | semops-sites | **Customer-Supplier** | MDX content, resume seed.sql, fonts/templates | Bidirectional supply |

### Integration Relationship Metadata

Each integration relationship should capture:

```yaml
source_repo: semops-core
target_repo: semops-publisher
integration_pattern: shared-kernel    # DDD integration pattern (a 3P Pattern record)
shared_artifact: UBIQUITOUS_LANGUAGE.md
direction: bidirectional
rationale: "Both repos must agree on domain terms; changes require coordination"
established: 2025-12-22              # When this integration was formalized
```

This metadata will be stored as Edge records with `integration` predicate between repository entities, typed by the DDD integration Pattern.

---

## Coherence Signals

The signals below are the current implementation of coherence measurement — stateless sensors that run, report, and forget. When Coherence Assessment becomes operational as a first-class aggregate (ADR-0012), these sensors feed into assessments that gain identity, lifecycle, and action tracking. The three modes of coherence (governance, discovery, regression) classify what each signal detects. See [Domain Model](#domain-model-aggregates-and-building-blocks) above.

### Capability-Pattern Coverage

Every core/supporting capability should trace to at least one Pattern. Current assessment:

| Capability | Pattern Coverage | Gap? |
|-----------|-----------------|------|
| `domain-data-model` | `ddd`, `skos`, `prov-o`, `explicit-architecture` (1p) | No |
| `internal-knowledge-access` | `agentic-rag` (3p) | **New pattern needed** — `agentic-rag` |
| `coherence-scoring` | `semantic-coherence` | No |
| `ingestion-pipeline` | `semantic-ingestion` (1p), `etl` (3p), `medallion-architecture` (3p), `mlops` (3p) | **New patterns needed** — all four |
| `agentic-lineage` | `agentic-lineage` (1p), `open-lineage` (3p), `episode-provenance` (3p) | **New patterns needed** — all three |
| `research` | `semantic-ingestion` (1p), `raptor` (3p) | No — patterns exist or planned |
| `pattern-management` | `semantic-object-pattern` (1p), `knowledge-organization-systems` (3p), `pattern-language` (3p), `explicit-architecture` (1p) | **New patterns needed** — all three |
| `publishing-pipeline` | `dam` (3p), `dublin-core` (3p) | No |
| `agentic-composition` | `semantic-ingestion` (1p), `agentic-rag` (3p), `zettelkasten` (3p) | **New pattern needed** — `zettelkasten` |
| `surface-deployment` | `dam` (3p) | No |
| `style-learning` | `scale-projection` (1p), `rlhf` (3p), `seci` (3p) | **New patterns needed** — all three |
| `synthesis-simulation` | `scale-projection` (1p), `semops-dataofiling` (3p), `data-lineage` (3p), `data-modeling` (3p), `synthetic-data` (3p) | **New patterns needed** — all four 3p |
| `concept-documentation` | `ddd` (3p) | Possible — may need specific pattern |
| `orchestration` | `explicit-enterprise` (1p), `platform-engineering` (3p), `explicit-architecture` (1p) | **New patterns needed** — both |
| `context-engineering` | `explicit-enterprise` (1p), `context-engineering` (3p) | **New patterns needed** — both |
| `autonomous-execution` | `scale-projection` (1p), `ci-cd` (3p), `containerization` (3p) | **New patterns needed** — `ci-cd`, `containerization` |
| `attention-management` | `explicit-enterprise` (1p), `task-management` (3p) | **New patterns needed** — both |
| `financial-pipeline` | `explicit-enterprise` (1p), `accounting-system` (3p) | **New patterns needed** — both |

**Action items:**

- Register `agentic-rag` as 3p pattern. Sources: [arXiv survey](https://arxiv.org/abs/2501.09136), [IBM](https://www.ibm.com/think/topics/agentic-rag), [Microsoft Azure](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview), [NVIDIA](https://developer.nvidia.com/blog/traditional-rag-vs-agentic-rag-why-ai-agents-need-dynamic-knowledge-to-get-smarter/)
- Register `agentic-lineage` as 1p concept pattern (SemOps innovation — extends OpenLineage with agent decision context and trust provenance)
- Register `open-lineage` as 3p domain pattern (adopted standard for data flow lineage)
- Register `episode-provenance` as 3p domain pattern (adopted pattern for episode-centric provenance tracking)
- SKOS: `agentic-lineage` --broader--> `open-lineage`, `agentic-lineage` --broader--> `episode-provenance`
- Register `semantic-ingestion` as 1p concept pattern (SemOps innovation — unified pipeline where every byproduct becomes a queryable knowledge signal)
- Register `etl` as 3p domain pattern (Extract, Transform, Load)
- Register `mlops` as 3p domain pattern (ML Operations / experiment tracking)
- Register `medallion-architecture` as 3p domain pattern (Bronze→Silver→Gold progressive enrichment; source: [Databricks](https://www.databricks.com/glossary/medallion-architecture))
- SKOS: `semantic-ingestion` --broader--> `etl`, `semantic-ingestion` --broader--> `medallion-architecture`, `semantic-ingestion` --broader--> `mlops`
- Register `knowledge-organization-systems` as 3p domain pattern (LIS/NISO Z39.19 — controlled vocabularies, authority control, taxonomy management)
- Register `pattern-language` as 3p domain pattern (Alexander 1977 / GoF 1994 — structured pattern documentation and cataloguing)
- Register `semantic-object-pattern` as 1p concept pattern (SemOps innovation — patterns as provenance-tracked, lineage-measured, AI-agent-usable semantic objects; the aggregate root of the domain model)
- SKOS: `semantic-object-pattern` --broader--> `knowledge-organization-systems`, `semantic-object-pattern` --broader--> `pattern-language`
- Register `scale-projection` as 1p concept pattern (SemOps innovation — validate domain coherence by projecting architecture to scale; manual HITL processes intentionally generate structured data that becomes ML training data. See [semops-dx-orchestrator#96](https://github.com/semops-ai/semops-dx-orchestrator/issues/96))
- Register `rlhf` as 3p domain pattern (Reinforcement Learning from Human Feedback — human corrections improve AI output)
- Register `seci` as 3p domain pattern (Nonaka's knowledge creation model — Socialization, Externalization, Combination, Internalization; tacit→explicit knowledge conversion)
- SKOS: `scale-projection` --broader--> `rlhf`, `scale-projection` --broader--> `seci`
- Register `zettelkasten` as 3p domain pattern (Luhmann — atomic, interconnected knowledge notes as composable units; foundation for treating entities/chunks as composable atoms in agentic composition)
- Register `semops-dataofiling` as 3p domain pattern (data quality measurement, statistical profiling, schema inference)
- Register `data-lineage` as 3p domain pattern (tracking data flow and transformation provenance across systems)
- Register `data-modeling` as 3p domain pattern (conceptual/logical/physical data modeling tools and methods)
- Register `synthetic-data` as 3p domain pattern (AI-driven synthetic data generation — SDV, Faker, privacy-preserving test data)
- SKOS: `scale-projection` --broader--> `semops-dataofiling`, `scale-projection` --broader--> `synthetic-data` (synthesis-simulation context)
- Register `explicit-enterprise` as 1p concept pattern (SemOps innovation — enterprise systems that treat architecture, data, and AI as first class; humble tools become agent-addressable signal streams. See [explicit-enterprise.md](https://github.com/semops-ai/semops-docs/blob/main/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/EXPLICIT_ARCHITECTURE/explicit-enterprise.md))
- Register `platform-engineering` as 3p domain pattern (cross-system orchestration, aggregation, dependency management, operational intelligence)
- Register `context-engineering` as 3p domain pattern (emerging AI pattern — designing context windows, system prompts, and agent boundaries for effective LLM operation)
- Register `ci-cd` as 3p domain pattern (continuous integration/continuous delivery — automated testing, build, deployment pipelines)
- Register `containerization` as 3p domain pattern (Docker, sandboxing — isolated execution environments for safe agent autonomy)
- SKOS: `explicit-enterprise` --broader--> `platform-engineering`, `explicit-enterprise` --broader--> `context-engineering`
- SKOS: `scale-projection` --broader--> `ci-cd`, `scale-projection` --broader--> `containerization` (autonomous-execution context)
- Register `task-management` as 3p domain pattern (personal productivity and attention management — GTD, Eisenhower, time blocking)
- Register `accounting-system` as 3p domain pattern (double-entry bookkeeping, ledger systems — beancount, plain-text accounting)
- SKOS: `explicit-enterprise` --broader--> `task-management`, `explicit-enterprise` --broader--> `accounting-system`
- **Define pattern naming convention and audit existing names.** Current names are generic abbreviations (`etl`, `mlops`, `dam`, `ddd`) or vague labels (`semantic-ingestion`) that don't convey domain meaning. Establish a convention (e.g., descriptive slug vs. acronym, when to use full name vs. abbreviation) and audit all pattern IDs for clarity and consistency.

### Capability-Repo Coverage

Every capability should have at least one delivering repo. Current registry shows full coverage.

### Script-Capability Coverage

Every script in `scripts/` should trace to a capability. Conversely, every capability should decompose into at least one script. This extends the traceability chain (see [Capability Traceability](#capability-traceability)) into a measurable signal:

| Signal | Meaning |
| ------ | ------- |
| Script with no capability trace | Unjustified code — either missing attribution or a candidate for removal |
| Capability with no scripts | Unimplemented intent — either aspirational or implemented outside `scripts/` |
| Script attributed to wrong capability | Misalignment — the script's actual function doesn't match its stated capability |

Script inventories live in each repo's `ARCHITECTURE.md` "Key Components" section. The `/arch-sync` workflow (Step 5) audits per-repo coverage; `/global-arch-sync` (Step 4e) checks cross-repo.

### Library-Capability Crosswalk

Libraries appearing in multiple repos signal shared infrastructure candidates and patterns stable enough for deterministic scripts. A simple analysis of `pyproject.toml` across repos reveals:

| Signal | Meaning |
| ------ | ------- |
| Library in 3+ repos, no shared module | Convergence candidate — standardize in `semops-core` |
| Library declared but not imported | Phantom dependency — tech debt, candidate for removal |
| Library used by scripts with no capability trace | Unjustified infrastructure — cost without architectural purpose |
| Library overlap across different capabilities | Shared abstraction candidate (e.g., `pydantic` for settings across repos) |

The crosswalk maps `Library → Repo → Script → Capability`, closing the loop between infrastructure choices and architectural intent. This is maintained in [GLOBAL_INFRASTRUCTURE.md § Stack Ecosystem](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/GLOBAL_INFRASTRUCTURE.md#stack-ecosystem).

---

## Schema Representation

These strategic concepts will be represented in the schema as:

- **Capabilities** → `entity` with `entity_type: capability`, metadata containing capability-specific fields
- **Repositories** → `entity` with `entity_type: repository`, metadata containing repo-specific fields
- **Integration relationships** → `edge` records between repository entities with `integration` predicate
- **Capability-Pattern links** → `edge` records with `implements` predicate (or `primary_pattern_id` for single-pattern capabilities)
- **Capability-Repo links** → `edge` records with `delivered_by` predicate

See [ADR-0009](decisions/ADR-0009-strategic-tactical-ddd-refactor.md) for schema migration details.

### Sample Queries

Every table in this document is parsed into the database by `ingest_architecture.py`. The following queries demonstrate what becomes queryable — these are the governance questions that `explicit-architecture` turns into SQL.

**Which patterns does a capability implement?**

```sql
SELECT e.src_id AS capability, p.name AS pattern, p.provenance
FROM edge e
JOIN pattern p ON p.id = e.dst_id
WHERE e.predicate = 'implements'
  AND e.src_id = 'domain-data-model';
```

**Which capabilities lack pattern justification? (governance gap)**

```sql
SELECT capability_id, capability_name, pattern_count, repo_count
FROM capability_coverage
WHERE pattern_count = 0;
```

**Which patterns have no capabilities implementing them?**

```sql
SELECT pattern_id, pattern_name, capability_count, content_count
FROM pattern_coverage
WHERE capability_count = 0
ORDER BY content_count DESC;
```

**Which repos deliver a given capability?**

```sql
SELECT repo_id, repo_name, repo_role, capability_name
FROM repo_capabilities
WHERE capability_id = 'pattern-management';
```

**How do two repos integrate?**

```sql
SELECT source_repo_id, target_repo_id, integration_pattern,
       shared_artifact, direction
FROM integration_map
WHERE source_repo_id = 'semops-core'
   OR target_repo_id = 'semops-core';
```

**What's the derived lifecycle stage of each capability?**

```sql
SELECT id, title, metadata->>'lifecycle_stage' AS lifecycle,
       metadata->>'domain_classification' AS domain
FROM entity
WHERE entity_type = 'capability'
ORDER BY metadata->>'domain_classification', title;
```

**Full traceability: pattern → capability → repo (three-layer model)**

```sql
SELECT p.name AS pattern, p.provenance,
       c.title AS capability,
       r.title AS repository
FROM pattern p
JOIN edge ei ON ei.dst_id = p.id AND ei.predicate = 'implements'
JOIN entity c ON c.id = ei.src_id AND c.entity_type = 'capability'
JOIN edge ed ON ed.src_id = c.id AND ed.predicate = 'delivered_by'
JOIN entity r ON r.id = ed.dst_id AND r.entity_type = 'repository'
WHERE p.id = 'explicit-architecture'
ORDER BY c.title, r.title;
```

---

## Evolution

This document is the **source of truth** for strategic DDD concepts. When capabilities, repos, or integration patterns change:

1. Update this document first
2. Create/update corresponding entity and edge records in the schema
3. Verify coherence signals (capability-pattern, script-capability, library-capability)
4. Update GLOBAL_ARCHITECTURE.md DDD Alignment section

When aggregate structure or DDD building block classifications change, update [ADR-0012](decisions/ADR-0012-pattern-coherence-co-equal-aggregates.md) and the [Domain Model](#domain-model-aggregates-and-building-blocks) section above.
