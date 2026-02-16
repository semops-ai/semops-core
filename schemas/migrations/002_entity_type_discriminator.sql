-- Phase 2 Tactical DDD: Entity Type Discriminator
-- Issue: #122, ADR-0009
-- Schema Version: 7.1.0 → 8.0.0
--
-- Adds entity_type discriminator to entity table (content, capability, repository).
-- Extends edge predicates and node types for strategic DDD concepts.
-- Makes asset_type nullable (only meaningful for content entities).
--
-- Safe to run on existing databases — all existing entities backfill as 'content'.

BEGIN;

-- ============================================================================
-- ENTITY TABLE CHANGES
-- ============================================================================

-- 1. Add entity_type column (DEFAULT 'content' backfills existing rows)
ALTER TABLE entity
  ADD COLUMN IF NOT EXISTS entity_type TEXT NOT NULL DEFAULT 'content';

-- 2. Add CHECK constraint for entity_type values
-- (Drop first in case of re-run)
ALTER TABLE entity DROP CONSTRAINT IF EXISTS entity_entity_type_check;
ALTER TABLE entity ADD CONSTRAINT entity_entity_type_check
  CHECK (entity_type IN ('content', 'capability', 'repository'));

-- 3. Make asset_type nullable (capabilities and repos don't need file/link)
-- PostgreSQL CHECK allows NULL by default, so just drop NOT NULL
ALTER TABLE entity ALTER COLUMN asset_type DROP NOT NULL;

-- 4. Indexes for entity_type queries
CREATE INDEX IF NOT EXISTS idx_entity_type ON entity(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_type_pattern ON entity(entity_type, primary_pattern_id);

-- 5. Update comments
COMMENT ON TABLE entity IS 'Unified entity table: content (DAM), capability (strategic), repository (strategic)';
COMMENT ON COLUMN entity.entity_type IS 'Discriminator: content = DAM artifact, capability = system capability, repository = implementation location';
COMMENT ON COLUMN entity.asset_type IS 'file = you possess it, link = external reference. Only meaningful for content entities (NULL for capability/repository)';
COMMENT ON COLUMN entity.primary_pattern_id IS 'Main pattern this entity documents/implements; NULL = orphan (content) or use edges (multi-pattern capabilities)';

-- ============================================================================
-- EDGE TABLE CHANGES
-- ============================================================================

-- 6. Extend src_type/dst_type to include 'pattern' for cross-layer edges
ALTER TABLE edge DROP CONSTRAINT IF EXISTS edge_src_type_check;
ALTER TABLE edge ADD CONSTRAINT edge_src_type_check
  CHECK (src_type IN ('entity', 'surface', 'pattern'));

ALTER TABLE edge DROP CONSTRAINT IF EXISTS edge_dst_type_check;
ALTER TABLE edge ADD CONSTRAINT edge_dst_type_check
  CHECK (dst_type IN ('entity', 'surface', 'pattern'));

-- 7. Extend predicate with strategic DDD predicates
ALTER TABLE edge DROP CONSTRAINT IF EXISTS edge_predicate_check;
ALTER TABLE edge ADD CONSTRAINT edge_predicate_check
  CHECK (predicate IN (
    -- Existing PROV-O / Schema.org / Domain predicates
    'derived_from', 'cites', 'version_of', 'part_of',
    'documents', 'depends_on', 'related_to',
    -- Strategic DDD predicates (ADR-0009)
    'implements',      -- capability -> pattern (what pattern does this implement?)
    'delivered_by',    -- capability -> repository (what repo delivers this?)
    'integration'      -- repository -> repository (DDD integration pattern)
  ));

-- 8. Update comments
COMMENT ON TABLE edge IS 'Entity relationships: PROV-O lineage, Schema.org structure, strategic DDD links';
COMMENT ON COLUMN edge.predicate IS
  'PROV-O: derived_from, cites, version_of; Schema.org: part_of, documents; '
  'Domain: depends_on, related_to; Strategic DDD: implements, delivered_by, integration';

-- ============================================================================
-- VIEWS (updated + new)
-- ============================================================================

-- 9. Scope orphan_entities to content only (capabilities use edges, not primary_pattern_id)
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

-- 10. Enhanced pattern_coverage with per-entity_type counts
CREATE OR REPLACE VIEW pattern_coverage AS
SELECT
  p.id AS pattern_id,
  p.preferred_label,
  p.provenance,
  COUNT(DISTINCT e.id) FILTER (WHERE e.entity_type = 'content') AS content_count,
  COUNT(DISTINCT e.id) FILTER (WHERE e.entity_type = 'capability') AS capability_count,
  COUNT(DISTINCT e.id) FILTER (WHERE e.entity_type = 'repository') AS repo_count,
  COUNT(DISTINCT e.id) AS total_entity_count
FROM pattern p
LEFT JOIN entity e ON e.primary_pattern_id = p.id
GROUP BY p.id, p.preferred_label, p.provenance
ORDER BY p.preferred_label;

COMMENT ON VIEW pattern_coverage IS 'Pattern graph coverage with per-entity-type counts';

-- 11. NEW: Capability coverage (strategic DDD coherence signal)
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

-- 12. NEW: Repository capabilities
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

-- 13. NEW: Integration map
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
-- SCHEMA VERSION
-- ============================================================================

INSERT INTO schema_version (version, description) VALUES
  ('8.0.0', 'Phase 2 Tactical DDD: entity_type discriminator (content/capability/repository), strategic edge predicates (implements/delivered_by/integration), nullable asset_type, strategic DDD views')
ON CONFLICT (version) DO NOTHING;

COMMIT;
