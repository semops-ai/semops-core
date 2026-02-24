# ADR-0007: Concept Content Value Objects

> **Status:** Proposed
> **Date:** 2025-12-07
> **Related Issue:** [](https://github.com/semops-ai/semops-core/issues/83) - Schema Option: Concept Content Value Objects
> **Builds On:** [ADR-0004-concept-aggregate-root](./ADR-0004-concept-aggregate-root.md)

---

## Executive Summary

Proposes a schema pattern where **Concept** remains the aggregate root, with **Content Value Objects** representing composable pieces (atoms, lenses, examples, etc.) that belong to the concept. Surfaces provide governance boundaries for where content is delivered.

---

## Context

The current schema has:
- `concept` - aggregate root with definition, provenance, SKOS relationships
- `concept_edge` - relationships between concepts
- `entity` - independent content with own lifecycle
- `surface` / `delivery` - publication destinations

**Problem:** Where do composable content pieces live?

Examples of content that belongs to a concept but isn't the concept itself:
- **Atom** - canonical markdown document explaining the concept
- **Lens** - a perspective/framing (e.g., "AI transformation lens on DDD")
- **Code Example** - implementation illustrating the concept
- **DIKW Table** - structured artifact showing transformation stages
- **Diagram** - visual representation

These aren't independent entities - they have no meaning without their parent concept.

---

## Decision

### Option A: Content as Value Objects (Proposed)

Content pieces are **value objects** belonging to the concept aggregate:

```sql
CREATE TABLE concept_content (
 concept_id text REFERENCES concept(id) ON DELETE CASCADE,
 content_type text NOT NULL, -- atom, lens, code_example, dikw_table, diagram
 version integer DEFAULT 1,
 uri text NOT NULL, -- file:///path/to/content.md
 content_hash text, -- sha256 for change detection
 status text DEFAULT 'active', -- active | deprecated | draft
 metadata jsonb DEFAULT '{}', -- type-specific fields
 created_at timestamptz DEFAULT now,
 PRIMARY KEY (concept_id, content_type, version)
);
```

**Value Object Characteristics:**
- No independent identity (composite PK from parent + type + version)
- Belongs to exactly one aggregate root
- Immutable - versions rather than mutates
- Deletable without affecting concept integrity

**Metadata by Content Type:**
```jsonc
// atom
{"summary": "...", "key_insight": "..."}

// lens
{"perspective": "ai-transformation", "target_audience": "executives"}

// code_example
{"language": "python", "framework": "pydantic"}

// dikw_table
{"stages": ["data", "information", "knowledge", "wisdom"]}

// diagram
{"format": "svg", "tool": "mermaid"}
```

### Surface Governance

Surfaces have varying governance levels that determine drift tracking:

```sql
ALTER TABLE surface ADD COLUMN governance text
 DEFAULT 'loose'
 CHECK (governance IN ('strict', 'loose', 'ephemeral', 'frozen'));
```

| Governance | Meaning | Drift Policy |
|------------|---------|--------------|
| `strict` | Source of truth (e.g., private repos) | Content IS the VO |
| `loose` | Editorial content (e.g., blog) | Flag for review if concept changes |
| `ephemeral` | Social/transient (e.g., tweets) | Don't track, point-in-time snapshot |
| `frozen` | Archived/client deliverables | Intentionally out of date, no alerts |

### Full Model

```
┌─────────────────────────────────────────────────────────────────┐
│ Concept Aggregate │
│ │
│ concept: semantic-coherence (root) │
│ ├── definition: "A state of stable..." │
│ ├── provenance: 1p │
│ │ │
│ └── concept_content (Value Objects) │
│ ├── (atom, v1) → atom.md │
│ ├── (lens, v1) → lens-ai-transformation.md │
│ ├── (code_example, v1) → example.py │
│ └── (dikw_table, v1) → dikw-breakdown.md │
│ │
└─────────────────────────────────────────────────────────────────┘
 │
 │ delivery
 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Surfaces │
│ │
│ github-project-ike-private (strict) │
│ └── atom.md, lens.md (source of truth) │
│ │
│ wordpress-blog (loose) │
│ └── blog-post-coherence.md (may drift, flag for review) │
│ │
│ twitter (ephemeral) │
│ └── tweet-123 (snapshot, don't track) │
│ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Consequences

### Positive
- Clear ownership: content belongs to concept, not floating independently
- Composable: hubs can query `concept_content` to assemble views
- Versioned: content evolves without losing history
- Governance tiers: different surfaces have appropriate drift policies
- Cascade delete: removing concept removes all its content

### Negative
- More complex than flat `entity` table
- Requires content type registry (what types are valid?)
- Version management overhead

### Risks
- Over-engineering if content types don't stabilize
- May need to split large concepts if they accumulate too much content

---

## Alternatives Considered

### B: Everything in Entity Table
Use existing `entity` with `metadata.content_type` and edge to concept.

**Rejected because:** Entities have independent lifecycle/identity. Content pieces don't exist without their concept.

### C: JSONB Array on Concept
Store content as JSONB array directly on concept row.

**Rejected because:** Harder to query, version, and index. No referential integrity.

### D: Separate Tables per Type
`concept_atom`, `concept_lens`, `concept_example`, etc.

**Rejected because:** Proliferates tables. Harder to query across types.

---

## Implementation Plan

**Not implementing yet.** This ADR documents the pattern for future reference.

When ready:
1. Clean up atoms manually to understand the pattern
2. Validate content types stabilize (atom, lens, example, etc.)
3. Implement `concept_content` table
4. Add `governance` to `surface` table
5. Build hub generator that queries `concept_content`

---

## Coherence Audit Pattern

The value object model enables coherence audits:

```sql
-- Find content that may have drifted from concept
SELECT
 c.id as concept,
 cc.content_type,
 cc.uri,
 cc.created_at as content_created,
 c.updated_at as concept_updated
FROM concept c
JOIN concept_content cc ON cc.concept_id = c.id
WHERE c.updated_at > cc.created_at
 AND cc.status = 'active';

-- Find loose surface deliveries needing review
SELECT d.*, s.governance
FROM delivery d
JOIN surface s ON d.surface_id = s.id
WHERE s.governance = 'loose'
 AND d.published_at < (
 SELECT updated_at FROM concept
 WHERE id = d.concept_id
 );
```

---

## References

- [ADR-0004: Concept Aggregate Root](./ADR-0004-concept-aggregate-root.md)
- Vernon, V. "Implementing Domain-Driven Design" - Value Object patterns
- Evans, E. "Domain-Driven Design" - Aggregate design

---

**End of Document**
