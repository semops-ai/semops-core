# ADR-0011: Agent Governance Model

> **Status:** Complete
> **Date:** 2026-02-14
> **Related Issue:** [](https://github.com/semops-ai/semops-core/issues/112)
> **Extends:** ADR-0009 (three-layer architecture), ADR-0004 (pattern as aggregate root)
> **Spec:** [schemas/GOVERNANCE_MODEL.md](../../schemas/GOVERNANCE_MODEL.md)

## Executive Summary

Defines how SemOps governs agent-produced and agent-managed artifacts. Introduces a 5-stage universal lifecycle (draft/active/stable/deprecated/archived), two governance modes (self-correcting andon cord for internal operations, hard gates for public boundary), and four driving principles that formalize the transition from manual governance to automated agent governance.

## Context

### What existed before

- `lifecycle_stage` with 3 values (draft/active/retired) — implemented in source_config.py and source configs
- `delivery.approval_status` — exists in schema but not enforced
- Ingestion episodes (ingestion_episode table) — already tracking agent operations
- Manual governance via session notes, ADRs, commit messages, architecture sync

### What was missing

- No universal lifecycle model across all entity types
- No definition of what agents can do autonomously
- No spec for how manual governance transitions to automated
- No formal connection between coherence scoring and lifecycle transitions
- `active` doing double duty (operational AND coherence baseline)
- `retired` conflating deprecated (still visible) and archived (gone)

## Decision

### 1. Five-stage universal lifecycle

Replace 3-value lifecycle_stage with 5 stages adopted from 3P patterns (CI/CD promotion, Backstage catalog, DDD aggregate):

```
DRAFT → ACTIVE → STABLE → DEPRECATED → ARCHIVED
```

- **stable** distinguishes "trusted coherence baseline" from "operational"
- **deprecated** vs **archived** separates "signaled for retirement" from "removed"

### 2. Universal governance matrix

Same treatment for ALL entity types — no exceptions:

| | draft | active | stable | deprecated | archived |
|---|---|---|---|---|---|
| **Lineage** | created | validated | promoted | flagged | removed |
| **Coherence** | forecasted | measured | **baseline** | excluded | excluded |
| **Search** | filtered | default | prioritized | flagged | excluded |

Entity type determines creation/iteration mechanism, not governance coverage.

### 3. Two governance modes

- **Internal (andon cord):** act → record → auto-recover → continue. Self-correcting semantic governance. 3P: andon cord + jidoka (Lean/TPS). 1P: the system fixes the problem itself.
- **Public boundary (hard gate):** act → record → gate → approve → publish. Required for any transition that makes content visible to customers/public.

Mode is determined by **delivery target**, not entity type or lifecycle stage.

### 4. Sticky lifecycle + episodes as version history

Entities are mutable (`ON CONFLICT DO UPDATE`). Lifecycle_stage does NOT reset on iteration. The episode chain is the version history. Coherence scoring detects if changes introduced drift.

### 5. Scale Projection levels for transition authority

| Level | Model | Current Examples |
|-------|-------|-----------------|
| L1 | Human drives | Most operations |
| L2 | Agent recommends, human approves | — |
| L3 | Agent acts, human reviews | Ingestion classification |
| L4 | Agent autonomous, coherence validates | Ingestion episodes |
| L5 | Full agentic, anomalies trigger HITL | Target state |

## Consequences

### Positive

- Universal lifecycle eliminates per-type special cases
- Coherence scoring gains a formal role in governance (quality gate)
- Clear path from manual (L1) to autonomous (L5) governance
- Draft entities become proactively useful (forecast zone)
- Episode chain provides full version history without versioning table

### Negative

- Migration needed: existing `retired` entities → `deprecated` or `archived`
- `stable` stage requires defining promotion criteria per entity type
- Governance model doc adds another schema-level document to maintain

### Risks

- Coherence scoring doesn't exist yet at the level needed for auto-recovery (L4-L5)
- Per-entity governance specs needed to operationalize the universal matrix

## Implementation Plan

1. ~~5-stage lifecycle in source_config.py, source configs, UBIQUITOUS_LANGUAGE.md~~ **DONE**
2. ~~GOVERNANCE_MODEL.md spec document~~ **DONE**
3. ~~Per-entity governance spec (Pattern as aggregate root)~~ **DONE**
4. ~~Per-entity governance spec (Capability, Repository, Content)~~ **DONE**
5. ~~DB migration for existing `retired` entities~~ **N/A** — 0 retired entities in DB
6. ~~`pattern_coverage` view fix — edge-based capability/repo counts~~ **DONE**
7. ~~`/arch-sync` Capability → Pattern traceability check (Step 6b)~~ **DONE**
8. ~~`ingest_architecture.py` lifecycle_stage derivation from edge coverage~~ **DONE**
9. ~~`ingest_domain_patterns.py` Layer 2 governance audit (`--audit` flag)~~ **DONE**
10. ~~semops-dx-orchestrator references (GLOBAL_ARCHITECTURE.md, system landscape)~~ **DONE**
11. ~~Revisit jidoka as a potential 3P pattern registration~~ **DEFERRED** — better as documented analogy in GOVERNANCE_MODEL.md than a registered pattern; revisit when L4-L5 coherence scoring capabilities exist

## Session Log

### 2026-02-14

- Researched lifecycle patterns across DDD, Backstage, CI/CD — all converge on 5 universal phases
- Identified 4 driving principles (three-layer governance, temporal complements, andon cord, draft as forecast zone)
- Resolved all 5 design questions from original issue
- Implemented 5-stage lifecycle in code and documentation
- Created GOVERNANCE_MODEL.md spec
- Added two operational layers: Layer 1 (state inspection / andon cord) and Layer 2 (content verification / continuous audit)
- Completed per-entity governance for all 4 entity types (Pattern, Capability, Repository, Content)
- Key design insight: Pattern is stateless — activation is per-context via `implements` edge + capability lifecycle
- 3P→1P innovation is per-context: same 3P anchor, N different applications with N different 1P innovations
- Pattern emergence: 1P concepts become patterns through architectural decision, not lifecycle promotion
- Architecture precedes implementation: model (register pattern, declare capability) before building
- Registration is an agentic guard rail (jidoka): system enforces pattern registration as prerequisite for `implements` edges

### 2026-02-15

- Investigated DB migration: 0 `retired` entities, 90 NULL lifecycle_stage (all from architecture ingestion scripts)
- Discovered `pattern_coverage` view gap: only measured documentation coverage (FK), not architectural coverage (edges). Fixed to use `implements`/`delivered_by` edge table. 33 patterns now show capability coverage (was 7).
- Extended `/arch-sync` with Step 6b: Capability → Pattern traceability check (governance trigger)
- Implemented `derive_lifecycle_stages` in `ingest_architecture.py`: capabilities get `active` when pattern_count > 0 AND repo_count > 0, repos get `active` when delivering capabilities. All 18 capabilities and 7 repos now have lifecycle_stage in metadata.
- Added `--audit` flag to `ingest_domain_patterns.py`: Layer 2 governance cross-check reports coverage mismatches. First run: 0 HIGH, 1 MEDIUM (66 dp-* content entities missing lifecycle_stage), 22 INFO.
- Key design discovery: two separate edge mechanisms (FK vs edge table) were disconnected — now unified in `pattern_coverage` view
- Fixed dp-* content entity lifecycle_stage (66 entities, now all `active` in metadata)
- Added governance model section to GLOBAL_ARCHITECTURE.md (§ Governance Model) and SYSTEM_LANDSCAPE.md (§ Agent Governance Model)
- Added ADR-0011 to ADR_INDEX.md (both repo section and timeline)
- Reviewed jidoka as 3P pattern — deferred (better as documented analogy; revisit when L4-L5 coherence capabilities exist)
- **All 11 implementation plan items complete** (9 DONE, 1 N/A, 1 DEFERRED)

## References

- [schemas/GOVERNANCE_MODEL.md](../../schemas/GOVERNANCE_MODEL.md) — full governance model spec
- [Issue #112](https://github.com/semops-ai/semops-core/issues/112) — design discussion
- [](https://github.com/semops-ai/semops-dx-orchestrator/issues/138) — alignment/reframing
- [ADR-0009](ADR-0009-strategic-tactical-ddd-refactor.md) — three-layer architecture
- [ADR-0004](ADR-0004-schema-phase2-pattern-aggregate-root.md) — pattern as aggregate root
