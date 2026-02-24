# Episode-Centric Provenance

> **Status:** Active
> **Version:** 1.0.0
> **Last Updated:** 2026-01-01
> **Related Issue:** [#102](https://github.com/semops-ai/semops-core/issues/102)

## Executive Summary

Episode-Centric Provenance is SemOps' approach to tracking lineage for all semantic operations. It combines enterprise data lineage patterns (OpenLineage) with agentic context tracking (Graphiti's Episode concept) to enable:

- **Automatic lineage capture** - Operations are instrumented, not manually tracked
- **Full audit trails** - Answer "why was this classified this way?"
- **Semantic coherence measurement** - Quality signals for pattern alignment
- **Agentic reproducibility** - Capture model, prompt, and context for any decision

## The Thesis: Semantic Operations as Data Infrastructure

**SemOps is building a reference implementation of how an organization manages semantic coherence at the infrastructure level.**

Just as modern data teams have evolved from ad-hoc scripts to mature data infrastructure, semantic operations need the same treatment. Meaning isn't just content—it's infrastructure.

### Enterprise Data Infrastructure Mapping

| Traditional Data Infra | SemOps Equivalent | Notes |
|------------------------|-------------------|-------|
| Data Warehouse | Pattern Knowledge Base | PostgreSQL + Neo4j |
| ETL Pipelines | Ingestion Pipelines | Source → Entity → Pattern alignment |
| Data Lineage (OpenLineage) | Episode-Centric Provenance | Automatic, instrumented |
| Data Quality (Great Expectations) | Coherence Scoring | Embedding similarity + LLM evaluation |
| Data Catalog (DataHub/Marquez) | Pattern Catalog | Pattern as aggregate root |
| Data Governance (policies, ownership) | Semantic Governance | Provenance (1p/2p/3p), attribution |
| ML Feature Store | Pattern-Entity Graph | Reusable semantic units |

The key difference: **semantic operations treats meaning as infrastructure**, not just data.

## Architecture: Two Distinct Layers

### 1. Infrastructure Layer (General Purpose)

Tools and services that any pipeline can use:

- **Chunking strategies** - Document segmentation
- **Embedding models** - text-embedding-3-small, nomic-embed-text
- **Vector databases** - Qdrant, pgvector
- **Crawlers/fetchers** - GitHub, web, document processing
- **Ephemeral corpora** - Tool-specific RAG, temporary research

These are commodity components. They don't require lineage tracking—they're just tools.

### 2. DDD Architecture Layer (Pattern-Aligned)

The intentional, semantic layer where meaning is managed:

```
Pattern → Entity → Edge → Delivery → Surface
```

This is where Episode-Centric Provenance operates. Every operation that touches this layer is tracked:

- **Pattern creation** - Where did this semantic unit come from?
- **Entity classification** - What context was used to align this entity to a pattern?
- **Edge detection** - Why was this relationship created?
- **Delivery publishing** - Full chain from entity through pattern to sources

**Critical insight:** Research ingestion IS architecture-touching because it's how patterns emerge. The pipeline `Research → Synthesis → Pattern Declaration` is a tracked operation.

## Why OpenLineage-Style Instrumentation?

### The Problem with Manual Lineage

Traditional approaches require developers to manually create edges:

```python
# Manual approach - error-prone, incomplete
entity = create_entity(content)
edge = create_edge(entity.id, pattern.id, "aligned_to") # Easy to forget
```

### The OpenLineage Insight

OpenLineage solves this for Spark/Airflow by **instrumenting the operations themselves**. When Spark reads a table, an event fires automatically. No developer intervention needed.

We apply the same pattern to semantic operations:

```python
@emit_lineage(operation=OperationType.CLASSIFY)
def classify_entity(entity_id: str, context: ClassificationContext):
 patterns = retrieve_relevant_patterns(entity.embedding) # Captured
 result = llm.classify(entity, patterns) # Captured
 return result

# Lineage captured automatically:
# - inputs: entity_id, pattern_ids retrieved
# - operation: classify
# - outputs: entity.primary_pattern_id assignment
# - edges: detected relationships
# - context: which patterns were considered
```

### What Gets Captured

| Trigger Event | What Happens | Lineage Captured |
|---------------|--------------|------------------|
| Pattern created | New row in `pattern` table | Trace back: what research informed this? |
| Entity gets `primary_pattern_id` | Orphan → aligned | Classification episode + context |
| Delivery created (original) | Entity published | Full chain: entity → pattern → sources |
| Edge created | Explicit relationship | Relationship itself is lineage |
| Embedding generated | Vector created | Model, input hash for reproducibility |

## Why Graphiti's Episode Concept?

### The Problem with Pure Lineage

OpenLineage gives us "what touched what" but not "why" or "with what context." For agent operations, context is everything.

### Graphiti's Contribution

Graphiti introduced the concept of an **Episode** as the unit of agent memory:

- An episode captures a meaningful interaction
- It includes the context that was active during the interaction
- It enables temporal reasoning about agent decisions

### Our Hybrid: Episode-Centric Provenance

We combine both:

1. **OpenLineage instrumentation** - Automatic capture via decorated operations
2. **Graphiti episodes** - Rich context for each operation

```sql
CREATE TABLE ingestion_episode (
 id TEXT PRIMARY KEY,
 run_id TEXT REFERENCES ingestion_run(id),

 -- What happened? (OpenLineage-style)
 operation TEXT NOT NULL, -- 'ingest', 'classify', 'declare_pattern'
 target_type TEXT NOT NULL, -- 'entity', 'pattern', 'edge'
 target_id TEXT NOT NULL,

 -- What context was used? (Graphiti-style)
 context_pattern_ids TEXT[], -- Patterns retrieved/considered
 context_entity_ids TEXT[], -- Entities used as context

 -- Quality signals
 coherence_score DECIMAL(4,3), -- Semantic alignment 0-1

 -- Reproducibility
 agent_name TEXT, -- Which classifier/agent
 model_name TEXT, -- gpt-4o-mini, claude-3
 prompt_hash TEXT, -- Hash of prompt template

 -- Model-detected relationships
 detected_edges JSONB -- [{predicate, target_id, strength, rationale}]
);
```

## Agentic-First Design

### Edge Detection is Model-Driven

Traditional systems require humans to define relationships. In SemOps, the agent proposes edges during classification:

```python
class ClassificationResult(BaseModel):
 primary_pattern_id: str
 confidence: float
 detected_edges: list[DetectedEdge] # Model-detected relationships

class DetectedEdge(BaseModel):
 predicate: str # derived_from, cites, related_to
 target_id: str
 strength: float
 rationale: str # Why the model thinks this relationship exists
```

The episode captures these detected edges. A human or downstream process can approve or reject them, but the detection is automatic.

### Coherence as a Quality Signal

Instead of just "valid/invalid," we measure **semantic coherence**:

- **Embedding similarity** - Fast, embedding-based scoring
- **LLM evaluation** - Deeper analysis for edge cases or audits

This gives us a continuous quality signal, not just a binary gate.

## Storage Architecture

### PostgreSQL for Episodes (Operational)

Episodes are time-series operational data:

- High write volume during ingestion
- Time-based queries ("what happened in the last run?")
- Retention policies (90 days detailed, then aggregate)

PostgreSQL handles this well with proper indexing.

### Neo4j for Pattern Graph (Structural)

The pattern graph is structural:

- Community detection
- PageRank importance scoring
- Orphan detection
- Hierarchy validation

Neo4j with GDS (Graph Data Science) handles these queries efficiently.

### Dual-Store Philosophy

```
PostgreSQL: "What happened, when, and why?"
Neo4j: "How is everything connected?"
```

They complement each other. Episodes reference patterns, but the graph structure lives in Neo4j.

## Comparison to DataHub

DataHub is the reference implementation for enterprise data catalogs. Here's how SemOps maps to their architecture:

| DataHub Component | SemOps Equivalent | Enhancement |
|-------------------|-------------------|-------------|
| Metadata Ingestion | Ingestion Pipeline | Episode-tracked with context |
| Entity Model (Datasets, Dashboards) | Pattern/Entity/Delivery | Semantic alignment via Pattern as aggregate root |
| Relationships (Lineage) | Edge + Episode.detected_edges | Model-detected, not just system-detected |
| Search (Elasticsearch) | pgvector + Qdrant | Semantic search, not just keyword |
| Ownership/Domain | Provenance (1p/2p/3p) + Repository ownership | Simpler model for smaller teams |
| Data Quality | Coherence Scoring | Semantic coherence, not just data validity |
| Access Control | Visibility (public/private) on Delivery | Per-surface, not per-entity |

### What We Add

1. **Agentic-first lineage** - Operations are instrumented for agent workflows
2. **Semantic coherence layer** - Quality measured as alignment to patterns
3. **Episode context** - Full audit trail including what the agent "knew"
4. **Model-detected edges** - Relationships proposed by LLM, not just system
5. **Pattern as aggregate root** - DDD-aligned, not just asset management

## Usage

### Basic Instrumentation

```python
from lineage import LineageTracker, OperationType

with LineageTracker(source_name="github-docs") as tracker:
 with tracker.track_operation(
 operation=OperationType.INGEST,
 target_type="entity",
 target_id=entity_id,
 ) as episode:
 # Do the work
 entity = create_entity(content)

 # Add context
 episode.add_context_pattern("semantic-operations")
 episode.coherence_score = compute_coherence(entity)
 episode.set_agent_info(
 name="github_ingest",
 version="1.0.0",
 model="text-embedding-3-small"
 )
```

### Decorator Pattern

```python
from lineage import emit_lineage, OperationType
from lineage.decorators import add_context_pattern, set_coherence_score

@emit_lineage(operation=OperationType.CLASSIFY)
def classify_entity(entity_id: str) -> ClassificationResult:
 patterns = retrieve_patterns(entity_id)
 for p in patterns:
 add_context_pattern(p.id)

 result = llm_classify(entity_id, patterns)
 set_coherence_score(result.confidence)

 return result
```

## Files

| File | Purpose |
|------|---------|
| [schemas/migrations/001_episode_provenance.sql](../schemas/migrations/001_episode_provenance.sql) | Database schema |
| [scripts/lineage/episode.py](../scripts/lineage/episode.py) | Episode model |
| [scripts/lineage/tracker.py](../scripts/lineage/tracker.py) | LineageTracker context manager |
| [scripts/lineage/decorators.py](../scripts/lineage/decorators.py) | @emit_lineage decorator |
| [scripts/lineage/test_lineage.py](../scripts/lineage/test_lineage.py) | Test suite |

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) - Overall system architecture
- [Phase 2 Schema](../schemas/phase2-schema.sql) - Pattern as aggregate root
- [Issue #102](https://github.com/semops-ai/semops-core/issues/102) - Implementation tracking
- [](https://github.com/semops-ai/semops-data/issues/27) - Open source Agentic Lineage project
