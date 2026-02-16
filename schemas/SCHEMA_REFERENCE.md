# Project SemOps Schema Reference

> Data dictionary for the Project SemOps database schema.
> **Version:** 8.0.0 | **Last Updated:** 2026-02-08

---

## How to Use This Document

| Need | Go To |
|------|-------|
| Domain definitions and business rules | [UBIQUITOUS_LANGUAGE.md](UBIQUITOUS_LANGUAGE.md) |
| Column specs, JSONB schemas, constraints | This document |
| Schema DDL (SQL) | [phase2-schema.sql](phase2-schema.sql) |
| Schema change history | [SCHEMA_CHANGELOG.md](SCHEMA_CHANGELOG.md) |
| Schema fitness validation | [fitness-functions.sql](fitness-functions.sql) |
| W3C standard mappings | [SKOS_PROVO_MAPPING.md](SKOS_PROVO_MAPPING.md) |

---

## Pattern Table

The aggregate root of the domain model. See [UBIQUITOUS_LANGUAGE.md — Pattern](UBIQUITOUS_LANGUAGE.md#pattern-aggregate-root) for business context.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `TEXT` | NOT NULL | — | Primary key. Kebab-case, 3–50 chars. |
| `preferred_label` | `TEXT` | YES | — | SKOS `prefLabel` — canonical display name |
| `definition` | `TEXT` | YES | — | SKOS `definition` — authoritative meaning (≥10 chars) |
| `alt_labels` | `TEXT[]` | YES | — | SKOS `altLabel` — synonyms, abbreviations |
| `provenance` | `TEXT` | NOT NULL | — | `'1p'`, `'2p'`, `'3p'` |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Flexible fields (pattern_type, subject_area, quality_score) |
| `embedding` | `vector(1536)` | YES | — | OpenAI `text-embedding-3-small` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |

### Pattern Enums

**provenance** — Whose semantic structure is this?

| Value | Meaning |
|-------|---------|
| `1p` | First party — operates in my system (may be synthesis from 3P sources) |
| `2p` | Second party — jointly developed with external party |
| `3p` | Third party — industry standard or external IP we adopt |

### Pattern Metadata Schema

Stored in `pattern.metadata` (JSONB). No formal `$schema` versioning yet.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pattern_type` | string | `"concept"`, `"domain"`, or `"implementation"` | `"domain"` |
| `subject_area` | string[] | Domain classifications | `["Knowledge Management", "AI/ML"]` |
| `quality_score` | float | Relevance/quality 0.0–1.0 | `0.9` |
| `lifecycle_stage` | string | `"draft"`, `"active"`, `"stable"`, `"deprecated"`, `"archived"` | `"active"` |

### Pattern Embedding

- **Model:** OpenAI `text-embedding-3-small`
- **Dimensions:** 1536
- **Input text:** `"{preferred_label}: {definition}"`
- **Index:** HNSW with `vector_cosine_ops` for approximate nearest neighbor search
- **Uses:** Semantic similarity search, duplicate detection (similarity > 0.95), coherence scoring

---

## Pattern Edge Table

SKOS semantic relations plus adoption predicates between patterns.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `src_id` | `TEXT` | NOT NULL | — | FK → `pattern.id` |
| `dst_id` | `TEXT` | NOT NULL | — | FK → `pattern.id` |
| `predicate` | `TEXT` | NOT NULL | — | Relationship type (see enum below) |
| `strength` | `DECIMAL(3,2)` | YES | `1.0` | Importance/confidence 0.0–1.0 |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Additional context |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | |

**Primary key:** `(src_id, dst_id, predicate)`

### Pattern Edge Predicates

**SKOS Hierarchy:**

| Predicate | SKOS Mapping | Meaning |
|-----------|--------------|---------|
| `broader` | `skos:broader` | Source is more specific than destination |
| `narrower` | `skos:narrower` | Source is more general than destination |
| `related` | `skos:related` | Associative, non-hierarchical |

**Adoption Lineage:**

| Predicate | Meaning | Example |
|-----------|---------|---------|
| `adopts` | Uses 3P pattern as-is | `semantic-operations` → adopts → `skos` |
| `extends` | Builds on pattern with additions | `semantic-operations` → extends → `ddd` |
| `modifies` | Changes pattern for specific use | `content-classify-pattern` → modifies → `dam` |

---

## Brand Table

Unified actor table for CRM/PIM. See [UBIQUITOUS_LANGUAGE.md — Brand](UBIQUITOUS_LANGUAGE.md#brand-unified-actor) for business context.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `TEXT` | NOT NULL | — | Primary key. Kebab-case. |
| `brand_type` | `TEXT` | NOT NULL | — | `'person'`, `'organization'`, `'brand'` |
| `name` | `TEXT` | NOT NULL | — | Schema.org `name` — display name |
| `alt_names` | `TEXT[]` | YES | — | Schema.org `alternateName` |
| `slogan` | `TEXT` | YES | — | Brand tagline (brands only) |
| `logo_uri` | `TEXT` | YES | — | Logo asset URI (brands only) |
| `url` | `TEXT` | YES | — | Primary URL |
| `owned_domains` | `TEXT[]` | YES | — | Domains owned by this actor |
| `given_name` | `TEXT` | YES | — | First name (persons only) |
| `family_name` | `TEXT` | YES | — | Last name (persons only) |
| `legal_name` | `TEXT` | YES | — | Legal name (organizations only) |
| `emails` | `TEXT[]` | YES | — | Contact emails |
| `external_ids` | `JSONB` | YES | — | External identifiers (linkedin, github, etc.) |
| `pattern_id` | `TEXT` | YES | — | FK → `pattern.id`. 1P pattern this commercializes. |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Additional metadata |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |

### Brand Enums

**brand_type** — Actor type (Schema.org foundation)

| Value | Schema.org Type | Meaning |
|-------|-----------------|---------|
| `person` | `schema:Person` | Individual person |
| `organization` | `schema:Organization` | Company or institution |
| `brand` | `schema:Brand` | Commercial identity |

---

## Product Table

PIM entity. See [UBIQUITOUS_LANGUAGE.md — Product](UBIQUITOUS_LANGUAGE.md#product) for business context.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `TEXT` | NOT NULL | — | Primary key. Kebab-case. |
| `name` | `TEXT` | NOT NULL | — | Product name |
| `sku` | `TEXT` | YES | — | Stock keeping unit |
| `description` | `TEXT` | YES | — | Product description |
| `brand_id` | `TEXT` | NOT NULL | — | FK → `brand.id`. Brand that offers this. |
| `pattern_id` | `TEXT` | YES | — | FK → `pattern.id`. 1P pattern this packages. |
| `pricing` | `JSONB` | NOT NULL | `'{}'` | Pricing info (price, currency, unit, availability) |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Additional metadata |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |

---

## Brand Relationship Table

CRM-style connections between actors and products.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `src_id` | `TEXT` | NOT NULL | — | FK → `brand.id`. Source actor. |
| `dst_type` | `TEXT` | NOT NULL | — | `'brand'` or `'product'` |
| `dst_id` | `TEXT` | NOT NULL | — | Destination ID |
| `predicate` | `TEXT` | NOT NULL | — | Relationship type (flexible, not enumerated) |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Context (source, met_at, etc.) |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | |

**Primary key:** `(src_id, dst_type, dst_id, predicate)`

### Common Predicates

| Predicate | Meaning | Example |
|-----------|---------|---------|
| `owns` | Ownership | Person → Brand |
| `knows` | Peer relationship | Person → Person |
| `works_for` | Employment | Person → Organization |
| `represents` | Represents commercially | Person → Brand |
| `interested_in` | Interest in product/brand | Person → Product |
| `wants_to_hire` | Wants to hire | Person → Person |
| `customer_of` | Customer relationship | Person/Org → Brand |
| `partner_with` | Partnership | Brand → Brand |

---

## Entity Table

Unified entity table with type discriminator (ADR-0009). See [UBIQUITOUS_LANGUAGE.md — Entity](UBIQUITOUS_LANGUAGE.md#entity-unified) for business context.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `TEXT` | NOT NULL | — | Primary key. Kebab-case, 3–80 chars. |
| `entity_type` | `TEXT` | NOT NULL | `'content'` | `'content'`, `'capability'`, `'repository'` |
| `asset_type` | `TEXT` | YES | — | `'file'` or `'link'`. Only meaningful for content entities. |
| `title` | `TEXT` | YES | — | Human-readable title (≥5 chars, not generic) |
| `version` | `TEXT` | YES | `'1.0'` | Semantic versioning |
| `primary_pattern_id` | `TEXT` | YES | — | FK → `pattern.id`. Main pattern. NULL = orphan (content) or use edges (multi-pattern). |
| `filespec` | `JSONB` | NOT NULL | `'{}'` | `filespec_v1` — physical location and file properties |
| `attribution` | `JSONB` | NOT NULL | `'{}'` | `attribution_v2` — Dublin Core aligned creator/rights |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Per-type metadata (see schemas below) |
| `embedding` | `vector(1536)` | YES | — | OpenAI `text-embedding-3-small` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |

### Entity Type Field Usage

| Field | content | capability | repository |
|-------|---------|------------|------------|
| `entity_type` | `'content'` | `'capability'` | `'repository'` |
| `asset_type` | Required (`'file'`/`'link'`) | NULL | NULL |
| `title` | Optional | Required | Required |
| `primary_pattern_id` | Optional (NULL = orphan) | Optional (use `implements` edges for multi-pattern) | Optional |
| `filespec` | Used (file location) | Typically `'{}'` | Typically `'{}'` |
| `attribution` | Used (Dublin Core) | Typically `'{}'` | Typically `'{}'` |
| `metadata` | `content_metadata_v1` | `capability_metadata_v1` | `repository_metadata_v1` |
| `embedding` | Used | Used | Used |

### Entity Enums

**entity_type** — Type discriminator (ADR-0009)

| Value | Meaning |
|-------|---------|
| `content` | DAM publishing artifact (blog post, research paper, media) |
| `capability` | What the system delivers. Must trace to ≥1 pattern. |
| `repository` | Where implementation lives. Delivers capabilities. |

**asset_type** — Physical nature (content entities only)

| Value | Meaning |
|-------|---------|
| `file` | You possess the actual content (PDF, markdown, image) |
| `link` | External reference to content you don't possess (URL, arXiv paper) |

---

## Edge Table

Typed directional relationships between entities, patterns, and surfaces. See [UBIQUITOUS_LANGUAGE.md — Edge](UBIQUITOUS_LANGUAGE.md#edge) for business context.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `src_type` | `TEXT` | NOT NULL | — | `'entity'`, `'surface'`, `'pattern'` |
| `src_id` | `TEXT` | NOT NULL | — | Source ID |
| `dst_type` | `TEXT` | NOT NULL | — | `'entity'`, `'surface'`, `'pattern'` |
| `dst_id` | `TEXT` | NOT NULL | — | Destination ID |
| `predicate` | `TEXT` | NOT NULL | — | Relationship type (see enum below) |
| `strength` | `DECIMAL(3,2)` | YES | `1.0` | Importance/confidence 0.0–1.0 |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Additional context |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | |

**Primary key:** `(src_type, src_id, dst_type, dst_id, predicate)`

### Edge Node Types

| Value | Meaning |
|-------|---------|
| `entity` | Reference to entity table |
| `surface` | Reference to surface table |
| `pattern` | Reference to pattern table (enables cross-layer edges) |

### Edge Predicates

**PROV-O / Schema.org / Domain:**

| Predicate | Origin | Meaning |
|-----------|--------|---------|
| `derived_from` | PROV-O `prov:wasDerivedFrom` | Created by transforming source |
| `cites` | PROV-O `prov:wasQuotedFrom` | Formal reference for attribution |
| `version_of` | PROV-O `prov:wasRevisionOf` | New version of existing content |
| `part_of` | Schema.org | Component of larger whole |
| `documents` | Schema.org | Explains or covers in detail |
| `depends_on` | Domain | Requires another for definition/function |
| `related_to` | Domain | Associated without hierarchy |

**Strategic DDD (ADR-0009):**

| Predicate | Direction | Meaning |
|-----------|-----------|---------|
| `implements` | capability → pattern | Capability implements this pattern |
| `delivered_by` | capability → repository | Capability is delivered by this repository |
| `integration` | repository → repository | DDD integration pattern between repos |

### Integration Edge Metadata

Required fields for `predicate = 'integration'`:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `integration_pattern` | string | DDD integration pattern type | `"shared-kernel"`, `"conformist"` |
| `direction` | string | Data/dependency flow | `"bidirectional"`, `"upstream"` |
| `shared_artifact` | string | What is shared | `"UBIQUITOUS_LANGUAGE.md"` |
| `rationale` | string | Why this integration type | `"Schema owner defines terms"` |

---

## Surface Table

Publication destinations and ingestion sources.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `TEXT` | NOT NULL | — | Primary key. `{platform}-{identifier}` format. |
| `platform` | `TEXT` | NOT NULL | — | Platform name (youtube, github, wordpress, etc.) |
| `surface_type` | `TEXT` | YES | — | Type of surface (site, channel, repository, etc.) |
| `direction` | `TEXT` | NOT NULL | — | `'publish'`, `'ingest'`, `'bidirectional'` |
| `constraints` | `JSONB` | NOT NULL | `'{}'` | Platform limits (max_size, formats, rate_limits) |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Platform-specific data (site_url, api_endpoint) |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | |

### Surface Enums

**direction** — Data flow direction

| Value | Meaning |
|-------|---------|
| `publish` | Content pushed to this surface |
| `ingest` | Content pulled from this surface |
| `bidirectional` | Both publish and ingest |

---

## Delivery Table

Publication lifecycle records linking entities to surfaces.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `TEXT` | NOT NULL | — | Primary key |
| `entity_id` | `TEXT` | NOT NULL | — | FK → `entity.id` |
| `surface_id` | `TEXT` | NOT NULL | — | FK → `surface.id` |
| `role` | `TEXT` | NOT NULL | — | `'original'` or `'syndication'` |
| `status` | `TEXT` | NOT NULL | `'planned'` | Publication lifecycle state |
| `approval_status` | `TEXT` | NOT NULL | `'pending'` | Per-surface approval |
| `visibility` | `TEXT` | NOT NULL | `'private'` | Per-surface access level |
| `url` | `TEXT` | YES | — | Where content lives on this surface |
| `remote_id` | `TEXT` | YES | — | Platform-specific ID |
| `field_mapping` | `JSONB` | NOT NULL | `'{}'` | Entity → platform field mapping |
| `source_hash` | `TEXT` | YES | — | Content hash for deduplication |
| `published_at` | `TIMESTAMPTZ` | YES | — | When published (required if status = 'published') |
| `failed_at` | `TIMESTAMPTZ` | YES | — | When failed |
| `error_message` | `TEXT` | YES | — | Error details |
| `metadata` | `JSONB` | NOT NULL | `'{}'` | Delivery-specific data |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |

### Delivery Enums

**role**

| Value | Meaning |
|-------|---------|
| `original` | First/primary publication (at most one per entity) |
| `syndication` | Republication or cross-posting |

**status** — Publication lifecycle

| Value | Meaning |
|-------|---------|
| `planned` | Scheduled but not yet queued |
| `queued` | Waiting to be published |
| `published` | Successfully published |
| `failed` | Publication attempt failed |
| `removed` | Previously published, now removed |

**approval_status** — Per-surface approval

| Value | Meaning |
|-------|---------|
| `pending` | Not yet reviewed for this surface |
| `approved` | Approved for publication |
| `rejected` | Not approved for this surface |

**visibility** — Per-surface access level

| Value | Meaning |
|-------|---------|
| `public` | Open access on this surface |
| `private` | Restricted access on this surface |

**Status transitions:**
```
planned → queued → published
               ↓
             failed
               ↓
             queued (retry)

published → removed
```

---

## Ingestion Run Table

Bounded execution of an ingestion pipeline.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `TEXT` | NOT NULL | — | Primary key. ULID for time-ordering. |
| `run_type` | `TEXT` | NOT NULL | — | `'manual'`, `'scheduled'`, `'agent'` |
| `agent_name` | `TEXT` | YES | — | Pipeline that executed |
| `source_name` | `TEXT` | YES | — | Config source name |
| `status` | `TEXT` | NOT NULL | `'running'` | `'running'`, `'completed'`, `'failed'`, `'cancelled'` |
| `source_config` | `JSONB` | NOT NULL | `'{}'` | Snapshot of config used |
| `metrics` | `JSONB` | NOT NULL | `'{}'` | Run-level aggregated metrics |
| `started_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |
| `completed_at` | `TIMESTAMPTZ` | YES | — | |

---

## Ingestion Episode Table

Single agent operation tracked for provenance.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `TEXT` | NOT NULL | — | Primary key. ULID for time-ordering. |
| `run_id` | `TEXT` | YES | — | FK → `ingestion_run.id`. NULL if standalone. |
| `operation` | `TEXT` | NOT NULL | — | Operation type (see enum below) |
| `target_type` | `TEXT` | NOT NULL | — | `'entity'`, `'pattern'`, `'edge'`, `'delivery'` |
| `target_id` | `TEXT` | YES | — | ID of the target created/modified |
| `context_pattern_ids` | `TEXT[]` | YES | — | Patterns retrieved/considered |
| `context_entity_ids` | `TEXT[]` | YES | — | Entities used as context |
| `coherence_score` | `DECIMAL(3,2)` | YES | — | Semantic coherence 0.0–1.0 |
| `agent_name` | `TEXT` | YES | — | Agent that performed the operation |
| `model_name` | `TEXT` | YES | — | LLM or embedding model used |
| `detected_edges` | `JSONB` | YES | — | Model-proposed relationships |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |

### Episode Operation Types

| Operation | Meaning |
|-----------|---------|
| `ingest` | New entity created from source |
| `classify` | Entity gets primary_pattern_id assigned |
| `declare_pattern` | New pattern created from synthesis |
| `publish` | Delivery created (original publication) |
| `synthesize` | Research synthesis → pattern emergence |
| `create_edge` | Relationship established |
| `embed` | Embedding generated |

### Detected Edge Value Object

Model-proposed relationships captured during classification. Not yet committed to the `edge` table.

| Field | Type | Description |
|-------|------|-------------|
| `predicate` | string | Relationship type |
| `target_id` | string | Related entity/pattern ID |
| `strength` | float | Confidence 0.0–1.0 |
| `rationale` | string | Why the agent proposed this |

---

## Value Objects (JSONB Schemas)

All JSONB value objects follow: `{"$schema": "schema_name_vN", ...fields}`

### filespec_v1

**Question answered:** WHERE is the content?

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `$schema` | string | Yes | Always `"filespec_v1"` |
| `uri` | string | Yes | Location (`file://`, `s3://`, `gs://`, `https://`) |
| `format` | string | No | File extension (pdf, markdown, mp4, jpg, txt) |
| `mime_type` | string | No | MIME type (application/pdf, text/markdown) |
| `hash` | string | No | Content hash (`algorithm:hash`, e.g., `sha256:abc123`) |
| `size_bytes` | integer | No | File size |
| `encoding` | string | No | Character encoding (utf-8, ascii) |
| `platform` | string | No | For links (youtube, github, arxiv) |
| `accessible` | boolean | No | Currently accessible? |
| `last_checked` | string | No | When verified (ISO 8601) |

### attribution_v2

**Question answered:** WHO created it? Dublin Core-aligned with AI attribution extensions.

| Field | Type | Required | Dublin Core Mapping | Description |
|-------|------|----------|---------------------|-------------|
| `$schema` | string | Yes | — | Always `"attribution_v2"` |
| `creator` | string[] | No | `dc:creator` | Primary creators with IP ownership |
| `contributor` | string[] | No | `dc:contributor` | Secondary contributors |
| `publisher` | string | No | `dc:publisher` | Entity responsible for availability |
| `rights` | string | No | `dc:rights` | License (MIT, CC-BY-4.0, etc.) |
| `organization` | string | No | — | Institutional affiliation |
| `platform` | string | No | — | Publication platform |
| `channel` | string | No | — | Specific channel/account name |
| `original_source` | string | No | `dc:source` | Original URL |
| `agents` | object[] | No | — | AI tools used (`{name, role, version}`) |
| `publication_date` | string | No | `dc:date` | When originally published |

### content_metadata_v1

**Question answered:** WHAT kind of content is this? (For `entity_type = 'content'`)

| Field | Type | Description |
|-------|------|-------------|
| `$schema` | string | Always `"content_metadata_v1"` |
| `content_type` | string | Form classification (article, paper, transcript, pattern, etc.) |
| `media_type` | string | Broad category (text, video, audio, image, data, code) |
| `language` | string | ISO 639-1 language code |
| `tags` | string[] | Freeform tags |
| `summary` | string | Brief abstract |
| `word_count` | integer | For text content |
| `reading_time_minutes` | integer | Estimated reading time |
| `duration_seconds` | integer | For video/audio |
| `subject_area` | string[] | Domain classifications (classifier-assigned) |
| `quality_score` | float | Relevance/quality 0.0–1.0 (classifier-assigned) |
| `corpus` | string | Knowledge base partition |
| `lifecycle_stage` | string | `"draft"`, `"active"`, `"stable"`, `"deprecated"`, `"archived"` |

### capability_metadata_v1

**For `entity_type = 'capability'`** (ADR-0009)

| Field | Type | Description |
|-------|------|-------------|
| `$schema` | string | Always `"capability_metadata_v1"` |
| `domain_classification` | string | `"core"`, `"supporting"`, `"generic"` |
| `description` | string | What this capability delivers |
| `implements_patterns` | string[] | Pattern IDs this capability implements |
| `delivered_by_repos` | string[] | Repository IDs that deliver this |
| `status` | string | `"active"`, `"planned"`, `"deprecated"` |

### repository_metadata_v1

**For `entity_type = 'repository'`** (ADR-0009)

| Field | Type | Description |
|-------|------|-------------|
| `$schema` | string | Always `"repository_metadata_v1"` |
| `role` | string | Repository role in the system |
| `github_url` | string | GitHub repository URL |
| `delivers_capabilities` | string[] | Capability IDs this repo delivers |
| `status` | string | `"active"`, `"archived"`, `"planned"` |

---

## Views

### orphan_entities

Content entities without pattern connection — the flexible edge awaiting incorporation.

```sql
WHERE entity_type = 'content' AND primary_pattern_id IS NULL
```

### pattern_coverage

Pattern graph coverage with per-entity-type counts.

| Column | Description |
|--------|-------------|
| `pattern_id` | Pattern ID |
| `preferred_label` | Display name |
| `provenance` | 1p/2p/3p |
| `content_count` | Content entities linked |
| `capability_count` | Capabilities linked |
| `repo_count` | Repositories linked |
| `total_entity_count` | All entities linked |

### capability_coverage

Strategic DDD coherence signal — capabilities with pattern implementation and repo delivery counts.

| Column | Description |
|--------|-------------|
| `capability_id` | Capability entity ID |
| `capability_name` | Display name |
| `domain_classification` | core/supporting/generic |
| `primary_pattern_id` | Direct pattern link |
| `pattern_count` | Patterns via `implements` edges |
| `repo_count` | Repos via `delivered_by` edges |

### repo_capabilities

Repositories and the capabilities they deliver.

| Column | Description |
|--------|-------------|
| `repo_id` | Repository entity ID |
| `repo_name` | Display name |
| `repo_role` | Repository role |
| `capability_id` | Capability entity ID |
| `capability_name` | Capability display name |

### integration_map

Repo-to-repo integration relationships with DDD pattern typing.

| Column | Description |
|--------|-------------|
| `source_repo_id` | Source repository |
| `target_repo_id` | Target repository |
| `integration_pattern` | DDD pattern type (shared-kernel, conformist, etc.) |
| `shared_artifact` | What is shared |
| `direction` | Data/dependency flow |
| `rationale` | Why this integration type |

---

## Naming Conventions

### Pattern IDs
**Format:** `kebab-case`, 3–50 characters
**Examples:** `semantic-coherence`, `ddd`, `prov-o`, `content-classify-pattern`

### Entity IDs
**Format:** `kebab-case`, 3–80 characters
**Examples:** `blog-post-ai-adoption-2024`, `research-vector-db-comparison`, `publishing-pipeline` (capability), `semops-core` (repository)

### Predicate Names
**Format:** `snake_case` verbs or relationships
**Examples:** `derived_from`, `depends_on`, `implements`, `delivered_by`

### Surface IDs
**Format:** `{platform}-{identifier}`
**Examples:** `wordpress-my-blog`, `youtube-main-channel`, `github-project-repo`

---

## Indexes

### Pattern Indexes
| Index | Columns | Type |
|-------|---------|------|
| `idx_pattern_provenance` | `provenance` | B-tree |
| `idx_pattern_metadata` | `metadata` | GIN |
| `idx_pattern_alt_labels` | `alt_labels` | GIN |
| `idx_pattern_embedding` | `embedding` | HNSW (`vector_cosine_ops`) |

### Entity Indexes
| Index | Columns | Type | Notes |
|-------|---------|------|-------|
| `idx_entity_type` | `entity_type` | B-tree | |
| `idx_entity_type_pattern` | `(entity_type, primary_pattern_id)` | B-tree | |
| `idx_entity_asset_type` | `asset_type` | B-tree | |
| `idx_entity_primary_pattern` | `primary_pattern_id` | B-tree | |
| `idx_entity_metadata` | `metadata` | GIN | |
| `idx_entity_filespec` | `filespec` | GIN | |
| `idx_entity_attribution` | `attribution` | GIN | |
| `idx_entity_orphans` | `id` | B-tree | Partial: `entity_type = 'content' AND primary_pattern_id IS NULL` |
| `idx_entity_embedding` | `embedding` | HNSW (`vector_cosine_ops`) | |

### Edge Indexes
| Index | Columns | Type |
|-------|---------|------|
| `idx_edge_src` | `(src_type, src_id)` | B-tree |
| `idx_edge_dst` | `(dst_type, dst_id)` | B-tree |
| `idx_edge_predicate` | `predicate` | B-tree |

---

## References

- [UBIQUITOUS_LANGUAGE.md](UBIQUITOUS_LANGUAGE.md) — Domain definitions and business rules
- [phase2-schema.sql](phase2-schema.sql) — Canonical DDL
- [fitness-functions.sql](fitness-functions.sql) — Schema validation rules
- [SCHEMA_CHANGELOG.md](SCHEMA_CHANGELOG.md) — Change history
- ADR-0004: Pattern as Aggregate Root
- ADR-0009: Three-Layer Architecture

---

**Document Status:** Active | **Schema Version:** 8.0.0
**Maintainer:** Project SemOps Schema Team
**Change Process:** All updates require schema governance review
