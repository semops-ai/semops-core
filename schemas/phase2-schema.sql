-- Project Ike Phase 2 Schema
-- Pattern as Aggregate Root + Tactical DDD Entity Type Discriminator
--
-- Three-layer architecture (ADR-0009):
-- Pattern (Core Domain) — Stable semantic concepts (the WHY)
-- Architecture (Strategic) — Capabilities, repos, integration (the WHAT/WHERE)
-- Content (DAM Publishing) — Publishing artifacts (the output)
--
-- Entity table uses entity_type discriminator: content, capability, repository
--
-- Key changes from Phase 1:
-- - Pattern replaces Concept as aggregate root
-- - Pattern = applied unit of meaning with business purpose, measured for semantic coherence
-- - Entity references Pattern via primary_pattern_id
-- - approval_status and visibility moved from Entity to Delivery
-- - provenance removed from Entity (lives on Pattern)
-- W3C Standards:
-- - SKOS (Simple Knowledge Organization System) for pattern properties
-- - PROV-O (Provenance Ontology) for entity edges

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- SCHEMA VERSION
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
 version TEXT PRIMARY KEY,
 applied_at TIMESTAMPTZ DEFAULT now,
 description TEXT
);

INSERT INTO schema_version (version, description) VALUES
 ('7.0.0', 'Phase 2: Pattern as aggregate root, approval_status/visibility moved to Delivery'),
 ('8.0.0', 'Phase 2 Tactical DDD: entity_type discriminator, strategic edge predicates, strategic views')
ON CONFLICT (version) DO NOTHING;

-- ============================================================================
-- PATTERN (Aggregate Root)
-- ============================================================================
-- An applied unit of meaning with a business purpose, measured for semantic
-- coherence and optimization. Patterns are stable semantic structures that
-- can be adopted, extended, or modified.
--
-- Examples:
-- - 3p standards we adopt: SKOS, PROV-O, DDD, Dublin-Core
-- - 1p methodologies: semantic-operations, real-data-framework
-- - 1p workflow patterns: content-classify-pattern, publication-pattern

CREATE TABLE IF NOT EXISTS pattern (
 id TEXT PRIMARY KEY, -- kebab-case: semantic-coherence, content-classify-pattern
 preferred_label TEXT NOT NULL, -- SKOS prefLabel: canonical display name
 definition TEXT NOT NULL, -- SKOS definition: authoritative meaning
 alt_labels TEXT[] DEFAULT '{}', -- SKOS altLabel: synonyms, abbreviations
 provenance TEXT NOT NULL DEFAULT '1p'
 CHECK (provenance IN ('1p', '2p', '3p')), -- whose semantic structure
 metadata JSONB NOT NULL DEFAULT '{}', -- flexible additional fields
 embedding vector(1536), -- OpenAI text-embedding-3-small for semantic search
 created_at TIMESTAMPTZ NOT NULL DEFAULT now,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now
);

COMMENT ON TABLE pattern IS 'Aggregate root: applied unit of meaning with business purpose, measured for semantic coherence';
COMMENT ON COLUMN pattern.id IS 'Unique identifier in kebab-case';
COMMENT ON COLUMN pattern.preferred_label IS 'SKOS prefLabel - canonical display name';
COMMENT ON COLUMN pattern.definition IS 'SKOS definition - authoritative meaning';
COMMENT ON COLUMN pattern.alt_labels IS 'SKOS altLabel - synonyms and abbreviations';
COMMENT ON COLUMN pattern.provenance IS '1p = operates in my system, 2p = collaborative, 3p = external reference';
COMMENT ON COLUMN pattern.embedding IS 'Vector embedding for semantic similarity search';

-- ============================================================================
-- PATTERN_EDGE (Pattern Relationships)
-- ============================================================================
-- Relationships between patterns using SKOS hierarchy plus adoption predicates.
--
-- SKOS predicates: broader, narrower, related
-- Adoption predicates: adopts (uses as-is), extends (builds on), modifies (changes)

CREATE TABLE IF NOT EXISTS pattern_edge (
 src_id TEXT NOT NULL REFERENCES pattern(id) ON DELETE CASCADE,
 dst_id TEXT NOT NULL REFERENCES pattern(id) ON DELETE CASCADE,
 predicate TEXT NOT NULL
 CHECK (predicate IN ('broader', 'narrower', 'related', 'adopts', 'extends', 'modifies')),
 strength DECIMAL(3,2) DEFAULT 1.0
 CHECK (strength >= 0.0 AND strength <= 1.0),
 metadata JSONB NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ DEFAULT now,
 PRIMARY KEY (src_id, dst_id, predicate),
 CHECK (src_id != dst_id)
);

COMMENT ON TABLE pattern_edge IS 'Relationships between patterns: SKOS hierarchy + adoption predicates';
COMMENT ON COLUMN pattern_edge.predicate IS 'broader/narrower/related (SKOS), adopts/extends/modifies (adoption)';
COMMENT ON COLUMN pattern_edge.strength IS 'Relationship strength 0.0-1.0';

-- ============================================================================
-- BRAND (CRM/PIM Actor)
-- ============================================================================
-- Unified actor table representing people, organizations, and commercial brands.
-- Based on Schema.org types (Person, Organization, Brand).
-- Enables company structure: actors own brands, brands offer products.

CREATE TABLE IF NOT EXISTS brand (
 id TEXT PRIMARY KEY, -- kebab-case: tim-mitchell, semantic-operations
 brand_type TEXT NOT NULL
 CHECK (brand_type IN ('person', 'organization', 'brand')),
 name TEXT NOT NULL, -- Display name
 alt_names TEXT[] DEFAULT '{}', -- Alternative names
 slogan TEXT, -- Brand tagline (brands only)
 logo_uri TEXT, -- Logo asset URI (brands only)
 url TEXT, -- Primary URL
 owned_domains TEXT[] DEFAULT '{}', -- Domains owned
 given_name TEXT, -- First name (persons only)
 family_name TEXT, -- Last name (persons only)
 legal_name TEXT, -- Legal name (orgs only)
 emails TEXT[] DEFAULT '{}', -- Contact emails (CRM)
 external_ids JSONB NOT NULL DEFAULT '{}', -- External identifiers (linkedin, github, etc.)
 pattern_id TEXT REFERENCES pattern(id), -- 1p pattern this commercializes
 metadata JSONB NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now
);

COMMENT ON TABLE brand IS 'Unified actor: people, organizations, and commercial brands (Schema.org based)';
COMMENT ON COLUMN brand.brand_type IS 'person = individual, organization = company, brand = commercial identity';
COMMENT ON COLUMN brand.pattern_id IS 'The 1p pattern this brand commercializes';

-- ============================================================================
-- PRODUCT (PIM)
-- ============================================================================
-- Products or services offered by a brand. Based on Schema.org Product.
-- Represents what you sell: consulting, courses, white papers, etc.

CREATE TABLE IF NOT EXISTS product (
 id TEXT PRIMARY KEY, -- kebab-case: semops-consulting
 name TEXT NOT NULL, -- Product name
 sku TEXT, -- Stock keeping unit
 description TEXT, -- Product description
 brand_id TEXT NOT NULL REFERENCES brand(id), -- Brand that offers this
 pattern_id TEXT REFERENCES pattern(id), -- 1p pattern this packages
 pricing JSONB NOT NULL DEFAULT '{}', -- Pricing info (price, currency, unit)
 metadata JSONB NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now
);

COMMENT ON TABLE product IS 'Products/services offered by a brand (Schema.org Product)';
COMMENT ON COLUMN product.brand_id IS 'Brand that offers this product';
COMMENT ON COLUMN product.pattern_id IS 'The 1p pattern this product packages';

-- ============================================================================
-- BRAND_RELATIONSHIP (CRM)
-- ============================================================================
-- Flexible relationships between actors (brands) and products.
-- Captures CRM-style connections: who knows whom, who owns what.

CREATE TABLE IF NOT EXISTS brand_relationship (
 src_id TEXT NOT NULL REFERENCES brand(id) ON DELETE CASCADE,
 dst_type TEXT NOT NULL
 CHECK (dst_type IN ('brand', 'product')),
 dst_id TEXT NOT NULL, -- ID of brand or product
 predicate TEXT NOT NULL, -- Relationship type (flexible)
 metadata JSONB NOT NULL DEFAULT '{}', -- Context (source, met_at, etc.)
 created_at TIMESTAMPTZ DEFAULT now,
 PRIMARY KEY (src_id, dst_type, dst_id, predicate)
);

COMMENT ON TABLE brand_relationship IS 'CRM relationships between actors and products';
COMMENT ON COLUMN brand_relationship.predicate IS 'Relationship type: owns, knows, works_for, interested_in, etc.';

-- ============================================================================
-- ENTITY (Unified: Content + Strategic)
-- ============================================================================
-- Unified entity table with type discriminator (ADR-0009):
-- content = DAM publishing artifacts (blog posts, articles, media)
-- capability = What the system delivers (traces to >=1 pattern)
-- repository = Where implementation lives (delivers capabilities)
--
-- Content entities use filespec, attribution, and asset_type.
-- Capability/repository entities use metadata schemas and edges.
-- approval_status and visibility live on Delivery (per-surface, content only).

CREATE TABLE IF NOT EXISTS entity (
 id TEXT PRIMARY KEY, -- kebab-case: blog-post-ai-adoption-2024
 entity_type TEXT NOT NULL DEFAULT 'content'
 CHECK (entity_type IN ('content', 'capability', 'repository')),
 asset_type TEXT -- nullable: only meaningful for content entities
 CHECK (asset_type IN ('file', 'link')), -- file = possess it, link = reference it
 title TEXT, -- human-readable title
 version TEXT DEFAULT '1.0', -- semantic versioning
 primary_pattern_id TEXT REFERENCES pattern(id), -- main pattern (NULL = orphan content, or use edges for multi-pattern)
 filespec JSONB NOT NULL DEFAULT '{}', -- filespec_v1: uri, format, hash, mime_type, size
 attribution JSONB NOT NULL DEFAULT '{}', -- attribution_v2: Dublin Core aligned
 metadata JSONB NOT NULL DEFAULT '{}', -- content_metadata_v1 / capability_metadata_v1 / repository_metadata_v1
 embedding vector(1536), -- OpenAI text-embedding-3-small for semantic search
 created_at TIMESTAMPTZ NOT NULL DEFAULT now,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now
);

COMMENT ON TABLE entity IS 'Unified entity table: content (DAM), capability (strategic), repository (strategic)';
COMMENT ON COLUMN entity.entity_type IS 'Discriminator: content = DAM artifact, capability = system capability, repository = implementation location';
COMMENT ON COLUMN entity.asset_type IS 'file = you possess it, link = external reference. Only meaningful for content entities (NULL for capability/repository)';
COMMENT ON COLUMN entity.primary_pattern_id IS 'Main pattern this entity documents/implements; NULL = orphan (content) or use edges (multi-pattern capabilities)';
COMMENT ON COLUMN entity.embedding IS 'Vector embedding for semantic similarity search';

-- ============================================================================
-- EDGE (Entity/Pattern/Surface Relationships)
-- ============================================================================
-- Relationships between entities, patterns, and surfaces.
-- PROV-O predicates for content lineage.
-- Strategic DDD predicates for capability/repo links (ADR-0009).

CREATE TABLE IF NOT EXISTS edge (
 src_type TEXT NOT NULL CHECK (src_type IN ('entity', 'surface', 'pattern')),
 src_id TEXT NOT NULL,
 dst_type TEXT NOT NULL CHECK (dst_type IN ('entity', 'surface', 'pattern')),
 dst_id TEXT NOT NULL,
 predicate TEXT NOT NULL
 CHECK (predicate IN (
 -- PROV-O / Schema.org / Domain predicates
 'derived_from', 'cites', 'version_of', 'part_of',
 'documents', 'depends_on', 'related_to',
 -- Strategic DDD predicates (ADR-0009)
 'implements', -- capability -> pattern
 'delivered_by', -- capability -> repository
 'integration' -- repository -> repository (DDD integration pattern)
 )),
 strength DECIMAL(3,2) DEFAULT 1.0
 CHECK (strength >= 0.0 AND strength <= 1.0),
 metadata JSONB NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ DEFAULT now,
 PRIMARY KEY (src_type, src_id, dst_type, dst_id, predicate)
);

COMMENT ON TABLE edge IS 'Entity relationships: PROV-O lineage, Schema.org structure, strategic DDD links';
COMMENT ON COLUMN edge.predicate IS
 'PROV-O: derived_from, cites, version_of; Schema.org: part_of, documents; '
 'Domain: depends_on, related_to; Strategic DDD: implements, delivered_by, integration';

-- ============================================================================
-- SURFACE (Publication Destinations)
-- ============================================================================

CREATE TABLE IF NOT EXISTS surface (
 id TEXT PRIMARY KEY, -- youtube-my-channel, github-my-repo
 platform TEXT NOT NULL, -- youtube, github, wordpress, etc.
 surface_type TEXT NOT NULL, -- channel, repo, site, publication, feed, profile
 direction TEXT NOT NULL
 CHECK (direction IN ('publish', 'ingest', 'bidirectional')),
 constraints JSONB NOT NULL DEFAULT '{}', -- platform limits/capabilities
 metadata JSONB NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now
);

COMMENT ON TABLE surface IS 'Publication destinations and ingestion sources';

-- ============================================================================
-- SURFACE_ADDRESS (URLs and Endpoints)
-- ============================================================================

CREATE TABLE IF NOT EXISTS surface_address (
 surface_id TEXT NOT NULL REFERENCES surface(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, -- public, feed, api, webhook, deeplink
 uri TEXT NOT NULL,
 active BOOLEAN NOT NULL DEFAULT true,
 first_seen TIMESTAMPTZ DEFAULT now,
 last_seen TIMESTAMPTZ DEFAULT now,
 PRIMARY KEY (surface_id, kind, uri)
);

-- ============================================================================
-- DELIVERY (Publishing Layer)
-- ============================================================================
-- Entity published to or ingested from a Surface.
-- approval_status and visibility live here (per-surface publishing governance).

CREATE TABLE IF NOT EXISTS delivery (
 id TEXT PRIMARY KEY, -- delivery-blog-post-123-wordpress
 entity_id TEXT NOT NULL REFERENCES entity(id),
 surface_id TEXT NOT NULL REFERENCES surface(id),
 role TEXT NOT NULL
 CHECK (role IN ('original', 'syndication')),
 status TEXT NOT NULL
 CHECK (status IN ('planned', 'queued', 'published', 'failed', 'removed')),
 approval_status TEXT NOT NULL DEFAULT 'pending'
 CHECK (approval_status IN ('pending', 'approved', 'rejected')),
 visibility TEXT NOT NULL DEFAULT 'private'
 CHECK (visibility IN ('public', 'private')),
 url TEXT, -- where content lives on surface
 remote_id TEXT, -- platform-specific ID
 field_mapping JSONB NOT NULL DEFAULT '{}',
 source_hash TEXT,
 published_at TIMESTAMPTZ,
 failed_at TIMESTAMPTZ,
 error_message TEXT,
 metadata JSONB NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now
);

COMMENT ON TABLE delivery IS 'Publishing layer: entity delivered to surface with per-surface governance';
COMMENT ON COLUMN delivery.approval_status IS 'Per-surface approval: pending, approved, rejected';
COMMENT ON COLUMN delivery.visibility IS 'Per-surface visibility: public, private';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Pattern indexes
CREATE INDEX IF NOT EXISTS idx_pattern_provenance ON pattern(provenance);
CREATE INDEX IF NOT EXISTS idx_pattern_metadata ON pattern USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_pattern_embedding ON pattern USING hnsw (embedding vector_cosine_ops);

-- Pattern edge indexes
CREATE INDEX IF NOT EXISTS idx_pattern_edge_src ON pattern_edge(src_id);
CREATE INDEX IF NOT EXISTS idx_pattern_edge_dst ON pattern_edge(dst_id);
CREATE INDEX IF NOT EXISTS idx_pattern_edge_predicate ON pattern_edge(predicate);

-- Brand indexes
CREATE INDEX IF NOT EXISTS idx_brand_type ON brand(brand_type);
CREATE INDEX IF NOT EXISTS idx_brand_pattern ON brand(pattern_id);
CREATE INDEX IF NOT EXISTS idx_brand_metadata ON brand USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_brand_external_ids ON brand USING gin(external_ids);

-- Product indexes
CREATE INDEX IF NOT EXISTS idx_product_brand ON product(brand_id);
CREATE INDEX IF NOT EXISTS idx_product_pattern ON product(pattern_id);
CREATE INDEX IF NOT EXISTS idx_product_metadata ON product USING gin(metadata);

-- Brand relationship indexes
CREATE INDEX IF NOT EXISTS idx_brand_rel_src ON brand_relationship(src_id);
CREATE INDEX IF NOT EXISTS idx_brand_rel_dst ON brand_relationship(dst_type, dst_id);
CREATE INDEX IF NOT EXISTS idx_brand_rel_predicate ON brand_relationship(predicate);

-- Entity indexes
CREATE INDEX IF NOT EXISTS idx_entity_type ON entity(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_type_pattern ON entity(entity_type, primary_pattern_id);
CREATE INDEX IF NOT EXISTS idx_entity_asset_type ON entity(asset_type);
CREATE INDEX IF NOT EXISTS idx_entity_primary_pattern ON entity(primary_pattern_id);
CREATE INDEX IF NOT EXISTS idx_entity_metadata ON entity USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_entity_filespec ON entity USING gin(filespec);
CREATE INDEX IF NOT EXISTS idx_entity_attribution ON entity USING gin(attribution);
CREATE INDEX IF NOT EXISTS idx_entity_orphans ON entity(id) WHERE entity_type = 'content' AND primary_pattern_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_entity_embedding ON entity USING hnsw (embedding vector_cosine_ops);

-- Edge indexes
CREATE INDEX IF NOT EXISTS idx_edge_src ON edge(src_type, src_id);
CREATE INDEX IF NOT EXISTS idx_edge_dst ON edge(dst_type, dst_id);
CREATE INDEX IF NOT EXISTS idx_edge_predicate ON edge(predicate);

-- Surface indexes
CREATE INDEX IF NOT EXISTS idx_surface_platform ON surface(platform);
CREATE INDEX IF NOT EXISTS idx_surface_type ON surface(surface_type);
CREATE INDEX IF NOT EXISTS idx_surface_direction ON surface(direction);

-- Surface address indexes
CREATE INDEX IF NOT EXISTS idx_surface_address_active ON surface_address(active);

-- Delivery indexes
CREATE INDEX IF NOT EXISTS idx_delivery_entity_id ON delivery(entity_id);
CREATE INDEX IF NOT EXISTS idx_delivery_surface_id ON delivery(surface_id);
CREATE INDEX IF NOT EXISTS idx_delivery_status ON delivery(status);
CREATE INDEX IF NOT EXISTS idx_delivery_approval_status ON delivery(approval_status);
CREATE INDEX IF NOT EXISTS idx_delivery_visibility ON delivery(visibility);
CREATE INDEX IF NOT EXISTS idx_delivery_role ON delivery(role);
CREATE INDEX IF NOT EXISTS idx_delivery_published_at ON delivery(published_at);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column
RETURNS TRIGGER AS $$
BEGIN
 NEW.updated_at = now;
 RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_pattern_updated_at ON pattern;
CREATE TRIGGER update_pattern_updated_at BEFORE UPDATE ON pattern
 FOR EACH ROW EXECUTE FUNCTION update_updated_at_column;

DROP TRIGGER IF EXISTS update_brand_updated_at ON brand;
CREATE TRIGGER update_brand_updated_at BEFORE UPDATE ON brand
 FOR EACH ROW EXECUTE FUNCTION update_updated_at_column;

DROP TRIGGER IF EXISTS update_product_updated_at ON product;
CREATE TRIGGER update_product_updated_at BEFORE UPDATE ON product
 FOR EACH ROW EXECUTE FUNCTION update_updated_at_column;

DROP TRIGGER IF EXISTS update_entity_updated_at ON entity;
CREATE TRIGGER update_entity_updated_at BEFORE UPDATE ON entity
 FOR EACH ROW EXECUTE FUNCTION update_updated_at_column;

DROP TRIGGER IF EXISTS update_surface_updated_at ON surface;
CREATE TRIGGER update_surface_updated_at BEFORE UPDATE ON surface
 FOR EACH ROW EXECUTE FUNCTION update_updated_at_column;

DROP TRIGGER IF EXISTS update_delivery_updated_at ON delivery;
CREATE TRIGGER update_delivery_updated_at BEFORE UPDATE ON delivery
 FOR EACH ROW EXECUTE FUNCTION update_updated_at_column;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Orphan entities: content at the flexible edge awaiting incorporation
-- Scoped to content entities only (capabilities use edges, not primary_pattern_id)
CREATE OR REPLACE VIEW orphan_entities AS
SELECT
 e.id,
 e.title,
 e.asset_type,
 e.created_at,
 e.metadata->>'content_type' AS content_type
FROM entity e
WHERE e.entity_type = 'content'
 AND e.primary_pattern_id IS NULL
ORDER BY e.created_at DESC;

COMMENT ON VIEW orphan_entities IS 'Content entities without pattern connection - flexible edge awaiting incorporation';

-- Pattern coverage: documentation (FK + documents edges), capability (implements edges), delivery (delivered_by chain)
-- DROP required: v8.0.0 changed column list; v8.1.0 added edge-based content counting (#138)
DROP VIEW IF EXISTS pattern_coverage;
CREATE OR REPLACE VIEW pattern_coverage AS
SELECT
 p.id AS pattern_id,
 p.preferred_label,
 p.provenance,
 -- Documentation coverage: content via primary_pattern_id FK OR documents/related_to edges (#138)
 (SELECT COUNT(DISTINCT content_id) FROM (
 SELECT e.id AS content_id
 FROM entity e
 WHERE e.primary_pattern_id = p.id AND e.entity_type = 'content'
 UNION
 SELECT ed.src_id AS content_id
 FROM edge ed
 JOIN entity e2 ON ed.src_id = e2.id AND e2.entity_type = 'content'
 WHERE ed.dst_type = 'pattern' AND ed.dst_id = p.id
 AND ed.src_type = 'entity'
 AND ed.predicate IN ('documents', 'related_to')
 ) combined) AS content_count,
 -- Architectural coverage: capabilities linked via 'implements' edges
 (SELECT COUNT(DISTINCT ed.src_id)
 FROM edge ed
 WHERE ed.dst_type = 'pattern' AND ed.dst_id = p.id
 AND ed.src_type = 'entity' AND ed.predicate = 'implements'
 ) AS capability_count,
 -- Delivery coverage: repos that deliver capabilities implementing this pattern
 (SELECT COUNT(DISTINCT ed2.dst_id)
 FROM edge ed
 JOIN edge ed2 ON ed2.src_type = 'entity' AND ed2.src_id = ed.src_id
 AND ed2.dst_type = 'entity' AND ed2.predicate = 'delivered_by'
 WHERE ed.dst_type = 'pattern' AND ed.dst_id = p.id
 AND ed.src_type = 'entity' AND ed.predicate = 'implements'
 ) AS repo_count
FROM pattern p
ORDER BY p.preferred_label;

COMMENT ON VIEW pattern_coverage IS 'Pattern coverage: documentation (FK + documents edges), capability (implements edges), delivery (delivered_by via capability chain)';

-- Capability coverage: strategic DDD coherence signal
-- Every capability should trace to >=1 pattern and be delivered by >=1 repo
CREATE OR REPLACE VIEW capability_coverage AS
SELECT
 cap.id AS capability_id,
 cap.title AS capability_name,
 cap.metadata->>'domain_classification' AS domain_classification,
 cap.primary_pattern_id,
 p.preferred_label AS primary_pattern_label,
 (SELECT COUNT(DISTINCT e.dst_id)
 FROM edge e
 WHERE e.src_type = 'entity' AND e.src_id = cap.id
 AND e.dst_type = 'pattern' AND e.predicate = 'implements'
 ) AS pattern_count,
 (SELECT COUNT(DISTINCT e.dst_id)
 FROM edge e
 WHERE e.src_type = 'entity' AND e.src_id = cap.id
 AND e.dst_type = 'entity' AND e.predicate = 'delivered_by'
 ) AS repo_count,
 cap.created_at
FROM entity cap
LEFT JOIN pattern p ON cap.primary_pattern_id = p.id
WHERE cap.entity_type = 'capability'
ORDER BY cap.title;

COMMENT ON VIEW capability_coverage IS 'Strategic DDD: capabilities with pattern implementation and repo delivery counts';

-- Repository capabilities: which repos deliver which capabilities
CREATE OR REPLACE VIEW repo_capabilities AS
SELECT
 repo.id AS repo_id,
 repo.title AS repo_name,
 repo.metadata->>'role' AS repo_role,
 cap.id AS capability_id,
 cap.title AS capability_name,
 e.metadata AS edge_metadata
FROM entity repo
JOIN edge e ON e.dst_type = 'entity' AND e.dst_id = repo.id
 AND e.predicate = 'delivered_by'
JOIN entity cap ON e.src_type = 'entity' AND e.src_id = cap.id
 AND cap.entity_type = 'capability'
WHERE repo.entity_type = 'repository'
ORDER BY repo.title, cap.title;

COMMENT ON VIEW repo_capabilities IS 'Strategic DDD: repositories and the capabilities they deliver';

-- Integration map: repo-to-repo integration relationships with DDD pattern typing
CREATE OR REPLACE VIEW integration_map AS
SELECT
 src_repo.id AS source_repo_id,
 src_repo.title AS source_repo_name,
 dst_repo.id AS target_repo_id,
 dst_repo.title AS target_repo_name,
 e.metadata->>'integration_pattern' AS integration_pattern,
 e.metadata->>'shared_artifact' AS shared_artifact,
 e.metadata->>'direction' AS direction,
 e.metadata->>'rationale' AS rationale,
 e.created_at
FROM edge e
JOIN entity src_repo ON e.src_type = 'entity' AND e.src_id = src_repo.id
 AND src_repo.entity_type = 'repository'
JOIN entity dst_repo ON e.dst_type = 'entity' AND e.dst_id = dst_repo.id
 AND dst_repo.entity_type = 'repository'
WHERE e.predicate = 'integration'
ORDER BY src_repo.title, dst_repo.title;

COMMENT ON VIEW integration_map IS 'Strategic DDD: repo-to-repo integration relationships with DDD pattern typing';

-- ============================================================================
-- SEED DATA: Foundation Patterns (3p)
-- ============================================================================

INSERT INTO pattern (id, preferred_label, definition, provenance) VALUES
 ('skos', 'SKOS', 'W3C Simple Knowledge Organization System - standard for knowledge organization with concepts, labels, and semantic relations.', '3p'),
 ('prov-o', 'PROV-O', 'W3C Provenance Ontology - standard for representing provenance information including derivation and attribution.', '3p'),
 ('ddd', 'Domain-Driven Design', 'Software design approach focusing on modeling complex domains with bounded contexts, aggregates, and ubiquitous language.', '3p'),
 ('dublin-core', 'Dublin Core', 'Metadata standard for describing digital resources including creator, rights, and publication information.', '3p'),
 ('dam', 'Digital Asset Management', 'Industry pattern for managing digital content lifecycle including approval workflows and multi-channel distribution.', '3p')
ON CONFLICT (id) DO NOTHING;

-- Foundation pattern relationships
INSERT INTO pattern_edge (src_id, dst_id, predicate, strength) VALUES
 ('skos', 'ddd', 'related', 0.7),
 ('prov-o', 'dublin-core', 'related', 0.8)
ON CONFLICT DO NOTHING;
