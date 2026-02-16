# User Guide: Ingestion Pipeline

> **Version:** 2.1.0 | **Last Updated:** 2026-02-13
> **See also:** [SEARCH_GUIDE.md](SEARCH_GUIDE.md) for querying the knowledge base

---

## Quick Reference

| Task | Command |
|------|---------|
| List available sources | `python scripts/source_config.py` |
| Dry-run ingestion | `python scripts/ingest_from_source.py --source <name> --dry-run` |
| Ingest (no LLM) | `python scripts/ingest_from_source.py --source <name> --no-llm` |
| Ingest (with LLM) | `python scripts/ingest_from_source.py --source <name>` |
| Generate embeddings | `python scripts/generate_embeddings.py` |
| Materialize graph | `python scripts/materialize_graph.py` |
| Check entity count | `SELECT count(*) FROM entity;` |
| Check chunk count | `SELECT count(*) FROM document_chunk;` |
| Corpus distribution | `SELECT metadata->>'corpus', count(*) FROM entity GROUP BY 1 ORDER BY 2 DESC;` |

**Note:** All Python commands assume `source .venv/bin/activate` (or use `uv run`) and `OPENAI_API_KEY` is set (loaded from `.env`). SQL queries can be run via your preferred database client.

---

## Prerequisites

1. **Docker services running** — `python start_services.py --skip-clone`
2. **Python venv activated** — `source .venv/bin/activate` (or use `uv run`)
3. **`.env` file** with `OPENAI_API_KEY` and `POSTGRES_PASSWORD`
4. **Database connection** — Scripts connect automatically via database connection environment variables configured in `.env`. Direct PostgreSQL access is available via the configured database connection.

---

## Source Management

### Source Config Format

Source configurations live in `config/sources/*.yaml`. Each file defines a GitHub repository to ingest from, with routing rules that assign entities to corpora.

**Full annotated example:**

```yaml
# Source Configuration for <repo-name>
# $schema: source_config_v1

# Required: unique kebab-case identifier
source_id: github-semops-docs

# Required: surface this source belongs to
surface_id: github-semops-ai

# Required: human-readable name
name: "SemOps Documentation (semops-docs)"

# Required: GitHub repository settings
github:
  owner: semops-ai              # GitHub org or user
  repo: semops-docs             # Repository name
  branch: main                  # Branch to ingest from
  base_path: docs/SEMOPS_DOCS   # Subdirectory to start from (empty = repo root)
  include_directories:          # Only ingest from these dirs (relative to base_path)
    - SEMANTIC_OPERATIONS_FRAMEWORK
    - RESEARCH
  exclude_patterns:             # Glob patterns to skip
    - "**/drafts/**"
    - "**/_archive/**"
    - "**/WIP-*"
  file_extensions:              # File types to include
    - .md

# Optional: defaults applied to all entities from this source
defaults:
  asset_type: file              # "file" (you possess it) or "link" (external reference)
  version: "1.0"                # Semantic version

# Optional: attribution template (Dublin Core aligned)
attribution:
  $schema: attribution_v2
  creator:
    - Tim Mitchell
  rights: CC-BY-4.0
  organization: TJMConsulting
  platform: github
  channel: semops-ai
  epistemic_status: synthesis   # synthesis, original, curation, etc.

# Optional: LLM classification settings
llm_classify:
  enabled: true
  model: claude-opus-4-5-20251101   # Default classification model
  fields:                            # Fields the LLM should classify
    - concept_ownership
    - content_type
    - primary_concept
    - broader_concepts
    - narrower_concepts
    - subject_area
    - summary

# Required: corpus routing rules (ADR-0005)
corpus_routing:
  rules:
    - path_pattern: "docs/SEMOPS_DOCS/RESEARCH/**"
      corpus: research_ai
      content_type: concept
    - path_pattern: "docs/SEMOPS_DOCS/SEMANTIC_OPERATIONS_FRAMEWORK/**"
      corpus: core_kb
      content_type: concept
  default_corpus: core_kb           # Fallback if no rule matches
  default_content_type: article     # Fallback content type
```

### Corpus Routing Rules

Corpus routing determines which corpus each entity belongs to based on its file path. Rules are evaluated **in order — first match wins**.

**How it works:**

1. During ingestion, each file's repo-relative path (including `base_path`) is matched against `corpus_routing.rules`
2. The first matching `path_pattern` (fnmatch-style glob) determines `corpus` and `content_type`
3. If no rule matches, `default_corpus` and `default_content_type` are used
4. These values are stored in `entity.metadata->>'corpus'` and `entity.metadata->>'content_type'`

**Path matching note:** The path matched includes `github.base_path`. For example, if `base_path: docs/SEMOPS_DOCS` and the file is `RESEARCH/FOUNDATIONS/foo.md`, the path matched against rules is `docs/SEMOPS_DOCS/RESEARCH/FOUNDATIONS/foo.md`.

**Rule order matters.** More specific rules should come before general ones:

```yaml
# CORRECT: specific before general
rules:
  - path_pattern: "docs/RESEARCH/FOUNDATIONS/**"    # Specific
    corpus: research_ai
  - path_pattern: "docs/RESEARCH/**"                # General fallback
    corpus: research_general

# WRONG: general rule shadows specific
rules:
  - path_pattern: "docs/RESEARCH/**"                # Catches everything
    corpus: research_general
  - path_pattern: "docs/RESEARCH/FOUNDATIONS/**"     # Never reached
    corpus: research_ai
```

### Available Corpus Types

| Corpus | Description | Use For |
|--------|-------------|---------|
| `core_kb` | Curated knowledge: patterns, theory, schema | Domain pattern docs, theory, canonical references |
| `deployment` | Operational artifacts | ADRs, session notes, architecture docs, CLAUDE.md |
| `published` | Published content | Blog posts, public docs |
| `research_ai` | AI/ML research | AI foundations, cognitive science, AI transformation |
| `research_general` | General research | Ad-hoc, unsorted, triage/staging |
| `ephemeral_*` | Temporary/experimental | Experiments, WIP (prefix with custom suffix) |

### Available Content Types

| Content Type | Description |
|-------------|-------------|
| `concept` | Theoretical/conceptual document |
| `pattern` | Domain pattern documentation |
| `architecture` | Architecture docs, topology |
| `adr` | Architecture Decision Record |
| `article` | General prose, blog post |
| `session_note` | Work log, decision provenance |

Content types are non-exhaustive — LLM classification may produce additional values.

### Adding a New Source

**Step-by-step:**

1. **Create the YAML config:**

   ```bash
   cp config/sources/semops-docs.yaml config/sources/my-new-source.yaml
   ```

2. **Edit the config:** Update `source_id`, `surface_id`, `name`, `github` settings, and `corpus_routing` rules.

3. **Validate with dry-run:**

   ```bash
   python scripts/ingest_from_source.py \
     --source my-new-source --dry-run
   ```

   Check: all files discovered, corpus assignments correct, no validation errors.

4. **Ingest:**

   ```bash
   # Without LLM (fast, title + metadata only)
   python scripts/ingest_from_source.py \
     --source my-new-source --no-llm

   # With LLM (slower, generates summaries + classification)
   python scripts/ingest_from_source.py \
     --source my-new-source
   ```

5. **Generate embeddings:**

   ```bash
   python scripts/generate_embeddings.py
   ```

   This only processes entities with NULL embeddings, so it's safe to run after any ingestion.

6. **Verify:**

   Run via your preferred database client:

   ```sql
   SELECT metadata->>'corpus', count(*) FROM entity GROUP BY 1 ORDER BY 2 DESC;
   ```

**Checklist:**

- [ ] `source_id` is unique kebab-case
- [ ] `github.base_path` matches the actual directory structure
- [ ] `include_directories` are relative to `base_path`
- [ ] `corpus_routing.rules` path patterns include `base_path` prefix
- [ ] More specific routing rules come before general ones
- [ ] `default_corpus` and `default_content_type` are set
- [ ] Dry-run shows correct entity count and corpus assignments

### Modifying an Existing Source

When you modify a source config, the downstream impact depends on what changed:

| Change | Action Required |
|--------|----------------|
| New `include_directories` or paths | Re-ingest source, generate embeddings for new entities |
| Changed `corpus_routing` rules | Re-ingest source (upsert updates metadata including corpus tag) |
| Changed `attribution` template | Re-ingest source |
| Changed `exclude_patterns` | Re-ingest source (may create new entities or leave removed ones in DB) |
| Changed `llm_classify` fields | Re-ingest with LLM (not `--no-llm`) |
| Changed `defaults` | Re-ingest source |

**Re-ingestion is safe.** The ingestion script uses `ON CONFLICT (id) DO UPDATE`, so re-running updates existing entities with new metadata, attribution, and filespec without creating duplicates. Entity IDs are derived from file paths, so the same file always produces the same ID.

**Embeddings after re-ingestion:** If metadata changed (e.g., new summary from LLM classification), re-generate embeddings:

```bash
# Regenerate all embeddings (not just missing)
python scripts/generate_embeddings.py --regenerate
```

**Removing entities:** Re-ingestion does not delete entities that are no longer in the source. To remove stale entities, use SQL directly via your preferred database client:

```sql
DELETE FROM entity WHERE id LIKE 'prefix-%' AND updated_at < '2026-01-31';
```

---

## Ingestion

### Running Ingestion

```bash
# Dry run — shows what would be ingested without touching the DB
python scripts/ingest_from_source.py \
  --source semops-docs --dry-run

# Ingest without LLM classification (fast, metadata from file only)
python scripts/ingest_from_source.py \
  --source semops-docs --no-llm

# Ingest with LLM classification (generates summaries, subject_area, etc.)
python scripts/ingest_from_source.py \
  --source semops-docs
```

### What `--no-llm` Skips

With `--no-llm`, entities get:

- Title (extracted from first heading or filename)
- Corpus and content_type (from routing rules)
- Word count, reading time, file format, size
- Attribution (from template)
- Filespec (URI, hash, format)

Without `--no-llm` (LLM enabled), entities additionally get:

- Summary
- Subject area classification
- Concept ownership analysis
- Broader/narrower concept mapping
- Quality score

**Recommendation:** Use `--no-llm` for initial bulk ingestion, then run a separate LLM classification pass for richer metadata.

### Current Sources

| Source | Config File | Entities | Chunks |
|--------|------------|----------|--------|
| `semops-docs` | `config/sources/semops-docs.yaml` | 61 | 1,523 |
| `semops-dx-orchestrator-domain-patterns` | `config/sources/semops-dx-orchestrator-domain-patterns.yaml` | 24 | 613 |
| `semops-publisher` | `config/sources/semops-publisher.yaml` | 117 | 1,793 |

---

## Embedding Generation

```bash
# Generate embeddings for entities that don't have them
python scripts/generate_embeddings.py

# Regenerate all embeddings
python scripts/generate_embeddings.py --regenerate

# Process a specific entity
python scripts/generate_embeddings.py \
  --entity-id semantic-compression

# Dry run
python scripts/generate_embeddings.py --dry-run
```

**Model:** OpenAI `text-embedding-3-small` (1536 dimensions). The same model is used at both ingestion (to embed entities and chunks) and query time (to embed the search query). Both sides must share the same vector space for cosine similarity scores to be meaningful.

**Embedding text:** Built from entity title + metadata (summary, content_type, subject_area, broader/narrower concepts). Richer metadata = better embeddings.

**When to regenerate:**

- After ingesting with LLM (new summaries improve embedding quality)
- After changing how `build_embedding_text()` works in `generate_embeddings.py`
- Not needed after re-ingestion if only corpus/attribution changed (embeddings use title + content metadata)

---

## Chunking

Ingestion automatically chunks each document by markdown headings and stores passages in the `document_chunk` table with entity_id foreign keys. Chunks get their own OpenAI embeddings (same model as entities) for passage-level retrieval.

**How it works:**
1. During ingestion, each file is split by markdown headings (##, ###, etc.)
2. Sections exceeding 512 tokens are split with 50-token overlap
3. Each chunk gets an OpenAI `text-embedding-3-small` embedding (1536d)
4. Chunks are stored with `entity_id` FK, `corpus`, `content_type`, and heading hierarchy

**No separate chunking step is needed.** Chunking happens automatically during `ingest_from_source.py`. The standalone `chunk_markdown_docs.py` script is deprecated.

---

## Graph Materialization

Ingestion automatically writes entity relationships to Neo4j from `detected_edges` metadata. For backfilling or rebuilding the graph from existing entities:

```bash
# Backfill graph from all entities with detected_edges
python scripts/materialize_graph.py

# Clear graph and rebuild
python scripts/materialize_graph.py --clear

# Dry run
python scripts/materialize_graph.py --dry-run
```

The graph contains Entity nodes (from ingested files) and Concept nodes (from detected edges), connected by typed relationships (EXTENDS, RELATED, etc.).

---

## Troubleshooting

### Database Connection

Scripts connect automatically via database connection environment variables configured in `.env`. Direct PostgreSQL access is available via the configured database connection.

**Error:** `connection refused`
**Cause:** Docker services not running, or `.env` missing database connection variables.
**Fix:** Start services with `python start_services.py --skip-clone` and verify `.env` has the database connection settings.

### Embedding Generation

**Error:** `OPENAI_API_KEY not set in environment`
**Fix:** The `.env` file has the key, but the script's `.env` loader may not pick it up. Export it explicitly:

```bash
export $(grep OPENAI_API_KEY .env)
```

### Ingestion

**Error:** `column "X" of relation "entity" does not exist`
**Cause:** Database schema doesn't match what the script expects.
**Fix:** Verify entity table structure by running `\d entity` via your preferred database client.

**All entities show status FAILED:**
**Cause:** First entity fails, then all subsequent fail with "current transaction is aborted". This is a single-transaction issue.
**Fix:** Fix the root cause of the first failure, then re-run.
