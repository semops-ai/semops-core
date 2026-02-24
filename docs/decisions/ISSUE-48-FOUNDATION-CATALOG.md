# Issue #48: Foundation Entity Catalog & Documentation Standards

> **Status:** Complete | **Date:** 2025-11-25
> **Related Issue:** https://github.com/timjmitchell/ike-knowledge-ops/issues/48
> **Builds On:** [Issue #47 Concept Strategy](ISSUE-47-CONCEPT-STRATEGY.md)

---

## Executive Summary

This issue implemented the **foundation entity catalog** - a golden sample of 15 core 1P concept documents from project-ike. Additionally, it established **documentation standards** for relationship extraction and citation patterns.

**Key Deliverables:**
1. ✅ Foundation entity catalog (15 entities in YAML format)
2. ✅ Mermaid concept graph visualization
3. ✅ Related Links convention for automated edge extraction
4. ✅ Inline citation convention for 3P entity discovery
5. ✅ Refactored documentation style guides (separation of concerns)

---

## Part 1: Foundation Entity Catalog

### Purpose

Create a **golden sample** of 15 1P concept documents that:
- Demonstrates complete schema compliance
- Establishes the foundational knowledge graph
- Provides a template for future entity catalogs
- Enables QA before full ingestion pipeline

### Entities Cataloged

| Entity ID | Title | Domain | SKOS Depth |
|-----------|-------|--------|------------|
| `dikw` | DIKW Hierarchy | First Principles | 0 (foundational) |
| `first-principles` | First Principles Thinking | First Principles | 0 |
| `real-data` | Real Data | Real Data | 0 |
| `domain-driven-design` | Domain-Driven Design | Architecture | 0 |
| `physics-of-data` | Physics of Data | Real Data | 1 |
| `global-architecture` | Global Architecture | Architecture | 1 |
| `semantic-operations` | Semantic Operations | Core | 1 |
| `semantic-coherence` | Semantic Coherence | Semantic Ops | 2 |
| `semantic-optimization` | Semantic Optimization | Semantic Ops | 2 |
| `semantic-coherence-audit-playbook` | Audit Playbook | Semantic Ops | 3 |
| `ai-transformation-problem` | AI Transformation Problem | AI | 2 |
| `the-hard-problem` | The Hard Problem | AI | 3 |
| `regression-paradox` | The Regression Paradox | AI | 3 |
| `runtime-emergence` | Runtime Emergence | AI | 2 |
| `semantic-decoherence` | Semantic Decoherence | Semantic Ops | 3 |

### Files Created

- **[foundation-entity-catalog.yaml](../foundation/foundation-entity-catalog.yaml)** - Complete entity records
- **[foundation-concept-graph.mmd](../foundation/foundation-concept-graph.mmd)** - Mermaid visualization
- **[foundation/README.md](../foundation/README.md)** - Documentation and workflow

### Entity Structure

Each entity includes:
```yaml
entity-id:
 entity_id: entity-id
 title: "Human-Readable Title"
 version: "1.0"
 asset_type: file
 provenance: 1p
 approval_status: approved
 visibility: public

 filespec:
 $schema: filespec_v1
 uri: "https://github.com/timjmitchell/project-ike/blob/main/docs/..."
 format: markdown
 platform: github

 attribution:
 $schema: attribution_v1
 authors: ["Tim Mitchell"]
 license: "CC-BY-4.0"

 metadata:
 $schema: content_metadata_v1
 content_type: github_doc
 primary_concept: entity-id
 preferred_label: "Human-Readable Title"
 definition: "..."
 broader_concepts: [parent-concept]
 narrower_concepts: [child-concept]
 related_concepts: [related-concept]

 edges:
 - destination_id: related-entity
 predicate: depends_on
 strength: 1.0
```

---

## Part 2: Concept Graph Visualization

### SKOS Hierarchy

The concept graph follows W3C SKOS `broader`/`narrower` relationships:

```
Foundational (depth 0)
├── dikw
├── first-principles
├── real-data
└── domain-driven-design

Intermediate (depth 1)
├── physics-of-data ← real-data
├── global-architecture ← domain-driven-design
└── semantic-operations ← dikw, domain-driven-design

Specialized (depth 2+)
├── semantic-coherence ← semantic-operations
├── semantic-optimization ← semantic-operations
├── ai-transformation-problem ← semantic-operations
└── ...
```

### Visualization Approach

**Decision:** Use Mermaid diagrams (`.mmd` files) for visualization

**Rationale:**
- GitHub renders `.mmd` files natively
- No Python runtime required for QA
- VS Code extension support
- Copy/paste to mermaid.live for interactive editing

**Rejected:** Python-based visualization tools
- Removed `tools/knowledge-graph-visualizer/` directory
- Full ingestion/visualization deferred to dockerized runtime

---

## Part 3: Documentation Standards

### Decision 1: Related Links Convention

**Status:** ✅ **Implemented**

**Purpose:** Enable automated edge extraction from markdown documents

**Convention:**
```markdown
---

## Related Links

### Citations
- [Title](URL) - 3P authoritative sources

### Builds On
- [Title](relative/path.md) - 1P foundational concepts

### See Also
- [Title](relative/path.md) - Related content
```

**Predicate Mapping:**

| Section Heading | Edge Predicate |
|-----------------|----------------|
| **Citations** | `cites` |
| **Builds On** | `depends_on` |
| **See Also** | `related_to` |
| **Derived From** | `derived_from` |
| **Implements** | `implements` |

**Files Created:**
- [related-links-convention.md](../domain-patterns/related-links-convention.md)
- Updated [project-ike/STYLE_GUIDE.md](https://github.com/timjmitchell/project-ike/blob/main/STYLE_GUIDE.md)
- Created 

---

### Decision 2: Inline Citation Convention

**Status:** ✅ **Implemented**

**Purpose:** Enable 3P entity discovery from inline prose citations

**Convention:**
```markdown
According to [Ackoff (1989)](https://doi.org/10.1016/0378-7206(89)90062-1), wisdom requires...

This aligns with the [DIKW pyramid](https://en.wikipedia.org/wiki/DIKW_pyramid) framework.
```

**Format:**

| Context | Format |
|---------|--------|
| Academic paper | `[Author (Year)](URL)` |
| Named resource | `[Resource Name](URL)` |
| With description | `[Author (Year)](URL) description...` |

**Why This Format:**
1. Self-documenting - Link text shows attribution inline
2. Standard markdown - Renders correctly everywhere
3. Parseable - Agents can extract external URLs as 3P entity candidates
4. Human readable - Clear even without clicking the link

**Files Updated:**
- [project-ike/STYLE_GUIDE.md](https://github.com/timjmitchell/project-ike/blob/main/STYLE_GUIDE.md) - Added "Inline Citations" section

---

### Decision 3: Style Guide Separation

**Status:** ✅ **Implemented**

**Problem:** Two style guides with overlapping content

**Solution:** Clear separation of concerns

| Guide | Location | Focus |
|-------|----------|-------|
| **Ike Framework Style Guide** | project-ike/STYLE_GUIDE.md | Content authoring: headings, frontmatter, citations, Related Links |
| **Schema Documentation Style** | ike-knowledge-ops/docs/domain-patterns/doc-style.md | Schema docs: JSON/YAML examples, validation rules, terminology |

**Changes:**
- Refactored `doc-style.md` from ~550 lines to ~210 lines
- Removed duplicated content (headings, lists, emphasis, etc.)
- Added cross-reference to main style guide
- Focused on schema-specific conventions only

---

## Part 4: Workflow Decisions

### Decision 4: YAML + Mermaid for Pre-Ingestion QA

**Status:** ✅ **Implemented**

**Rationale:**
- Full ingestion scripts will be part of dockerized runtime
- Don't need Python runtime just for QA
- YAML is human-readable and lintable
- Mermaid provides visual graph QA

**Workflow:**
1. Create YAML catalog following `foundation-entity-catalog.yaml` structure
2. Create Mermaid diagram showing concept hierarchy
3. Validate YAML manually or with linters
4. Visual QA via GitHub, mermaid.live, or VS Code
5. Full validation against `phase1-schema.sql` deferred to runtime

**Removed:**
- `tools/knowledge-graph-visualizer/` directory (Python scripts)

---

### Decision 5: Edges Inline with Entities

**Status:** ✅ **Implemented**

**Context:** Initial design had edges in separate section at bottom of YAML

**Decision:** Include edges inline on each entity

**Before:**
```yaml
entities:
 entity-a:
 # ...entity data...
 relationships: []

edges:
 - source_id: entity-a
 destination_id: entity-b
 predicate: depends_on
```

**After:**
```yaml
entities:
 entity-a:
 # ...entity data...
 edges:
 - destination_id: entity-b
 predicate: depends_on
 strength: 1.0
```

**Rationale:**
- Clearer ownership - edges belong to source entity
- Easier to maintain - all entity data in one place
- Better for ingestion - process entity with its edges together

---

## Part 5: Schema Compliance

### Issue #47 Decisions Implemented

| Decision | Status |
|----------|--------|
| No `semantic_type` field | ✅ Not used |
| No `abstraction_level` field | ✅ Not used |
| Concepts as metadata only | ✅ `primary_concept` field |
| SKOS hierarchy via `broader_concepts` | ✅ Implemented |

### W3C SKOS Compliance

All metadata uses SKOS-aligned fields:
- `preferred_label` ← `skos:prefLabel`
- `definition` ← `skos:definition`
- `broader_concepts` ← `skos:broader`
- `narrower_concepts` ← `skos:narrower`
- `related_concepts` ← `skos:related`

### Phase 1 Schema Compliance

All entities follow Phase 1 constraints:
- `asset_type: file` (all are GitHub markdown docs)
- `provenance: 1p` (all are first-party content)
- `approval_status: approved` (all are published docs)
- `visibility: public` (public GitHub repo)

---

## Summary of Deliverables

| Deliverable | File/Location | Status |
|-------------|---------------|--------|
| Entity catalog (15 entities) | [foundation-entity-catalog.yaml](../foundation/foundation-entity-catalog.yaml) | ✅ |
| Concept graph visualization | [foundation-concept-graph.mmd](../foundation/foundation-concept-graph.mmd) | ✅ |
| Foundation README | [foundation/README.md](../foundation/README.md) | ✅ |
| Related Links convention | [related-links-convention.md](../domain-patterns/related-links-convention.md) | ✅ |
| Inline citation convention | project-ike/STYLE_GUIDE.md | ✅ |
| Style guide refactor | [doc-style.md](../domain-patterns/doc-style.md) | ✅ |
| project-ike Issue #10 | Add Related Links to docs | ✅ Created |

---

## Next Steps

1. **User edits:** Refine `foundation-entity-catalog.yaml` with additional edges/metadata
2. **3P entities:** Add 3P reference entities (DIKW Wikipedia, DDD book, etc.)
3. **project-ike Issue #10:** Add Related Links sections to 15 foundation documents
4. **Ingestion:** Dockerized ingestion scripts (deferred to runtime environment)

---

**End of Document**
