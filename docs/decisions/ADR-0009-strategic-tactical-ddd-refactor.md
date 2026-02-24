# ADR-0009: Strategic/Tactical DDD Refactor — Three-Layer Architecture

> **Status:** In Progress
> **Date:** 2026-02-07
> **Related Issue:** [](https://github.com/semops-ai/semops-core/issues/122)
> **Supersedes:** Portions of ADR-0004 Section "Structure" and ADR-0005 Section 3 "DDD Core Three Layers"
> **Blocks:** #115, #117

## Executive Summary

Strategic DDD was never formally defined — we jumped straight to Tactical DDD (Pattern as aggregate root, Entity as DAM layer). This created scope creep in the DAM Entity layer, missing strategic concepts (capabilities, integration relationships), and overloading of `pattern_type`. This ADR introduces a three-layer architecture that separates **Pattern** (core domain — the WHY), **Architecture** (strategic design — the WHAT/WHERE), and **Content** (DAM publishing — the output).

## Context

### What worked (ADR-0004 decisions that remain valid)

1. **Pattern as aggregate root** — Stable, proven, no change needed.
2. **SKOS for pattern relationships** — Working well for taxonomy.
3. **PROV-O for entity edges** — Sound provenance model.
4. **Per-surface governance on Delivery** — Correct separation of concerns.
5. **Provenance on Pattern** (1p/2p/3p) — Right place for ownership signal.

### What's broken

1. **DAM Entity layer scope creep** — DAM was intended for digital publishing artifacts (blog posts, articles, media). It became a catch-all for "everything that isn't a Pattern," including architecture metadata (repos, data flows, subdomains) that doesn't belong there.

2. **Missing Strategic DDD** — Subdomains, context map, and integration patterns are documented in GLOBAL_ARCHITECTURE.md prose but not formalized in the domain model. There's no place in the schema for strategic-level concepts.

3. **Pattern aggregate root overloading** — `pattern_type` tries to classify concepts, domain patterns, architecture metadata, AND topology under one aggregate. Architecture and topology aren't patterns — they're structural metadata.

4. **Naming collision** — Schema "Entity" means "DAM content artifact," not "DDD Entity" (domain object with identity/lifecycle). This causes confusion when discussing domain modeling.

### Design session insights (2026-02-07)

Socratic exploration of 10 SemOps "things" revealed:
- **Blog posts** are DAM's original purpose (publishing artifacts with surface/delivery/PIM).
- **`content-classify-pattern`** is NOT a pattern — it's an implementation detail referencing Zettelkasten (which IS a pattern).
- **Repos** have dual nature — some are subdomain-aligned, others are containers.
- **Integration relationships** (conformist, shared-kernel) need to be first-class, queryable, with rich context.
- **Capabilities** are the bridge between repos and patterns — repos deliver capabilities; capabilities implement patterns.
- **Subdomains** were "just in my head" — they need to be formalized as capability groupings.
- **Data flows** are emergent from shared capabilities, not explicitly modeled.

## Decision

### Three-layer architecture

```
┌─────────────────────────────────────────────────┐
│ PATTERN (Core Domain) │
│ Stable semantic concepts — the WHY │
│ ddd, skos, semantic-coherence, shared-kernel │
├─────────────────────────────────────────────────┤
│ ARCHITECTURE (Strategic Design) [NEW] │
│ System structure — the WHAT and WHERE │
│ Capabilities, Repos, Integration relationships │
│ Every capability traces to ≥1 pattern │
├─────────────────────────────────────────────────┤
│ CONTENT (DAM - Publishing) │
│ Publishing artifacts — the output │
│ Blog posts, articles, media │
│ Surface, Delivery, PIM/Brand │
└─────────────────────────────────────────────────┘
```

Each layer links upward: Content documents Patterns. Architecture implements Patterns. Patterns are the stable core everything traces to.

### Entity table with type discriminator

Single `entity` table, three entity types with different metadata schemas:

```
entity (one table, type discriminator)
├── content → DAM atoms, rolled up via Surface/Delivery/Brand/Product
├── capability → WHAT the system delivers, traces to ≥1 Pattern
└── repository → WHERE implementation lives, delivers capabilities
```

All share: `id`, `primary_pattern_id`, `metadata` (JSONB), `embedding`.

**content** — DAM publishing artifacts. Surface, Delivery, PIM/brand via existing publication layer. Individual posts are atoms; DAM/PIM roll them up into products/brands.

**capability** — What the system delivers. Implements >=1 Pattern. Delivered by >=1 repo. Has documentation and implementation code. Examples: "Publishing Pipeline", "Domain Knowledge Base", "Coherence Scoring".

**repository** — Where implementation lives. Delivers capabilities. Has role, status. Some are subdomain-aligned, others are just containers.

### Key relationships

```
Pattern ←[implements]── Capability ←[delivered_by]── Repo
Pattern ←[documents]─── Content (DAM)
Repo ───[integration]──→ Repo (typed by DDD integration pattern)
```

- **Capability → Pattern**: Every capability MUST trace to >=1 pattern. If it can't, either a pattern is missing from the registry or the capability lacks domain justification. This is a measurable coherence signal.
- **Integration relationships**: Rich edges between repos, typed by DDD integration patterns (shared-kernel, conformist, etc.). The pattern IS a Pattern record (3P); the specific relationship is an Edge with metadata (why, when, what schema).
- **Data flows**: Emergent from shared capabilities, NOT explicitly modeled. "Publishing Pipeline" capability connects semops-publisher → semops-sites.
- **Subdomains**: Groupings of capabilities. Cross-cutting, not repo-aligned. Documented in GLOBAL_ARCHITECTURE.md, referenced in metadata.

### Key decisions

1. **DDD is the primary architecture.** DAM, SKOS, PROV-O bolt on as adopted 3P patterns serving specific roles within DDD.
2. **Entity is one table with type discriminator** (content, capability, repository). Not three separate tables.
3. **Every capability must trace to >=1 pattern.** Capability-to-pattern coverage is a coherence signal.
4. **Data flows are emergent from capabilities**, not explicitly modeled.
5. **Subdomains are groupings of capabilities**, not repo boundaries. Repos are agent role boundaries.
6. **SemOps has one bounded context** (single UBIQUITOUS_LANGUAGE.md). `bounded-context` should not be a pattern_type.
7. **Integration relationships are rich, first-class edges** between repos, typed by DDD integration patterns.
8. **1P concepts that become methods** (like semantic-coherence) are modeled as two linked Patterns: concept (broader) + operational method (narrower).

### pattern_type enum changes

| Current | Proposed | Rationale |
|---------|----------|-----------|
| `concept` | **Keep** | Theoretical/abstract knowledge |
| `domain` | **Keep** | Applied/operational patterns |
| `architecture` | **Remove** | Not a pattern — becomes `entity_type: capability` or `entity_type: repository` |
| `topology` | **Remove** | Not a pattern — emergent from capability/repo relationships |

### What stays, what changes

| Concept | Current state | Proposed state |
|---------|--------------|----------------|
| Pattern (aggregate root) | Exists | Unchanged, but audited for non-patterns |
| Pattern Edge (SKOS) | Exists | Unchanged |
| Entity (DAM) | Exists, overloaded | Scoped to `entity_type: content`, DAM publishing only |
| Entity (architecture) | Doesn't exist | `entity_type: capability` and `entity_type: repository` |
| Edge (PROV-O) | Exists | Enriched with `implements`, `delivered_by`, `integration` predicates |
| Surface, Delivery | Exists | Unchanged, scoped to content entities |
| Brand, Product | Exists | Unchanged, scoped to content entities |
| pattern_type enum | concept, domain, architecture, topology | `concept`, `domain` only |
| Capability | Doesn't exist | New entity_type with implements-pattern constraint |

## Consequences

### Positive

- **Clear separation of concerns** — Each layer has a defined purpose. No more "is this a pattern or an entity?"
- **Strategic DDD formalized** — Capabilities, repos, and integration patterns become queryable.
- **Coherence measurement** — Capability-to-pattern coverage provides a measurable quality signal.
- **DAM layer recovers original intent** — Content publishing artifacts only, as designed.
- **Pattern table cleaned up** — Architecture/topology concepts move to entity layer where they belong.

### Negative

- **Schema migration required** — Existing entities may need `entity_type` backfill.
- **Edge predicate expansion** — New predicates (`implements`, `delivered_by`, `integration`) need to be added.
- **Multi-document update** — UBIQUITOUS_LANGUAGE.md, GLOBAL_ARCHITECTURE.md, ADR-0005 all need revision.

### Risks

- **Over-modeling** — Capability/repo entities could become maintenance overhead if not populated from real data.
- **primary_pattern_id insufficiency** — Capabilities may need many-to-many pattern relationships (single FK may not suffice). Mitigation: use edges with `implements` predicate instead of or in addition to `primary_pattern_id`.

## Implementation Plan

### Phase 1: Strategic DDD formalization (this ADR)

1. Define capability registry — what capabilities exist, which repos deliver them, which patterns they implement
2. Formalize subdomain definitions as capability groupings
3. Clarify integration patterns between repos with rich metadata
4. Determine where strategic concepts live in the schema

### Phase 2: Schema changes (separate issue)

1. Add `entity_type` discriminator to Entity table (`content`, `capability`, `repository`)
2. Define metadata schemas per entity_type
3. Add edge predicates: `implements`, `delivered_by`, `integration`
4. Scope existing DAM constraints to `entity_type: content`
5. Audit Pattern table — remove implementation details that aren't patterns
6. Remove `architecture` and `topology` from pattern_type metadata values

### Phase 3: Artifact updates

1. ~~Split `schemas/UBIQUITOUS_LANGUAGE.md` into proper DDD Ubiquitous Language + `schemas/SCHEMA_REFERENCE.md` (data dictionary) — this repo~~ **DONE**
2. `semops-dx-orchestrator/docs/GLOBAL_ARCHITECTURE.md` — update DDD Alignment section → [](https://github.com/semops-ai/semops-dx-orchestrator/issues/99)
3. `semops-dx-orchestrator/docs/decisions/ADR-0005` — revise Section 3 (DDD Core Three Layers) → [](https://github.com/semops-ai/semops-dx-orchestrator/issues/99)
4. Register `ubiquitous-language` as 3P pattern → [](https://github.com/semops-ai/semops-dx-orchestrator/issues/100)

## Session Log

### 2026-02-07: Design session, ADR creation, capability review

- Socratic exploration of 10 SemOps "things" to determine their nature
- Identified three-layer architecture (Pattern / Architecture / Content)
- Decided on entity table with type discriminator (not separate tables)
- Created this ADR and STRATEGIC_DDD.md
- Phase 1 initial draft: 19 capabilities, 5 subdomains, 7 repos, 9 integration relationships
- **Capability review session** — refined core capabilities through Socratic review:
 - `domain-knowledge-base` decomposed into `domain-data-model` (DDD schema as structured data; implements `ddd`, `skos`, `prov-o`) + `internal-knowledge-access` (agentic RAG for operational queries; implements `agentic-rag`)
 - `semantic-search` absorbed into `internal-knowledge-access` (implementation detail)
 - `agent-knowledge-access` absorbed into `internal-knowledge-access` (delivery interface)
 - `corpus-routing` absorbed into `ingestion-pipeline` (ingest-side) and `internal-knowledge-access` (retrieval-side)
 - `coherence-scoring` confirmed as-is
 - Discovered missing 3p pattern: `agentic-rag` — sourced from arXiv, IBM, Microsoft, NVIDIA
 - SKOS alignment clarified: belongs with `domain-data-model` (edge predicates, taxonomy structure), not with retrieval or publishing
- Capability review paused at `ingestion-pipeline` — remaining: `ingestion-pipeline`, `episode-provenance`, `research-rag`, `pattern-management`, supporting, generic

### 2026-02-07 (Session 2): Core capability review completed

- **Completed Socratic review of all 7 core capabilities** using semantic optimization loop (adopt 3P → innovate 1P):
 - `episode-provenance` absorbed into `agentic-lineage`: `agentic-lineage` (1P) + `open-lineage`, `episode-provenance` (3P)
 - `ingestion-pipeline` refined: `semantic-ingestion` (1P) + `etl`, `medallion-architecture`, `mlops` (3P). Full pipeline diagram added to STRATEGIC_DDD.md.
 - `research-rag` renamed to `research`: `semantic-ingestion` (1P) + `raptor` (3P). `research-synthesis-pattern` determined to be just semantic-ingestion applied to research.
 - `pattern-management` refined: `semantic-object-pattern` (1P) + `knowledge-organization-systems`, `pattern-language` (3P). Pattern as aggregate root is itself a 1P innovation.
- **12+ new patterns identified** for registration (see STRATEGIC_DDD.md action items)
- **Pattern naming convention audit** added as action item — current names need clarity review
- Remaining: supporting and generic capability review, pattern registration, Phase 2 (schema), Phase 3 (artifacts)

### 2026-02-07 (Session 3): Supporting/generic capability review completed, semops-dx-orchestrator promoted to core

- **Completed Socratic review of all supporting (6) and generic (2) capabilities**:
 - Supporting: `publishing-pipeline`, `surface-deployment` (renamed from `deployment`), `agentic-composition` (new), `style-learning`, `synthesis-simulation` (new for semops-data), `concept-documentation` (renamed from `theory-documentation`)
 - Generic: `attention-management`, `financial-pipeline` — both under `explicit-enterprise` (1P) umbrella
 - `architecture-governance` and `project-coordination` removed (absorbed into semops-dx-orchestrator core capabilities)
- **semops-dx-orchestrator promoted to core** with 3 new capabilities: `orchestration`, `context-engineering`, `autonomous-execution`
- **Subdomain definitions removed** — premature to formalize; capabilities stand on their own
- **Pattern registration spun off** → [](https://github.com/semops-ai/semops-dx-orchestrator/issues/100) (25+ patterns, naming convention, pattern table audit)
- **Final capability count**: 10 core, 6 supporting, 2 generic
- Remaining: Phase 2 (schema), Phase 3 (artifacts)

### 2026-02-08: Phase 2 Tactical DDD schema implementation

- **Schema v8.0.0** — entity_type discriminator, strategic edge predicates, strategic views
- Migration: `schemas/migrations/002_entity_type_discriminator.sql`
- Key decisions: `asset_type` nullable for non-content entities; `primary_pattern_id` kept as optional FK with `implements` edges for many-to-many; `'pattern'` added to edge node types for cross-layer edges
- Fitness functions rewritten from Phase 1 table names; `check_capability_pattern_coverage` implements the ADR-0009 coherence signal
- Python scripts (entity_builder, ingest_from_source) updated with entity_type field
- Seeding script deferred pending pattern registration 

### 2026-02-08 (Session 2): Phase 3 UL/Schema Reference split

- **`schemas/UBIQUITOUS_LANGUAGE.md` rewritten** as proper DDD UL (v8.0.0, ~460 lines):
 - Evans-compliant: domain terms, business rules, relationships — no SQL types or JSONB schemas
 - Organized by three-layer architecture: Pattern (WHY) → Architecture (WHAT/WHERE) → Content (output)
 - Domain Overview informed by SemOps framework docs (semops-publisher, semops-docs)
 - Covers all entity types (content, capability, repository) and all edge predicates including strategic DDD
 - Pattern types reduced to concept + domain only (architecture/topology removed per ADR-0009)
- **`schemas/SCHEMA_REFERENCE.md` created** as ISO/IEC 11179-inspired data dictionary:
 - All technical content extracted from old UL: column specs, JSONB schemas, constraints, views, indexes
 - Entity table includes entity_type field usage matrix
 - Value Objects include new capability_metadata_v1 and repository_metadata_v1
- **Cross-references updated**: CLAUDE.md, README.md, SETUP.md, ARCHITECTURE.md, PR template
- Phase 3 (this repo) complete; semops-dx-orchestrator artifacts remain → [](https://github.com/semops-ai/semops-dx-orchestrator/issues/99)

## References

- [ADR-0004: Schema Phase 2 — Pattern as Aggregate Root](ADR-0004-schema-phase2-pattern-aggregate-root.md) (foundational, still valid)
- [UBIQUITOUS_LANGUAGE.md v8.0.0](../../schemas/UBIQUITOUS_LANGUAGE.md)
- [SCHEMA_REFERENCE.md v8.0.0](../../schemas/SCHEMA_REFERENCE.md)
- [GLOBAL_ARCHITECTURE.md v3.1.0](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/GLOBAL_ARCHITECTURE.md)
- [Issue #122](https://github.com/semops-ai/semops-core/issues/122) — design session log
- Coordination: 
