# Project SemOps Ubiquitous Language

> A shared vocabulary for the Project SemOps domain, structured around the domain model and used by all team members and AI agents within this bounded context.
> **Version:** 8.0.0 | **Last Updated:** 2026-02-08

---

## About This Document

This is a **Ubiquitous Language** as defined by Eric Evans in Domain-Driven Design:

> *"A language structured around the domain model and used by all team members within a bounded context to connect all the activities of the team with the software."*
> — Evans, *DDD Reference* (2015)

**Scope:** Single bounded context across all Project SemOps repositories. All repos share this vocabulary — `semops-core` owns it; other repos consume it as a shared kernel.

**For column-level specifications, JSONB schemas, SQL types, and index details, see [SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md).**

---

## Domain Overview

**Semantic Operations (SemOps)** is a framework for aligning technology and organization to benefit from data, AI, and agentic systems. The framework posits that **meaning is the critical currency in knowledge work** — every business system, decision process, and AI integration depends on shared meaning.

Project SemOps is both the framework and its proving ground. The system builds a **knowledge-first digital publishing platform** where patterns (units of meaning) are the stable core, content artifacts are the output, and the architecture connecting them is itself a first-class domain concept.

### The SemOps Framework

SemOps is built on a mental model and three pillars:

- **Semantic Funnel** — A mental model grounding how meaning transforms through progressive stages (Data → Information → Knowledge → Understanding → Wisdom). Each transition increases uncertainty and requires more complex inputs.

- **Strategic Data** — A playbook for making data a first-class strategic asset. Data must be governed, structured, and treated as an organizational challenge.

- **Symbiotic Architecture** — Encode your strategy into your systems so humans and AI can operate from shared structure. DDD provides the foundation.

- **Semantic Optimization** — Elevate your organization to operate like well-designed software: agent-ready, self-validating, and expanding through patterns, not features.

Each pillar provides value independent of AI. Together, they create an environment where ideas exist as human-readable patterns that agents can work with directly, and AI performs better because it has wider context and a well-understood domain.

### Core Thesis

AI excels where systems enforce coherent meaning. **Semantic Coherence** — the degree to which human and machine knowledge is available, consistent, and stable — is both the goal and the measurable signal:

```text
SC = (Availability × Consistency × Stability)^(1/3)
```

If any dimension collapses, coherence collapses. The framework builds the conditions for coherence; AI is both a beneficiary and an accelerant.

### Semantic Optimization Loop

The fundamental process by which the system evolves:

1. **Adopt** established 3P standards (the stable baseline)
2. **Innovate** 1P on top (tracked, intentional deviations)
3. **Link** 1P to its 3P foundations via SKOS broader/narrower relationships
4. **Measure** coherence to validate the innovation

This loop applies at every level — from adopting a W3C standard to evolving a business process.

---

## Three-Layer Architecture

Project SemOps organizes into three layers (ADR-0009). Each layer has a distinct purpose, and each links upward to the layer above it:

```text
┌─────────────────────────────────────────────────┐
│  PATTERN (Core Domain)                          │
│  Stable semantic concepts — the WHY             │
│  ddd, skos, semantic-coherence, shared-kernel   │
├─────────────────────────────────────────────────┤
│  ARCHITECTURE (Strategic Design)        [NEW]   │
│  System structure — the WHAT and WHERE          │
│  Capabilities, Repos, Integration relationships │
│  Every capability traces to ≥1 pattern          │
├─────────────────────────────────────────────────┤
│  CONTENT (DAM - Publishing)                     │
│  Publishing artifacts — the output              │
│  Blog posts, articles, media                    │
│  Surface, Delivery, PIM/Brand                   │
└─────────────────────────────────────────────────┘
```

- **Content documents Patterns** — A blog post explains semantic coherence.
- **Architecture implements Patterns** — The ingestion pipeline capability implements the semantic-ingestion pattern.
- **Patterns are the stable core** everything traces to.

### Adopted Standards (3P)

These standards directly shaped the database schema — their concepts are embedded in table structures, edge predicates, and value objects. Capabilities adopt additional 3P standards documented in [STRATEGIC_DDD.md](../docs/STRATEGIC_DDD.md).

| Standard | Role | Layer |
|----------|------|-------|
| **DDD** (Domain-Driven Design) | Primary architecture. Bounded contexts, aggregates, ubiquitous language. | All |
| **SKOS** (W3C Simple Knowledge Organization System) | Pattern taxonomy. Broader/narrower/related relationships between patterns. | Pattern |
| **PROV-O** (W3C Provenance Ontology) | Content lineage. Derived_from, cites, version_of edges between entities. | Content |
| **Dublin Core** | Content attribution. Creator, rights, publisher metadata on entities. | Content |
| **DAM** (Digital Asset Management) | Content publishing. Approval workflows, multi-channel distribution. | Content |
| **Schema.org** | Actor modeling. Person, Organization, Brand types for CRM/PIM. | Content |

### 1P Innovations

Derived from the capability audit in [STRATEGIC_DDD.md](../docs/STRATEGIC_DDD.md). Each innovation applies the Semantic Optimization Loop: adopt 3P standards, then innovate 1P on top.

| 1P Pattern | What It Does | Capabilities | Built On (3P) |
|------------|-------------|--------------|----------------|
| **`semantic-coherence`** | Measurable signal: SC = (Availability x Consistency x Stability)^(1/3). The goal and the measure. | coherence-scoring | *(original 1P concept)* |
| **`semantic-ingestion`** | Every byproduct of ingestion becomes a queryable knowledge artifact — classifications, detected edges, coherence scores, embeddings. | ingestion-pipeline, research, agentic-composition | ETL, Medallion Architecture, MLOps |
| **`agentic-lineage`** | Extends lineage tracking with agent decision context and trust provenance. | agentic-lineage | OpenLineage, Episode Provenance |
| **`semantic-object-pattern`** | Patterns as the aggregate root — provenance-tracked, lineage-measured, AI-agent-usable semantic objects. | pattern-management | Knowledge Organization Systems, Pattern Language |
| **`scale-projection`** | Validate domain coherence by projecting architecture to scale. Manual HITL processes intentionally generate structured ML training data. | style-learning, synthesis-simulation, autonomous-execution | RLHF, SECI, CI/CD |
| **`symbiotic-enterprise`** | Enterprise systems treat architecture, data, and AI as first class. Humble tools become agent-addressable signal streams. | orchestration, context-engineering, attention-management, financial-pipeline | Platform Engineering, Context Engineering |

---

## Pattern Layer (Core Domain)

### Pattern

An **applied unit of meaning** with a business purpose, measured for semantic coherence and optimization. Patterns are stable semantic structures that can be adopted, extended, or modified.

Pattern is the **aggregate root** of the domain model — the single entity through which all access to the aggregate occurs. Patterns enforce invariants for the entire system. External systems reference patterns; internal details (content, deliveries) can evolve without breaking integrations.

**Characteristics:**

- Has a business purpose (not abstract theory alone)
- Measured for semantic coherence and optimization
- Connected to other patterns via SKOS relationships
- Referenced by entities, capabilities, and repositories
- Survives even if all content artifacts are deleted

**Why Pattern is the aggregate root:** What we were calling "concepts" and "domain patterns" are the same thing. `semantic-coherence` is a pattern. `ddd` is a pattern we adopt. The pattern survives even if all blog posts referencing it are deleted — it is the durable meaning, not the ephemeral packaging.

### Provenance

Provenance answers: **whose semantic structure is this?**

| Provenance | Meaning | Example |
|------------|---------|---------|
| **1P** (first party) | Operates in my system. May be a synthesis from 3P sources, but it's now incorporated and operational. | `semantic-coherence`, `stable-core-flexible-edge` |
| **2P** (second party) | Jointly developed with an external party. Partnership/collaborative. | — |
| **3P** (third party) | External reference. Industry standard or external IP we adopt as-is. | `ddd`, `skos`, `prov-o`, `dublin-core` |

**Key insight:** 1P does not mean "I invented this." It means "this semantic structure now operates in my system." The provenance lifecycle flows: 3P (adoption) → 1P (incorporation) → optionally 2P (collaboration).

### Pattern Type

Patterns are typed by their role in the knowledge architecture:

| Type | Purpose | Examples |
|------|---------|---------|
| **concept** | Theoretical/abstract knowledge — ideas, frameworks, principles that inform design but are not directly coded as system features | `scale-projection`, `symbiotic-enterprise`, `seci`, `pattern-language` |
| **domain** | Patterns that model the knowledge domain — what the system represents and reasons about | `ddd`, `skos`, `prov-o`, `semantic-coherence`, `semantic-ingestion` |
| **implementation** | Solution-space patterns — how we build, deploy, and integrate. Specific technical choices and methods applied to realize the domain model | `shared-kernel`, `medallion-architecture`, `jamstack`, `mirror-architecture`, `ci-cd` |

The 1P/3P distinction is handled by provenance, not by pattern type. A 3P standard like `skos` is a `domain` pattern with `provenance: 3p`. A technical choice like `medallion-architecture` is `implementation` with `provenance: 3p` (we adopted Databricks' pattern). A 1P innovation like `scale-projection` is a `concept` pattern with `provenance: 1p` (aspirational, not yet operational).

### Pattern Relationships

Patterns connect to each other through two relationship families:

**SKOS Hierarchy** — Taxonomic positioning:

- **broader** — This pattern is more specific than the target. `semantic-drift` is broader → `semantic-coherence`.
- **narrower** — This pattern is more general than the target. `semantic-coherence` is narrower → `semantic-drift`.
- **related** — Associative, non-hierarchical. `semantic-coherence` is related → `bounded-context`.

**Adoption Lineage** — How patterns build on each other:

- **adopts** — Uses a 3P pattern as-is. `semantic-operations` adopts `skos`.
- **extends** — Builds on a pattern with additions. `semantic-operations` extends `ddd`.
- **modifies** — Changes a pattern for specific use. `content-classify-pattern` modifies `dam`.

---

## Architecture Layer (Strategic Design)

The Architecture layer formalizes the strategic design of Project SemOps — what the system delivers and where implementation lives. These concepts were previously in prose documentation only; ADR-0009 made them first-class domain objects.

### Capability

**What the system delivers.** A capability is a named, bounded piece of functionality that implements one or more patterns and is delivered by one or more repositories.

**Business rule:** Every capability MUST trace to at least one pattern, either via a direct link or via `implements` edges. If a capability cannot trace to a pattern, either a pattern is missing from the registry or the capability lacks domain justification. **This is a measurable coherence signal.**

**Domain classifications:**

- **Core** — Differentiating capabilities that are unique to SemOps. Examples: `domain-data-model`, `internal-knowledge-access`, `coherence-scoring`, `semantic-ingestion`, `research`, `pattern-management`, `agentic-lineage`, `orchestration`, `context-engineering`, `autonomous-execution`.
- **Supporting** — Important but not differentiating. Examples: `publishing-pipeline`, `surface-deployment`, `agentic-composition`, `style-learning`, `synthesis-simulation`, `concept-documentation`.
- **Generic** — Commodity functionality. Examples: `attention-management`, `financial-pipeline`.

### Repository

**Where implementation lives.** A repository is a codebase that delivers one or more capabilities and has a defined role in the system architecture.

Repositories are not necessarily aligned to subdomains — some are subdomain-aligned (e.g., `semops-publisher` delivers publishing capabilities), others are containers for cross-cutting concerns (e.g., `semops-dx-orchestrator` delivers orchestration, context-engineering, and autonomous-execution).

### Integration Relationships

Rich, first-class edges between repositories, typed by DDD integration patterns:

| Integration Pattern | Power Dynamic | Example |
|---------------------|---------------|---------|
| **Shared Kernel** | Equal, shared artifact | semops-core ↔ semops-publisher share UBIQUITOUS_LANGUAGE.md |
| **Conformist** | Upstream defines, downstream conforms | semops-publisher conforms to semops-core schema |
| **Customer-Supplier** | Upstream serves downstream needs | semops-core supplies schema to semops-sites |

Integration edges carry metadata: what is shared, why this pattern was chosen, and which direction the dependency flows. Data flows are emergent from shared capabilities, not explicitly modeled.

---

## Content Layer (DAM Publishing)

The Content layer is the original purpose of the Entity table — digital publishing artifacts that document, explain, or package patterns.

### Entity (Content)

A **concrete content artifact** in the publishing domain. Entities are the ephemeral packaging of durable patterns — they can be created, modified, and deleted while the underlying patterns persist.

**Asset type** distinguishes two fundamentally different relationships to content:
- **File** — You possess the actual content (a PDF you own, a markdown file you wrote, an image you created)
- **Link** — An external reference to content you don't possess (a YouTube URL, an arXiv paper link, an external blog post)

**Orphan entities** have no pattern connection (`primary_pattern_id` is NULL). They float at the **flexible edge**, awaiting incorporation into the stable core (promotion = assigning a pattern) or rejection (deletion/archival).

### Surface

A **publication destination or ingestion source** — a channel, repository, site, or platform where content is published to or pulled from.

**Direction** defines the data flow:
- **Publish** — Content is pushed to this surface (your blog, your YouTube channel)
- **Ingest** — Content is pulled from this surface (external feeds, APIs you monitor)
- **Bidirectional** — Both publish and ingest (GitHub repos, collaborative platforms)

### Delivery

A **record of an entity published to or ingested from a surface.** Delivery is where per-surface governance lives — the same entity can have different approval states and visibility on different surfaces.

**Per-surface governance:**
- **Approval status** (`pending`, `approved`, `rejected`) — Is this content ready for this specific surface?
- **Visibility** (`public`, `private`) — Who can see this content on this surface?

This design means the same blog post can be `approved` + `public` on WordPress but `pending` + `private` on LinkedIn. Governance is per-surface, not global.

**Delivery lifecycle:** `planned` → `queued` → `published`. Failed deliveries can be retried. Published content can be `removed`.

**Delivery role:** Each entity has at most one `original` delivery (its primary publication). Additional deliveries are `syndication` (cross-postings to other surfaces).

---

## Entity (Unified)

The Entity table uses a **type discriminator** to serve three purposes within a single table:

| Entity Type | Layer | Purpose | Key Relationships |
|-------------|-------|---------|-------------------|
| **content** | Content | DAM publishing artifact | Delivered to surfaces, documented by patterns |
| **capability** | Architecture | What the system delivers | Implements patterns, delivered by repositories |
| **repository** | Architecture | Where implementation lives | Delivers capabilities, integrates with other repositories |

All entity types share: an ID, an optional primary pattern link, flexible metadata, and a vector embedding for semantic search. The metadata schema varies by type — content entities carry filespec and attribution, capabilities carry domain classification and pattern links, repositories carry role and GitHub URL.

**Why one table, not three:** The shared infrastructure (embeddings, pattern links, edges) is identical. A type discriminator avoids duplicating tables while enabling type-specific behavior through metadata schemas and views.

---

## Edge

A **typed, directional relationship** between entities, patterns, and surfaces. Edges are the connective tissue of the knowledge graph.

### Content Lineage (PROV-O)

How content entities relate to each other:

- **derived_from** — Created by transforming a source (a transcript derived from a video)
- **cites** — Formal reference for support or attribution
- **version_of** — A new version of existing content
- **part_of** — Component of a larger whole
- **documents** — Explains or covers in detail

### Strategic Design (ADR-0009)

How architecture entities relate to patterns and each other:

- **implements** — A capability implements a pattern (capability → pattern)
- **delivered_by** — A capability is delivered by a repository (capability → repository)
- **integration** — A DDD integration relationship between repositories (repository → repository)

### Domain Extensions

General-purpose relationships:

- **depends_on** — Requires another entity for definition or function
- **related_to** — Associated without hierarchy

### Edge Strength

A **confidence or importance signal** from 0.0 to 1.0. A strength of 1.0 means "this relationship is definitive." Lower values indicate weaker association or lower confidence. Strength must always be within bounds.

---

## Provenance and Lineage

### Ingestion Run

A **bounded execution of an ingestion pipeline.** A run contains multiple episodes — one per operation performed. Runs track the pipeline lifecycle from start to completion or failure, capturing source configuration for reproducibility and aggregated metrics.

**Run types:** Manual (human-triggered), scheduled (cron), or agent-triggered (autonomous).

### Ingestion Episode

A **single agent operation that modifies the domain model**, tracked automatically for provenance. Episodes capture the full context of what happened, why, and with what quality — enabling audits like "why was this classified this way?"

**Operations include:** Ingesting a new entity from source, classifying an entity against patterns, declaring a new pattern from research synthesis, publishing a delivery, establishing an edge, generating an embedding.

**Key properties:**

- **Automatic capture** — Lineage is emitted by instrumented operations, not created manually
- **Episode as context unit** — Each episode records which patterns and entities were considered, the coherence score, and the agent's proposed relationships
- **Detected edges** — Model-proposed relationships that haven't yet been committed to the edge table, preserving the agent's assessment for human review

---

## Actors (CRM/PIM)

### Brand (Unified Actor)

A **unified actor table** representing people, organizations, and commercial brands. Rather than separate tables, Brand uses a type discriminator:

- **Person** — Individual people (the owner, contacts, connections)
- **Organization** — Companies and institutions
- **Brand** — Commercial identities (SemOps, product lines)

This enables flexible relationship modeling: Tim Mitchell (person) → owns → Semantic Operations (brand) → offers → SemOps Consulting (product).

Brands can link to a 1P pattern, answering: "what does this actor commercialize?"

### Product

**What you sell**, connected to a brand (who offers it) and optionally a pattern (what methodology it packages). Products represent consulting services, white papers, courses, and other offerings.

### Brand Relationship

**CRM-style connections** between actors and products. Flexible predicates capture who knows whom, who owns what, and who's interested in what product. Metadata provides context (where you met, the source of the relationship).

---

## Business Rules

### Pattern as Aggregate Root

- Pattern is the primary aggregate root — the stable core (SKOS-based)
- Content entities belong to the DAM supporting domain — ephemeral packaging (Dublin Core)
- Capabilities and repositories belong to the Architecture layer (DDD Strategic Design)
- All entity types reference patterns to be part of the stable system

### Stable Core vs. Flexible Edge

- **Stable core:** Patterns + entities with pattern connections
- **Flexible edge:** Orphan content entities without pattern connections
- Orphans are temporary — audit processes promote or reject them
- Promotion = assigning a pattern; rejection = deletion or archival

### Per-Surface Governance

- Approval status and visibility live on Delivery, not on Entity
- Same entity can have different states on different surfaces
- Governance decisions are per-surface because audiences and standards differ

### Capability-Pattern Coverage

- Every capability must trace to at least one pattern (ADR-0009 coherence signal)
- Coverage is tracked via the `capability_coverage` view
- Gaps indicate either missing patterns or unjustified capabilities
- This is a CRITICAL-severity fitness function

### Delivery Constraints

- At most one delivery with role `original` per entity
- Private deliveries cannot target public surfaces
- Deliveries should be approved before being published
- Published deliveries must have a `published_at` timestamp

### Relationship Integrity

- Edge endpoints must reference existing entities, patterns, or surfaces
- Pattern edges must reference existing patterns on both sides
- Edge strength must be between 0.0 and 1.0
- Integration edges require metadata (integration_pattern and direction)

---

## Corpus (Knowledge Organization)

A **named partition** of the knowledge base that determines schema integration level, retention policy, and retrieval scope. Corpus assignment is the first-order routing decision during ingestion.

| Corpus | Integration | Retention | Purpose |
|--------|------------|-----------|---------|
| **DDD Core** | Full (Pattern + Entity + Edge) | Permanent | Curated knowledge: registered patterns, domain patterns, canonical theory |
| **Deployment** | Entity + Edge | Permanent | Operational artifacts: ADRs, session notes, architecture docs |
| **Published** | Full + Delivery | Permanent + tracked | Blog posts, public docs (re-ingested for coherence measurement) |
| **Research** | Optional (Entity only) | Project-scoped | 3P external research; can promote to core |
| **Ephemeral** | None (vectors only) | Session/temporary | Experiments, WIP, throwaway |

**Key insight:** A pattern like `semantic-coherence` is the attractor for all related content across corpora. Whether it's a theory doc (core), an ADR deploying it (deployment), or a blog post explaining it (published) — all feed the same pattern's understanding. Corpus controls the promotion gate and retrieval priority, not knowledge boundaries.

### Promotion Paths

Content moves between corpora as its status changes:

- **Research → Core** — 3P content reveals a pattern we adopt (creates Pattern record)
- **Deployment → Core** — Operational artifact crystallizes into a pattern
- **Ephemeral → Research** — Experiment becomes structured investigation
- **Published → Core** — Published content becomes canonical reference

### Lifecycle Stage

Where an entity is in the knowledge lifecycle. Distinct from delivery approval (which gates publication to surfaces). Adopted from 3P patterns: CI/CD artifact promotion, Backstage software catalog lifecycle, DDD aggregate lifecycle.

| Stage | Meaning | Coherence Role | Examples |
|-------|---------|---------------|---------|
| **draft** | Pre-delivery. Ideas, unvalidated, planned work. | Forecast zone — coherence predicts fit | Open issues, feature branches, draft narratives, blog ideas |
| **active** | Validated, operational. Merged, deployed, in use. | Measured for coherence, not baseline | Merged code, deployed configs, operational docs |
| **stable** | Trusted coherence baseline. Authoritative. | **IS the baseline** — semantic anchor for classifiers and scoring | Domain patterns, canonical theory docs, published ADRs |
| **deprecated** | Signaled for retirement. Still visible. | Excluded from baseline, flagged for migration | Superseded ADRs, replaced approaches |
| **archived** | Removed from operational system. | Excluded from search and scoring | Abandoned experiments, deleted branches (retained for lineage) |

**Lifecycle stage is sticky** — iteration (re-ingestion, updates) does not reset the stage. The episode chain records what changed; coherence scoring detects if the change introduced drift.

**Governance model:**

```text
Pattern (WHY)           →  Lifecycle defines WHAT states mean
Architecture (WHAT)     →  Governance defines WHO can transition
Content (output)        →  Episodes record THAT it happened
```

The governance matrix is universal — same behavior for ALL entity types across all 5 stages. Entity type only determines the creation/iteration mechanism, not whether governance applies.

---

## Domain Model

```text
Pattern (aggregate root — core domain)
    │
    ├── pattern_edge (SKOS: broader, narrower, related)
    │                (Adoption: adopts, extends, modifies)
    │
    ├── Entity: capability (implements patterns, delivered by repos)
    │       │
    │       └── edge: delivered_by → Entity: repository
    │
    ├── Entity: repository (delivers capabilities, integrates with repos)
    │       │
    │       └── edge: integration → Entity: repository
    │
    └── Entity: content (DAM — documents patterns)
            │
            ├── edge (PROV-O: derived_from, cites, version_of, etc.)
            │
            └── Delivery (per-surface governance)
                    │
                    └── Surface (publication destinations)

Brand (CRM/PIM actors)
    │
    ├── Product (what you sell)
    └── Brand Relationship (who knows whom)

Ingestion Run (provenance — operational)
    │
    └── Ingestion Episode (per-operation lineage)
```

---

## Evolution Guidelines

**Adding new terms:**
1. Propose definition in PR with usage examples
2. Ensure no conflicts with existing terms
3. Update this document and [SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md) as appropriate
4. Add validation rules if applicable

**Changing definitions:**
1. Mark as MAJOR schema version change
2. Provide migration path for existing data
3. Update all dependent documentation
4. Communicate changes to affected systems

**Deprecating terms:**
1. Mark as deprecated with replacement guidance
2. Support old term for one minor version cycle
3. Remove in next major version with migration

---

**Document Status:** Active | **Schema Version:** 8.0.0
**Maintainer:** Project SemOps Schema Team
**Change Process:** All updates require schema governance review
**Companion:** [SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md) for column specs, JSONB schemas, and technical details
