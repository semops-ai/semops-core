# Issue #47: Concept Entity Strategy & Implementation Plan

> **Status:** Draft | **Date:** 2025-11-25
> **Related Issue:** https://github.com/timjmitchell/ike-semantic-ops/issues/47

---

## Executive Summary

This document analyzes the **content_metadata vs attribution overlap** and proposes a **strategy for defining and ingesting concept entities** before document entities.

**Key Findings:**
1. **Clear separation exists** - `content_metadata` handles semantic/SKOS data, `attribution` handles authorship/licensing
2. **Overlap discovered** - `metadata.source` field duplicates `attribution.authors` and `attribution.original_source`
3. **Concept-first approach is correct** - Documents should reference pre-existing concept entities

---

## Part 1: Content_Metadata vs Attribution Overlap Analysis

### Current Field Mapping

| Field | Value Object | Purpose | Overlaps? |
|-------|-------------|---------|-----------|
| `$schema` | Both | Schema versioning | ❌ No overlap |
| **Authorship** | | | |
| `authors` | `attribution` | List of creators | ✅ **Primary** |
| `organization` | `attribution` | Institution/company | ✅ **Primary** |
| `source` | `content_metadata` | Reference source (3P concepts) | ⚠️ **OVERLAP** |
| **Content Classification** | | | |
| `semantic_type` | `content_metadata` | SKOS concept type | ❌ No overlap |
| `content_type` | `content_metadata` | What this IS | ❌ No overlap |
| `preferred_label` | `content_metadata` | Canonical name (SKOS) | ❌ No overlap |
| `alt_labels` | `content_metadata` | Alternative names (SKOS) | ❌ No overlap |
| `definition` | `content_metadata` | Concept definition (SKOS) | ❌ No overlap |
| **Relationships** | | | |
| `broader_concepts` | `content_metadata` | Parent concepts (SKOS) | ❌ No overlap |
| `narrower_concepts` | `content_metadata` | Child concepts (SKOS) | ❌ No overlap |
| `related_concepts` | `content_metadata` | Related concepts (SKOS) | ❌ No overlap |
| **Publishing** | | | |
| `platform` | `attribution` | Publication platform | ❌ No overlap |
| `channel` | `attribution` | Specific channel/account | ❌ No overlap |
| `original_source` | `attribution` | Original URL | ⚠️ **OVERLAP** |
| `publication_date` | `attribution` | When originally published | ❌ No overlap |
| **Legal** | | | |
| `license` | `attribution` | Content license | ❌ No overlap |
| `copyright` | `attribution` | Copyright notice | ❌ No overlap |
| `agents` | `attribution` | AI tools used | ❌ No overlap |
| **Content Properties** | | | |
| `media_type` | `content_metadata` | Broad category | ❌ No overlap |
| `language` | `content_metadata` | Primary language | ❌ No overlap |
| `tags` | `content_metadata` | Freeform tags | ❌ No overlap |
| `subject_area` | `content_metadata` | Domains | ❌ No overlap |
| `summary` | `content_metadata` | Brief abstract | ❌ No overlap |
| `word_count` | `content_metadata` | For text content | ❌ No overlap |
| `reading_time_minutes` | `content_metadata` | Estimated reading time | ❌ No overlap |
| `duration_seconds` | `content_metadata` | For video/audio | ❌ No overlap |
| `quality_score` | `content_metadata` | Relevance/quality | ❌ No overlap |

### Identified Overlap: `metadata.source`

**The Problem:**
```python
# In concept-inventory.md, 3P concepts use:
"metadata.source": "Eric Evans (2003)"

# But attribution also has:
"attribution.authors": ["Eric Evans"]
"attribution.original_source": "https://..."
```

**Why this happened:**
- `metadata.source` comes from W3C SKOS (bibliographic citation for concepts)
- `attribution.authors` tracks WHO created content
- For **3P concepts**, these overlap (e.g., "Eric Evans" is both the source AND the author)

### Recommended Resolution

**For Concept Entities (3P concepts like DIKW, DDD):**

```json
{
 "id": "domain-driven-design",
 "provenance": "3p",
 "attribution": {
 "$schema": "attribution_v1",
 "authors": ["Eric Evans"],
 "organization": "Domain Language, Inc.",
 "original_source": "https://www.domainlanguage.com/ddd/",
 "publication_date": "2003",
 "license": "proprietary"
 },
 "metadata": {
 "$schema": "content_metadata_v1",
 "semantic_type": "framework",
 "preferred_label": "Domain-Driven Design",
 "alt_labels": ["DDD"],
 "definition": "Software development philosophy...",
 "source": "Eric Evans (2003)" // ← Keep for SKOS compliance (bibliographic reference)
 }
}
```

**Decision:**
- **KEEP `metadata.source`** - It's part of SKOS and serves a bibliographic reference role
- **POPULATE `attribution.authors`** - Provides structured authorship data
- **Accept semantic overlap** - They serve different purposes (SKOS citation vs. structured attribution)

**Benefits:**
- ✅ Maintains SKOS compliance
- ✅ Enables structured queries ("all content by Eric Evans")
- ✅ Supports licensing and copyright tracking via attribution
- ✅ Bibliographic citations remain human-readable in metadata.source

---

## Part 2: Concept-First Ingestion Strategy

### Why Concepts First?

**From the concept-inventory.md:**
> "Documents are the primary entities; concepts are reusable semantic building blocks."

**Dependency Chain:**
```
3P Concepts (DIKW, DDD, etc.)
 ↓ (referenced by)
1P Concepts (Semantic Operations, Real Data)
 ↓ (referenced by)
1P Documents (.md files from project-ike)
```

**Example Dependency:**
- **Document:** `SEMANTIC_OPERATIONS.md`
- **References concepts:** `semantic-operations` (1P), `dikw` (3P), `domain-driven-design` (3P)
- **Must ingest concepts first** so document entity can reference them via `metadata.broader_concepts`

### Ingestion Phases

#### Phase 1: Foundation Layer (3P Concepts)

Ingest the "Big 4" foundational concepts from `concept-inventory.md`:

1. `dikw` (DIKW Hierarchy)
2. `domain-driven-design` (DDD)
3. `information-theory` (Shannon)
4. `systems-theory-cybernetics` (Systems Theory)

**Why these first:**
- All other concepts depend on these
- Provides `broader_concepts` targets for 1P concepts
- Establishes knowledge graph foundation

**Action:**
- [ ] Create script: `scripts/ingest_foundation_concepts.py`
- [ ] Manually map from concept-inventory.md table format → entity records
- [ ] Insert into Supabase `entity` table
- [ ] Verify via `SELECT * FROM entity WHERE provenance='3p'`

#### Phase 2: Supporting 3P Concepts

Ingest supporting 3P concepts:

- `understanding`
- `meaning`
- `semantic-drift`
- `dimensional-modeling`
- `bounded-context`
- `ubiquitous-language`
- `ai-transformation`

**Why second:**
- Some reference Foundation Layer concepts via `broader_concepts`
- Provide targets for 1P concepts to reference

#### Phase 3: 1P Concepts (Semantic Operations)

Ingest your original concepts:

- `semantic-operations`
- `semantic-coherence`
- `semantic-optimization`
- `real-data`
- `data-physics`
- etc.

**Why third:**
- Depend on 3P concepts via `metadata.broader_concepts`
- Will be referenced by documents

#### Phase 4: 1P Documents

Finally, ingest markdown documents from project-ike:

- `docs/SEMANTIC_OPERATIONS/SEMANTIC_OPERATIONS.md`
- `docs/FRAMEWORK/*.md`
- etc.

**Why last:**
- Reference concept entities via `metadata.broader_concepts` and `metadata.primary_concept`
- Can create `documents` edges to concepts

---

## Part 3: Concept Entity Data Model

### Concept vs Document: Key Differences

| Attribute | Concept Entity | Document Entity |
|-----------|---------------|-----------------|
| `asset_type` | `link` (for 3P) or `file` (for 1P standalone) | `file` |
| `provenance` | `1p` or `3p` | `1p` (your docs) |
| `metadata.semantic_type` | `concept`, `framework`, `methodology`, `pattern` | Usually NOT "concept" |
| `metadata.content_type` | Usually NULL (it IS the concept) | `markdown_doc`, `blog_post`, etc. |
| `metadata.primary_concept` | Self-referential (e.g., `dikw` → `dikw`) | References another entity (e.g., `semantic-operations`) |
| `metadata.preferred_label` | Canonical concept name | Document title |
| `metadata.definition` | Core concept definition | Summary/abstract |

### Example: 3P Concept (DIKW)

```python
{
 "id": "dikw",
 "asset_type": "link", # External concept, no file we possess
 "provenance": "3p",
 "approval_status": "approved",
 "visibility": "public",
 "title": "DIKW Hierarchy",
 "filespec": {
 "$schema": "filespec_v1",
 "uri": "https://en.wikipedia.org/wiki/DIKW_pyramid",
 "platform": "wikipedia",
 "accessible": true
 },
 "attribution": {
 "$schema": "attribution_v1",
 "authors": ["Russell Ackoff", "Gene Bellinger"],
 "publication_date": "1989",
 "original_source": "https://en.wikipedia.org/wiki/DIKW_pyramid"
 },
 "metadata": {
 "$schema": "content_metadata_v1",
 "semantic_type": "framework",
 "abstraction_level": "foundational",
 "primary_concept": "dikw",
 "preferred_label": "DIKW Hierarchy",
 "alt_labels": ["Data-Information-Knowledge-Wisdom", "DIKW"],
 "definition": "Hierarchical model: Data → Information → Knowledge → Wisdom, with Understanding as the process transforming each level by creating meaning",
 "source": "Ackoff (1989), Bellinger et al.",
 "broader_concepts": [],
 "narrower_concepts": ["understanding", "meaning", "semantic-transformation"],
 "subject_area": ["Knowledge Management", "Information Science"]
 }
}
```

### Example: 1P Concept (Semantic Operations)

```python
{
 "id": "semantic-operations",
 "asset_type": "file", # You defined it in a document
 "provenance": "1p",
 "approval_status": "approved",
 "visibility": "public",
 "title": "Semantic Operations",
 "filespec": {
 "$schema": "filespec_v1",
 "uri": "file:///docs/SEMANTIC_OPERATIONS/SEMANTIC_OPERATIONS.md",
 "format": "markdown"
 },
 "attribution": {
 "$schema": "attribution_v1",
 "authors": ["Tim Mitchell"],
 "license": "CC-BY-4.0"
 },
 "metadata": {
 "$schema": "content_metadata_v1",
 "semantic_type": "methodology",
 "abstraction_level": "intermediate",
 "primary_concept": "semantic-operations",
 "preferred_label": "Semantic Operations",
 "definition": "Operational framework for managing semantic coherence at runtime",
 "broader_concepts": ["dikw", "domain-driven-design", "systems-theory-cybernetics"],
 "narrower_concepts": ["semantic-coherence", "semantic-optimization"],
 "subject_area": ["Knowledge Management", "AI/ML", "Systems Engineering"]
 }
}
```

---

## Part 4: Implementation Plan

### Step 1: Create Concept Ingestion Script

**File:** `scripts/ingest_foundation_concepts.py`

```python
"""
Ingest foundation concept entities from concept-inventory.md.

This script creates concept entities in Supabase, establishing the
knowledge graph foundation before ingesting documents.
"""

import json
from datetime import datetime
from supabase import create_client, Client

# Concept definitions from concept-inventory.md
FOUNDATION_CONCEPTS = [
 {
 "id": "dikw",
 "asset_type": "link",
 "provenance": "3p",
 "approval_status": "approved",
 "visibility": "public",
 "title": "DIKW Hierarchy",
 # ... (complete data structure)
 },
 # ... more concepts
]

def ingest_concepts(supabase: Client):
 """Insert concept entities into Supabase."""
 for concept in FOUNDATION_CONCEPTS:
 result = supabase.table("entity").insert(concept).execute
 print(f"✅ Inserted: {concept['id']}")

if __name__ == "__main__":
 # Initialize Supabase client
 supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 ingest_concepts(supabase)
```

### Step 2: Create Concept → Concept Edges

After ingesting concepts, create edges between them:

```python
# Example: semantic-operations depends on dikw
{
 "src_type": "entity",
 "src_id": "semantic-operations",
 "dst_type": "entity",
 "dst_id": "dikw",
 "predicate": "depends_on",
 "strength": 1.0
}
```

### Step 3: Verify Concept Graph

Query to verify concept relationships:

```sql
-- All 3P foundation concepts
SELECT id, title, metadata->>'semantic_type' as type
FROM entity
WHERE provenance = '3p'
 AND metadata->>'abstraction_level' = 'foundational';

-- All concepts that depend on DIKW
SELECT e.id, e.title
FROM entity e
JOIN edge eg ON eg.src_id = e.id
WHERE eg.dst_id = 'dikw'
 AND eg.predicate = 'depends_on';
```

### Step 4: Ingest Documents (After Concepts)

Now that concepts exist, ingest documents that reference them:

```python
# Document entity referencing concepts
{
 "id": "doc-semantic-operations-overview",
 "asset_type": "file",
 "provenance": "1p",
 "metadata": {
 "content_type": "markdown_doc",
 "primary_concept": "semantic-operations", # References concept entity
 "broader_concepts": ["dikw", "domain-driven-design"] # References concept entities
 }
}
```

---

## Part 5: Next Actions for Issue #47

### Immediate Actions

1. **[ ] Review and approve this strategy document**
2. **[ ] Create `scripts/ingest_foundation_concepts.py`**
3. **[ ] Manually map all concepts from concept-inventory.md → Python data structures**
4. **[ ] Test ingestion on local Supabase instance**
5. **[ ] Create edges between concept entities**
6. **[ ] Verify concept graph with SQL queries**

### Follow-Up Actions

7. **[ ] Document abstraction_level values** (not in current schema)
8. **[ ] Decide: Add `abstraction_level` to content_metadata schema?**
9. **[ ] Plan RAG strategy** (deferred until concepts are stable)

### Open Questions

1. **Abstraction Level:** `concept-inventory.md` uses `metadata.abstraction_level` (foundational, intermediate), but this isn't in `content_metadata_v1` schema. Should we add it?

2. **Category Field:** `concept-inventory.md` uses `category` (first-principles, semantic-operations, ai-transformation), but entity schema doesn't have a top-level `category` field. Where should this live?

3. **Primary Concept:** For concept entities, should `metadata.primary_concept` be self-referential (e.g., `dikw` → `dikw`) or NULL?

---

## Appendix: Field Comparison Table

| Field in concept-inventory.md | Maps to Entity Schema | Notes |
|-------------------------------|----------------------|-------|
| `entity_id` | `id` | ✅ Direct mapping |
| `provenance` | `provenance` | ✅ Direct mapping |
| `category` | ❓ **Missing** | Not in entity schema |
| `visibility` | `visibility` | ✅ Direct mapping |
| `approval_status` | `approval_status` | ✅ Direct mapping |
| `metadata.semantic_type` | `metadata.semantic_type` | ✅ Direct mapping |
| `metadata.abstraction_level` | ❓ **Missing** | Not in content_metadata_v1 |
| `metadata.primary_concept` | `metadata.primary_concept` | ⚠️ Not documented in UBIQUITOUS_LANGUAGE |
| `metadata.preferred_label` | `metadata.preferred_label` | ✅ SKOS field |
| `metadata.alt_labels` | `metadata.alt_labels` | ✅ SKOS field |
| `metadata.definition` | `metadata.definition` | ✅ SKOS field |
| `metadata.source` | `metadata.source` | ⚠️ Not documented (SKOS bibliographic) |
| `metadata.broader_concepts` | `metadata.broader_concepts` | ✅ SKOS field |
| `metadata.narrower_concepts` | `metadata.narrower_concepts` | ✅ SKOS field |

---

## Part 6: Architectural Decisions (2025-11-25)

### Decision 1: Remove `semantic_type` Field

**Status:** ✅ **DECIDED** - Removed from prototype

**Rationale:**
- `semantic_type` (framework, concept, methodology, pattern) is **NOT a W3C SKOS standard**
- It's a custom classification attempting to categorize concept types
- Conflicts with DDD principle: documents have a `content_type`, concepts exist in metadata

**Decision:**
- **Remove `semantic_type` entirely**
- Use `content_type` to classify what the entity **IS** (reference_doc, github_doc, blog_post, etc.)
- Concepts are established through `primary_concept` field, not entity type
- The SKOS hierarchy (`broader_concepts`) naturally organizes concepts

**Example:**
```yaml
# OLD (removed)
metadata:
 semantic_type: framework # ← REMOVED
 content_type: ???

# NEW (standards-aligned)
metadata:
 content_type: reference_doc # ← What this entity IS
 primary_concept: dikw # ← What concept it's about
```

---

### Decision 2: Remove `abstraction_level` Field

**Status:** ✅ **DECIDED** - Removed from prototype

**Rationale:**
- `abstraction_level` (foundational, intermediate, advanced) is **NOT a W3C SKOS standard**
- It's a custom field that appeared in `concept-inventory.md`
- The SKOS `broader_concepts` hierarchy naturally communicates abstraction

**Decision:**
- **Remove `abstraction_level` field**
- Rely on SKOS hierarchy depth:
 - `broader_concepts: []` → Foundational concepts
 - References to foundational concepts → Intermediate concepts
 - Deeper nesting → More specific/advanced concepts

---

### Decision 3: Concepts as Metadata, Not Separate Entities

**Status:** ✅ **DECIDED** - Implemented in prototype

**Rationale:**
- Concepts are **abstract ideas**, not concrete assets
- Documents **about** concepts ≠ the concept itself
- File locations change, but concept identity should be stable
- Aligns with DDD (every entity needs an asset) and SKOS (concepts in metadata)

**Decision:**
- **Concepts are NOT separate entities** - they exist in metadata only
- Documents establish concepts via `primary_concept` field
- Multiple documents can reference the same concept
- Concepts "emerge" from consistent usage across entities

**Example:**
```yaml
# 3P Reference document about DIKW
dikw-wikipedia:
 entity_id: dikw-wikipedia
 asset_type: link
 filespec:
 uri: "https://en.wikipedia.org/wiki/DIKW_pyramid"
 metadata:
 content_type: reference_doc
 primary_concept: dikw # ← Establishes "dikw" as a concept

# 1P Document about DIKW
blog-dikw-explained:
 entity_id: blog-dikw-explained
 asset_type: file
 metadata:
 content_type: blog_post
 primary_concept: dikw # ← References same concept
```

---

### Decision 4: Keep Custom `attribution` Value Object

**Status:** ✅ **IMPLEMENTED** (2025-12-02) - Implemented as attribution_v2 with Dublin Core alignment

**Rationale:**
- **Unified catalog** (1P/2P/3P) requires richer attribution than Dublin Core provides
- **Provenance-first design** - IP ownership, contribution, and agent attribution are critical
- **AI attribution** - Need to track which models/agents were involved (no standard exists yet)
- **Future CRM integration** - Will need to link content to sales/marketing activities

**Decision:**
- **Keep `attribution` as custom value object**
- **Rename fields to align with Dublin Core** for interoperability:
 - `authors` → `creator` (maps to `dc:creator`)
 - `license` → `rights` (maps to `dc:rights`)
 - Add `contributor` (maps to `dc:contributor`)
 - Add `publisher` (maps to `dc:publisher`)
- **Keep custom extensions:**
 - `agents[]` - AI/automation agent attribution (unique to our domain)
 - `organization` - For 1P vs 2P distinction
 - `source_reference` - For 3P content without formal authors

**Planned structure:**
```yaml
attribution:
 $schema: attribution_v2 # ← Version bump for field rename

 # Dublin Core compatible fields
 creator: [] # dc:creator - Primary IP creators
 contributor: [] # dc:contributor - Secondary contributors
 publisher: null # dc:publisher - Publishing organization
 rights: null # dc:rights - License/copyright

 # Custom extensions (our domain-specific needs)
 agents: [] # AI/automation agents used
 organization: null # Organization context
 source_reference: null # For 3P without formal authorship

 # Future extensions
 # crm_activity: {} # Future: Link to CRM campaigns/opportunities
```

---

### Summary of Decisions

| Decision | Status | Impact |
|----------|--------|--------|
| Remove `semantic_type` | ✅ Completed | Use `content_type` for entity classification |
| Remove `abstraction_level` | ✅ Completed | Use SKOS hierarchy depth instead |
| Concepts as metadata only | ✅ Completed | No separate concept entities |
| DC-aligned attribution | ✅ Completed | Renamed to attribution_v2 with Dublin Core fields |

---

## Session Log

_Track session-by-session progress for multi-session implementation work._

<!-- Add session entries as work progresses:

### YYYY-MM-DD: Brief Session Description
**Status:** In Progress | Completed | Blocked
**Tracking Issue:** 

**Completed:**
- What was accomplished

**Next Session Should Start With:**
1. Next steps

-->

---

**End of Document**
