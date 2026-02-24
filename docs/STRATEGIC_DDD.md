# Strategic DDD: Capabilities, Repos, and Integration

> **Version:** 1.9.0
> **Last Updated:** 2026-02-22
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
8. **Model depth earns intake freedom.** The domain model must be deep enough (patterns, lineage, coherence signals) that new ideas can enter without upfront classification. Don't gate ideation; audit coherence. Semantic measurement bridges the gap between "I have an idea" and "here's where it fits." (See [](https://github.com/semops-ai/semops-dx-orchestrator/issues/152))

### Repos, Bounded Contexts, and the DDD Repository Pattern

Three uses of "repository" coexist in SemOps — understanding the distinction is important for reading this document and for DDD alignment:

1. **Git repositories (repos)** — the physical code boundaries listed in the [Repository Registry](#repository-registry) below. These are **agent role boundaries**, not bounded contexts. Each repo scopes what an AI agent (or human) needs in context to do useful work, simulating team structure in a one-person operation. Repos can be reorganized — merged, split, renamed — without changing the domain model. When that happens, the `repository` entity mappings in this document update, but `capability` and `pattern` entities don't.

2. **Bounded Contexts** — the semantic boundaries where a particular domain model and ubiquitous language apply. SemOps has a layered context structure described in [SYSTEM_LANDSCAPE.md](SYSTEM_LANDSCAPE.md): **SemOps Core** (semops-dx-orchestrator, semops-core, semops-data) is the product — always present regardless of domain. **Domain applications** (Content: semops-publisher, semops-docs, semops-sites; Operations: semops-backoffice) are pluggable contexts that consume Core but own their own domain logic. The key boundary rule: Core never depends on a domain application. Domain applications depend on Core.

3. **DDD Repository pattern** — the data access abstraction that mediates between the domain model and the transactional data layer (OLTP), responsible for retrieving and persisting Aggregates. Currently this lives in **semops-core** — the ingestion scripts, entity builders, and edge creation logic that persist domain objects to PostgreSQL. This is distinct from **semops-data**, which is the analytics layer (OLAP) — it reads from the domain model for coherence scoring and profiling, but doesn't persist aggregates. Research RAG and data due diligence were extracted to **semops-research** (a domain application) via [](https://github.com/semops-ai/semops-data/issues/50). The Repository pattern handles concerns like tenant isolation at the infrastructure layer, keeping the domain model unaware of which tenant or deployment context it operates within.

This OLTP/OLAP distinction maps to the [Four Data System Types](../../semops-docs/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/STRATEGIC_DATA/four-data-system-types.md) framework: semops-core is the **Application Data System** (transactional, DDD-governed), semops-data is the **Analytics Data System** (read-heavy, dimensional). GitHub issues, projects, and session notes are the **Enterprise Work System** (unstructured knowledge artifacts). semops-backoffice's financial pipeline is an **Enterprise Record System** (canonical truth, double-entry constraints). Each system type has different scaling physics, governance approaches, and integration patterns — understanding which type you're operating in determines which DDD patterns apply.

The relationship between these three is itself a [Scale Projection](../../semops-docs/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/EXPLICIT_ARCHITECTURE/scale-projection.md) proof: because the mapping from domain model (capabilities, patterns) to physical boundaries (repos) is explicit and queryable in this document, changing the physical structure is an infrastructure decision. The architecture — what this document captures — remains stable.

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

### Lifecycle Model

All domain model entities use the same 5-state lifecycle, sourced from the [Backstage Software Catalog](../../semops-dx-orchestrator/docs/domain-patterns/backstage-software-catalog.md) `spec.lifecycle` mapping.

| State | Meaning |
|-------|---------|
| `planned` | Identified as relevant, not yet evaluated |
| `draft` | Being evaluated or researched for adoption |
| `in_progress` | Actively being adopted or implemented |
| `active` | Adopted/implemented and operational |
| `retired` | No longer used (superseded or dropped) |

**Patterns and capabilities have independent lifecycles connected by the `implements` edge.**

- A pattern can be `active` while the capabilities implementing it range across all states (e.g., `ddd` is `active`; `bounded-context-extraction` which implements it is `planned`)
- A capability can be `planned` while multiple `draft` patterns are being evaluated for it (e.g., a planned `financial-pipeline` might evaluate 3 candidate accounting patterns)
- A pattern can be `retired` while the capability it served remains `active` via a replacement pattern

**Lifecycle governance rules:**

| Entity State | Coherence Signals | Orphan Detection | Ingestion | Audit Checks |
|---|---|---|---|---|
| `planned` | Skip — intent only | Skip — expected to be unmapped | Yes (seed for future) | Verify exists in registry |
| `draft` | Discovery mode only | Skip — evaluation in progress | Yes | Verify pattern linkage attempted |
| `in_progress` | Full audit | Full audit | Yes | Full consistency checks |
| `active` | Full audit | Full audit | Yes | Full consistency checks |
| `retired` | Skip | Skip — intentionally disconnected | Optional (historical) | Verify retirement documented |

**Where lifecycle is declared:**

| Entity | Authority | Field |
|--------|-----------|-------|
| Capability | This document (Capability Registry, Status column) | `status` |
| Pattern | `pattern_v1.yaml` | `status` |
| Repository | `REPOS.yaml` | `lifecycle_stage` |
| Pattern doc | Doc header | `Status:` |

### The Semantic Optimization Loop

```text
Pattern ──produces──→ Capability
 ↑ ↓
 └──── Coherence ←──audits──┘
 (informs)

Pattern pushes. Coherence aligns.
```

When `semantic-optimization` becomes operational, coherence scoring becomes the objective function — Pattern sets the target, Coherence measures the gap, the optimization loop minimizes the gap. The existing agentic lineage system (episodes with `coherence_score` fields) provides the telemetry layer. See ADR-0012 §10.

---

## Capability Registry

A **capability** is what the system delivers. It implements one or more Patterns. It is delivered by one or more repos. Capability-to-pattern coverage is a measurable coherence signal.

### Core Domain Capabilities

These are the differentiating capabilities aligned with the [Semantic Operations Framework](../../semops-docs/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/README.md).— what makes SemOps unique.

| ID | Capability | Status | Implements Patterns | Delivered By |
|----|-----------|--------|-------------------|--------------|
| `domain-data-model` | Domain Data Model | active | `ddd`, `skos`, `prov-o`, `explicit-architecture`, `edge-predicates`, `shape`, `unified-catalog` | semops-core |
| `internal-knowledge-access` | Internal Knowledge Access | active | `agentic-rag` | semops-core |
| `coherence-scoring` | Coherence Scoring | in_progress | `semantic-coherence` | semops-data, semops-core |
| `ingestion-pipeline` | Ingestion Pipeline | in_progress | `semantic-ingestion`, `etl`, `medallion-architecture` | semops-core |
| `agentic-lineage` | Agentic Lineage | planned | `agentic-lineage`, `open-lineage`, `episode-provenance`, `derivative-work-lineage` | semops-core, semops-data |
| `pattern-management` | Pattern Management | active | `semantic-object-pattern`, `pattern-language`, `explicit-architecture`, `arc42`, `backstage-software-catalog`, `provenance-first-design` | semops-core, semops-dx-orchestrator |
| `orchestration` | Orchestration | active | `explicit-enterprise`, `platform-engineering`, `explicit-architecture` | semops-dx-orchestrator |
| `context-engineering` | Context Engineering | active | `explicit-enterprise` | semops-dx-orchestrator |
| `scale-projection` | Scale Projection | in_progress | `scale-projection`, `rlhf`, `seci` | semops-publisher, semops-data, semops-dx-orchestrator |
| `bounded-context-extraction` | Bounded Context Extraction | planned | `ddd`, `explicit-architecture` | semops-core, semops-dx-orchestrator |
| `autonomous-execution` | Autonomous Execution | planned | `explicit-enterprise` | semops-dx-orchestrator |

#### Ingestion Pipeline Detail

> Implementation detail relocated to [semops-core ARCHITECTURE.md § Retrieval Pipeline](ARCHITECTURE.md#retrieval-pipeline). The 1P innovation (`semantic-ingestion`) is that every byproduct — classifications, detected edges, coherence scores, embeddings — is captured and queryable, not discarded.

### Supporting Domain Capabilities

These are capabilities used to create the published content that is the marketing product of SemOps. They are based on standard (3p) domain patterns. They are used as examples and showcase of the core domain as part of the SemOps project, but are not necessary to define the Semantic Operations Framework, nor are they unique to SemOps.

| ID | Capability | Status | Implements Patterns | Delivered By |
|----|-----------|--------|-------------------|--------------|
| `publishing-pipeline` | Publishing Pipeline | active | `dam`, `dublin-core`, `cms`, `pim` | semops-publisher |
| `surface-deployment` | Surface Deployment | active | `dam` | semops-sites |
| `agentic-composition` | Agentic Composition | in_progress | `semantic-ingestion`, `agentic-rag`, `zettelkasten` | semops-publisher |
| `style-learning` | Style Capture | in_progress | `scale-projection`, `rlhf`, `seci` | semops-publisher |
| `corpus-meta-analysis` | Corpus Meta-Analysis | active | `semantic-ingestion`, `raptor`, `agentic-rag` | semops-research |
| `data-due-diligence` | Data Due Diligence | active | `ddd`, `data-modeling`, `explicit-architecture`, `business-domain` | semops-research |
| `reference-generation` | Reference Generation | active | `ddd`, `data-modeling`, `explicit-architecture`, `business-domain` | semops-research |
| `synthesis-simulation` | Synthesis and Simulation | draft | `scale-projection`, `semops-dataofiling`, `data-lineage`, `data-modeling` | semops-data |
| `concept-documentation` | Concept Documentation | draft | `ddd` | semops-docs |

> **Bounded context candidate:** Agentic composition applied to domain-specific outputs (e.g., resume composition, consulting proposals) may warrant a second bounded context via Customer-Supplier (challenges ADR-0009 decision #6). See per-repo ARCHITECTURE.md for implementation detail.

> **Gap noted:** `design-system` capability likely needed for semops-sites visual design governance (font management, per-brand styles). To be formalized in a future review.

---

### Capability Traceability

The system enforces a full traceability chain from stable meaning to executable code:

```text
Pattern → Capability → Script
(why) (what) (where it runs)
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

| ID | Capability | Status | Implements Patterns | Delivered By |
|----|-----------|--------|-------------------|--------------|
| `cap-inbox` | Inbox | active | `explicit-enterprise` | semops-backoffice |
| `financial-pipeline` | Financial Pipeline | planned | `explicit-enterprise` | semops-backoffice |
| `cap-voice-control` | Voice Control | draft | `explicit-enterprise` | semops-backoffice |

Generic capabilities implement `explicit-enterprise` (1P) — humble tools become agent-addressable signal streams. See [explicit-enterprise pattern doc](../../semops-docs/docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/EXPLICIT_ARCHITECTURE/explicit-enterprise.md).

---

## Repository Registry

A **repository** is where implementation lives. Repos deliver capabilities.

| ID | Repo | Role | Delivers Capabilities |
|----|------|------|----------------------|
| `semops-core` | semops-core | Schema/Infrastructure | `domain-data-model`, `internal-knowledge-access`, `ingestion-pipeline`, `agentic-lineage`, `pattern-management`, `coherence-scoring`, `bounded-context-extraction` |
| `semops-dx-orchestrator` | semops-dx-orchestrator | Platform/DX | `orchestration`, `context-engineering`, `autonomous-execution`, `pattern-management`, `scale-projection`, `bounded-context-extraction` |
| `semops-publisher` | semops-publisher | Publishing | `publishing-pipeline`, `agentic-composition`, `style-learning`, `scale-projection` |
| `semops-docs` | semops-docs | Documents | `concept-documentation` |
| `semops-data` | semops-data | Analytics/MLOps | `coherence-scoring`, `agentic-lineage`, `synthesis-simulation`, `scale-projection` |
| `semops-research` | semops-research | Research/Consulting | `corpus-meta-analysis`, `data-due-diligence`, `reference-generation` |
| `semops-sites` | semops-sites | Frontend | `surface-deployment` |
| `semops-backoffice` | semops-backoffice | Operations | `cap-inbox`, `financial-pipeline`, `cap-voice-control` |

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
| semops-core | semops-research | **Customer-Supplier** | Ollama, Qdrant, Docling services | Upstream provides |
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
integration_pattern: shared-kernel # DDD integration pattern (a 3P Pattern record)
shared_artifact: UBIQUITOUS_LANGUAGE.md
direction: bidirectional
rationale: "Both repos must agree on domain terms; changes require coordination"
established: 2025-12-22 # When this integration was formalized
```

This metadata will be stored as Edge records with `integration` predicate between repository entities, typed by the DDD integration Pattern.

---

## Governance: Change Propagation

When the domain model changes, multiple documents and systems must stay consistent. This section defines the authority chain, change types, and consistency checks.

### Document Authority Chain

Each data type has a single authority. All other documents derive from it.

| Data | Authority | Derived By |
|------|-----------|------------|
| Pattern identity + lineage | `pattern_v1.yaml` (semops-dx-orchestrator) | Pattern docs, PATTERN_AUDIT.md, DB pattern table |
| Capability registry (ID, status, patterns, repos) | This document (STRATEGIC_DDD) | REPOS.yaml, GLOBAL_ARCHITECTURE, per-repo ARCHITECTURE.md, PATTERN_AUDIT.md, DB entity/edge tables |
| Repository registry + integration map | This document (STRATEGIC_DDD) | REPOS.yaml, GLOBAL_ARCHITECTURE, per-repo ARCHITECTURE.md |
| Coherence signal definitions | This document (STRATEGIC_DDD) | Audit commands (`/arch-sync`, `/global-arch-sync`) |
| Per-repo infrastructure (services, ports, env) | Per-repo `INFRASTRUCTURE.md` | GLOBAL_INFRASTRUCTURE.md, PORTS.md |
| Process + templates | semops-dx-orchestrator docs | Per-repo docs (via templates) |

**Rule:** Author changes at the authority. Then run audit commands to find and fix inconsistencies in derived documents.

### Change Types

Each change type defines **where to author first** (the authority) and **what consistency checks to run**.

#### Pattern Adopted or Removed

**Author at:** `pattern_v1.yaml` + this document (Capability Registry)

1. Add/remove pattern record in `pattern_v1.yaml` (identity, lineage, docs)
2. Create/deprecate `domain-patterns/<id>.md`
3. Update capability "Implements Patterns" column in this document
4. Update Coherence Signals coverage table
5. **Run audit:** `/arch-sync` (per-repo) → `/global-arch-sync` (cross-repo)
6. Audit checks: per-repo ARCHITECTURE.md capabilities, GLOBAL_ARCHITECTURE per-repo sections, REPOS.yaml capability descriptions, PATTERN_AUDIT.md, derives_from references in other patterns
7. Re-run ingestion when DB is operational

#### Capability Added, Modified, or Status Changed

**Author at:** This document (Capability Registry + Repository Registry)

1. Add/update capability row (ID, Name, Status, Implements Patterns, Delivered By)
2. Update Repository Registry "Delivers Capabilities" column
3. Update Coherence Signals coverage
4. **Run audit:** `/arch-sync` (per-repo) → `/global-arch-sync` (cross-repo)
5. Audit checks: REPOS.yaml capabilities, GLOBAL_ARCHITECTURE per-repo sections, per-repo ARCHITECTURE.md Capabilities table + status indicators, per-repo INFRASTRUCTURE.md if capability implies new services

#### Repo Registered or Reorganized

**Author at:** This document (Repository Registry) + `REPOS.yaml`

1. Add/update repo in Repository Registry
2. Add/update repo in `REPOS.yaml`
3. Update Integration Patterns if relationships change
4. **Run audit:** `/global-arch-sync`
5. Audit checks: GLOBAL_ARCHITECTURE repo section, GLOBAL_INFRASTRUCTURE services/ports, per-repo ARCHITECTURE.md + INFRASTRUCTURE.md existence and template compliance

#### Integration Pattern Changed

**Author at:** This document (Integration Patterns)

1. Update Integration Map table
2. **Run audit:** `/arch-sync` (affected repos) → `/global-arch-sync`
3. Audit checks: per-repo ARCHITECTURE.md Dependencies/Integration sections, GLOBAL_ARCHITECTURE DDD Alignment

#### Unclassified Input (Principle 8)

**Author at:** GitHub Issue

New ideas enter the system as GitHub Issues — no upfront classification required. But pattern recognition requires enough definition to match against. The process has two phases: **scope the goal**, then **evaluate coherence**. The `/intake` command operationalizes this workflow.

**Summary flow:**

1. Create issue describing the idea — no classification required
2. Scope the goal (Tier 1 in-issue, or Tier 2 Project Spec)
3. Evaluate against coherence signals (manually or via `/intake`)
4. Assign coherence mode: Discovery, Governance, Regression, or Novel
5. Once classified, follow the appropriate change type above

The issue is the flexible edge. No document updates until classification happens. See [Principle 8](#principles).

##### Goal Scoping (Tiered)

Pattern recognition requires enough definition to match against. A raw "I want better data ingestion" matches everything; a scoped "I want to extend `explicit-enterprise` to data systems architecture and build out an open source first class data system" matches `explicit-enterprise`, `open-primitive-pattern`, and Project 30's existing scope specifically.

Goal scoping is the forcing function — not the coherence checklist.

**Tier 1: Goal statement (in-issue)** — for small, focused ideas. The issue needs one thing:

- **Outcome:** What does done look like? (1-2 sentences, free-form natural language)

The Outcome statement is the input — no structured fields required. The description naturally contains entity references that the evaluation step extracts. Users reference patterns, projects, and capabilities in their natural language without being asked to fill in forms.

The Outcome must be concrete enough to validate against — even if validation is human-in-the-loop. "Make the system better" has nothing to match; "extend `explicit-enterprise` to data systems architecture" gives the evaluation process entity references to extract and a territory map to present.

**Entity extraction hints** — signals in the Outcome text that accelerate context loading:

| Signal | Example | What it loads |
|--------|---------|---------------|
| Backtick references | `explicit-enterprise`, `ingestion-pipeline` | Direct pattern/capability lookup |
| Project numbers | "project 30", "Project 18" | Project spec (outcome, AC, child issues, related patterns) |
| Issue references | `#42`, `` | Issue body, labels, linked context |
| Natural language | "open source data system" | KB semantic search for matching entities |

Backticks are a strong hint — they signal "this is a known entity name" vs casual language. But natural language without backticks still works via KB semantic search.

**Tier 2: Project Spec** — for bigger ideas. When Tier 1 reveals broader scope, promote to a `PROJECT-NN` spec (see [semops-dx-orchestrator/docs/project-specs/TEMPLATE.md](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/docs/project-specs/TEMPLATE.md)) with full Outcome, Acceptance Criteria, Execution Sequence.

**When to promote Tier 1 → Tier 2:**

| Trigger | Why |
|---------|-----|
| Spans 3+ repos | Needs sequenced execution and cross-repo coordination |
| Requires an ADR | Architectural decision needs formal recording |
| Has dependencies on other projects | Needs dependency tracking beyond a single issue |
| Needs multiple ordered steps | Execution Sequence required to avoid misordering |

**The #152 insight applies:** Users often start narrow (a capability idea) and discover the broader pattern during goal scoping. The process supports that journey — Tier 1 scoping surfaces existing structure before you conclude novelty.

##### Evaluation Process

Evaluation is semantic, not structural. The agent extracts entity references from the Outcome text, expands context from authority sources, and presents the territory map. The `/intake` command operationalizes this.

**Step 1: Extract entity references** from the Outcome text:

| Priority | Signal | Action |
|----------|--------|--------|
| 1 | Backtick references (`explicit-enterprise`) | Direct lookup in `pattern_v1.yaml` or Capability Registry |
| 2 | Project numbers ("project 30") | Load project spec from `semops-dx-orchestrator/docs/project-specs/` |
| 3 | Issue references (`#42`, ``) | Load issue body, labels, linked context |
| 4 | Natural language (everything else) | KB semantic search (`search_knowledge_base`) |

**Step 2: Expand context** — for each extracted reference, load from authority sources:

- Patterns → `pattern_v1.yaml` (status, lineage, derives_from)
- Capabilities → Capability Registry in this document (status, implements, delivered by)
- Projects → Project spec (outcome, acceptance criteria, child issues, related patterns)
- Repos → `REPOS.yaml` (capabilities, integration patterns, dependencies)

**Step 3: Present territory map** — show the user what already exists that relates to their input. This is the key step: most inputs connect to something existing. The map reveals the landscape before any classification happens.

**Step 4: Identify delta** — what's new vs what already has coverage. Compare the input's intent against the expanded context:

- Input extends an existing capability → Discovery
- Input fills a gap (something should trace but doesn't) → Governance
- Input conflicts with existing structure → Regression
- Input has no matches after KB search + authority lookup → likely Novel (ask clarifying questions to confirm)

**Net new is rare.** If Steps 1-3 found nothing, ask a few focused questions before concluding novelty. The domain model is broad enough that most ideas connect somewhere.

##### Classification Decision Tree

After the evaluation process presents the territory map, classify based on the delta:

```text
Territory map presented (entity references expanded, context loaded)
│
├── Input extends existing pattern/capability coverage
│ └── Discovery (coverage increase)
│ ├── Capability exists → link issue, update coverage tables
│ │ Change type: none, or Capability Modified if status changes
│ └── Pattern exists but no capability → create capability
│ Change type: Capability Added
│
├── Input fills a gap (something exists without proper trace)
│ └── Governance (coverage gap)
│ └── Action: add missing traces (pattern→capability, capability→script)
│ Change type: Capability Modified or Pattern Adopted
│
├── Input conflicts with existing structure
│ └── Regression (would break existing coherence)
│ └── Action: evaluate trade-off — modify input, modify architecture, or reject
│ Change type: depends on resolution
│
├── Input describes infrastructure/tooling
│ └── Route to Repo or Integration change types
│ Change type: Repo Registered/Reorganized or Integration Pattern Changed
│
└── No matches after KB search + authority lookup + clarifying questions
 └── Novel — evaluate scope:
 ├── Narrow (single capability) → Capability Added + evaluate pattern need
 ├── Broad (cross-cutting) → Pattern Adopted + derive capabilities
 └── Unknown scope → stays at flexible edge, revisit at next review
```

**Key principle:** Classification does not need to happen immediately. The decision tree is a tool for when you choose to classify, not a gate on creation.

##### Flexible Edge Policy

The flexible edge is where unclassified inputs live. This section defines the cost and governance of that space.

**What "free to exist" means:**

- Issues can remain unclassified indefinitely — there is no deadline
- Unclassified issues do NOT appear in coherence signal reports (they are not yet part of the domain model)
- No documents update until classification happens
- The issue label `intake:unclassified` tracks flexible-edge items

**What triggers classification:**

| Trigger | Mechanism |
|---------|-----------|
| Voluntary | Author runs `/intake` or manually classifies |
| Review cycle | `/intake --review` surfaces unclassified issues older than 30 days for batch triage |
| Dependency | Another issue or capability needs this input classified to proceed |
| Coherence signal | An audit (`/arch-sync`, `/global-arch-sync`) detects something that matches an unclassified input |

**Cost of the flexible edge:**

The flexible edge has a carrying cost: unclassified inputs represent potential coherence improvements that aren't being captured. Discovery mode is the most valuable coherence mode because it compounds — every unclassified input that turns out to align with existing structure is a missed compounding opportunity.

The review cycle (30-day surfacing) balances freedom with this carrying cost. It does not force classification — it makes the cost visible.

##### Coherence Mode Assignment

Once the evaluation process has been run against the scoped goal (entity extraction → context expansion → territory map → delta identification), assign the coherence mode based on what the signals indicate.

| Mode | Signal Pattern | What It Means | Actions Triggered |
|------|---------------|---------------|-------------------|
| **Discovery** | Input matches existing pattern or capability that wasn't tracking it | Coverage increase — the domain model is more complete than we thought | Link input to existing structure; update coverage tables; close gap in Capability-Pattern or Script-Capability coverage |
| **Governance** | Input reveals something that exists without justification (a script, service, or practice that should trace to a pattern but doesn't) | Coverage gap — something is operating outside the model | Evaluate: formalize (add pattern/capability trace) or remove (the thing shouldn't exist) |
| **Regression** | Input conflicts with an existing pattern or would break a currently-coherent capability trace | Coherence loss — adopting this input has a cost | Quantify the cost (how many capability traces break?); evaluate trade-off; decide to adapt input, adapt architecture, or defer |

**Novel inputs** (no mode assigned) stay at the flexible edge until enough context exists to classify. They are not a coherence finding — they are simply uncharted territory.

**Disambiguation: Discovery vs. Governance.** Both involve gaps, but the direction differs:

- **Discovery:** Something good exists that we didn't know about → formalize it (additive)
- **Governance:** Something exists that shouldn't, or lacks justification → justify it or remove it (corrective)

The test: "Is the input revealing hidden alignment (Discovery) or hidden debt (Governance)?"

**Labels:**

| Label | Meaning |
|-------|---------|
| `intake:unclassified` | At flexible edge, not yet evaluated |
| `intake:discovery` | Evaluated — aligns with existing structure, needs formalization |
| `intake:governance` | Evaluated — coverage gap identified |
| `intake:regression` | Evaluated — conflicts with existing coherence |
| `intake:novel` | Evaluated — genuinely new, needs pattern/capability decision |

### Consistency Checks

`/arch-sync` (per-repo) and `/global-arch-sync` (cross-repo) enforce this propagation model. Each check verifies derived documents match their authority.

**Per-repo checks (`/arch-sync`):**

- ARCHITECTURE.md capabilities match this document's Capability Registry (names, status, patterns)
- ARCHITECTURE.md integration patterns match this document's Integration Map
- INFRASTRUCTURE.md services match actual Docker/service state
- Key Components trace to capabilities (no orphan scripts)

**Cross-repo checks (`/global-arch-sync`):**

- REPOS.yaml capability names match this document exactly
- GLOBAL_ARCHITECTURE per-repo sections match this document (capabilities, status)
- GLOBAL_INFRASTRUCTURE matches per-repo INFRASTRUCTURE.md (ports, services)
- Every pattern in `pattern_v1.yaml` has a doc in `domain-patterns/`
- Every pattern referenced in Capability Registry exists in `pattern_v1.yaml`
- PATTERN_AUDIT.md is current (regenerate if stale)
- No orphan patterns (every pattern has ≥1 capability, or is explicitly superseded/infrastructure)

---

## Coherence Signals

The signals below are the current implementation of coherence measurement — stateless sensors that run, report, and forget. When Coherence Assessment becomes operational as a first-class aggregate (ADR-0012), these sensors feed into assessments that gain identity, lifecycle, and action tracking. The three modes of coherence (governance, discovery, regression) classify what each signal detects. See [Domain Model](#domain-model-aggregates-and-building-blocks) above.

### Capability-Pattern Coverage

Every core/supporting capability should trace to at least one Pattern. Current assessment:

| Capability | Pattern Coverage | Gap? |
|-----------|-----------------|------|
| `domain-data-model` | `ddd`, `skos`, `prov-o`, `explicit-architecture` (1p), `edge-predicates`, `shape`, `unified-catalog` | No |
| `internal-knowledge-access` | `agentic-rag` (3p) | No |
| `coherence-scoring` | `semantic-coherence` | No |
| `ingestion-pipeline` | `semantic-ingestion` (1p), `etl` (3p), `medallion-architecture` (3p) | No |
| `agentic-lineage` | `agentic-lineage` (1p), `open-lineage` (3p), `episode-provenance` (3p), `derivative-work-lineage` (1p) | No |
| `corpus-meta-analysis` | `semantic-ingestion` (1p), `raptor` (3p), `agentic-rag` (3p) | No |
| `data-due-diligence` | `ddd` (3p), `data-modeling` (3p), `explicit-architecture` (1p), `business-domain` (3p) | No |
| `reference-generation` | `ddd` (3p), `data-modeling` (3p), `explicit-architecture` (1p), `business-domain` (3p) | No |
| `pattern-management` | `semantic-object-pattern` (1p), `pattern-language` (3p), `explicit-architecture` (1p), `arc42` (3p), `backstage-software-catalog` (3p), `provenance-first-design` (1p) | No |
| `publishing-pipeline` | `dam` (3p), `dublin-core` (3p), `cms` (3p), `pim` (3p) | No |
| `agentic-composition` | `semantic-ingestion` (1p), `agentic-rag` (3p), `zettelkasten` (3p) | No |
| `surface-deployment` | `dam` (3p) | No |
| `style-learning` | `scale-projection` (1p), `rlhf` (3p), `seci` (3p) | No |
| `synthesis-simulation` | `scale-projection` (1p), `semops-dataofiling` (3p), `data-lineage` (3p), `data-modeling` (3p) | No |
| `concept-documentation` | `ddd` (3p) | Possible — may need specific pattern |
| `orchestration` | `explicit-enterprise` (1p), `platform-engineering` (3p), `explicit-architecture` (1p) | No |
| `context-engineering` | `explicit-enterprise` (1p) | No — pattern exists |
| `scale-projection` | `scale-projection` (1p), `rlhf` (3p), `seci` (3p) | No |
| `bounded-context-extraction` | `ddd` (3p), `explicit-architecture` (1p) | No — patterns exist |
| `autonomous-execution` | `explicit-enterprise` (1p) | No — pattern exists |
| `cap-inbox` | `explicit-enterprise` (1p) | No |
| `financial-pipeline` | `explicit-enterprise` (1p) | No — pattern exists |
| `cap-voice-control` | `explicit-enterprise` (1p) | **3P pattern TBD** — speech-to-text, audio production |

**Status:** All pattern registration and SKOS lineage action items completed (, #146). 37 patterns registered in `pattern_v1.yaml` v1.7.0 with `derives_from` edges. DB ingestion verified .

**Remaining:**

- `cap-voice-control` — 3P pattern TBD for speech-to-text / audio production
- `concept-documentation` — may need a specific pattern beyond `ddd`
- **Pattern naming convention** — current IDs are generic abbreviations; establish a convention and audit for clarity

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

> Governance queries relocated to developer docs. Every table in this document is parsed into the database by `ingest_architecture.py`. Key governance questions (orphan patterns, capability coverage gaps, repo delivery, integration map, lifecycle stages, full traceability) become SQL via `capability_coverage` and `pattern_coverage` views.

---

## Evolution

This document is the **source of truth** for strategic DDD concepts. For change procedures, see [Governance: Change Propagation](#governance-change-propagation) above.

When aggregate structure or DDD building block classifications change, update [ADR-0012](decisions/ADR-0012-pattern-coherence-co-equal-aggregates.md) and the [Domain Model](#domain-model-aggregates-and-building-blocks) section above.
