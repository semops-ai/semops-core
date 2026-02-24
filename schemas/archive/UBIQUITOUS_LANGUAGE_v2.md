# Project Ike Ubiquitous Language

> Canonical definitions of terms used throughout Project Ike schema and systems.
> **Version:** 2.0.0 | **Last Updated:** 2025-11-07

This document establishes the precise meaning of terms used across Project Ike to ensure consistent understanding between developers, documentation, and systems. This is the foundation of our ubiquitous language in Domain-Driven Design (DDD) and semantic operations.

## Project Domain

Project Ike is fundamentally a **digital publishing** domain model, as all work is aimed at creating public or private digital content entities of various types across different surfaces. There is a recursive property, as Project Ike's content is describing the use of this architecture while putting it into practice.

### Multi-Domain Convergence

Project Ike's schema represents a **convergence of established patterns** from multiple specialized domains, creating a unified system for knowledge-first digital publishing.

**Adopted Industry Patterns:**

- ✅ **DAM (Digital Asset Management)** - Approval workflows, asset storage and organization, multi-channel distribution tracking, version control and metadata
- ✅ **CMS (Content Management System)** - Content lifecycle (draft → published), visibility controls (public/private), multi-surface publishing, syndication support
- ✅ **Knowledge Management / Graph Database** - Semantic relationships (Edge entity), typed predicates (cites, derived_from, etc.), relationship strength weighting, graph-based lineage tracking
- ✅ **PIM (Product Information Management)** - Channel syndication patterns, platform-specific field mapping, centralized source of truth
- ✅ **AI/LLM Operations (Emerging)** - RAG-aware architecture, agent attribution tracking, quality scoring for retrieval, internal surfaces for vector DBs

**Unique Innovations:**

1. **Provenance-First Design (1P/2P/3P)** - Differentiates owned content from referenced content
2. **Unified Catalog (Owned + Referenced)** - Single system for both your content AND external references, with citations and sources as first-class entities
3. **Dual-Status Model** - Approval Status (is it ready?) vs. Delivery Status (where is it live?). Needed because the Unified Catalog includes 3P content that's "approved for internal use" but never "delivered", and 1P content that can be "approved" but not yet "published"
4. **Derivative Work Lineage** - Explicit `derived_from` edges for transformations, enabling multi-hop derivation chains
5. **Graph-Native Relationships** - Rich semantic predicates beyond simple parent/child, enabling bidirectional querying

**See [Domain Patterns](../docs/domain-patterns/)** for comprehensive documentation of these patterns and how attributes combine to represent real-world publishing workflows.

In the [Ike Framework](https://github.com/timjmitchell/project-ike/tree/main/FRAMEWORK), this is tied to [Global Architecture](https://github.com/timjmitchell/project-ike/blob/main/docs/GLOBAL_ARCHITECTURE/GLOBAL_ARCHITECTURE.md).

---

## Attribute Type Categories

Throughout this document, entity attributes are classified into the following type categories:

### Identity
- **Purpose**: Uniquely identifies an entity instance
- **Characteristics**: Required, unique id across all instances of that entity type
- **Example**: `id: "blog-post-knowledge-ops-2024"`

### Primitive
- **Purpose**: Simple, atomic values (built-in types)
- **Characteristics**: Single scalar value of basic type (string, number, boolean, etc.)
- **Examples**: `title: "My Title"`, `word_count: 1500`, `is_featured: true`

### Enum
- **Purpose**: Constrained set of allowed values with business meaning
- **Characteristics**: Fixed set of valid options, type-safe, single scalar value
- **Example**: `status: "published"` (can only be `"draft"`, `"published"`, or `"archived"`)

### Value Object
- **Purpose**: Composite domain concept bundling related attributes. Value Objects are how we defer encoding hard schema - it is our "flexible edge".
- **Characteristics**:
 - Multiple fields grouped together as one logical unit
 - Immutable (replace entire object to change)
 - No identity of its own (defined by all attribute values)
 - Compared by values, not by reference
- **Example**: `filespec: {"uri": "s3://...", "format": "pdf", "hash": "sha256:...", "size_bytes": 104857600}`

### Timestamp
- **Purpose**: Track entity lifecycle events
- **Characteristics**: DateTime values marking when events occurred
- **Examples**: `created_at`, `updated_at`, `published_at`

### Foreign Key
- **Purpose**: Reference to another entity
- **Characteristics**: Contains the ID of a related entity
- **Examples**: `entity_id` (references Entity), `surface_id` (references Surface)

---

## W3C Standards Foundation

Project Ike is built on W3C semantic web standards for interoperability and semantic correctness:

### **SKOS (Simple Knowledge Organization System)** → `content_metadata`

**Purpose:** Semantic organization WITHIN entities

- [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/)
- SKOS provides vocabulary for concept hierarchies, labels, and definitions
- Stored in Entity's `metadata` value object (JSONB)
- See [content_metadata_v1.json](./metadata/content_metadata_v1.json) schema

**Key SKOS mappings:**
- `skos:Concept` → `metadata.semantic_type`
- `skos:prefLabel` → `metadata.preferred_label`
- `skos:broader` → `metadata.broader_concepts`
- `skos:narrower` → `metadata.narrower_concepts`

### **PROV-O (Provenance Ontology)** → Edge Predicates

**Purpose:** Provenance relationships BETWEEN entities

- [W3C PROV-O Specification](https://www.w3.org/TR/prov-o/)
- PROV-O provides vocabulary for derivation, attribution, and lineage
- Expressed as typed edges in the knowledge graph

**Key PROV-O mappings:**
- `prov:wasDerivedFrom` → `derived_from` predicate
- `prov:wasQuotedFrom` → `cites` predicate
- `prov:wasRevisionOf` → `version_of` predicate

See [EDGE_PREDICATES.md](../docs/EDGE_PREDICATES.md) and [SKOS_PROVO_MAPPING.md](../docs/SKOS_PROVO_MAPPING.md) for complete documentation.

---

## Core Entities

### Entity (Aggregate Root)
**Definition:** For Project Ike, the core entity represents any concrete "content object", representing all concrete content objects deliverables, content, and artifacts in the system. This is the single aggregate root in our DDD design.

**Ike Conception:** In Ike, our aggregate root represents 

**Examples:** Blog posts, research papers, research documents, code repositories, images, datasets, notes, 3p quotes, YouTube video, concept definition notes or documents, work deliverable, etc.

**Attributes:**

| Attribute | Type Category | Specific Type | Description | Example Value |
| -------------- | ------------- | -------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `id` | Identity | String (kebab-case) | Unique identifier for the entity | `"blog-post-knowledge-ops-2024"` |
| `asset_type` | Enum | AssetType | Concrete type indicating if you possess the content or reference it | `"file"` or `"link"` |
| `title` | Primitive | String | Human-readable title | `"Introduction to Semantic Operations"` |
| `version` | Primitive | String (semantic versioning) | Version number for iteration tracking | `"1.0"`, `"1.1"`, `"2.0"` |
| `provenance` | Enum | ProvenanceType | Who created THIS artifact | `"1p"`, `"2p"`, or `"3p"` |
| `approval_status` | Enum | ApprovalStatus | Asset readiness and approval state | `"pending"`, `"approved"`, or `"rejected"` |
| `visibility` | Enum | Visibility | Access level | `"public"` or `"private"` |
| `filespec` | Value Object | FileSpec (JSONB: filespec_v1) | Physical location and file properties | `{"$schema": "filespec_v1", "uri": "...", "format": "pdf", ...}` |
| `attribution` | Value Object | Attribution (JSONB: attribution_v1) | Authorship and provenance details | `{"$schema": "attribution_v1", "authors": [...], ...}` |
| `metadata` | Value Object | ContentMetadata (JSONB: content_metadata_v1) | Semantic content metadata (W3C SKOS-based) | `{"$schema": "content_metadata_v1", "semantic_type": "concept", ...}` |
| `created_at` | Timestamp | DateTime | When entity was created | `2024-11-07T10:30:00Z` |
| `updated_at` | Timestamp | DateTime | When entity was last modified | `2024-11-15T14:22:00Z` |
| `approved_at` | Timestamp | DateTime (Optional) | When approval_status became 'approved' | `2024-11-10T09:00:00Z` or `null` |

#### Attribute Combination Examples

The following examples illustrate how attributes combine to create meaningful contexts:

**Approval Status vs. Visibility:**
- `approval_status=approved` + `visibility=private` → Content approved for internal use (e.g., indexed in RAG system, added to knowledge base)
- `approval_status=approved` + `visibility=public` → Content approved and ready for public delivery
- `approval_status=pending` + `visibility=private` → Work in progress, internal only
- `approval_status=pending` + `visibility=public` → **INVALID** (pending content must remain private)
- `approval_status=rejected` → Content not approved for any use

**Provenance Implications:**
- `provenance=3p` + `approval_status=pending` → External link staged in inbox, needs classification
- `provenance=3p` + `approval_status=approved` → External content fully cataloged and ready for use
- `provenance=1p` + Edge `derived_from` → You created a derivative work from source material
- `provenance=1p` + `asset_type=file` → You possess original or derivative content
- `provenance=3p` + `asset_type=link` → Reference to external content you don't possess

**For comprehensive pattern documentation, see [Domain Patterns](../docs/domain-patterns/).**

---

### Edge (Entity)
**Definition:** An Edge entity is a typed relationship between two aggregate roots. Based on W3C PROV-O (Provenance Ontology), edges capture how entities connect through provenance, derivation, and semantic relationships. Edge represents the connections in the knowledge graph.

**W3C Foundation:** Edge predicates implement [W3C PROV-O](https://www.w3.org/TR/prov-o/) patterns for provenance tracking.

**Attributes:**
- `source_id` - **Foreign Key**: Reference to source Entity (the "from" side of the relationship)
- `destination_id` - **Foreign Key**: Reference to destination Entity (the "to" side of the relationship)
- `predicate` - **Enum**: Edge Predicate (W3C PROV-O based: `derived_from`, `cites`, `version_of`, `part_of`, `documents`, `depends_on`, `related_to`)
- `strength` - **Primitive**: Relationship weighting (float: 0.0 to 1.0, indicating importance or confidence)
- `metadata` - **Value Object**: Additional relationship context (JSONB, flexible for evolving relationship attributes)
- `created_at` - **Timestamp**: When relationship was established (datetime)

**Characteristics:**
- Always directional (source → destination)
- Both source and destination must reference valid Entity instances
- Predicate defines the semantic meaning of the relationship
- Based on W3C PROV-O standard for provenance tracking

**See:** [Edge Predicates](../docs/domain-patterns/edge-predicates.md) for complete predicate documentation

---

### Surface (Entity)
**Definition:** A publication destination or ingestion source where content is published to or pulled from. Represents channels, repositories, sites, publications, and other addressable platforms.

**Examples:** YouTube channel, GitHub repository, WordPress site, Medium publication, LinkedIn profile, Twitter/X account

**Attributes:**
- `id` - **Identity**: Unique identifier (string, slug format, e.g., `youtube-my-channel`, `github-my-repo`)
- `platform` - **Enum**: Platform name (`youtube`, `github`, `wordpress`, `medium`, `linkedin`, `twitter`, `instagram`, etc.)
- `surface_type` - **Enum**: Type of surface (`channel`, `repo`, `site`, `publication`, `feed`, `profile`)
- `direction` - **Enum**: Data flow direction (`publish`, `ingest`, `bidirectional`)
- `constraints` - **Value Object**: Platform limits and capabilities (JSONB: max_size, formats, rate_limits, etc.)
- `metadata` - **Value Object**: Platform-specific metadata (JSONB: youtube_channel_v1, github_repo_v1, etc.)
- `created_at`, `updated_at` - **Timestamps**: Lifecycle tracking (datetime)

---

### Delivery (Entity)
**Definition:** A record of an Entity published to or ingested from a Surface. Tracks the publication lifecycle, platform-specific identifiers, and URLs.

**Attributes:**
- `id` - **Identity**: Unique identifier (string, slug format)
- `entity_id` - **Foreign Key**: Reference to Entity being delivered
- `surface_id` - **Foreign Key**: Reference to Surface where content is delivered
- `role` - **Enum**: Delivery role (`original`, `syndication`)
- `status` - **Enum**: Delivery status (`planned`, `queued`, `published`, `failed`, `removed`)
- `url` - **Primitive**: Where the content lives on the surface (string, e.g., published blog post URL)
- `remote_id` - **Primitive**: Platform-specific ID (string: YouTube video ID, GitHub issue number, WordPress post ID, etc.)
- `field_mapping` - **Value Object**: How entity fields map to platform schema (JSONB)
- `source_hash` - **Primitive**: Hash for deduplication and lineage tracking (string)
- `published_at` - **Timestamp**: When content was successfully published (datetime, optional)
- `failed_at` - **Timestamp**: When delivery failed (datetime, optional)
- `error_message` - **Primitive**: Error details if delivery failed (string, optional)
- `metadata` - **Value Object**: Delivery-specific metadata (JSONB)
- `created_at`, `updated_at` - **Timestamps**: Lifecycle tracking (datetime)

**Characteristics:**
- One entity can have multiple deliveries (original + syndications)
- At most one delivery with `role='original'` per entity
- Status transitions: planned → queued → published (or failed/removed)

---

## Enums

These are constrained sets of valid values that describe characteristics of entities. Each Enum has a fixed set of allowed values.

### Asset Type (Enum)
Valid values for the `asset_type` attribute on Entity. This defines the **concrete** nature of the asset - do you physically possess it or is it an external reference?

#### `file`
**Definition:** You possess the actual content file/artifact.
**Examples:** PDF you downloaded, markdown file you wrote, image you created, video file you have locally, dataset CSV you own

#### `link`
**Definition:** External reference to content you don't possess (someone else hosts it).
**Examples:** YouTube video URL, arXiv paper link, external blog post URL, GitHub repo you don't own

**Note:** The abstract "what is it" (blog post, research paper, educational video, etc.) lives in `metadata.content_type`, not in `asset_type`.

---

### Content Type (Metadata Field)
Valid examples for the `metadata.content_type` field on Entity. This is **extensible** - new types can be added without schema changes. This defines the **abstract semantic** meaning of the content.

**Common content_type values:**
- `blog_post` - Blog articles, technical posts
- `research_paper` - Academic papers, research publications
- `educational_video` - Tutorial videos, lectures
- `transcript` - Text transcription of audio/video
- `quote` - Extracted quote or passage derived with specific attribution
- `block` - An atomic, reusable, typed, addressable compositional unit like an example, analogy, definition
- `definition` - Canonical concept explanations
- `example` - Text, document distinct use-case or answer to question
- `analogy` - Text, document like 'example', used to explain
- `technical_guide` - How-to documentation
- `code_snippet` - Code examples, scripts
- `dataset` - Structured data collections
- `image` - Graphics, diagrams, photos
- `note` - Quick captures, thoughts

**This list is not exhaustive** - you can use any string value that makes sense for your domain.

---

### Provenance Type (Enum)
Valid values for the `provenance` attribute on Entity. Provenance answers: **WHO created THIS specific artifact?**

**Note:** Derived/transformed content is indicated by `derived_from` **edges**, not by provenance value. Provenance indicates who created the derivative work itself.

#### `1p` (first party)
**Definition:** Content created by you, including AI-generated content you directed, derivative works you created (transcripts, quotes, summaries), and original content.

**Ownership:** Full control and rights
**Examples:**
- Your original blog posts
- AI content you prompted
- Transcripts you extracted from 3p videos
- Quotes you extracted from 3p papers
- Summaries you wrote of 3p content
- Your code contributions

#### `2p` (second party)
**Definition:** Content created through direct collaboration with partners or colleagues.

**Ownership:** Shared or negotiated rights (assume permission given)
**Examples:** Co-authored papers, joint projects, collaborative repositories

#### `3p` (third party)
**Definition:** External content created by others without your direct involvement.

**Ownership:** External, may require attribution/licensing
**Examples:** Research papers you reference, external blog posts, YouTube videos, open source projects

---

**Key Insight:** A transcript you create from a 3p YouTube video is `1p` (you created it), but has a `derived_from` edge pointing to the 3p video entity.

---

### Approval Status (Enum)
Valid values for the `approval_status` attribute on Entity. Represents the **processing and approval state** of content in the catalog system, following DAM (Digital Asset Management) industry standards.

**Industry Alignment:** This follows the approval workflow pattern used by DAM systems like Bynder, Adobe Experience Manager, and Acquia DAM, where assets go through approval gates before being available for use or distribution.

#### `pending`
**Definition:** Content is incomplete, unprocessed, or awaiting approval for use.

**For 1P/2P Content:**
- Content being written or developed
- Not yet finalized or approved
- Subject to significant changes
- Internal use only

**For 3P Content:**
- Link dropped in staging inbox
- Needs classification and metadata enrichment
- Not yet fully cataloged
- Awaiting approval for inclusion in catalog

**Characteristics:**
- May be incomplete or placeholder
- Not ready for delivery to any surface
- Not searchable in approved catalog

#### `approved`
**Definition:** Content is complete, approved, and ready for use by its intended audience (internal or external).

**For 1P/2P Content:**
- Content finalized and approved for use
- Version is stable
- Can be delivered to surfaces (via Delivery entity)
- Ready for citation or reference

**For 3P Content:**
- Fully cataloged with complete metadata
- Classified, enriched, and approved for inclusion
- Ready for search, retrieval, citation
- May be delivered to internal systems (RAG, knowledge base)

**Characteristics:**
- Considered complete for current version
- Ready for delivery (actual delivery tracked via Delivery entity)
- Searchable and referenceable
- Should be stable unless versioned

**Note:** "Approved" does NOT mean delivered to external surfaces. Actual distribution is tracked separately via the Delivery entity with its own status workflow.

#### `rejected`
**Definition:** Content that has been reviewed and rejected for use in the catalog.

**For 1P/2P Content:**
- Does not meet quality standards
- Inappropriate for intended use
- May be deleted or reworked

**For 3P Content:**
- Not relevant for catalog inclusion
- Low quality or unreliable source
- Duplicate or superseded content

**Characteristics:**
- Not available for use or delivery
- May be deleted from system
- Can be reconsidered (status changed back to pending)

---

### Visibility (Enum)
Valid values for the `visibility` attribute on Entity.

#### `public`
**Definition:** Content intended for open access and sharing on public platforms.

**Access:** Anyone can view and reference, assuming access rules are met. For example, a public chat-bot may require LinkedIn authentication. 
**Usage:** Blog posts, open source projects, public research

#### `private`
**Definition:** Content restricted to personal or internal use. Content may exist as both public and private versions, depending on context (a quote from research paper, cited in a blog post may be public, but my notes on that paper may be private).

**Access:** Limited to authorized parties
**Usage:** Personal notes, proprietary research, draft content

---

## Lifecycle States

### Content Approval Lifecycle
- `pending` - Awaiting approval (1P: in development, 3P: being cataloged)
- `approved` - Approved and ready for use
- `rejected` - Not approved for catalog inclusion

**Note:** Actual delivery to surfaces is tracked separately via the Delivery entity with statuses: `planned`, `queued`, `published`, `failed`, `removed`.

## Value Objects (JSONB Schema Patterns)

In DDD, **Value Objects** are composite objects with multiple related attributes, no identity of their own, and are compared by their values. They are immutable - to change them, you replace the entire object.

Entity has three typed JSONB fields that hold structured data with versioned schemas. These are true Value Objects:

1. **`filespec`** - WHERE is it? (physical location: uri, format, hash, etc.)
2. **`attribution`** - WHO made it? (authors, platform, sources, agents, license)
3. **`metadata`** - WHAT is it? (content_type, media_type, subject_area, tags, etc.)

### Typed JSONB Convention
All JSONB fields follow the pattern: `{"$schema": "schema_name_v1", ...fields}`

**Purpose:**
- Enable schema evolution without database migrations
- Validate structure and contents with JSON Schema definitions
- Support automated processing and migration
- Keep database schema simple while allowing rich metadata

### Common JSONB Schema Types

#### filespec_v1
**Purpose:** Physical location and file properties

**Fields:**
- `$schema` - Schema version identifier (always "filespec_v1")
- `uri` - Location of the file (file://, s3://, gs://, https://)
- `format` - File format/extension (pdf, markdown, mp4, jpg, txt, json, csv)
- `mime_type` - MIME type (application/pdf, text/markdown, video/mp4)
- `hash` - Content hash for verification (algorithm:hash, e.g., sha256:abc123...)
- `size_bytes` - File size in bytes
- `encoding` - Character encoding for text files (utf-8, ascii)
- `platform` - Platform for links (youtube, github, arxiv, gdrive)
- `accessible` - Whether the file/link is currently accessible
- `last_checked` - When the file/link was last verified

#### attribution_v1
**Purpose:** Track content sources, collaborators, and licensing

**Fields:**
- `$schema` - Schema version identifier (always "attribution_v1")
- `authors` - List of authors/creators (array of strings)
- `organization` - Organization/institution that produced the content (e.g., "Google Brain", "OpenAI", "NVIDIA")
- `platform` - Platform where content was published (e.g., "youtube", "arxiv", "github")
- `channel` - Specific channel/account name on the platform
- `original_source` - Original URL where content was published
- `license` - Content license (e.g., "MIT", "CC-BY-4.0", "All Rights Reserved")
- `copyright` - Copyright notice
- `agents` - AI agents or tools used in creation (array of objects with name, role, version)
- `publication_date` - When the original content was published

#### content_metadata_v1
**Purpose:** Generic content metadata (base schema for all content types)

**Fields:**
- `$schema` - Schema version identifier (always "content_metadata_v1")
- `content_type` - What this content IS conceptually (research_paper, blog_post, educational_video, transcript, quote, concept_definition, etc.)
- `media_type` - Broad media category (text, video, audio, image, data, code)
- `language` - Primary language (ISO 639-1 code, e.g., "en", "es")
- `tags` - Freeform tags for categorization (array of strings)
- `subject_area` - Subject areas or domains (array of strings, e.g., ["AI/ML", "NLP"])
- `summary` - Brief summary or abstract
- `word_count` - Word count for text content
- `reading_time_minutes` - Estimated reading time in minutes
- `duration_seconds` - Duration in seconds for video/audio
- `quality_score` - Quality/relevance score (0.0-1.0)

#### blog_post_v1 
**Purpose:** Blog-specific content metadata

**Fields:**
- `target_audience` - Intended reader personal
- `word_count` - Content length
- `reading_time` - Estimated minutes to read
- `seo_title` - Search-optimized title

#### research_v1
**Purpose:** Research quality and methodology metadata

**Fields:**
- `research_depth` - Quality score (0.0-10.0)
- `source_count` - Number of references
- `methodology` - Research approach used
- `confidence_level` - Reliability assessment

---

### Edge Predicate (Enum)
Valid values for the `predicate` attribute on Edge entities. These define the semantic type of relationship between two entities.

#### `documents`
**Definition:** An entity explains, covers, or provides detailed information about another entity.

**Usage:** `entity → entity`
**Example:** Blog post entity documents knowledge-ops concept entity

#### `derived_from`
**Definition:** Content that was created based on or transformed from another piece of content.

**Usage:** `entity → entity`
**Example:** Video content entity derived from research paper entity

#### `depends_on`
**Definition:** An entity that requires another for its definition or functionality.

**Usage:** `entity → entity`
**Example:** RAG implementation entity depends on vector database concept entity

#### `cites`
**Definition:** Formal reference to external source material for support or attribution.

**Usage:** `entity → entity`
**Example:** Blog post entity cites research paper entity

#### `uses`
**Definition:** Practical utilization of a tool, framework, or concept in implementation.

**Usage:** `entity → entity`
**Example:** Project entity uses vector database tool entity

#### `implements`
**Definition:** Concrete realization or embodiment of an abstract concept.

**Usage:** `entity → entity`
**Example:** Pinecone tool entity implements vector database concept entity

**Usage:** `entity → entity`
**Example:** Project Ike entity curates Pinecone entity as recommended tool

**Note:** The set of predicates can evolve over time to include additional relationship types such as: `supersedes` (newer content replaces older content), `refutes` (content disagrees with or contradicts other content), `extends` (content builds upon other content), `summarizes` (condensed version of other content), `translates` (same content in different language/format)

---

### Surface Direction (Enum)
Valid values for the `direction` attribute on Surface. Defines the data flow direction for the surface.

#### `publish`
**Definition:** Content is pushed to this surface (we publish content here).
**Examples:** Your WordPress blog, your YouTube channel, your Medium publication

#### `ingest`
**Definition:** Content is pulled from this surface (we consume/import content from here).
**Examples:** External RSS feeds, third-party APIs you monitor, competitor blogs

#### `bidirectional`
**Definition:** Content flows both ways (we both publish to and ingest from this surface).
**Examples:** GitHub repos (you push code, you also track issues), collaborative platforms

---

### Delivery Role (Enum)
Valid values for the `role` attribute on Delivery. Defines whether this is the original publication or a syndication.

#### `original`
**Definition:** The first/primary publication of this entity. At most one delivery per entity can have this role.
**Examples:** Original blog post on your WordPress site, first YouTube upload

#### `syndication`
**Definition:** Republication or cross-posting of content that was originally published elsewhere.
**Examples:** Cross-posting blog to Medium, sharing YouTube video on LinkedIn

---

### Delivery Status (Enum)
Valid values for the `status` attribute on Delivery. Tracks the publication lifecycle.

#### `planned`
**Definition:** Delivery is scheduled or intended but not yet queued for publication.

#### `queued`
**Definition:** Delivery is queued and waiting to be processed/published.

#### `published`
**Definition:** Content has been successfully published to the surface.

#### `failed`
**Definition:** Delivery attempt failed. Check `error_message` for details.

#### `removed`
**Definition:** Previously published content has been removed or unpublished.

---

## Naming Conventions

### Item IDs
**Format:** `kebab-case` with descriptive context 
**Examples:** `blog-post-ai-adoption-2024`, `research-vector-db-comparison`

### Predicate Names
**Format:** `snake_case` verbs or relationships 
**Examples:** `derived_from`, `depends_on`, `documents`

---

## Business Rules

### Single Aggregate Root
- **Entity** is the only true entity - all business logic flows through entities


### Approval and Delivery Constraints
- Private entities cannot be delivered to public surfaces
- Entities with `approval_status=pending` should not have delivery records (not yet approved for distribution)
- Entities with `approval_status=rejected` should not have delivery records (not approved for use)
- Approved entities should not have breaking changes without versioning

### Relationship Integrity 
- Edge relationships must reference valid entities
- Circular dependencies should be flagged for review
- Missing relationships should be flagged for potential data quality issues
- Relationship strength should reflect actual importance

---

## Evolution Guidelines

### Adding New Terms
1. Propose definition in PR with usage examples
2. Ensure no conflicts with existing terms
3. Update this document with clear boundaries
4. Add validation rules if applicable

### Changing Definitions
1. Mark as MAJOR schema version change
2. Provide migration path for existing data
3. Update all dependent documentation
4. Communicate changes to affected systems

### Deprecating Terms
1. Mark as deprecated with replacement guidance
2. Support old term for one minor version cycle
3. Remove in next major version with migration

---

**Document Status:** Active | **Next Review:** 2024-09-28 
**Maintainer:** Project Ike Schema Team 
**Change Process:** All updates require schema governance review