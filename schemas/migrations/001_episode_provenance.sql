-- Episode-Centric Provenance Schema
-- Issue: #102
-- Purpose: Track lineage for all DDD-touching operations with context
--
-- Design principles (from OpenLineage):
-- - Lineage is automatic: instrumented operations emit events
-- - Episodes capture the context used for classification/declaration
-- - Enables "why was this classified this way?" audits
--
-- Key insight: Episodes stay in PostgreSQL (operational data, time-series).
-- Neo4j stays for pattern graph (structural queries, algorithms).

-- ============================================================================
-- INGESTION RUN
-- ============================================================================
-- Tracks each pipeline execution (manual, scheduled, or agent-triggered).
-- A run contains multiple episodes - one per operation performed.

CREATE TABLE IF NOT EXISTS ingestion_run (
  id TEXT PRIMARY KEY,                              -- ulid or uuid
  run_type TEXT NOT NULL
    CHECK (run_type IN ('manual', 'scheduled', 'agent')),
  agent_name TEXT,                                  -- e.g., 'ingest_from_source', 'research_synthesizer'
  source_name TEXT,                                 -- config source name (e.g., 'project-ike-private')
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
  source_config JSONB NOT NULL DEFAULT '{}',        -- snapshot of config used
  metrics JSONB NOT NULL DEFAULT '{}'               -- run-level metrics (files_processed, entities_created, etc.)
);

COMMENT ON TABLE ingestion_run IS 'Pipeline execution tracking - each run contains multiple episodes';
COMMENT ON COLUMN ingestion_run.run_type IS 'manual = human-triggered, scheduled = cron, agent = autonomous';
COMMENT ON COLUMN ingestion_run.source_config IS 'Snapshot of configuration for reproducibility';
COMMENT ON COLUMN ingestion_run.metrics IS 'Aggregated metrics: files_processed, entities_created, etc.';

-- ============================================================================
-- INGESTION EPISODE
-- ============================================================================
-- Tracks each agent operation (instrumented automatically via @emit_lineage).
-- Episode = one meaningful operation that modifies the DDD layer.
--
-- Episodes capture:
-- - What operation was performed (ingest, classify, declare_pattern, publish)
-- - What was created/modified (target_type + target_id)
-- - What context was used (patterns/entities retrieved for the operation)
-- - Quality signals (coherence score)
-- - Agent metadata (for reproducibility and audits)

CREATE TABLE IF NOT EXISTS ingestion_episode (
  id TEXT PRIMARY KEY,                              -- ulid for time-ordering
  run_id TEXT REFERENCES ingestion_run(id) ON DELETE SET NULL,  -- NULL if standalone

  -- What was the operation?
  operation TEXT NOT NULL
    CHECK (operation IN (
      'ingest',           -- new entity created from source
      'classify',         -- entity gets primary_pattern_id
      'declare_pattern',  -- new pattern created from synthesis
      'publish',          -- delivery created (original)
      'synthesize',       -- research → pattern emergence
      'create_edge',      -- relationship established
      'embed'             -- embedding generated
    )),

  -- What was created/modified?
  target_type TEXT NOT NULL
    CHECK (target_type IN ('entity', 'pattern', 'edge', 'delivery')),
  target_id TEXT NOT NULL,

  -- Context used (for classification/declaration audits)
  context_pattern_ids TEXT[] DEFAULT '{}',          -- patterns retrieved/considered
  context_entity_ids TEXT[] DEFAULT '{}',           -- entities used as context

  -- Quality signals
  coherence_score DECIMAL(4,3)                      -- 0.000-1.000, NULL if not computed
    CHECK (coherence_score IS NULL OR (coherence_score >= 0 AND coherence_score <= 1)),

  -- Agent info (for reproducibility)
  agent_name TEXT,                                  -- e.g., 'llm_classifier', 'graph_classifier'
  agent_version TEXT,                               -- e.g., '1.0.0'
  model_name TEXT,                                  -- e.g., 'gpt-4o-mini', 'text-embedding-3-small'
  prompt_hash TEXT,                                 -- hash of prompt template for reproducibility
  token_usage JSONB DEFAULT '{}',                   -- {prompt_tokens, completion_tokens, total_tokens}

  -- Detected edges (for model-proposed relationships)
  detected_edges JSONB DEFAULT '[]',                -- [{predicate, target_id, strength, rationale}]

  -- Metadata
  input_hash TEXT,                                  -- hash of input for deduplication
  error_message TEXT,                               -- if operation failed
  metadata JSONB NOT NULL DEFAULT '{}',             -- flexible additional fields
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE ingestion_episode IS 'Episode-centric provenance: each DDD-touching operation with context';
COMMENT ON COLUMN ingestion_episode.operation IS 'Operation type: ingest, classify, declare_pattern, publish, synthesize, create_edge, embed';
COMMENT ON COLUMN ingestion_episode.target_type IS 'What was modified: entity, pattern, edge, delivery';
COMMENT ON COLUMN ingestion_episode.context_pattern_ids IS 'Patterns retrieved/considered during classification';
COMMENT ON COLUMN ingestion_episode.context_entity_ids IS 'Entities used as context for the operation';
COMMENT ON COLUMN ingestion_episode.coherence_score IS 'Semantic coherence 0-1 (embedding similarity or LLM evaluation)';
COMMENT ON COLUMN ingestion_episode.detected_edges IS 'Model-proposed relationships: [{predicate, target_id, strength, rationale}]';
COMMENT ON COLUMN ingestion_episode.prompt_hash IS 'Hash of prompt template for reproducibility audits';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Run indexes
CREATE INDEX IF NOT EXISTS idx_ingestion_run_status ON ingestion_run(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_run_type ON ingestion_run(run_type);
CREATE INDEX IF NOT EXISTS idx_ingestion_run_started ON ingestion_run(started_at);
CREATE INDEX IF NOT EXISTS idx_ingestion_run_source ON ingestion_run(source_name);

-- Episode indexes
CREATE INDEX IF NOT EXISTS idx_episode_run ON ingestion_episode(run_id);
CREATE INDEX IF NOT EXISTS idx_episode_operation ON ingestion_episode(operation);
CREATE INDEX IF NOT EXISTS idx_episode_target ON ingestion_episode(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_episode_created ON ingestion_episode(created_at);
CREATE INDEX IF NOT EXISTS idx_episode_agent ON ingestion_episode(agent_name);
CREATE INDEX IF NOT EXISTS idx_episode_context_patterns ON ingestion_episode USING gin(context_pattern_ids);
CREATE INDEX IF NOT EXISTS idx_episode_context_entities ON ingestion_episode USING gin(context_entity_ids);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Recent episodes with run context
CREATE OR REPLACE VIEW recent_episodes AS
SELECT
  e.id AS episode_id,
  e.operation,
  e.target_type,
  e.target_id,
  e.coherence_score,
  e.agent_name,
  e.created_at,
  r.id AS run_id,
  r.run_type,
  r.source_name,
  r.status AS run_status
FROM ingestion_episode e
LEFT JOIN ingestion_run r ON e.run_id = r.id
ORDER BY e.created_at DESC
LIMIT 100;

COMMENT ON VIEW recent_episodes IS 'Last 100 episodes with run context for monitoring';

-- Entity lineage: all episodes that touched an entity
CREATE OR REPLACE VIEW entity_lineage AS
SELECT
  e.target_id AS entity_id,
  e.operation,
  e.context_pattern_ids,
  e.coherence_score,
  e.agent_name,
  e.model_name,
  e.detected_edges,
  e.created_at AS episode_at,
  r.source_name,
  r.run_type
FROM ingestion_episode e
LEFT JOIN ingestion_run r ON e.run_id = r.id
WHERE e.target_type = 'entity'
ORDER BY e.target_id, e.created_at;

COMMENT ON VIEW entity_lineage IS 'Full lineage history for entities - for "why was this classified?" audits';

-- Pattern emergence: episodes that declared patterns
CREATE OR REPLACE VIEW pattern_emergence AS
SELECT
  e.target_id AS pattern_id,
  e.context_pattern_ids AS source_patterns,
  e.context_entity_ids AS source_entities,
  e.coherence_score,
  e.agent_name,
  e.detected_edges AS proposed_edges,
  e.created_at AS declared_at,
  r.source_name AS research_source
FROM ingestion_episode e
LEFT JOIN ingestion_run r ON e.run_id = r.id
WHERE e.operation = 'declare_pattern'
ORDER BY e.created_at DESC;

COMMENT ON VIEW pattern_emergence IS 'Track how patterns emerge from research synthesis';

-- ============================================================================
-- SCHEMA VERSION
-- ============================================================================

INSERT INTO schema_version (version, description) VALUES
  ('7.1.0', 'Episode-Centric Provenance: ingestion_run and ingestion_episode tables')
ON CONFLICT (version) DO NOTHING;
