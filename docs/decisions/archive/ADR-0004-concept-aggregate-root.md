# ADR-0004: Concept as Aggregate Root

**Status:** Superseded by [ADR-0004-schema-phase2-pattern-aggregate-root.md](ADR-0004-schema-phase2-pattern-aggregate-root.md)
**Date:** 2025-12-05
**Related Issue:** [](https://github.com/semops-ai/semops-core/issues/95) - Schema Phase-2 Refactor
**Context:** Exploring schema redesign for semantic-first knowledge management

---

## Context

The current schema uses **Entity** (a concrete content artifact) as the single aggregate root. This works well for digital asset management (DAM) and content management (CMS) workflows.

However, Project Ike is fundamentally about **semantic coherence** - the consistent meaning of concepts across contexts. When you think "source problem" or "semantic drift," you're thinking about a concept first, not a specific blog post or transcript about it.

**Current Model:**
```
Entity (aggregate root)
 → contains metadata.primary_concept
 → has edges to other entities
 → delivered to surfaces
```

**Problem:** Concepts are buried inside entities. Multiple entities can reference the same concept, but there's no first-class representation of the concept itself.

---

## Decision

Promote **Concept** to aggregate root. Entities become manifestations (expressions) of concepts.

**Proposed Model:**
```
Concept (aggregate root)
 → expressed_by many Entities (manifestations)
 → relates_to other Concepts (semantic web)
 → organized_by Framings and Lenses

Entity (manifestation)
 → expresses one primary Concept
 → references many Concepts
 → still has asset_type, provenance, visibility
 → still delivered to surfaces
```

---

## Proposed Schema

### concept table

The canonical definition of a domain concept.

```sql
create table if not exists concept (
 id text primary key, -- kebab-case: source-problem, semantic-drift
 preferred_label text not null, -- Human-readable: "The Source Problem"
 definition text not null, -- One-sentence canonical definition

 -- Ownership and maturity
 ownership text not null default '1p' -- 1p (coined), 2p (adapted), 3p (industry standard)
 check (ownership in ('1p', '2p', '3p')),
 maturity text not null default 'emerging' -- emerging, established, canonical
 check (maturity in ('emerging', 'established', 'canonical')),

 -- SKOS-style semantic organization (first-class columns, not buried in JSONB)
 alt_labels text[] default '{}', -- Alternative names (SKOS altLabel)

 -- Epistemic classification
 epistemic_type text not null default 'synthesis' -- fact, synthesis, hypothesis
 check (epistemic_type in ('fact', 'synthesis', 'hypothesis')),

 -- Subject classification
 subject_areas text[] default '{}', -- ["Data Architecture", "Semantic Operations"]

 -- Metadata and lifecycle
 metadata jsonb not null default '{}', -- Additional structured data
 created_at timestamptz not null default now,
 updated_at timestamptz not null default now
);

comment on table concept is 'Aggregate root - the semantic unit of knowledge';
comment on column concept.ownership is '1p = we coined this, 2p = adapted, 3p = industry standard';
comment on column concept.maturity is 'Lifecycle: emerging → established → canonical';
comment on column concept.epistemic_type is 'Type of knowledge claim: fact, synthesis, hypothesis';
```

### concept_relation table

Semantic relationships between concepts (replaces in-entity SKOS fields).

```sql
create table if not exists concept_relation (
 source_concept_id text not null references concept(id),
 target_concept_id text not null references concept(id),
 relation_type text not null
 check (relation_type in (
 'broader', -- SKOS broader (is-a, part-of hierarchy)
 'narrower', -- SKOS narrower (inverse of broader)
 'related', -- SKOS related (associative)
 'prerequisite', -- Must understand X before Y
 'contrasts_with', -- Opposing or alternative concept
 'solves', -- X is solution to problem Y
 'causes' -- X leads to Y
 )),
 strength decimal(3,2) default 1.0
 check (strength >= 0.0 and strength <= 1.0),
 metadata jsonb not null default '{}',
 created_at timestamptz default now,
 primary key (source_concept_id, target_concept_id, relation_type)
);

comment on table concept_relation is 'Semantic web of concept relationships (SKOS-based)';
```

### framing table

Formal theoretical frameworks that can be applied to concepts.

```sql
create table if not exists framing (
 id text primary key, -- dikw, ddd, prov-o
 name text not null, -- "DIKW Hierarchy", "Domain-Driven Design"
 description text,
 framework_uri text, -- Link to formal spec if 3p
 ownership text not null default '3p'
 check (ownership in ('1p', '2p', '3p')),
 created_at timestamptz not null default now
);

comment on table framing is 'Formal theoretical frameworks for interpreting concepts';
```

### concept_framing table

How a concept maps to a framing.

```sql
create table if not exists concept_framing (
 concept_id text not null references concept(id),
 framing_id text not null references framing(id),
 mapping text not null, -- Markdown text explaining the mapping
 level text, -- Position in framework (e.g., "D→I transition" for DIKW)
 implications text, -- What this mapping reveals
 created_at timestamptz default now,
 primary key (concept_id, framing_id)
);

comment on table concept_framing is 'How concepts map to theoretical frameworks';
```

### lens table

Practical interpretive perspectives.

```sql
create table if not exists lens (
 id text primary key, -- ai-transformation, semops, governance
 name text not null, -- "AI Transformation Lens"
 description text,
 question_template text, -- "What does this mean for AI?"
 created_at timestamptz not null default now
);

comment on table lens is 'Practical interpretive perspectives for concepts';
```

### concept_lens table

How a concept is seen through a lens.

```sql
create table if not exists concept_lens (
 concept_id text not null references concept(id),
 lens_id text not null references lens(id),
 impact text not null, -- Key insight through this lens
 without_this text, -- What goes wrong without this concept
 with_this text, -- What becomes possible
 practical_implication text, -- Actionable guidance
 created_at timestamptz default now,
 primary key (concept_id, lens_id)
);

comment on table concept_lens is 'How concepts are interpreted through practical lenses';
```

### Modified entity table

Entities become manifestations of concepts.

```sql
create table if not exists entity (
 id text primary key,

 -- Link to concept (NEW - the key relationship)
 primary_concept_id text references concept(id), -- What concept this entity primarily expresses

 -- Document structure type (NEW)
 structure_type text not null default 'atom' -- atom, hub, pattern, decision, editorial
 check (structure_type in ('atom', 'hub', 'pattern', 'decision', 'editorial', 'glossary')),

 -- Existing fields
 asset_type text not null
 check (asset_type in ('file', 'link')),
 title text,
 version text default '1.0',
 visibility text not null default 'public'
 check (visibility in ('public', 'private')),
 approval_status text not null default 'pending'
 check (approval_status in ('pending', 'approved', 'rejected')),
 provenance text not null default '1p'
 check (provenance in ('1p', '2p', '3p')),
 filespec jsonb not null default '{}',
 attribution jsonb not null default '{}',
 metadata jsonb not null default '{}', -- Still useful for content-specific metadata
 created_at timestamptz not null default now,
 updated_at timestamptz not null default now,
 approved_at timestamptz
);

comment on column entity.primary_concept_id is 'The concept this entity primarily expresses/documents';
comment on column entity.structure_type is 'Document structure: atom (single concept), hub (curator), pattern (GoF-style), etc.';
```

### entity_concept table

Secondary concepts referenced by an entity.

```sql
create table if not exists entity_concept (
 entity_id text not null references entity(id),
 concept_id text not null references concept(id),
 role text not null default 'references' -- references, explains, contrasts, extends
 check (role in ('references', 'explains', 'contrasts', 'extends')),
 strength decimal(3,2) default 0.5
 check (strength >= 0.0 and strength <= 1.0),
 primary key (entity_id, concept_id)
);

comment on table entity_concept is 'Secondary concepts mentioned or explained in an entity';
```

---

## Key Distinction: Concept vs Entity Ownership

This design cleanly separates two different ownership questions:

| Question | Where It Lives | Values |
|----------|---------------|--------|
| **Who coined/owns the CONCEPT?** | `concept.ownership` | 1p (coined), 2p (adapted), 3p (industry standard) |
| **Who created THIS ARTIFACT?** | `entity.provenance` | 1p (you made it), 2p (collaboration), 3p (external) |

**Examples:**

| Concept | concept.ownership | Entity | entity.provenance |
|---------|-------------------|--------|-------------------|
| Source Problem | 1p (Tim coined it) | Your blog post | 1p |
| Source Problem | 1p (Tim coined it) | Someone else's article | 3p link |
| DIKW Hierarchy | 3p (Ackoff coined it) | Ackoff's original paper | 3p link |
| DIKW Hierarchy | 3p (Ackoff coined it) | Your synthesis doc | 1p |
| Bounded Context | 3p (Eric Evans) | Your pattern doc | 1p |

**Why this matters:**
- You can write 1p content about 3p concepts (synthesis, explanation)
- Others can write 3p content about your 1p concepts (adoption, critique)
- Attribution/licensing flows from entity, not concept
- Semantic ownership is distinct from artifact ownership

---

## What This Enables

### 1. Concept-Centric Queries

```sql
-- Find all content about "source-problem"
SELECT e.* FROM entity e
WHERE e.primary_concept_id = 'source-problem'
 OR EXISTS (SELECT 1 FROM entity_concept ec
 WHERE ec.entity_id = e.id
 AND ec.concept_id = 'source-problem');

-- Get concept with all its framings and lenses
SELECT c.*,
 json_agg(DISTINCT cf.*) as framings,
 json_agg(DISTINCT cl.*) as lenses
FROM concept c
LEFT JOIN concept_framing cf ON c.id = cf.concept_id
LEFT JOIN concept_lens cl ON c.id = cl.concept_id
WHERE c.id = 'source-problem'
GROUP BY c.id;
```

### 2. Semantic Navigation

```sql
-- "What should I understand before learning about X?"
WITH RECURSIVE prereqs AS (
 SELECT target_concept_id as id, 0 as depth
 FROM concept_relation
 WHERE source_concept_id = 'semantic-drift'
 AND relation_type = 'prerequisite'
 UNION ALL
 SELECT cr.target_concept_id, p.depth + 1
 FROM concept_relation cr
 JOIN prereqs p ON cr.source_concept_id = p.id
 WHERE cr.relation_type = 'prerequisite' AND p.depth < 5
)
SELECT DISTINCT c.* FROM concept c
JOIN prereqs p ON c.id = p.id
ORDER BY p.depth;
```

### 3. Framework Analysis

```sql
-- "Show me all concepts at the D→I transition in DIKW"
SELECT c.preferred_label, cf.mapping, cf.implications
FROM concept c
JOIN concept_framing cf ON c.id = cf.concept_id
WHERE cf.framing_id = 'dikw'
 AND cf.level LIKE '%D→I%';
```

### 4. Impact Analysis

```sql
-- "What's the AI transformation impact of all 1p concepts?"
SELECT c.preferred_label, cl.impact, cl.practical_implication
FROM concept c
JOIN concept_lens cl ON c.id = cl.concept_id
WHERE c.ownership = '1p'
 AND cl.lens_id = 'ai-transformation';
```

---

## Migration Path

### Phase 1: Add concept table alongside entity
- Create `concept`, `concept_relation` tables
- Populate from existing `metadata.primary_concept` values
- Add `primary_concept_id` FK to entity (nullable initially)

### Phase 2: Add framing/lens tables
- Create framing, lens, concept_framing, concept_lens tables
- Migrate inline framings/lenses from markdown files

### Phase 3: Backfill and validate
- Script to extract concepts from existing entities
- Validate all entities have valid concept references
- Remove duplicated concept data from metadata JSONB

### Phase 4: Make concept_id required
- Add NOT NULL constraint
- Concept becomes true aggregate root

---

## Trade-offs

### Benefits
- **Semantic coherence by design** - Concepts are explicit, not implicit
- **Reusable framings/lenses** - Apply once, use everywhere
- **Concept-centric navigation** - "Show me everything about X"
- **Clear ownership** - Who coined/owns each concept is explicit
- **Queryable semantic web** - Concept relationships are structured

### Costs
- **More tables** - 6 new tables vs current 1-table concept storage
- **Migration effort** - Existing entities need concept extraction
- **Two aggregate roots?** - Concept AND Entity both important
- **Potential over-engineering** - May be premature for current content volume

### Open Questions
1. **Is Concept really an aggregate root, or is it a Value Object?**
 - Concepts have identity and lifecycle (aggregate root)
 - But they're also immutable once canonical (value object-ish)

2. **Should framings/lenses be in the database or just markdown?**
 - Database enables queries and consistency
 - Markdown is more flexible for writing

3. **How do Hubs fit?**
 - A Hub is an entity with structure_type='hub'
 - Its primary_concept_id is the theme (e.g., "real-data")
 - It references multiple concepts via entity_concept

---

## Consequences

If we adopt this:
- All new content requires identifying the primary concept first
- Ingestion pipelines must extract/assign concepts
- RAG queries can be concept-centric ("explain source-problem")
- Semantic drift becomes detectable (multiple definitions for same concept)
- Graph visualization becomes concept → concept, not just entity → entity

---

## Decision

**Proposed** - Seeking feedback before implementation.

The question: Is the complexity justified by the semantic coherence it enables?

---

**Author:** Tim Mitchell
**Reviewers:** [Pending]
