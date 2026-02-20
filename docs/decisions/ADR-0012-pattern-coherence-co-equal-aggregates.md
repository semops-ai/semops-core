# ADR-0012: Pattern + Coherence as Co-Equal Core Aggregates

> **Status:** Draft
> **Date:** 2026-02-19
> **Related Issue:** [semops-core#142](https://github.com/semops-ai/semops-core/issues/142)
> **Supersedes:** ADR-0004 § "Pattern as sole aggregate root" framing
> **Related:** ADR-0009 (three-layer architecture), #141 (bounded context alignment)

## Executive Summary

The current domain model declares Pattern as the sole aggregate root for the entire SemOps bounded context. This conflates "most important domain concept" with "aggregate root" (a DDD transactional consistency boundary). The schema already implements multiple independent aggregates. More fundamentally, Pattern alone captures only the prescriptive force of SemOps. The evaluative/directive force — coherence measurement — has no first-class domain object.

This ADR introduces **Coherence Assessment** as a co-equal core aggregate alongside Pattern, formalizes the multiple aggregates that already exist implicitly in the schema, and reframes the Semantic Optimization Loop as the Pattern ⇄ Coherence feedback loop.

## Context

### What ADR-0004 got right

1. **Pattern as the core domain concept** — the stable meaning everything traces to
2. **SKOS for taxonomy** — broader/narrower/related relationships
3. **Provenance** (1P/2P/3P) — whose semantic structure is this
4. **Adoption lineage** — adopts/extends/modifies relationships

### What needs revision

**"Pattern is the aggregate root of the domain model — the single entity through which all access to the aggregate occurs."**

In Evans' DDD, an aggregate root is the transactional consistency boundary leader for its aggregate — not the most important concept in the system. The schema already has multiple independent lifecycles:

- You create Deliveries without going through Pattern
- You register Surfaces independently
- You create Brands and Products with their own lifecycle
- Capabilities and Repositories have independent identity

These are separate aggregates, not children of Pattern.

### The missing force

SemOps described briefly: **business optimization with AI by operating on optimal semantic objects — using semantically rich objects to address large chunks of a domain, then constantly auditing and realigning to ensure executability.**

This has two forces:

1. **Prescriptive** — Pattern defines "what should we look like?" (adopt 3P → innovate 1P)
2. **Evaluative/Directive** — Coherence measures "does reality match intent?" and DRIVES changes

The prescriptive force is well-modeled (Pattern + SKOS + provenance). The evaluative force exists only as:
- A pattern (`semantic-coherence`) — the *idea* of measurement
- A capability (`coherence-scoring`) — the *ability* to measure
- Views (`pattern_coverage`, `capability_coverage`) — computed snapshots
- Fitness functions — binary pass/fail checks

There is no domain object for the measurement itself — no way to track "pattern X had coherence score Y as of date Z, triggered by change W, with these gaps identified."

### Design session insight: the CRM lifecycle

A concrete example revealed the gap:

1. **Adopt**: Register "Zendesk" as a 3P CRM pattern (reverse-engineer API to core components)
2. **Implement**: Build capabilities aligned to the pattern
3. **Achieve coherence**: System reaches a stable, aligned state — *this moment has no domain representation*
4. **Evolve**: After months, diverge from Zendesk. Create 1P CRM pattern with `extends` → Zendesk (SKOS preserved)
5. **Coherence drops**: Changes affect financial-pipeline, attention-management, publishing — cross-cutting impact
6. **Assess and realign**: Measure gaps, act on them, restore coherence
7. **Traceability**: Can always "run it back" via SKOS chain to original CRM functions

Steps 3, 5, and 6 have no first-class domain objects. Pattern handles 1, 4, and 7. Entity handles 2. Coherence Assessment would handle 3, 5, and 6.

### Coherence is directive, not just evaluative

A critical insight: coherence assessment doesn't just report status — it drives action. A coherence assessment can trigger:

| Coherence signal | Action |
|-----------------|--------|
| Gap detected (missing coverage) | Adopt new pattern or create capability |
| Misalignment (conflict between patterns) | Modify or constrain a pattern |
| Regression (new pattern broke existing coherence) | **Revert or remove the pattern** |
| Drift (implementation diverged from intent) | Realign implementation OR evolve pattern to match reality |

Coherence can command pattern reversal or feature removal just as easily as it can prompt additions. This makes it a true peer to Pattern, not a subordinate measurement.

### Earlier framing: "Pattern and Provenance"

An earlier analysis identified the core pair as "Pattern and Provenance." This was close but incomplete — Provenance (1P/2P/3P) is a *property* of Pattern that feeds into coherence assessment as one signal among several. It answers "whose structure is this?" — important, but not the full evaluative force.

## Decision

### 1. Two core aggregates: Pattern + Coherence

Pattern and Coherence Assessment are the two core aggregates of the Semantic Operations domain:

```
┌─────────────────────────────────────────────────┐
│           Semantic Optimization Loop             │
│                                                  │
│   Pattern ──produces──→ Capability               │
│      ↑                      ↓                    │
│      └──── Coherence ←──audits──┘                │
│            (informs)                             │
│                                                  │
│   Pattern pushes. Coherence aligns.              │
└─────────────────────────────────────────────────┘
```

- **Pattern** = what we should look like (prescriptive force)
- **Coherence Assessment** = how well reality matches intent, and what to do about it (evaluative/directive force)
- **Capability** = the operational entity both aggregates act upon — Pattern produces it, Coherence audits it

Pattern without Coherence is just documentation. Coherence without Pattern is measurement without a reference. The "semantic object" that SemOps operates on is the pair.

### 2. DDD building block classifications

#### Core Aggregates

| Aggregate | Root | Children / Value Objects | Invariants |
|-----------|------|--------------------------|------------|
| **Pattern** | `pattern` | `pattern_edge` | Valid SKOS hierarchy, provenance rules, unique preferred_label |
| **Coherence Assessment** | *new* | measurements, gaps, actions | Must reference ≥1 pattern, lifecycle state machine |

#### Entities (not aggregates — shared between core aggregates)

| Entity | Produced by | Audited by | Classification |
|--------|------------|------------|----------------|
| **Capability** | Pattern (adopting/modifying patterns creates capabilities) | Coherence (measures coverage, alignment, regression) | Entity — has identity, lifecycle, coverage trajectory |

Capabilities implement multiple patterns and are measured by Coherence assessments. They are the operational consequence of pattern decisions and the primary subject of coherence audits. They are not owned by either aggregate — they exist in the space between, referenced by both.

#### Value Objects

| Value Object | Belongs to | Reasoning |
|-------------|-----------|-----------|
| **Repository** | Capability (describes WHERE) | Identity doesn't matter — role and delivery mapping do. STRATEGIC_DDD.md: "Repos can be reorganized — merged, split, renamed — without changing the domain model." |

#### Supporting Aggregates

Each supporting aggregate traces to a 3P pattern that defines its structure — the adopted pattern prescribes the aggregate boundary.

| Aggregate | Root | Children / Value Objects | 3P Pattern | Invariants |
|-----------|------|--------------------------|-----------|------------|
| **Content** (DAM) | `entity` (content) | `delivery` (publication records), edges | DAM, Dublin Core | Valid filespec if asset_type=file; Delivery has per-surface governance |
| **Surface** | `surface` | `surface_address` | DAM (channels) | Valid platform/direction |
| **Brand** (PIM/CRM) | `brand` | `product`, `brand_relationship` | Schema.org, PIM *(unregistered)* | Brand_type constraints, product ownership |

Note: Delivery is a child entity within the Content aggregate (not its own aggregate). In DAM, the asset is the root and its publication records are part of its lifecycle. "This blog post and where it's been published" is a coherent consistency boundary. Surface remains separate because channels exist independently of any content.

Brand is currently scaffolding at the flexible edge — one brand (Semantic Operations), one person, no products. The PIM/CRM pattern is unregistered. This is a valid coherence audit finding, not a problem — the tables are ready for when CRM is needed.

### 3. Coherence is audit, not gate

**Coherence does not block action.** The protection of the stable core comes from aggregate root invariants (valid SKOS hierarchy, provenance rules, etc.), not from coherence.

The flexible edge — orphan entities, unattributed scripts, experimental infrastructure — is free to exist. Nothing at the flexible edge can corrupt the stable core because aggregate root invariants prevent it.

Coherence audits the gap between what exists and what's formalized:

```
Stable Core                    Flexible Edge
(aggregate root invariants)    (anything goes)
                                    │
Pattern ─── enforces ──→ SKOS,      │  scripts, experiments,
            provenance,  links      │  orphan entities, infra
                                    │
                              Coherence audits
                              the gap between
                              core and edge
```

The flexible edge is the space where you can move fast. Coherence is how you stay honest about the cost of that speed. The aggregate root is why moving fast doesn't break things.

You CAN create coherence gates (blocking rules for specific workflows), but the default posture is audit. Incorporation — moving from the flexible edge into the stable core — is voluntary. When you do incorporate (link a script to a capability, link a capability to a pattern), that's when aggregate root invariants kick in and enforce structural integrity.

### 4. Three modes of coherence

| Mode | Signal | Action |
|------|--------|--------|
| **Governance** | Something exists without justification | "This script has no pattern trace — here's your coverage gap" |
| **Discovery** | Something aligns but isn't tracked | "This infrastructure aligns with ingestion-pipeline — formalizing would close a gap" |
| **Regression** | Something that was coherent broke | "This change opened 3 new gaps across these capabilities — here's the trade-off" |

**Discovery mode compounds.** Every time coherence finds a latent alignment and makes it explicit, pattern coverage increases, which makes future assessments more accurate, which finds more latent structure. The semantic optimization loop accelerates itself.

### 5. Fitness functions are sensors

The existing fitness functions and coverage views are **coherence sensors** — they detect signals that feed into assessments:

| Sensor | What it detects | Current form |
|--------|----------------|-------------|
| `check_capability_pattern_coverage()` | Capability without pattern trace | Fitness function (pass/fail) |
| `pattern_coverage` view | Pattern without implementations | SQL view (snapshot) |
| `capability_coverage` view | Capability without repo delivery | SQL view (snapshot) |
| `/arch-sync` audit | Script without capability attribution | Workflow (manual) |
| `orphan_entities` view | Content without pattern link | SQL view (snapshot) |

As fitness functions, these are stateless — they run, report, and forget. As sensors feeding Coherence Assessment, they produce signals that get identity, lifecycle, and action tracking.

### 6. Full traceability chain

Coherence audits the entire Pattern → Capability → Script/Infrastructure chain:

| What exists | What's missing | Coherence signal |
|-------------|---------------|-----------------|
| Script/infrastructure | No capability, no pattern | **Unjustified code** — why does this exist? |
| Capability | No pattern | **Unjustified capability** — what's the domain reason? |
| Pattern | No capability, no scripts | **Unimplemented intent** — aspirational or dead? |
| Pattern + Capability | No scripts | **Declared but not built** |
| Scripts | Capability exists, but wrong one | **Misattribution** — the code does something different than claimed |

Every break is an audit finding. The fix can go in either direction — a script without a capability might mean "create a capability," "delete the script," or "this script is actually part of an existing capability we just didn't realize."

### 7. Revise "aggregate root" language

- **Pattern is the aggregate root of the Pattern Aggregate** (pattern + pattern_edge)
- **Pattern is the core domain concept** of the bounded context — the stable meaning all other aggregates reference
- Pattern is NOT "the single entity through which all access to the aggregate occurs" for the whole system

### 8. Coherence Assessment aggregate shape (preliminary)

```
Coherence Assessment (Aggregate Root)
├── Trigger: what change prompted this assessment
│   (pattern evolution, new capability, implementation change)
├── Scope: which patterns/capabilities are being assessed
├── Measurements: per-pattern/per-capability alignment signals
│   ├── Availability (can agents/systems use this?)
│   ├── Consistency (do patterns conflict?)
│   └── Stability (how much churn?)
├── SC Score: (A × C × S)^(1/3) — the semantic-coherence formula
├── Gaps: identified misalignments (with mode: governance/discovery/regression)
├── Actions: recommended changes (add, remove, modify, revert, formalize)
├── State: assessed → acting → resolved → superseded
└── Timestamp
```

Lifecycle: an assessment is created when coherence-relevant changes occur. It identifies gaps, recommends actions (which may include pattern changes tracked as decisions/ADRs), and is eventually resolved or superseded by a subsequent assessment.

### 9. `semantic-coherence` pattern describes its own aggregate

There is a clean recursion: `semantic-coherence` the pattern describes *why* we measure. Coherence Assessment the aggregate is *how* we measure and act. The pattern justifies its own aggregate — exactly how the Pattern → Coherence loop should work.

### 10. Coherence as optimization objective

When `semantic-optimization` becomes operational (an actual experiment/MLOps-style loop), coherence scoring IS the objective function:

```
Pattern ──defines──→ "what good looks like" (target)
    │                        │
    │                   Coherence ──measures──→ gap from target (loss)
    │                        │
    └── Optimization ←──minimizes──┘
         (uses coherence as objective/guardrail)
```

- **Pattern** sets the target state (prescriptive)
- **Coherence scoring** measures the gap between target and reality (evaluative)
- **Optimization** drives the gap toward zero (directive)

The three modes of coherence map directly to optimization signals:

| Mode | Optimization signal | Effect on objective |
| --- | --- | --- |
| **Governance** gaps | Coverage loss — something exists without justification | Increases loss |
| **Discovery** | Free improvement — coverage increases without effort | Decreases loss (compounds) |
| **Regression** | The primary loss trigger — something that was coherent degraded | Triggers corrective action |

#### Current state: L1-L2 audit via `/arch-sync`

Today, patterns are audited manually through the architecture sync workflow. `/arch-sync` validates the Pattern → Capability → Script chain and reports gaps. This is coherence assessment at maturity level 1-2 (human decides, agent executes).

#### Infrastructure already in place: Agentic Lineage

The episode-centric provenance system (ADR: ISSUE-101) already captures coherence signals per operation:

- Each `Episode` has a `coherence_score` field (0-1 alignment signal)
- `OperationType.DECLARE_PATTERN` exists but is not yet invoked
- Episodes track `context_pattern_ids` (which patterns were considered during an operation)

When optimization becomes operational, episodes are the telemetry that feeds the objective function. The lineage system is the instrumentation layer; coherence assessment is the scoring layer; optimization is the control loop.

#### Coherence gates vs. coherence audit in optimization context

The default posture remains "audit, not gate" (Decision §3). However, an operational optimization loop is a natural place for hard thresholds — coherence guardrails that prevent regression below a minimum score. This is a specific workflow gate, not a change to the default posture. The flexible edge remains free; optimization gates apply to proposed changes within the stable core.

## Consequences

### What actually changes

The schema is already correct — multiple independent aggregates are already implemented. The change is primarily **vocabulary and framing**, not infrastructure.

#### Nothing changes (schema is already right)

- `pattern` + `pattern_edge` tables — Pattern Aggregate, already correct
- `entity` table with type discriminator — still works for content, capability, repository
- `edge` table with all predicates — still works
- `surface` + `surface_address` — Surface Aggregate, already correct
- `delivery` table — already correct (reclassified from separate aggregate to child of Content)
- `brand` + `product` + `brand_relationship` — Brand Aggregate, already correct
- All views, fitness functions, indexes, scripts — no changes

#### Documentation updates (framing changes)

- UBIQUITOUS_LANGUAGE.md: "Pattern as sole aggregate root" → "Pattern as aggregate root of Pattern Aggregate + core domain concept"
- UBIQUITOUS_LANGUAGE.md: Add Coherence Assessment definition
- UBIQUITOUS_LANGUAGE.md: Reclassify Capability as Entity, Repository as Value Object
- STRATEGIC_DDD.md: Add Coherence Assessment to domain model
- ADR-0004: Mark "aggregate root" section as superseded by ADR-0012

#### Future work (deferred)

- Coherence Assessment table/schema — when coherence scoring is operational
- PIM/CRM pattern registration — when CRM is built out
- Schema.org pattern registration — when Brand aggregate is active

### Positive

- **Completes the Semantic Optimization Loop** — both forces have first-class domain representation
- **Formalizes implicit aggregates** — no more claiming one aggregate root governs everything
- **Low implementation cost** — schema doesn't change; this is a vocabulary correction
- **Enables temporal coherence tracking** — assessments over time show whether changes helped or hurt
- **Coherence becomes actionable** — gaps and recommended actions are domain objects, not just dashboard metrics
- **Cleaner DDD alignment** — aggregate boundaries match transactional realities
- **Pattern prescribes aggregate structure** — each supporting aggregate traces to a 3P pattern (DAM → Content, Schema.org → Brand), demonstrating that Pattern produces structure at every level

### Negative

- **Schema addition required (deferred)** — Coherence Assessment needs a new table eventually
- **ADR-0004 framing needs revision** — "Pattern as aggregate root" language in multiple docs

### Risks

- **Over-modeling** — Coherence Assessment could become complex before there's data to populate it. Mitigation: start with the aggregate shape, defer schema until coherence scoring is operational.

## Implementation Plan

### Phase 1: Documentation (this ADR)

1. ~~Create ADR-0012~~ ✅
2. Create session notes for design session
3. Review with stakeholder

### Phase 2: Domain model updates

1. Update UBIQUITOUS_LANGUAGE.md — revise "Pattern as sole aggregate root" language, add Coherence Assessment definition, enumerate aggregates
2. Update STRATEGIC_DDD.md — add Coherence Assessment to capability registry or domain model section
3. Update ADR-0004 status — mark "aggregate root" section as superseded by ADR-0012

### Phase 3: Schema (deferred)

1. Design Coherence Assessment table or entity_type extension
2. Define edges from assessments to patterns and capabilities
3. Integrate with existing fitness functions and coverage views
4. Connect to lineage system (assessments as tracked events)

## Session Log

### 2026-02-19: Design session — Pattern + Coherence discovery

#### Phase 1: Aggregate root confusion

- Started from: "I only declare 1 aggregate root (Pattern) for the whole project — that seems wrong"
- Identified confusion between "most important domain concept" and "aggregate root"
- Enumerated 7+ aggregates already implicit in the schema
- Explored whether three-layer architecture (ADR-0009) already represents multiple aggregates — conclusion: layers are modules, aggregates live within them

#### Phase 2: The missing force

- CRM lifecycle example revealed the missing Coherence Assessment concept
- Key insight: Coherence is directive, not just evaluative — can trigger pattern reversal
- Refined earlier "Pattern + Provenance" framing — Provenance is a property of Pattern, not a peer force
- The Semantic Optimization Loop IS SemOps: Pattern pushes, Coherence aligns

#### Phase 3: DDD building block classification

- Capability is an Entity (not an aggregate) — produced by Pattern decisions, measured by Coherence, implements multiple patterns
- Repository is a Value Object — identity doesn't matter, role and delivery mapping do ("repos can be reorganized without changing the domain model")
- Capability exists in the space between the two core aggregates, referenced by both, owned by neither

#### Phase 4: Coherence as audit

- Coherence is NOT gated governance — it's an audit
- Aggregate root invariants (SKOS hierarchy, provenance rules) protect the stable core
- The flexible edge is free to exist — orphan entities, unattributed scripts, experimental infra
- Coherence audits the gap between what exists and what's formalized
- Incorporation (moving from flexible edge to stable core) is voluntary — that's when aggregate root invariants kick in
- You CAN build coherence gates for specific workflows, but the default posture is informational

#### Phase 5: Three modes of coherence

- Governance: something exists without justification — report the coverage gap
- Discovery: something aligns but isn't tracked — "this infra is actually part of an existing capability we didn't realize" (most valuable mode — the loop accelerates itself)
- Regression: something that was coherent broke — report the trade-off

#### Phase 6: Fitness functions as sensors

- Existing fitness functions and coverage views are coherence sensors
- As standalone tools, they're stateless (run, report, forget)
- As sensors feeding Coherence Assessment, signals get identity, lifecycle, and action tracking
- Full traceability chain (Pattern → Capability → Script) is Coherence's audit domain

#### Phase 7: Supporting aggregate classification

- Content aggregate: DAM pattern defines the structure. Content Entity is root, Delivery is child (publication record). "This asset and its publication history" is the consistency boundary.
- Surface: separate aggregate (channels exist independently of content)
- Brand (PIM/CRM): Schema.org + PIM pattern. Currently scaffolding — one brand, one person, no products. Valid flexible-edge state. Pattern unregistered (coherence audit finding).
- Key insight: adopted 3P patterns prescribe aggregate boundaries in supporting domains, same way Zendesk would prescribe CRM aggregate structure.

#### Phase 8: Impact assessment

- Schema doesn't change — the hard-wiring is already correct
- Change is vocabulary/framing, not infrastructure
- Delivery reclassified from separate aggregate to child of Content (no schema change, just understanding)
- Coherence Assessment schema deferred until operational
- PIM/CRM pattern registration deferred until CRM buildout

#### Phase 9: Coherence as optimization objective

- When `semantic-optimization` becomes operational, coherence scoring IS the objective function (or at minimum a guardrail)
- Pattern = target, Coherence = loss function, Optimization = control loop that minimizes the gap
- Three coherence modes map directly to optimization signals: governance = coverage loss, discovery = free improvement, regression = primary loss trigger
- Current state: L1-L2 audit via `/arch-sync` — manual pattern lifecycle management
- Agentic Lineage (ISSUE-101) already captures coherence signals per episode — `coherence_score` field, `context_pattern_ids`, `DECLARE_PATTERN` operation type (unused)
- Episodes are the telemetry layer; Coherence Assessment is the scoring layer; optimization is the control loop
- Coherence gates (hard thresholds on regression) are natural for the optimization loop, without changing the default "audit not gate" posture for the flexible edge

## References

- [ADR-0004: Pattern as Aggregate Root](ADR-0004-schema-phase2-pattern-aggregate-root.md) — foundational, partially superseded
- [ADR-0009: Three-Layer Architecture](ADR-0009-strategic-tactical-ddd-refactor.md) — layers as organizational modules
- [UBIQUITOUS_LANGUAGE.md](../../schemas/UBIQUITOUS_LANGUAGE.md) — domain definitions
- [STRATEGIC_DDD.md](../STRATEGIC_DDD.md) — capability registry
- [Issue #142](https://github.com/semops-ai/semops-core/issues/142) — tracking issue
- [Issue #141](https://github.com/semops-ai/semops-core/issues/141) — bounded context alignment (related)
- Evans, Eric. *Domain-Driven Design* (2003) — Aggregates, Ch. 6
