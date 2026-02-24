# ADR-0006: V1 Documentation Plan

> **Status:** In Progress
> **Date:** 2025-12-07
> **Related Issues:** [#79](https://github.com/semops-ai/semops-core/issues/79), [#78](https://github.com/semops-ai/semops-core/issues/78)
> **Builds On:** [ADR-0004-concept-aggregate-root](./ADR-0004-concept-aggregate-root.md)

---

## Executive Summary

Consolidates scattered planning docs into a single execution plan for V1 documentation. Defines three phases: Architecture Documentation, Source Document Cleanup (#79), and Publisher Integration (#78).

---

## Context

Multiple overlapping planning documents existed:
- `concept-promotion-plan.md` (phases 1-4 complete)
- `ISSUE-62-SOURCE-INGESTION-PIPELINE.md` (complete)
- `ADR-0004-schema-phase2-pattern-aggregate-root.md` (complete)
- Various open GitHub issues with unclear priorities

This created confusion about what to work on next. The infrastructure is built (61 concepts, 195 edges, 183 classifications, Neo4j synced) but documentation explaining the system is incomplete.

---

## Decision

Create a single ADR that tracks V1 documentation work. Close/defer scattered issues. Execute in order: Phase 1 → Phase 2 (#79) → Phase 3 (#78).

---

## Current State

### Infrastructure (Complete)
- PostgreSQL + pgvector running (Supabase)
- Neo4j running with 61 nodes, 195 edges
- n8n workflows available
- Schema: phase2-schema.sql applied (concept as aggregate root)

### Data State
| Table | Count | Status |
|-------|-------|--------|
| `concept` | 63 | Ingested from project-ike-private + 2 new hubs |
| `concept_edge` | 219 | SKOS relationships (broader/narrower/related) |
| `classification` | 183 | 3 classifiers × 61 concepts |
| `entity` | 114 | Ingested docs from project-ike-private |

### What's Working
- Concept ingestion pipeline (`scripts/ingest_from_source.py`)
- Embedding generation (OpenAI text-embedding-3-small)
- Tiered classifier pipeline (rule-based, embedding, graph)
- Neo4j sync (`scripts/sync_concepts_to_neo4j.py`)
- RAG chat via n8n (basic)

---

## Implementation Plan

**Goal:** Clean, accurate documentation that explains the system.

### Phase 1: Architecture Documentation
- [ ] Complete `GLOBAL_ARCHITECTURE.md` - technical stack and repo relationships
- [ ] Complete `SYSTEM_CONTEXT.md` - design philosophy
- [ ] Update user-level `~/.claude/CLAUDE.md` with any missing context

### Phase 2: Source Document Cleanup 
The 61 concepts came from project-ike-private docs. Those source docs have:
- Inconsistent/outdated frontmatter (ignore it - database is source of truth)
- Good definitions (already extracted to concept table)
- Hub structure that needs validation

**Tasks:**
- [x] Validate hub hierarchy matches database (DDA → DDD relationship fixed)
- [x] Identify orphan concepts needing relationships (17 flagged by embedding classifier)
- [x] Address isolated concept: `schema-theory-constructivism` (no edges)
- [x] Create canonical hub documents using hub-template.md
- [x] Document that source doc frontmatter is legacy/unvalidated

### Phase 3: Publisher Integration 
- [ ] Ensure concept table is ready for ike-publisher consumption
- [ ] Define API/interface for publisher to query concepts
- [ ] Test concept-to-content linking

---

## Deferred Work

These are parked for later - not blocking V1:

| Work | Issue | Why Deferred |
|------|-------|--------------|
| Advanced RAG | #74 | Basic RAG works; optimize later |
| 3P Ingestion | #68 | Focus on 1p content first |
| Semantic Coherence | #72 | Need stable concept graph first |
| MCP Server | #76 | Nice-to-have, not blocking |
| Concept Promotion | - | Need v1 docs first; 61 concepts sufficient |

---

## Superseded/Closed Issues

| Issue | Title | Status | Reason |
|-------|-------|--------|--------| | | Phase 2: Classification Refinement & Diff-Based Updates | Closed | Classification complete (183 records) | | | Phase 3: Hybrid Search, Docling, Graph & Local Models | Closed | Deferred to Advanced RAG | | | Reclass content | Closed | Merged into Phase 2 | | | Global Context and architecture | Closed | Merged into Phase 1 |

---

## Key Files Reference

### Architecture
- `docs/GLOBAL_ARCHITECTURE.md` - Technical stack
- `docs/SYSTEM_CONTEXT.md` - Design philosophy
- `~/.claude/CLAUDE.md` - User-level Claude instructions

### Schema
- `schemas/UBIQUITOUS_LANGUAGE.md` - Domain terms
- `schemas/phase2-schema.sql` - Current database schema

### Scripts
- `scripts/ingest_from_source.py` - Entity ingestion
- `scripts/run_classifiers.py` - Classifier pipeline
- `scripts/sync_concepts_to_neo4j.py` - Neo4j sync
- `scripts/generate_concept_embeddings.py` - Embedding generation

### Templates
- `docs/domain-patterns/hub-template.md` - Hub document template

---

## Session Log

### 2025-12-07: Plan Consolidation
**Status:** Complete
**Tracking Issue:** N/A (meta-work)

**Completed:**
- Created MASTER-PLAN.md (temporary)
- Closed issues #65, #69, #70, #75
- Created issue #79 for Phase 2
- Migrated plan to this ADR
- Deleted MASTER-PLAN.md

**Next Session Should Start With:**
1. Phase 1: Complete GLOBAL_ARCHITECTURE.md
2. Then Phase 2 (#79): Source document cleanup

### 2025-12-07: Phase 2 Complete
**Status:** Complete
**Tracking Issue:** 

**Completed:**
- Validated L0 hub hierarchy: `semantic-operations` (1p), `hard-problem-of-ai` (1p), `first-principles` (3p)
- Created `first-principles` and `dikw-mental-model` concepts in database
- Wired `semantic-operations` with 4 pillars: real-data, dikw-mental-model, semantic-optimization, domain-driven-architecture
- Wired `domain-driven-design` under `domain-driven-architecture`
- Wired all orphan concepts to appropriate parents
- Added edges for isolated concepts (schema-theory-constructivism, information-theory)
- Created 4 canonical hub documents in project-ike-private/docs/HUBS/:
 - hub-semantic-operations.md (L0 hub)
 - hub-hard-problem-of-ai.md (L0 hub)
 - hub-first-principles.md (L0 hub)
 - hub-domain-driven-design.md (child hub)
- Created FRONTMATTER-STATUS.md documenting source doc frontmatter is legacy/unvalidated
- Synced 63 concepts, 219 edges to Neo4j

**Database State:**
- Concepts: 63 (was 61)
- Edges: 219 (was 195)
- Provenance: 32 1p, 31 3p

**Next Session Should Start With:**
1. Close Issue #79 (Phase 2 complete)
2. Phase 3 (#78): Publisher Integration

---

## References

- 
- 
- [ADR-0004: Concept Aggregate Root](./ADR-0004-concept-aggregate-root.md)

---

**End of Document**
