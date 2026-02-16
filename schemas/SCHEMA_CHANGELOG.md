# SemOps Schema Changelog

All notable changes to the SemOps schema will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [8.0.0] - 2026-02-08

### Changed - Entity Type Discriminator (Phase 2 Tactical DDD)

**Major architectural change:** Entity table gains `entity_type` discriminator enabling three types of entities: content (DAM), capability (strategic), repository (strategic). Edge predicates extended with strategic DDD predicates. Part of three-layer architecture formalized in ADR-0009.

#### What Changed

**Entity Table:**
- Added: `entity_type TEXT NOT NULL DEFAULT 'content'` — discriminator for content/capability/repository
- Changed: `asset_type` now nullable (only meaningful for content entities)
- Updated: `idx_entity_orphans` partial index scoped to `entity_type = 'content'`
- Added: `idx_entity_type`, `idx_entity_type_pattern` indexes

**Edge Table:**
- Added node types: `'pattern'` (joins existing `'entity'`, `'surface'`) — enables cross-layer edges
- Added predicates: `'implements'` (capability → pattern), `'delivered_by'` (capability → repository), `'integration'` (repository → repository with DDD pattern typing)

**Views:**
- Updated: `orphan_entities` scoped to content entities only
- Updated: `pattern_coverage` shows per-entity-type counts (content_count, capability_count, repo_count). Capability and repo counts now use `edge` table `implements`/`delivered_by` predicates instead of `primary_pattern_id` FK (which only links documentation content). Removed `total_entity_count` (mixed mechanisms). Requires `DROP VIEW` before `CREATE` due to column change.
- Added: `capability_coverage` — capabilities with pattern/repo link counts (ADR-0009 coherence signal)
- Added: `repo_capabilities` — repositories and the capabilities they deliver
- Added: `integration_map` — repo-to-repo integration relationships with DDD pattern metadata

**Fitness Functions:**
- Rewritten for Phase 2 table names (was referencing Phase 1 `item`/`concept`)
- Added: `check_capability_pattern_coverage()` — CRITICAL: every capability must trace to >=1 pattern
- Added: `check_content_entity_asset_type()` — content entities must have asset_type set
- Added: `check_integration_edge_metadata()` — integration edges need integration_pattern and direction

**Metadata Schemas:**
- `capability_metadata_v1`: domain_classification, description, implements_patterns, delivered_by_repos, status
- `repository_metadata_v1`: role, github_url, delivers_capabilities, status
- `pattern_type` enum: `architecture` and `topology` removed (moved to entity_type capability/repository)

#### Three-Layer Architecture (ADR-0009)

```text
Pattern (Core Domain)      — Stable semantic concepts (the WHY)
Architecture (Strategic)   — Capabilities, repos, integration (the WHAT/WHERE)
Content (DAM Publishing)   — Publishing artifacts (the output)
```

Each layer links upward via edges: Content `documents` Patterns. Capabilities `implements` Patterns. Repos `delivered_by` from Capabilities.

#### Migration

For existing databases, run `schemas/migrations/002_entity_type_discriminator.sql`. All existing entities automatically backfill as `entity_type = 'content'`.

For fresh installs, `phase2-schema.sql` includes all changes.

#### References

- ADR-0009: Strategic/Tactical DDD Refactor
- [STRATEGIC_DDD.md](../docs/STRATEGIC_DDD.md) — Capability registry, repo registry, integration map

---

## [7.0.0] - 2025-12-22

### Changed - Pattern as Aggregate Root (Phase 2)

**Major architectural change:** Pattern replaces Concept as the aggregate root. This is a breaking change requiring fresh schema deployment.

#### What Changed

**New Tables:**
- `pattern` - Aggregate root: applied unit of meaning with business purpose
- `pattern_edge` - Pattern relationships with SKOS + adoption predicates
- `brand` - Unified actor table (person/organization/brand) - Schema.org based
- `product` - Products/services offered by brands - Schema.org Product
- `brand_relationship` - CRM-style relationships between actors and products

**Removed Tables:**
- `concept` - Replaced by `pattern`
- `concept_edge` - Replaced by `pattern_edge`
- `classification` - Deferred to later phase
- `entity_concept` - Simplified to single `primary_pattern_id`

**Entity Changes:**
- Removed: `approval_status`, `visibility`, `provenance`, `approved_at`
- Added: `primary_pattern_id` (replaces `primary_concept_id`)

**Delivery Changes:**
- Added: `approval_status` (moved from entity)
- Added: `visibility` (moved from entity)

#### Pattern Definition

> **Pattern:** An applied unit of meaning with a business purpose, measured for semantic coherence and optimization. Patterns are stable semantic structures that can be adopted, extended, or modified.

#### Pattern Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | text (PK) | kebab-case identifier |
| `preferred_label` | text | SKOS prefLabel |
| `definition` | text | SKOS definition |
| `alt_labels` | text[] | SKOS altLabel |
| `provenance` | enum | 1p / 2p / 3p |
| `metadata` | jsonb | Flexible fields |
| `embedding` | vector(1536) | Semantic search |

#### Pattern Edge Predicates

**SKOS (hierarchy):**
- `broader` - More general pattern
- `narrower` - More specific pattern
- `related` - Associative relationship

**Adoption (lineage):**
- `adopts` - Uses 3p pattern as-is
- `extends` - Builds on pattern
- `modifies` - Changes pattern

#### Rationale

1. **Applied meaning**: Patterns have business purpose, not just semantic definition
2. **Measurable**: Patterns are measured for semantic coherence and optimization
3. **Unifies concepts and workflows**: No artificial distinction
4. **Per-surface governance**: approval_status on Delivery allows different states per surface
5. **Clean adoption model**: 3p patterns adopted/extended/modified to become 1p

#### Migration

**This is a clean slate deployment.** Drop existing tables and run `phase2-schema.sql`.

```sql
-- Drop old schema
DROP TABLE IF EXISTS delivery CASCADE;
DROP TABLE IF EXISTS surface_address CASCADE;
DROP TABLE IF EXISTS surface CASCADE;
DROP TABLE IF EXISTS edge CASCADE;
DROP TABLE IF EXISTS entity_concept CASCADE;
DROP TABLE IF EXISTS entity CASCADE;
DROP TABLE IF EXISTS classification CASCADE;
DROP TABLE IF EXISTS brand_relationship CASCADE;
DROP TABLE IF EXISTS product CASCADE;
DROP TABLE IF EXISTS brand CASCADE;
DROP TABLE IF EXISTS concept_edge CASCADE;
DROP TABLE IF EXISTS concept CASCADE;
DROP TABLE IF EXISTS schema_version CASCADE;

-- Apply new schema
\i schemas/phase2-schema.sql
```

#### Seed Data

Foundation 3p patterns included:
- `skos` - W3C Simple Knowledge Organization System
- `prov-o` - W3C Provenance Ontology
- `ddd` - Domain-Driven Design
- `dublin-core` - Metadata standard
- `dam` - Digital Asset Management

#### References

- ADR-0004: Schema Phase 2 — Pattern as Aggregate Root
- [phase2-schema.sql](./phase2-schema.sql)

---

## [6.3.0] - 2025-12-02

### Changed - Attribution Value Object v2 (Dublin Core Alignment + Epistemic Fields)

**Upgraded `attribution` value object to v2 with Dublin Core metadata standard alignment and epistemic classification.**

#### Field Changes

**Renamed Fields (Dublin Core alignment):**
- `authors` → `creator` (maps to `dc:creator`)
- `license` → `rights` (maps to `dc:rights`)
- `copyright` → merged into `rights`

**New Fields Added:**
- `contributor` - Secondary contributors (maps to `dc:contributor`)
- `publisher` - Publishing entity (maps to `dc:publisher`)
- `source_reference` - Bibliographic reference for 3P content without formal authorship
- `epistemic_status` - Type of knowledge claim: `fact | synthesis | hypothesis`
- `concept_ownership` - Who owns/coined the CONCEPT: `1p | 2p | 3p`

**Retained Fields:**
- `organization` - Organization/institution context (custom extension)
- `platform` - Publication platform
- `channel` - Specific channel/account name
- `original_source` - Original URL (maps to `dc:source`)
- `agents` - AI tools used (custom extension for AI attribution)
- `publication_date` - When originally published (maps to `dc:date`)

#### Dublin Core Mappings

| attribution_v2 Field | Dublin Core Element |
|---------------------|---------------------|
| `creator` | `dc:creator` |
| `contributor` | `dc:contributor` |
| `publisher` | `dc:publisher` |
| `rights` | `dc:rights` |
| `original_source` | `dc:source` |
| `publication_date` | `dc:date` |

#### Epistemic Classification Fields (Custom Extensions)

**`epistemic_status`** - Type of knowledge claim:
- `fact` - Empirically verifiable, widely accepted (e.g., "OLTP handles transactions")
- `synthesis` - Integration of established facts/theories (e.g., "DDD solves AI transformation problems")
- `hypothesis` - Testable proposed explanation (e.g., "We hypothesize that semantic drift causes...")

**`concept_ownership`** - Who owns/coined the CONCEPT being documented:
- `1p` - You coined this concept (e.g., "Semantic Operations", "Real Data")
- `2p` - Borrowed/adapted concept (your specific application of industry patterns)
- `3p` - Industry/external standard concept (e.g., "OLTP", "DDD", "SKOS")

**Key Distinction:** `Entity.provenance` tracks who owns THIS artifact. `attribution.concept_ownership` tracks who owns the CONCEPT being documented. This enables filtering for branding/marketing (1p concepts) vs industry standard terms (3p concepts).

#### Files Updated

- **schemas/attribution/attribution_v2.json** - NEW: JSON Schema for attribution_v2
- **schemas/UBIQUITOUS_LANGUAGE.md** - Updated Attribution Value Object section (v3.1.0)
- **schemas/phase1-schema.sql** - Updated comments and examples to use attribution_v2

#### Migration from v1

```json
// Before (attribution_v1)
{
  "$schema": "attribution_v1",
  "authors": ["Tim Mitchell"],
  "license": "CC-BY-4.0",
  "copyright": "© 2024 Tim Mitchell"
}

// After (attribution_v2)
{
  "$schema": "attribution_v2",
  "creator": ["Tim Mitchell"],
  "rights": "CC-BY-4.0"
}
```

**Migration Notes:**
- `authors` values move to `creator`
- `license` and `copyright` merge into `rights`
- Existing v1 data remains valid (JSONB flexibility)
- New entities should use v2 schema

#### Rationale

From the Concept Entity Strategy decision:
> **Unified catalog** (1P/2P/3P) requires richer attribution than Dublin Core provides, but aligning field names improves interoperability.

Benefits:
- ✅ Dublin Core compatibility for metadata interchange
- ✅ Clear distinction between primary creators (`creator`) and secondary contributors (`contributor`)
- ✅ Publisher field for 3P content attribution
- ✅ `source_reference` for bibliographic citations without formal authorship
- ✅ Retained custom extensions for AI attribution tracking

**See:** Concept Entity Strategy, Decision 4

---

## [6.2.0] - 2025-11-27

### Changed - Edge Predicates Formalized with Standards Foundation

**Formalized standards foundation for all 7 edge predicates.**

#### Predicates Standardized

**W3C PROV-O Based (3):**
- `derived_from` ← `prov:wasDerivedFrom`
- `cites` ← `prov:wasQuotedFrom`
- `version_of` ← `prov:wasRevisionOf`

**Schema.org Extensions (2):**
- `part_of` ← `schema:isPartOf`
- `documents` ← `schema:about` (inverted)

**SemOps Domain Extensions (2):**
- `depends_on` - Prerequisite knowledge (inspired by software dependency graphs)
- `related_to` - Semantic association (inspired by SKOS `skos:related`)

#### Changes Made

**UBIQUITOUS_LANGUAGE.md:**
- Added W3C spec links for PROV-O predicates
- Added Schema.org spec links for extensions
- Removed predicates not in actual schema (`implements`, `s`, `uses`)
- Clarified standards foundation for each predicate category

**phase1-schema.sql:**
- Updated `edge.predicate` comment to document standards foundation
- Clarified relationship to W3C PROV-O, Schema.org, and domain extensions

#### Migration

- ✅ No schema changes required (predicates already in CHECK constraint)
- ✅ Documentation-only change
- ✅ No data migration needed

#### Rationale

Using a "standard set" of predicates based on established W3C and Schema.org vocabularies improves:
- Interoperability with other semantic systems
- Clear provenance lineage from authoritative standards
- Transparency about which predicates are standard vs custom

**See:** Edge Predicates Formalization decision

---

## [6.1.0] - 2025-11-23

### Changed - Documentation Reorganization

**Major documentation restructuring for improved usability and navigation.**

#### UBIQUITOUS_LANGUAGE.md v3.0.0

Completely reorganized with entity-first structure:

**New Organization:**
- **Core Entities first** - Jump directly to Entity, Edge, Surface, Delivery definitions
- **Enums grouped with entities** - See all AssetType values right where Entity uses them
- **Value Objects integrated** - Each entity shows its value objects with full schemas
- **W3C standards contextualized** - SKOS explained with ContentMetadata, PROV-O explained with Edge
- **Examples moved to appendix** - Cleaner entity sections with cross-references to domain-patterns

**Key Improvements:**
- ✅ Navigate by entity ("I want to understand Entity" → go to Core Entities → Entity)
- ✅ Everything in one place (enums, value objects, W3C mappings all with parent entity)
- ✅ More concise (608 lines vs 636, 28 lines shorter while more comprehensive)
- ✅ Better cross-references to domain-patterns documentation

**Old version archived:** `archive/UBIQUITOUS_LANGUAGE_v2.md`

#### Domain Patterns Reorganization

Moved DOMAIN_PATTERNS.md into structured folder: `docs/domain-patterns/`

**New Structure:**
- **[README.md](../docs/domain-patterns/README.md)** - Folder overview with reading order
- **[foundation.md](../docs/domain-patterns/foundation.md)** - Domain context, W3C standards, industry alignment
- **[provenance-and-lineage.md](../docs/domain-patterns/provenance-and-lineage.md)** - NEW: How patterns emerged from practice (pattern discovery vs invention)
- **[publication-patterns.md](../docs/domain-patterns/publication-patterns.md)** - 7 content workflow patterns
- **[constraints.md](../docs/domain-patterns/constraints.md)** - Validation rules
- **[lifecycles.md](../docs/domain-patterns/lifecycles.md)** - State machines
- **[relationships.md](../docs/domain-patterns/relationships.md)** - High-level relationship patterns
- **[edge-predicates.md](../docs/domain-patterns/edge-predicates.md)** - Moved from docs/EDGE_PREDICATES.md
- **[edge-predicate-examples.md](../docs/domain-patterns/edge-predicate-examples.md)** - Moved from docs/EDGE_PREDICATES_USE_CASES.md
- **[anti-patterns.md](../docs/domain-patterns/anti-patterns.md)** - Invalid combinations
- **[doc-style.md](../docs/domain-patterns/doc-style.md)** - Documentation style guide

**Benefits:**
- All domain patterns in one cohesive folder
- Clear navigation and reading order
- Better organization by category (foundation, patterns, constraints, lifecycles, relationships)

#### Cross-Reference Updates

Updated all references throughout repository:
- `schemas/UBIQUITOUS_LANGUAGE.md` - Updated domain patterns references
- `schemas/README.md` - Updated links
- `docs/SKOS_PROVO_MAPPING.md` - Updated edge predicate links
- All domain-pattern files - Updated internal cross-references

**Old version archived:** `schemas/archive/DOMAIN_PATTERNS.md` (original monolithic file)

---

## [6.0.0] - 2025-11-21

### Added - W3C Standards Foundation

**Major architectural enhancement:** Aligned schema with W3C semantic web standards for interoperability and long-term viability.

#### W3C SKOS Integration (content_metadata)

**Content metadata now based on [W3C SKOS (Simple Knowledge Organization System)](https://www.w3.org/TR/skos-reference/)**

Added SKOS fields to `content_metadata_v1.json`:
- `semantic_type` - Maps to `rdf:type skos:Concept`
- `preferred_label` - Maps to `skos:prefLabel`
- `alt_labels[]` - Maps to `skos:altLabel`
- `definition` - Maps to `skos:definition`
- `broader_concepts[]` - Maps to `skos:broader` (parent concepts)
- `narrower_concepts[]` - Maps to `skos:narrower` (child concepts)
- `related_concepts[]` - Maps to `skos:related` (associative relationships)
- `scope_note` - Maps to `skos:scopeNote`
- `example` - Maps to `skos:example`
- `history_note` - Maps to `skos:historyNote`

**Purpose:** SKOS describes semantic organization WITHIN entities (concept hierarchies, labels, definitions).

#### W3C PROV-O Alignment (edge predicates)

**Edge predicates now explicitly based on [W3C PROV-O (Provenance Ontology)](https://www.w3.org/TR/prov-o/)**

Documented W3C mappings:
- `derived_from` ← `prov:wasDerivedFrom` (transformation/extraction)
- `cites` ← `prov:wasQuotedFrom` (citation/attribution)
- `version_of` ← `prov:wasRevisionOf` (version succession)
- `part_of` ← `schema:isPartOf` (compositional hierarchy)
- `documents` ← `schema:about` inverted (explanation/documentation)

**Purpose:** PROV-O describes provenance relationships BETWEEN entities (derivation, attribution, versioning).

#### Architecture Principle

**Separation of Concerns:**
- **SKOS (content_metadata)** = Semantics WITHIN entities (intrinsic properties)
- **PROV-O (edge predicates)** = Relationships BETWEEN entities (extrinsic provenance)

This clean separation ensures:
- Standards compliance and interoperability
- Clear distinction between internal semantics and external relationships
- Queryable graph structure with semantic metadata

#### Updated Predicates

Added/documented in edge table:
- `version_of` - PROV-O `prov:wasRevisionOf` (explicitly added)
- `related_to` - SKOS `skos:related` (documented mapping)

Updated predicate CHECK constraint:
```sql
check (predicate in ('derived_from','cites','version_of','part_of','documents','depends_on','related_to'))
```

### Changed

**content_metadata_v1.json**
- Changed required field from `content_type` to `semantic_type`
- `content_type` is now optional (legacy compatibility)
- Added SKOS-based semantic fields

**Documentation Updates**
- [SKOS_PROVO_MAPPING.md](../docs/SKOS_PROVO_MAPPING.md) - NEW: Visual architecture guide with mermaid diagrams
- [Edge Predicates](../docs/domain-patterns/edge-predicates.md) - Added W3C standards alignment section, moved to domain-patterns
- [Domain Patterns](../docs/domain-patterns/) - Reorganized into structured folder with multiple category files
- [UBIQUITOUS_LANGUAGE.md](./UBIQUITOUS_LANGUAGE.md) - Added SKOS/PROV-O architecture overview
- [frontmatter_template.md](../docs/frontmatter_template.md) - Updated with SKOS metadata fields
- [phase1-schema.sql](./phase1-schema.sql) - Added W3C standards comments

### Migration Notes

**Backward Compatible:**
- Existing `content_type` values still work
- SKOS fields are optional (can be added incrementally)
- No database migration required (JSONB is flexible)

**Recommended Updates:**
1. Start using `semantic_type` instead of `content_type` in new entities
2. Add SKOS hierarchy fields (`broader_concepts`, `narrower_concepts`) to concept definitions
3. Use W3C-aligned predicates when creating new edges

### References

- [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/)
- [W3C PROV-O Specification](https://www.w3.org/TR/prov-o/)
- [Schema.org](https://schema.org/)
- [SKOS_PROVO_MAPPING.md](../docs/SKOS_PROVO_MAPPING.md) - Visual guide

---

## Schema Versioning Guidelines

### MAJOR (x.0.0)
- Breaking changes to field meanings or removals
- Enum value removals or meaning changes
- Required field additions
- Table/constraint removals

### MINOR (0.x.0)  
- New tables, columns, enums (additive)
- New nullable fields with defaults
- New optional constraints
- Metadata schema additions

### PATCH (0.0.x)
- Documentation updates
- Comment additions/corrections
- Index optimizations (non-breaking)
- Constraint clarifications

## [1.0.0] - 2024-08-28

### Added - Phase 1 Initial Schema

**Core Tables:**
- `concept` - Abstract ideas and categories (knowledge-ops, vector-database, etc.)
- `item` - Concrete content and artifacts (blog posts, research, code, etc.)  
- `edge` - Typed relationships between concepts and items
- `schema_version` - Schema version tracking table

**Key Design Decisions:**
- **3-tier provenance**: `first_party` | `second_party` | `third_party`
- **Typed metadata**: JSON with version tracking (`blog_post_v1`, `research_v1`, etc.)
- **Flexible relationships**: Edge table with strength scoring (0.0-1.0)
- **Human-readable IDs**: Slug-style primary keys for concepts and items

**Provenance Model:**
- `first_party` - Content created by you (including AI you directed)
- `second_party` - Direct collaborators and partners
- `third_party` - External sources and references

**Core Predicates:**
- `documents` - Item explains/covers a concept
- `derived_from` - Content lineage and transformation
- `depends_on` - Conceptual dependencies
- `cites` - Reference relationships
- `uses` - Tool/implementation usage
- `implements` - Concrete realization of abstract concept
- `s` - Endorsement/curation relationship

**Metadata Patterns:**
- `attribution_v1` - Source attribution and licensing
- `blog_post_v1` - Blog-specific metadata (word count, audience, etc.)
- `research_v1` - Research quality metrics and sources
- `concept_v1` - Concept maturity and domain classification

### Schema Constraints
- Provenance values restricted to approved enum
- Visibility must be `public` or `private`
- Status values: `draft` | `published` | `archived`
- Edge strength bounded to 0.0-1.0 range

### Indexes Added
- Performance indexes on provenance, status, content_kind
- GIN indexes on JSONB metadata fields
- Composite indexes on edge relationships

## Migration Notes

### From Legacy Schema (if applicable)
- Map `work_item` → `item` with appropriate `content_kind`
- Map `concept_tag` relationships → `edge` with `documents` predicate
- Preserve existing UUIDs where possible, convert others to slug format

### Rollback Plan
- Schema version table allows point-in-time restoration
- All changes are additive in v1.0.0 - no data loss risk
- Foreign key constraints are deferrable for flexibility

## Impacted Components

### Phase 1 (Current)
- Blog-geratror workflow integration
- SemOps knowledge base
- Basic RAG indexing preparation

### Phase 2 (Planned)
- Surface/Delivery tables for publishing workflows
- Enhanced metadata validators
- Advanced graph queries

## Testing Requirements

### Fitness Functions
- [ ] All items with `provenance = 'derived'` must have at least one `derived_from` edge
- [ ] Concept IDs must be valid slugs (lowercase, hyphens, no spaces)
- [ ] Metadata JSON must validate against declared schema versions
- [ ] Edge strength values must be between 0.0 and 1.0

### Contract Tests
- [ ] Sample data loads without errors
- [ ] All indexes perform within acceptable ranges  
- [ ] JSON schemas validate properly
- [ ] Foreign key constraints work as expected

## Breaking Change Policy

**Communication Requirements:**
- Announce breaking changes 2 weeks before release
- Provide migration scripts and documentation
- Update all dependent systems (blog-geratror, etc.)
- Test rollback procedures

**Deprecation Process:**
1. Mark field/enum as deprecated in documentation
2. Add deprecation warnings to queries/inserts
3. Provide migration path for 1 full minor version
4. Remove in next major version

## Related Documentation

- `UBIQUITOUS_LANGUAGE.md` - Canonical definitions of schema terms
- `phase1-schema.sql` - Current schema implementation  
- `sample-data.sql` - Test data reflecting real usage patterns
- `../examples/DDD_arch.md` - Architectural decision record