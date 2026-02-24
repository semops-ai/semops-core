# ADR-0010: Database Connectivity Convention

> **Status:** Complete
> **Date:** 2026-02-09
> **Related Issue:** [](https://github.com/semops-ai/semops-core/issues/124)
> **Related ADRs:** ADR-0005 (Global Developer Configuration)

## Executive Summary

Standardize how scripts, agents, and consuming repos connect to the SemOps PostgreSQL instance. Expose PostgreSQL on host port 5434 (bypassing Supavisor pooler on 5432), introduce `SEMOPS_DB_*` environment variables, and centralize connection logic in a shared `scripts/db_utils.py` module.

## Context

### Problem

semops-core owns the local Supabase instance used as shared infrastructure across multiple repos. Agents and scripts could not reliably connect because:

1. **Port collision** — Supavisor (connection pooler) binds `localhost:5432`. The actual PostgreSQL container (`semops-hub-pg`) had no host port binding.
2. **Fragile workaround** — The container's Docker bridge IP (`172.24.0.4`) was hardcoded in 30+ locations across scripts, configs, and documentation.
3. **Duplicated code** — Six or more scripts each implemented their own `get_db_connection` with inconsistent defaults and error handling.
4. **Naming collision** — `POSTGRES_*` env vars serve double duty: docker-compose uses them to build the Supabase container, and scripts use them to connect. Changing one breaks the other.

### Constraints

- Supabase docker-compose owns `POSTGRES_*` vars and port 5432 — cannot change without forking upstream.
- Multiple repos need to connect (semops-core, semops-publisher, semops-data, etc.).
- Must work for both long-running services and quick one-off queries.
- Schema-level isolation needed for future ephemeral corpora.

## Decision

### 1. Direct PostgreSQL port (5434)

Add `127.0.0.1:5434:5432` port mapping to the Supabase `db` service. This is purely additive — Supabase internals continue using `db:5432` over the Docker network. Supavisor keeps `localhost:5432` and `localhost:6543`.

### 2. SEMOPS_DB_* environment convention

Introduce a new env var family for application-level database access:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SEMOPS_DB_HOST` | `localhost` | Database host |
| `SEMOPS_DB_PORT` | `5434` | Direct PostgreSQL port |
| `SEMOPS_DB_NAME` | `postgres` | Database name |
| `SEMOPS_DB_USER` | `postgres` | Database user |
| `SEMOPS_DB_PASSWORD` | (from `POSTGRES_PASSWORD`) | Database password |
| `SEMOPS_DB_SCHEMA` | `public` | PostgreSQL schema (for isolation) |

Resolution order: `SEMOPS_DB_*` > `POSTGRES_*` > hardcoded defaults. This provides a clean migration path — existing `POSTGRES_*` configs still work, but `SEMOPS_DB_*` takes precedence when set.

### 3. Shared connection module (scripts/db_utils.py)

Single module providing `get_db_connection` with:

- Env var resolution chain (above)
- `host == "db"` guard (redirects Docker internal DNS to localhost)
- `autocommit` parameter (MCP server requires this)
- `schema` parameter (sets `search_path` for schema isolation)
- `.env` file loader (existing vars take precedence)

### 4. Centralized credentials in ~/.bashrc

`SEMOPS_DB_*` vars are exported in `~/.bashrc` (same pattern as `GITHUB_TOKEN`). This means:

- Every repo, script, and agent inherits them automatically
- No per-repo `.env` duplication for database credentials
- `POSTGRES_*` stays in `semops-core/.env` for docker-compose

## Consequences

### Positive

- **Zero-config for consuming repos** — any repo can `import db_utils` or use the env vars directly
- **No more fragile IPs** — stable port mapping replaces dynamic container IPs
- **Single source of truth** — one module, one convention, one place to update credentials
- **Schema isolation ready** — `SEMOPS_DB_SCHEMA` enables ephemeral corpora without separate databases
- **Backwards compatible** — `POSTGRES_*` fallback means nothing breaks during migration

### Negative

- **Two env var families** — `POSTGRES_*` and `SEMOPS_DB_*` coexist, which could confuse newcomers
- **Submodule commit** — Port change lives in the Supabase submodule (sparse checkout), adding a commit to upstream's history

### Deferred

- **External Docker network** (`semops-infra` with DNS alias `semops-db`) — for cross-compose service discovery. Port 5434 solves the immediate problem; network is for future multi-compose scenarios.
- **Qdrant migration** (issue #125) — move vector search from pgvector to Qdrant with collection-per-corpus.

## Implementation

Completed in commit `2763b4a`:

- 11 scripts migrated to `db_utils.py`
- All `172.24.0.4` references removed (verified via grep)
- Documentation updated: CLAUDE.md, RUNBOOK.md, USER_GUIDE.md, ARCHITECTURE.md
- semops-dx-orchestrator PORTS.md and INFRASTRUCTURE.md updated (commit `032b328`)
