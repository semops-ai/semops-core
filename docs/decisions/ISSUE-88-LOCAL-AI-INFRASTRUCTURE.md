# ISSUE-88: Local AI Infrastructure

> **Status:** In Progress
> **Date:** 2025-12-11
> **Related Issue:** 

## Executive Summary

Implement local AI infrastructure for RAG pipeline and semantic coherence measurement, using Ollama for embeddings/LLM and pgvector for vector storage. Goal: reduce API costs, enable offline development, maintain <500ms retrieval latency.

## Context

The existing infrastructure uses OpenAI embeddings (1536 dimensions) stored in the `embedding` column. This creates:
- API cost for every embedding operation
- Dependency on external service availability
- Privacy concerns for sensitive content

Local AI infrastructure enables:
- Zero-cost embedding generation
- Offline-capable development
- Faster iteration on RAG experiments
- Foundation for semantic coherence measurement

## Decisions

### D1: Dual Embedding Strategy

**Decision:** Maintain separate embedding columns rather than replacing OpenAI embeddings.

| Column | Model | Dimensions | Purpose |
|--------|-------|------------|---------|
| `embedding` | text-embedding-ada-002 | 1536 | Production/high-quality |
| `embedding_local` | nomic-embed-text | 768 | Development/offline |

**Rationale:** Different use cases benefit from different models. Local embeddings for rapid iteration, OpenAI for production quality.

### D2: Ollama as Local Inference Engine

**Decision:** Use Ollama for all local LLM/embedding inference.

**Models Selected:**
| Model | Size | Purpose |
|-------|------|---------|
| nomic-embed-text | 274MB | General text embeddings (768d) |
| mistral | 4.4GB | LLM generation for RAG answers |

**Rationale:** Ollama provides simple API, model management, and runs efficiently on consumer hardware.

### D3: Model Directory Structure

**Decision:** Organize local models in `~/models/` with clear separation from ComfyUI.

```
~/models/
├── ollama/ # Managed by Ollama service
├── embeddings/ # Manual embedding models (BGE-M3, etc.)
├── rerankers/ # Cross-encoder models
├── classifiers/ # NLI, sentiment models
├── gguf/ # Manual GGUF files
└── [ComfyUI dirs] # Unchanged
```

### D4: Confidence-Based Response Routing

**Decision:** Implement tiered response strategy based on retrieval confidence.

| Confidence | Threshold | Response |
|------------|-----------|----------|
| HIGH | >80% | Direct answer from context |
| MEDIUM | 60-80% | Answer with caveats |
| LOW | <60% | Suggest related topics |

**Rationale:** Prevents hallucination by not forcing answers when context is weak.

### D5: Chunking Strategy

**Decision:** Markdown heading-based chunking with token limits.

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Strategy | Heading splitter | Preserves semantic boundaries |
| Max tokens | 512 | Fits in context window |
| Overlap | 50 tokens (10%) | Prevents context loss at boundaries |

**Rationale:** Heading-based splitting respects document structure better than fixed-size windows.

## Implementation

### Phase 1: Foundation (Complete)

- [x] Install Ollama system service
- [x] Pull nomic-embed-text and mistral models
- [x] Create `~/models/` directory structure
- [x] Add `embedding_local` column to concept table
- [x] Create `generate_local_embeddings.py`
- [x] Create `local_semantic_search.py`

### Phase 2: Integration (Complete)

- [x] Create `chunk_markdown_docs.py` - document chunking
- [x] Create `search_chunks.py` - chunk-level search
- [x] Create `LocalEmbeddingClassifier` - classifier integration
- [x] Create `detect_drift.py` - embedding drift detection
- [x] Create `rag_query.py` - confidence-based routing
- [x] Verify latency (<500ms for retrieval)

### Phase 3: SC Measurement (Blocked)

**Blocked by:** / - Phase 2 Schema changes

**Reason:** SC measurement requires stable schema with concept as aggregate root. Docs also need cleanup before meaningful coherence metrics.

- [ ] DeltaClassifier for change detection
- [ ] Contradiction detection between chunks
- [ ] SC aggregator across concept clusters
- [ ] Dashboard/reporting

### Phase 4: Experimentation (Future)

- [ ] Ragas integration for RAG evaluation
- [ ] A/B testing framework for models
- [ ] Benchmark automation

## Consequences

### Positive

- Zero marginal cost for embedding generation
- Offline development capability
- Foundation for SC measurement experiments
- Sub-500ms retrieval latency achieved (~150ms)

### Negative

- Two embedding columns to maintain
- Local models require disk space (~5GB)
- Ollama service must be running

### Risks

- Model quality differences between local and OpenAI
- Potential embedding dimension mismatches in queries

## Test Protocol

See [TEST_PROTOCOL_RAG.md](../TEST_PROTOCOL_RAG.md) for full test procedures.

**Quick Validation:**
```bash
# Verify infrastructure
curl -s http://localhost:11434/api/tags | jq '.models[].name'

# Test embedding generation
python3 scripts/local_semantic_search.py "semantic coherence" --limit 3

# Test RAG query
python3 scripts/rag_query.py "what is semantic coherence" --verbose

# Verify latency
time python3 scripts/rag_query.py "test query"
# Expected: <500ms
```

## Scripts Created

| Script | Purpose |
|--------|---------|
| `scripts/generate_local_embeddings.py` | Embed concepts with Ollama |
| `scripts/local_semantic_search.py` | Search concepts by similarity |
| `scripts/chunk_markdown_docs.py` | Chunk and embed documents |
| `scripts/search_chunks.py` | Search document chunks |
| `scripts/detect_drift.py` | Detect embedding drift |
| `scripts/rag_query.py` | Confidence-routed RAG queries |
| `scripts/classifiers/embedding_local.py` | Local embedding classifier |

## References

- [Ollama](https://ollama.com/) - Local LLM inference
- [nomic-embed-text](https://huggingface.co/nomic-ai/nomic-embed-text-v1) - 768d embedding model
- [pgvector](https://github.com/pgvector/pgvector) - PostgreSQL vector extension
