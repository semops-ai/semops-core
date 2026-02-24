# Project Ike Ubiquitous Language

> Canonical definitions of terms used throughout Project Ike schema and systems.
> **Version:** 6.0.0 | **Last Updated:** 2025-12-06

---

## Overview

This document establishes the precise meaning of terms used across Project Ike to ensure consistent understanding between developers, documentation, and systems. This is the foundation of our ubiquitous language in Domain-Driven Design (DDD) and semantic operations.

**How to Use This Document:**
- **Navigate by entity** - Jump directly to [Concept](#concept-aggregate-root), [Brand](#brand-crmpim-actor), [Product](#product-pim), [Brand Relationship](#brand-relationship-crm), [Classification](#classification-semantic-coherence-audit), [Entity](#entity-dam-layer), [Edge](#edge), [Surface](#surface), or [Delivery](#delivery)
- **Each entity section is self-contained** - Definition, attributes, enums, value objects (with full schemas), and W3C standards all in one place
- **For patterns and workflows** - See [Domain Patterns](../docs/domain-patterns/) for how entities combine in real workflows
- **For detailed examples** - See Appendix B for attribute combination patterns
- **For design philosophy** - See [SYSTEM_CONTEXT.md](../docs/SYSTEM_CONTEXT.md) for why Concept is the aggregate root

---

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

**W3C Standards Foundation:**
- **[SKOS](https://www.w3.org/TR/skos-reference/)** (Simple Knowledge Organization System) - Used in `content_metadata` for semantic content organization
- **[PROV-O](https://www.w3.org/TR/prov-o/)** (Provenance Ontology) - Used in Edge predicates for provenance relationships

See [SKOS_PROVO_MAPPING.md](../docs/SKOS_PROVO_MAPPING.md) for visual architecture diagram.

**Unique Innovations:**

1. **Provenance-First Design (1P/2P/3P)** - Differentiates owned content from referenced content
2. **Unified Catalog (Owned + Referenced)** - Single system for both your content AND external references, with citations and sources as first-class entities
3. **Dual-Status Model** - Approval Status (is it ready?) vs. Delivery Status (where is it live?). Needed because the Unified Catalog includes 3P content that's "approved for internal use" but never "delivered", and 1P content that can be "approved" but not yet "published"
4. **Derivative Work Lineage** - Explicit `derived_from` edges for transformations, enabling multi-hop derivation chains
5. **Graph-Native Relationships** - Rich semantic predicates beyond simple parent/child, enabling bidirectional querying

**See [Domain Patterns](../docs/domain-patterns/)** for comprehensive documentation of these patterns and how attributes combine to represent real-world publishing workflows.

In the [Ike Framework](https://github.com/timjmitchell/project-ike/tree/main/FRAMEWORK), this is tied to [Global Architecture](https://github.com/timjmitchell/project-ike/blob/main/docs/GLOBAL_ARCHITECTURE/GLOBAL_ARCHITECTURE.md).

---

## Concept (Aggregate Root)

**Definition:** A stable semantic unit representing durable identity, ideas, principles, or intellectual property. Concepts are the aggregate root of the system - they persist even when all content artifacts referencing them are deleted.

**W3C SKOS Foundation:**

Concepts are based on [W3C SKOS](https://www.w3.org/TR/skos-reference/) (Simple Knowledge Organization System):
- `preferred_label` ← `skos:prefLabel`
- `alt_labels` ← `skos:altLabel`
- `definition` ← `skos:definition`

**Examples:** `semantic-coherence`, `bounded-context`, `aggregate-root`, `rtfm-principle`

**Characteristics:**
- Represents "what you know and think" not "what you've made"
- Has identity independent of any artifact (blog post, video, doc)
- Connected via SKOS relationships (broader, narrower, related)
- Can be referenced by many entities (artifacts) simultaneously
- Governed through approval workflow (pending → approved → rejected)
- Entities reference concepts but concepts can exist without entities

**Why Concept is Root:**

See [SYSTEM_CONTEXT.md](../docs/SYSTEM_CONTEXT.md) for full rationale. The key insight: a blog post about "semantic coherence" is ephemeral (can be rewritten, deleted, reformatted). The concept "semantic coherence" is stable (core IP, core identity). Multiple assets can reference the same concept. The concept survives even if all assets are deleted.

### Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `id` | Identity (String) | Unique identifier (kebab-case) | `"semantic-coherence"` |
| `preferred_label` | Primitive (String) | SKOS prefLabel - canonical name | `"Semantic Coherence"` |
| `definition` | Primitive (String) | SKOS definition - authoritative meaning | `"A state of stable, shared semantic alignment..."` |
| `alt_labels` | Array (String[]) | SKOS altLabel - synonyms, abbreviations | `["coherence", "semantic alignment"]` |
| `provenance` | Enum | Whose semantic structure is this? | `"1p"`, `"2p"`, `"3p"` |
| `approval_status` | Enum | Governance state | `"pending"`, `"approved"`, `"rejected"` |
| `attribution` | Value Object | Dublin Core: creator, rights, etc. | See [Attribution](#attribution-value-object) |
| `metadata` | Value Object | Agentic-decorated fields | `{"subject_area": [...], "quality_score": 0.9}` |
| `created_at` | Timestamp | When concept was created | `2024-11-07T10:30:00Z` |
| `updated_at` | Timestamp | When last modified | `2024-11-15T14:22:00Z` |
| `approved_at` | Timestamp (Optional) | When approved | `2024-11-10T09:00:00Z` or `null` |
| `embedding` | Vector(1536) | OpenAI embedding for semantic similarity | `[0.023, -0.041, ...]` |

### Embedding (Semantic Similarity)

The `embedding` column stores a 1536-dimensional vector generated by OpenAI's `text-embedding-3-small` model. Embeddings enable:

- **Semantic similarity search** - Find concepts semantically similar to a query
- **Duplicate detection** - Identify near-duplicate concepts (similarity > 0.95)
- **Coherence scoring** - Measure how well a concept relates to its neighbors
- **Orphan detection** - Find concepts far from the approved graph

**Generation:** Embedding is computed from `"{preferred_label}: {definition}"` text.

**Index:** HNSW index for fast approximate nearest neighbor search:
```sql
CREATE INDEX idx_concept_embedding ON concept
USING hnsw (embedding vector_cosine_ops);
```

**Similarity Query:**
```sql
-- Find 5 most similar concepts
SELECT id, preferred_label,
 1 - (embedding <=> query_embedding) as similarity
FROM concept
WHERE embedding IS NOT NULL
ORDER BY embedding <=> query_embedding
LIMIT 5;
```

### Enums Used by Concept

**ConceptProvenance** - Whose semantic structure is this?

- `1p` (first party) - "Operates in my system" - an incorporated semantic structure (may be synthesis from 3p sources)
- `2p` (second party) - Partnership/collaborative - jointly developed with external party
- `3p` (third party) - External reference - industry standard or external IP not yet incorporated

**Key Insight:** `1p` does NOT mean "I invented this" - it means "this semantic structure now operates in my system." A synthesis from 3p sources can become a 1p concept if it's useful and incorporated. The point is that "mine" simply means it's a semantic structure that now operates in your system.

**The Provenance Lifecycle:**
```
3p (external reference)
 ↓ synthesis/incorporation
1p (operates in my system)
 ↓ partnership
2p (collaborative evolution)
```

**Key Distinction - Provenance vs Attribution:**
- **Concept provenance (1p/2p/3p):** Whose semantic structure is this?
- **Entity attribution (Dublin Core):** Who made this specific artifact?

A transcript you create from a 3p YouTube video: the **entity** has `attribution.creator = ["You"]`, but the **concept** the video explains might be `provenance = "3p"`. If you synthesize insights into your own framework, that becomes a **new 1p concept**.

**ApprovalStatus** - Governance state

- `pending` - New concept, not yet reviewed
- `approved` - Incorporated into the stable concept graph
- `rejected` - Not useful, will not be incorporated

### Concept Edge (SKOS Relations)

Concepts are connected via SKOS semantic relations:

| Predicate | SKOS Mapping | Meaning | Example |
|-----------|--------------|---------|---------|
| `broader` | `skos:broader` | src is more specific than dst | `semantic-drift` → broader → `semantic-coherence` |
| `narrower` | `skos:narrower` | src is more general than dst | `semantic-coherence` → narrower → `semantic-drift` |
| `related` | `skos:related` | Associative, non-hierarchical | `semantic-coherence` → related → `bounded-context` |

### Examples

**1P Concept (Operates in My System):**
```json
{
 "id": "semantic-coherence",
 "preferred_label": "Semantic Coherence",
 "definition": "A state of stable, shared semantic alignment between agents (human + machine) that enables optimal data-driven decision making including with AI.",
 "alt_labels": ["coherence", "semantic alignment"],
 "provenance": "1p",
 "approval_status": "approved",
 "attribution": {
 "$schema": "attribution_v2",
 "creator": ["Tim Mitchell"],
 "rights": "CC-BY-4.0"
 },
 "metadata": {
 "subject_area": ["Knowledge Management", "AI/ML"],
 "quality_score": 0.9
 }
}
```

**3P Concept (External Reference, Not Yet Incorporated):**
```json
{
 "id": "bounded-context",
 "preferred_label": "Bounded Context",
 "definition": "A boundary within which a particular domain model is defined and applicable, with a ubiquitous language that is internally consistent.",
 "alt_labels": ["BC"],
 "provenance": "3p",
 "approval_status": "approved",
 "attribution": {
 "$schema": "attribution_v2",
 "creator": ["Eric Evans"],
 "source_reference": "Domain-Driven Design (2003)"
 },
 "metadata": {
 "subject_area": ["Domain-Driven Design"]
 }
}
```

**1P Concept from 3P Synthesis:**
```json
{
 "id": "semantic-operations",
 "preferred_label": "Semantic Operations",
 "definition": "A methodology synthesizing DIKW, DDD, and W3C semantic standards to achieve semantic coherence at runtime.",
 "alt_labels": ["SemOps"],
 "provenance": "1p",
 "approval_status": "approved",
 "attribution": {
 "$schema": "attribution_v2",
 "creator": ["Tim Mitchell"],
 "rights": "CC-BY-4.0"
 },
 "metadata": {
 "subject_area": ["Knowledge Management", "AI/ML"],
 "quality_score": 0.95,
 "synthesis_sources": ["dikw-model", "domain-driven-design", "skos", "prov-o"]
 }
}
```

### Related Entities

- **Concept Edge** - SKOS relationships to other concepts (broader, narrower, related)
- **Brand** - Commercial identity marks that represent this concept
- **Entity** - Content artifacts that reference this concept
- **Entity-Concept** - Junction table for many-to-many concept references

---

## Brand (CRM/PIM Actor)

**Definition:** A unified actor table representing people, organizations, and commercial brands. Based on Schema.org types ([Person](https://schema.org/Person), [Organization](https://schema.org/Organization), [Brand](https://schema.org/Brand)). Simulates company structure where actors own brands, brands offer products, and actors have relationships with each other.

**Why Brand is a Unified Actor Table:**

Project Ike simulates a complete company structure. Rather than separate Person/Organization/Brand tables, we use a single "Brand" table with a `brand_type` discriminator:
- **person** - Individual people (you, LinkedIn connections, contacts)
- **organization** - Companies, institutions (external orgs, employers)
- **brand** - Commercial identities (SemOps, product lines)

This enables flexible relationships: Tim Mitchell (person) → owns → Semantic Operations (brand) → offers → SemOps Consulting (product).

**Schema.org Foundation:**

- `name` ← `schema:name`
- `alt_names` ← `schema:alternateName`
- Person: `given_name` ← `schema:givenName`, `family_name` ← `schema:familyName`
- Organization: `legal_name` ← `schema:legalName`
- Brand: `slogan` ← `schema:slogan`, `logo_uri` ← `schema:logo`, `url` ← `schema:url`

**Examples:**
- `tim-mitchell` (person) - the root owner
- `semantic-operations` (brand) - commercial identity
- `acme-corp` (organization) - external company
- `john-doe` (person) - LinkedIn connection

**Characteristics:**
- Unified actor model for CRM + PIM
- Type-specific fields (person: given_name/family_name, org: legal_name, brand: slogan/logo)
- Contact info for identity resolution (emails, external_ids)
- Can be connected to a 1p concept (what this brand commercializes)

### Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `id` | Identity (String) | Unique identifier (kebab-case) | `"tim-mitchell"` |
| `brand_type` | Enum | Actor type | `"person"`, `"organization"`, `"brand"` |
| `name` | Primitive (String) | Display name | `"Tim Mitchell"` |
| `alt_names` | Array (String[]) | Alternative names | `["Timothy Mitchell"]` |
| `slogan` | Primitive (String) | Brand tagline (brands only) | `"Coherence at Runtime"` |
| `logo_uri` | Primitive (String) | Logo asset URI (brands only) | `"file:///brand/semops-logo.svg"` |
| `url` | Primitive (String) | Primary URL | `"https://semanticoperations.ai"` |
| `owned_domains` | Array (String[]) | Domains owned | `["semops.ai"]` |
| `given_name` | Primitive (String) | First name (persons only) | `"Tim"` |
| `family_name` | Primitive (String) | Last name (persons only) | `"Mitchell"` |
| `legal_name` | Primitive (String) | Legal name (orgs only) | `"Acme Corporation"` |
| `emails` | Array (String[]) | Contact emails (CRM) | `["tim@example.com"]` |
| `external_ids` | Value Object | External identifiers | `{"linkedin": "...", "github": "..."}` |
| `concept_id` | Foreign Key (String) | 1p concept this commercializes | `"semantic-operations"` |
| `metadata` | Value Object | Additional metadata | `{}` |
| `created_at` | Timestamp | When created | `2024-11-07T10:30:00Z` |
| `updated_at` | Timestamp | When last modified | `2024-11-15T14:22:00Z` |

### Enums

**BrandType** - Actor type
- `person` - Individual person (Schema.org Person)
- `organization` - Company or institution (Schema.org Organization)
- `brand` - Commercial identity (Schema.org Brand)

### Examples

**Person (Root Owner):**
```json
{
 "id": "tim-mitchell",
 "brand_type": "person",
 "name": "Tim Mitchell",
 "given_name": "Tim",
 "family_name": "Mitchell",
 "emails": ["tim@semops.ai"],
 "external_ids": {"linkedin": "timjmitchell", "github": "timjmitchell"},
 "url": "https://timjmitchell.com"
}
```

**Brand (Commercial Identity):**
```json
{
 "id": "semantic-operations",
 "brand_type": "brand",
 "name": "Semantic Operations",
 "alt_names": ["SemOps", "Semantic Ops"],
 "slogan": "Coherence at Runtime",
 "url": "https://semanticoperations.ai",
 "owned_domains": ["semops.ai", "semanticoperations.ai", "semantic-ops.com"],
 "concept_id": "semantic-operations"
}
```

**Organization (External Company):**
```json
{
 "id": "acme-corp",
 "brand_type": "organization",
 "name": "Acme Corporation",
 "legal_name": "Acme Corporation Inc.",
 "url": "https://acme.com"
}
```

### Related Entities

- **Concept** - The 1p concept this brand commercializes (optional)
- **Product** - Products/services offered by this brand
- **Brand Relationship** - Relationships to other brands/products

---

## Product (PIM)

**Definition:** A product or service offered by a brand. Based on [Schema.org Product](https://schema.org/Product). Represents what you sell - consulting services, white papers, courses, etc.

**Examples:**
- `semops-consulting` - consulting service
- `semops-white-paper` - lead magnet / portfolio piece

**Characteristics:**
- Belongs to a brand (who offers it)
- Can connect to a 1p concept (what methodology it packages)
- Pricing stored in flexible JSONB (can promote to offers table later)

### Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `id` | Identity (String) | Unique identifier (kebab-case) | `"semops-consulting"` |
| `name` | Primitive (String) | Product name | `"SemOps Consulting"` |
| `sku` | Primitive (String) | Stock keeping unit | `"SEMOPS-CONSULT-001"` |
| `description` | Primitive (String) | Product description | `"Strategic consulting for semantic coherence..."` |
| `brand_id` | Foreign Key (String) | Brand that offers this | `"semantic-operations"` |
| `concept_id` | Foreign Key (String) | 1p concept this packages | `"semantic-operations"` |
| `pricing` | Value Object | Pricing info | `{"price": 500, "currency": "USD", "unit": "hour"}` |
| `metadata` | Value Object | Additional metadata | `{}` |
| `created_at` | Timestamp | When created | `2024-11-07T10:30:00Z` |
| `updated_at` | Timestamp | When last modified | `2024-11-15T14:22:00Z` |

### Example

**Consulting Service:**
```json
{
 "id": "semops-consulting",
 "name": "SemOps Consulting",
 "description": "Strategic consulting for achieving semantic coherence in AI-driven organizations.",
 "brand_id": "semantic-operations",
 "concept_id": "semantic-operations",
 "pricing": {
 "price": 500,
 "currency": "USD",
 "unit": "hour",
 "availability": "available"
 }
}
```
**Lead Magnet:**
```json
{
 "id": "semops-white-paper",
 "name": "Semantic Operations White Paper",
 "description": "Introduction to achieving semantic coherence at runtime.",
 "brand_id": "semantic-operations",
 "concept_id": "semantic-operations",
 "pricing": {
 "price": 0,
 "currency": "USD",
 "availability": "free"
 }
}
```

### Related Entities

- **Brand** - The brand that offers this product
- **Concept** - The 1p concept this product packages

---

## Brand Relationship (CRM)

**Definition:** Flexible relationships between actors (brands) and products. Captures CRM-style connections: who knows whom, who owns what, who's interested in what product.

**Examples:**
- `tim-mitchell → owns → semantic-operations`
- `tim-mitchell → knows → john-doe`
- `john-doe → works_for → acme-corp`
- `john-doe → interested_in → semops-consulting`
- `john-doe → wants_to_hire → tim-mitchell`

**Characteristics:**
- Source is always a brand (person/org/brand)
- Destination can be another brand OR a product
- Predicate defines the relationship type (flexible, not enumerated)
- Metadata captures context (source: "linkedin", met_at: "conference")

### Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `src_id` | Foreign Key (String) | Source brand | `"tim-mitchell"` |
| `dst_type` | Enum | Destination type | `"brand"`, `"product"` |
| `dst_id` | Primitive (String) | Destination ID | `"semantic-operations"` |
| `predicate` | Primitive (String) | Relationship type | `"owns"` |
| `metadata` | Value Object | Context | `{"source": "linkedin"}` |
| `created_at` | Timestamp | When created | `2024-11-07T10:30:00Z` |

### Common Predicates

| Predicate | Meaning | Example |
|-----------|---------|---------|
| `owns` | Ownership | Person → Brand |
| `knows` | Knows (peer relationship) | Person → Person |
| `works_for` | Employment | Person → Organization |
| `represents` | Represents commercially | Person → Brand |
| `interested_in` | Interest in product/brand | Person → Product |
| `wants_to_hire` | Wants to hire | Person → Person |
| `customer_of` | Customer relationship | Person/Org → Brand |
| `partner_with` | Partnership | Brand → Brand |

### Example

**Company Structure:**
```json
[
 {"src_id": "tim-mitchell", "dst_type": "brand", "dst_id": "semantic-operations", "predicate": "owns"},
 {"src_id": "tim-mitchell", "dst_type": "brand", "dst_id": "john-doe", "predicate": "knows",
 "metadata": {"source": "linkedin", "met_at": "DDD Europe 2024"}}
]
```

**Sales Pipeline:**
```json
[
 {"src_id": "john-doe", "dst_type": "product", "dst_id": "semops-consulting", "predicate": "interested_in"},
 {"src_id": "john-doe", "dst_type": "brand", "dst_id": "tim-mitchell", "predicate": "wants_to_hire"}
]
```

### Related Entities

- **Brand** - Source and destination actors
- **Product** - Destination for product-related relationships

---

## Classification (Semantic Coherence Audit)

**Definition:** An audit record capturing a classification attempt by an agent or classifier. Provides the audit trail for the promotion workflow - tracking how concepts and entities are evaluated over time.

**Why Separate from Metadata:**

Classification serves a different purpose than entity/concept metadata:
- **Metadata** = "What this is" (stable labels like subject_area, content_type)
- **Classification** = "How we evaluated it" (scores, rationale, classifier version)

A separate table enables:
- Full audit trail - every classification preserved, not overwritten
- Classifier version comparison - see how scores change across model versions
- Promotion workflow queries - "show all concepts scored >0.8 by classifier v2"
- Human review - rationale explains why a score was given

**Workflow:**
1. Classifier runs → writes to classification table
2. Query promotion candidates: `SELECT * FROM promotion_candidates`
3. Human/agent reviews → approves target (`approval_status = 'approved'`)
4. Optionally denormalize latest scores into target metadata for fast reads

**Examples:**
- LLM quality classifier scores a concept definition
- Rule-based validator checks entity completeness
- Embedding similarity classifier evaluates concept coherence

### Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `id` | Identity (UUID) | Unique identifier | `uuid` |
| `target_type` | Enum | What was classified | `"concept"`, `"entity"` |
| `target_id` | Primitive (String) | ID of classified item | `"semantic-coherence"` |
| `classifier_id` | Primitive (String) | Classifier identifier | `"llm-quality-v1"` |
| `classifier_version` | Primitive (String) | Semantic version | `"1.2.0"` |
| `scores` | Value Object | Numeric scores | `{"quality": 0.85, "promotion_ready": true}` |
| `labels` | Value Object | Categorical labels | `{"subject_area": ["AI/ML"]}` |
| `confidence` | Primitive (Decimal) | Overall confidence 0.0-1.0 | `0.92` |
| `rationale` | Primitive (String) | Human-readable explanation | `"Strong definition, clear scope..."` |
| `input_hash` | Primitive (String) | Hash for reproducibility | `"sha256:abc..."` |
| `created_at` | Timestamp | When classified | `2024-11-07T10:30:00Z` |

### Common Score Fields

| Score | Type | Description |
|-------|------|-------------|
| `quality` | Decimal 0.0-1.0 | Overall quality score |
| `relevance` | Decimal 0.0-1.0 | Relevance to concept graph |
| `completeness` | Decimal 0.0-1.0 | How complete is the definition/content |
| `promotion_ready` | Boolean | Classifier recommends promotion |

### Example

**LLM Quality Classification:**
```json
{
 "id": "550e8400-e29b-41d4-a716-446655440000",
 "target_type": "concept",
 "target_id": "semantic-coherence",
 "classifier_id": "llm-quality-v1",
 "classifier_version": "1.2.0",
 "scores": {
 "quality": 0.92,
 "completeness": 0.88,
 "clarity": 0.95,
 "promotion_ready": true
 },
 "labels": {
 "subject_area": ["Semantic Operations", "Knowledge Management"]
 },
 "confidence": 0.89,
 "rationale": "Strong definition with clear scope. Well-differentiated from related concepts. Minor improvement: could add more concrete examples.",
 "created_at": "2024-11-07T10:30:00Z"
}
```

### Related Entities

- **Concept** - Target for concept classification
- **Entity** - Target for entity classification

### Views

**promotion_candidates** - Pending items with classifier recommendation for promotion. Shows latest classification per target where `promotion_ready = true`.

### Classifier Infrastructure

The `scripts/classifiers/` module provides a tiered classification pipeline:

| Classifier | Purpose | Cost | Speed |
|------------|---------|------|-------|
| **RuleBasedClassifier** | Deterministic validation (completeness, format, relationships) | Free | Fast |
| **EmbeddingClassifier** | Semantic similarity (coherence, duplicates, orphans) via pgvector | Low | Fast |
| **LLMClassifier** | Quality scoring with rationale using Claude | Medium | Slow |
| **GraphClassifier** | Structural analysis (PageRank, community, cycles) via Neo4j GDS | Low | Medium |

**Usage Pattern:**
```python
from scripts.classifiers import RuleBasedClassifier, EmbeddingClassifier

# Run cheap classifiers first, expensive ones on edge cases
rule_classifier = RuleBasedClassifier
rule_classifier.classify_pending_concepts

embedding_classifier = EmbeddingClassifier
embedding_classifier.classify_pending_concepts
```

**Classifier Scores:**

Each classifier writes to the `classification` table with classifier-specific scores:

- **RuleBasedClassifier:** `completeness`, `format_valid`, `has_relationships`, `promotion_ready`
- **EmbeddingClassifier:** `coherence`, `duplicate_similarity`, `nearest_approved_similarity`, `promotion_ready`
- **LLMClassifier:** `definition_quality`, `naming_quality`, `scope_appropriateness`, `semantic_fit`, `promotion_ready`
- **GraphClassifier:** `degree`, `pagerank`, `is_orphan`, `has_hierarchy_cycle`, `promotion_ready`

---

## Entity (DAM Layer)

**Definition:** A concrete content artifact in the DAM (Digital Asset Management) supporting domain. Entities are the ephemeral packaging of durable concepts - they can be created, modified, and deleted while the underlying concepts persist.

**Relationship to Concepts:** Entities must reference at least one concept via `primary_concept_id` to be part of the stable core. Entities without concept connections are **orphans** - temporary content at the flexible edge awaiting incorporation or rejection.

**Examples:** Blog posts, research papers, code repositories, images, datasets, notes, quotes, YouTube videos, concept definitions, work deliverables, etc.

**Characteristics:**
- References concepts via `primary_concept_id` (required for stable core, NULL = orphan)
- Can possess the content (file) or reference it externally (link)
- Uses Dublin Core attribution for ownership/licensing (standard DAM pattern)
- Tracks approval state (pending/approved/rejected)
- Can be connected to other entities via Edge relationships
- Can be delivered to multiple Surfaces via Delivery records

**Why No Provenance Column:**

Entity follows standard DAM patterns where provenance is implicit:
- `attribution.creator` identifies who made the artifact
- `attribution.rights` indicates licensing/ownership
- Surface ownership (via delivery) shows if it's your platform
- Edges (`cites`, `derived_from`) track external references

Concept provenance (1p/2p/3p) is where "whose idea" is explicitly tracked.

### Attributes

| Attribute | Type | Description | Example |
| ----------------- | -------------------- | ---------------------------------------------------- | ---------------------------------------------------- |
| `id` | Identity (String) | Unique identifier (kebab-case) | `"blog-post-knowledge-ops-2024"` |
| `asset_type` | Enum | Do you possess it (`file`) or reference it (`link`)? | `"file"` or `"link"` |
| `title` | Primitive (String) | Human-readable title | `"Introduction to Semantic Operations"` |
| `version` | Primitive (String) | Version number (semantic versioning) | `"1.0"`, `"2.0"` |
| `visibility` | Enum | Access level | `"public"`, `"private"` |
| `approval_status` | Enum | Is it ready for use? | `"pending"`, `"approved"`, `"rejected"` |
| `primary_concept_id` | Foreign Key (String) | Main concept this entity documents (NULL = orphan) | `"semantic-coherence"` or `null` |
| `filespec` | Value Object | Physical location and file properties | See [FileSpec](#filespec-value-object) |
| `attribution` | Value Object | Dublin Core: creator, rights (standard DAM) | See [Attribution](#attribution-value-object) |
| `metadata` | Value Object | Content metadata (content_type, media_type, etc.) | See [ContentMetadata](#contentmetadata-value-object) |
| `created_at` | Timestamp | When entity was created | `2024-11-07T10:30:00Z` |
| `updated_at` | Timestamp | When last modified | `2024-11-15T14:22:00Z` |
| `approved_at` | Timestamp (Optional) | When approved | `2024-11-10T09:00:00Z` or `null` |

### Enums Used by Entity

**AssetType** - Physical nature of the asset

- `file` - You possess the actual content (PDF you own, markdown file you wrote, image you created)
- `link` - External reference to content you don't possess (YouTube URL, arXiv paper link, external blog)

**ApprovalStatus** - Asset readiness state (DAM industry pattern)

- `pending` - Incomplete, unprocessed, or awaiting approval (work in progress)
- `approved` - Complete and ready for use (finalized, can be delivered)
- `rejected` - Not approved for catalog inclusion

**Visibility** - Access level

- `public` - Intended for open access and public sharing
- `private` - Restricted to internal/personal use

### Value Objects

Value Objects are composite structures with multiple fields, no identity of their own, and compared by values. They are immutable - to change them, replace the entire object. All JSONB fields follow: `{"$schema": "schema_name_vN", ...fields}`

#### FileSpec Value Object

**Schema:** `filespec_v1` | **Question answered:** WHERE is the content?

**Purpose:** Physical location and file properties

**Fields:**
- `$schema` (required) - Always `"filespec_v1"`
- `uri` (required) - Location (file://, s3://, gs://, https://)
- `format` - File extension (pdf, markdown, mp4, jpg, txt)
- `mime_type` - MIME type (application/pdf, text/markdown)
- `hash` - Content hash (algorithm:hash, e.g., sha256:abc123...)
- `size_bytes` - File size
- `encoding` - Character encoding (utf-8, ascii)
- `platform` - For links (youtube, github, arxiv)
- `accessible` - Currently accessible? (boolean)
- `last_checked` - When verified (timestamp)

**Example:**
```json
{
 "$schema": "filespec_v1",
 "uri": "file:///content/blog/semantic-ops.md",
 "format": "markdown",
 "hash": "sha256:abc123...",
 "size_bytes": 15420,
 "encoding": "utf-8"
}
```

#### Attribution Value Object

**Schema:** `attribution_v2` | **Question answered:** WHO created it? + What TYPE of knowledge claim?

**Purpose:** Track content sources, collaborators, licensing, and epistemic classification. Dublin Core-aligned with custom extensions for AI attribution and knowledge claim tracking.

**Dublin Core Mappings:**
- `creator` ← `dc:creator`
- `contributor` ← `dc:contributor`
- `publisher` ← `dc:publisher`
- `rights` ← `dc:rights`
- `original_source` ← `dc:source`
- `publication_date` ← `dc:date`

**Fields:**
- `$schema` (required) - Always `"attribution_v2"`
- `creator` - Primary creators with IP ownership (array of strings)
- `contributor` - Secondary contributors (array of strings)
- `publisher` - Entity responsible for making the resource available (e.g., conference channel, journal, platform account)
- `rights` - License or rights statement (MIT, CC-BY-4.0, © 2024 John Doe, etc.)
- `organization` - Institutional affiliation of the creator (e.g., speaker's employer, author's university) - distinct from publisher
- `platform` - Publication platform (youtube, arxiv, github)
- `channel` - Specific channel/account name
- `original_source` - Original URL where content was published
- `source_reference` - Bibliographic reference for 3P content without formal authorship (custom extension)
- `agents` - AI tools used (array of {name, role, version}) - custom extension for AI attribution
- `publication_date` - When originally published
- `epistemic_status` - Type of knowledge claim (custom extension for epistemic tracking):
 - `fact` - Empirically verifiable, widely accepted (e.g., "OLTP handles transactions")
 - `synthesis` - Integration of established facts/theories (e.g., "DDD solves AI transformation problems")
 - `hypothesis` - Testable proposed explanation (e.g., "We hypothesize that semantic drift causes...")

**Key Distinctions:**
- `attribution.creator` = who made THIS artifact. Concept provenance (`1p`/`2p`/`3p`) = whose semantic structure.
- `publisher` = who made the resource available (conference, journal, channel). `organization` = creator's institutional affiliation (employer, university).

**Example - Conference talk:** A DDD Europe 2010 video where the speaker works at ThoughtWorks:
- `publisher`: "DDD Europe" (the conference channel publishing the video)
- `organization`: "ThoughtWorks" (the speaker's employer)
- `creator`: ["Eric Evans"] (the speaker)

**Example (Your content with AI assistance):**
```json
{
 "$schema": "attribution_v2",
 "creator": ["Tim Mitchell"],
 "rights": "CC-BY-4.0",
 "epistemic_status": "synthesis",
 "agents": [
 {
 "name": "Claude",
 "role": "draft_assistance",
 "version": "claude-3-opus"
 }
 ]
}
```

**Example (External reference):**
```json
{
 "$schema": "attribution_v2",
 "creator": ["Russell Ackoff"],
 "publisher": "Management Science",
 "rights": "All Rights Reserved",
 "original_source": "https://doi.org/10.1287/mnsc.35.2.219",
 "source_reference": "Ackoff (1989)",
 "publication_date": "1989-02-01",
 "epistemic_status": "fact"
}
```

#### ContentMetadata Value Object

**Schema:** `content_metadata_v1` | **Question answered:** WHAT kind of content is this?

**Purpose:** Content characteristics and classification (agentic-decorated)

**Note:** SKOS semantic fields (preferred_label, definition, broader/narrower/related) belong on **Concept**, not Entity. Entity metadata tracks content characteristics, not semantic structure.

**Fields:**
- `$schema` (required) - Always `"content_metadata_v1"`
- `content_type` (required) - What is this? The purpose/role of the content:
 - **Original works:** `article`, `paper`, `book`, `presentation`, `tutorial`, `guide`
 - **Derivatives:** `transcript`, `summary`, `quote`, `clip`, `translation`
 - **Reference:** `definition`, `glossary_entry`, `documentation`
 - **Intellectual constructs:** `pattern`, `framework`, `methodology`, `principle`
 - **Note:** Platform (github, youtube) is in `filespec.platform`. Format (video, text) is in `media_type`.
- `media_type` - Broad category (text, video, audio, image, data, code)
- `language` - Primary language (ISO 639-1: en, es, etc.)
- `tags` - Freeform tags (array) - classifier-assigned
- `summary` - Brief abstract
- `word_count` - For text content
- `reading_time_minutes` - Estimated reading time
- `duration_seconds` - For video/audio

**Classifier-Assigned Fields (agentic-decorated):**

These fields are populated by classification agents during semantic audit:
- `subject_area` - Domains (array: ["AI/ML", "NLP"])
- `quality_score` - Relevance/quality (0.0-1.0)
- `confidence` - Classifier confidence in assignments

**Example:**
```json
{
 "$schema": "content_metadata_v1",
 "content_type": "article",
 "media_type": "text",
 "language": "en",
 "word_count": 2500,
 "reading_time_minutes": 10,
 "summary": "An introduction to semantic operations methodology.",
 "subject_area": ["Knowledge Management", "AI/ML"],
 "quality_score": 0.85,
 "confidence": 0.92
}
```

### Related Entities

- **Edge** - Connects this entity to other entities via semantic relationships
- **Delivery** - Tracks where this entity has been published/delivered

---

## Edge

**Definition:** A typed, directional relationship between two entities. Based on W3C PROV-O (Provenance Ontology), edges capture how entities connect through provenance, derivation, and semantic relationships.

**W3C PROV-O Foundation:**

Project Ike uses [W3C PROV-O](https://www.w3.org/TR/prov-o/) (Provenance Ontology) for provenance relationships BETWEEN entities.

**PROV-O mappings to Edge predicates:**
- `prov:wasDerivedFrom` → `derived_from`
- `prov:wasQuotedFrom` → `cites`
- `prov:wasRevisionOf` → `version_of`

See [Edge Predicates](../docs/domain-patterns/edge-predicates.md) for complete predicate documentation and [SKOS_PROVO_MAPPING.md](../docs/SKOS_PROVO_MAPPING.md) for visual architecture.

**Characteristics:**
- Always directional (source → destination)
- Both source and destination must reference valid Entity instances
- Predicate defines the semantic meaning
- Strength indicates importance or confidence (0.0 to 1.0)

### Attributes

| Attribute | Type | Description | Example |
| ---------------- | -------------------- | --------------------------------- | ------------------------------------------ |
| `source_id` | Foreign Key (String) | Entity this edge originates from | `"transcript-karpathy-llms"` |
| `destination_id` | Foreign Key (String) | Entity this edge points to | `"video-karpathy-llms-youtube"` |
| `predicate` | Enum | Type of relationship | `"derived_from"` |
| `strength` | Primitive (Float) | Relationship weight (0.0-1.0) | `1.0` |
| `metadata` | Value Object (JSONB) | Additional context | `{"transformation_type": "transcription"}` |
| `created_at` | Timestamp | When relationship was established | `2024-11-15T10:00:00Z` |

### Predicates (Enum Values)

**W3C PROV-O Based:**
- `derived_from` - Created by transforming source (transcript from video, summary from paper)
 - Maps to: `prov:wasDerivedFrom` ([W3C spec](https://www.w3.org/TR/prov-o/#wasDerivedFrom))
- `cites` - Formal reference for support/attribution
 - Maps to: `prov:wasQuotedFrom` ([W3C spec](https://www.w3.org/TR/prov-o/#wasQuotedFrom))
- `version_of` - New version of existing content
 - Maps to: `prov:wasRevisionOf` ([W3C spec](https://www.w3.org/TR/prov-o/#wasRevisionOf))

**Schema.org Extensions:**
- `part_of` - Component of larger whole
 - Maps to: `schema:isPartOf` ([Schema.org spec](https://schema.org/isPartOf))
- `documents` - Explains or covers in detail
 - Maps to: `schema:about` (inverted) ([Schema.org spec](https://schema.org/about))

**Project Ike Domain Extensions:**
- `depends_on` - Requires another for definition/function
 - Inspired by: Software dependency graphs (npm, Maven)
- `related_to` - Associated without hierarchy
 - Inspired by: SKOS `skos:related` ([W3C spec](https://www.w3.org/TR/skos-reference/#semantic-relations))

**See:** [edge-predicates.md](../docs/domain-patterns/edge-predicates.md) for complete semantics, cardinality patterns, and strength guidelines.

### Examples

**Content Derivation:**
```json
{
 "source_id": "transcript-karpathy-llms",
 "destination_id": "video-karpathy-llms-youtube",
 "predicate": "derived_from",
 "strength": 1.0,
 "metadata": {
 "transformation_type": "transcription",
 "tool": "whisper-api"
 }
}
```

**Citation:**
```json
{
 "source_id": "blog-understanding-transformers",
 "destination_id": "paper-attention-is-all-you-need",
 "predicate": "cites",
 "strength": 0.9
}
```

---

## Surface

**Definition:** A publication destination or ingestion source where content is published to or pulled from. Represents channels, repositories, sites, publications, and other addressable platforms.

**Examples:** YouTube channel, GitHub repository, WordPress site, Medium publication, LinkedIn profile, internal knowledge base, vector database

**Characteristics:**
- Has a direction (publish, ingest, or bidirectional)
- May have platform-specific constraints (file size, formats, rate limits)
- Can receive multiple deliveries from different entities

### Attributes

| Attribute | Type | Description | Example |
| -------------- | -------------------- | ------------------------------- | --------------------------------------------------- |
| `id` | Identity (String) | Unique identifier (slug format) | `"wordpress-my-blog"` |
| `platform` | Enum | Platform name | `"wordpress"` |
| `surface_type` | Enum | Type of surface | `"site"` |
| `direction` | Enum | Data flow direction | `"publish"` |
| `constraints` | Value Object (JSONB) | Platform limits | `{"max_size": 10485760, "formats": ["md", "html"]}` |
| `metadata` | Value Object (JSONB) | Platform-specific data | `{"site_url": "https://myblog.com"}` |
| `created_at` | Timestamp | When surface was added | `2024-11-01T00:00:00Z` |
| `updated_at` | Timestamp | When last modified | `2024-11-15T10:00:00Z` |

### Enums Used by Surface

**Platform** - Platform name (extensible list)

Common values: `youtube`, `github`, `wordpress`, `medium`, `linkedin`, `twitter`, `instagram`, `knowledge_base`, `vector_db`, `rag_system`

**SurfaceType** - Type of surface

Values: `channel`, `repo`, `site`, `publication`, `feed`, `profile`, `database`, `knowledge_base`

**Direction** - Data flow direction

- `publish` - Content pushed to this surface (your blog, your YouTube channel)
- `ingest` - Content pulled from this surface (external RSS feeds, APIs you monitor)
- `bidirectional` - Both publish and ingest (GitHub repos, collaborative platforms)

---

## Delivery

**Definition:** A record of an Entity published to or ingested from a Surface. Tracks the publication lifecycle, platform-specific identifiers, and URLs.

**Characteristics:**
- Links one Entity to one Surface
- One entity can have multiple deliveries (original + syndications)
- At most one delivery with `role='original'` per entity
- Has independent status workflow (planned → queued → published)

### Attributes

| Attribute | Type | Description | Example |
| --------------- | ---------------------------- | ------------------------------- | ----------------------------------- |
| `id` | Identity (String) | Unique identifier | `"delivery-blog-wordpress-001"` |
| `entity_id` | Foreign Key (String) | Entity being delivered | `"blog-post-semantic-ops"` |
| `surface_id` | Foreign Key (String) | Surface receiving content | `"wordpress-my-blog"` |
| `role` | Enum | Original or syndication? | `"original"` |
| `status` | Enum | Publication lifecycle state | `"published"` |
| `url` | Primitive (String) | Where content lives | `"https://myblog.com/semantic-ops"` |
| `remote_id` | Primitive (String) | Platform-specific ID | `"12345"` (WordPress post ID) |
| `field_mapping` | Value Object (JSONB) | Entity → Platform field mapping | `{"title": "post_title", ...}` |
| `source_hash` | Primitive (String) | Hash for deduplication | `"sha256:abc123..."` |
| `published_at` | Timestamp (Optional) | When published | `2024-11-15T09:00:00Z` |
| `failed_at` | Timestamp (Optional) | When failed | `null` |
| `error_message` | Primitive (String, Optional) | Error details | `null` |
| `metadata` | Value Object (JSONB) | Delivery-specific data | `{"canonical_url": "..."}` |
| `created_at` | Timestamp | When delivery was created | `2024-11-14T10:00:00Z` |
| `updated_at` | Timestamp | When last modified | `2024-11-15T09:00:00Z` |

### Enums Used by Delivery

**DeliveryRole**

- `original` - First/primary publication (at most one per entity)
- `syndication` - Republication or cross-posting

**DeliveryStatus** - Publication lifecycle

- `planned` - Scheduled but not yet queued
- `queued` - Waiting to be published
- `published` - Successfully published
- `failed` - Publication attempt failed
- `removed` - Previously published, now removed

**Status Transitions:**
```
planned → queued → published
 ↓
 failed
 ↓
 queued (retry)

published → removed
```

---

## Naming Conventions

### Entity IDs
**Format:** `kebab-case` with descriptive context
**Examples:** `blog-post-ai-adoption-2024`, `research-vector-db-comparison`, `video-karpathy-intro-llms`

### Predicate Names
**Format:** `snake_case` verbs or relationships
**Examples:** `derived_from`, `depends_on`, `documents`, `cites`

### Surface IDs
**Format:** `{platform}-{identifier}`
**Examples:** `wordpress-my-blog`, `youtube-main-channel`, `github-project-repo`

---

## Business Rules

### Concept as Aggregate Root
- **Concept** is the primary aggregate root - the stable core (SKOS-based)
- **Entity** belongs to the DAM supporting domain - ephemeral packaging (Dublin Core)
- Entities must reference concepts to be part of the stable system
- Orphan entities (no concept reference) float at the flexible edge

### Stable Core vs Flexible Edge
- **Stable Core:** Concepts + entities with `primary_concept_id` set
- **Flexible Edge:** Orphan entities (`primary_concept_id = NULL`)
- Orphans are temporary - audit processes promote or reject them
- Promotion = assigning a concept; rejection = deletion or archival

### Flexible Edge as Emergence Zone

The flexible edge is where patterns emerge before formalization:
- Like JSONB metadata fields that get promoted to schema columns when used frequently
- Orphan entities may reveal new concepts during semantic audit
- Classifier-assigned metadata (subject_area, quality_score) follows the same pattern
- If a classifier consistently gets something wrong, that's a signal something is wrong with the model

**Agentic-Friendly Design:**
- Hard-coded schema fields are for things that "stick" (identity, governance)
- Soft metadata (JSONB) is for classifier-decorated fields
- HITL checks validate classifier outputs before promotion to stable core

### Approval and Delivery Constraints
- Private entities cannot be delivered to public surfaces
- Entities with `approval_status=pending` should not have delivery records
- Entities with `approval_status=rejected` should not have delivery records
- At most one delivery with `role='original'` per entity

### Relationship Integrity
- Edge source and destination must reference valid entities
- Circular dependencies should be flagged for review
- Relationship strength should reflect actual importance (0.0-1.0)

**See:** [constraints.md](../docs/domain-patterns/constraints.md) for complete validation rules.

---

## Appendix

### A. Attribute Type Categories

Entity attributes are classified into type categories:

**Identity**
- Purpose: Uniquely identifies an entity instance
- Example: `id: "blog-post-knowledge-ops-2024"`

**Primitive**
- Purpose: Simple, atomic values (string, number, boolean)
- Example: `title: "My Title"`, `word_count: 1500`

**Enum**
- Purpose: Constrained set of allowed values
- Example: `status: "published"` (from fixed set)

**Value Object**
- Purpose: Composite domain concept bundling related attributes
- Characteristics: Multiple fields, immutable, no identity, compared by values
- Example: `filespec: {"uri": "s3://...", "format": "pdf"}`

**Timestamp**
- Purpose: Track lifecycle events
- Example: `created_at`, `updated_at`, `published_at`

**Foreign Key**
- Purpose: Reference to another entity
- Example: `entity_id` (references Entity), `surface_id` (references Surface)

### B. Attribute Combination Patterns

How Entity attributes combine to create meaningful contexts:

**Approval Status + Visibility:**
- `approved` + `private` → Approved for internal use (RAG, knowledge base)
- `approved` + `public` → Ready for public delivery
- `pending` + `private` → Work in progress
- `pending` + `public` → **INVALID** (drafts must be private)

**Asset Type + Edge Relationships:**
- `file` → You possess the content (original or derivative)
- `link` → External reference (external URL, API endpoint)
- `file` + Edge `derived_from` → Derivative work you created from another entity
- `link` + Edge `cites` → Citation to external content

**Concept Connection:**
- `primary_concept_id` set → Part of stable core, connected to concept graph
- `primary_concept_id` NULL → Orphan at flexible edge, awaiting incorporation

**For comprehensive patterns, see:**
- [publication-patterns.md](../docs/domain-patterns/publication-patterns.md) - Workflow patterns
- [constraints.md](../docs/domain-patterns/constraints.md) - Validation rules
- [anti-patterns.md](../docs/domain-patterns/anti-patterns.md) - Invalid combinations

### C. Lifecycle States

**Entity Approval Lifecycle:**
```
pending → approved
 ↓
 rejected
```

**Delivery Status Lifecycle:**
```
planned → queued → published
 ↓
 failed → queued (retry)

published → removed
```

**See:** [lifecycles.md](../docs/domain-patterns/lifecycles.md) for state machine diagrams.

### D. Evolution Guidelines

**Adding New Terms:**
1. Propose definition in PR with usage examples
2. Ensure no conflicts with existing terms
3. Update this document with clear boundaries
4. Add validation rules if applicable

**Changing Definitions:**
1. Mark as MAJOR schema version change
2. Provide migration path for existing data
3. Update all dependent documentation
4. Communicate changes to affected systems

**Deprecating Terms:**
1. Mark as deprecated with replacement guidance
2. Support old term for one minor version cycle
3. Remove in next major version with migration

---

**Document Status:** Active | **Next Review:** 2026-01-02
**Maintainer:** Project Ike Schema Team
**Change Process:** All updates require schema governance review
