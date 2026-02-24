# Issue #58: Autonomous Experimentation Framework

> **Status:** Complete
> **Date:** 2025-12-01
> **Related Issue:** 

---

## Executive Summary

Implemented a minimal viable experimentation framework that enables Claude Code to autonomously test RAG configurations using Docker Compose. The framework uses slash commands for workflow automation, a PLAN.md for experiment definition, and PostgreSQL/pgvector (via Supabase) as the initial stack.

---

## Context

When developing semantic operations infrastructure, we need to:
- Test multiple RAG database types and embedding options
- Iterate quickly without polluting main branch or local environment
- Allow Claude Code to autonomously run experiments within subscription limits
- Maintain reproducibility through git-tracked results

The original proposal included complex hooks for git lifecycle events (onBranchSwitch, onCommit, onPullRequest), but Claude Code hooks don't support these events.

---

## Decision

Implemented a simplified layered approach:

1. **Slash Commands** (primary automation) - `/experiment` and `/experiment-cleanup` handle the full workflow
2. **PLAN.md** (experiment definition) - Simple markdown template defining what to test and requirements
3. **Docker Compose** (isolation) - Template connects to existing Supabase PostgreSQL with pgvector
4. **Stop Hook** (safety reminder) - Warns if experiment containers are still running when session ends

Deferred to future iterations:
- Neo4j, Qdrant, and hybrid stack templates
- `/experiment-stack` for multi-stack comparison
- GitHub Actions validation workflow
- Sentence-transformers local embeddings
- Docling integration

---

## Consequences

**Positive:**
- Simple, minimal implementation that works today
- Leverages existing Supabase stack (no new services needed)
- Git-tracked experiments with PLAN.md → RESULTS.md workflow
- Easy to extend with new stacks later

**Negative:**
- Only PostgreSQL/pgvector stack implemented initially
- Benchmark.py is scaffold only (TODOs for actual tests)
- No automated enforcement of RESULTS.md before PR

---

## Implementation

### Files Created

| File | Purpose |
|------|---------|
| `experiments/template/Dockerfile` | Python 3.11 benchmark container |
| `experiments/template/docker-compose.yml` | Connects to Supabase PostgreSQL |
| `experiments/template/benchmark.py` | Scaffold with connectivity tests |
| `experiments/template/PLAN.md` | Experiment definition template |
| `experiments/template/requirements.txt` | Python dependencies |
| `experiments/template/.env.example` | Environment variable template |
| `experiments/template/README.md` | Template usage guide |
| `experiments/README.md` | Framework documentation |
| `.claude/commands/experiment.md` | Main workflow slash command |
| `.claude/commands/experiment-cleanup.md` | Cleanup slash command |
| `.claude/settings.local.json` | Updated with docker permissions + Stop hook |

### Workflow

```
/experiment my-test
 ├── Create branch experiment/my-test
 ├── Copy template to experiments/my-test/
 ├── Read PLAN.md for requirements
 ├── Configure .env
 ├── Run docker compose up
 ├── Generate RESULTS.md
 └── Offer: PR, iterate, or discard

/experiment-cleanup my-test
 ├── docker compose down -v
 └── Optionally delete branch
```

---

## References

- [experiments/README.md](../../experiments/README.md) - Framework documentation
- [Commit 2366d68](https://github.com/timjmitchell/ike-semantic-ops/commit/2366d68) - Implementation commit

---

**End of Document**
