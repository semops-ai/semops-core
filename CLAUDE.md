# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role in Global Architecture

**Role:** Schema/Infrastructure (Model Owner)

```
semops-core [SCHEMA/INFRASTRUCTURE]
        │
        ├── Owns: Model (what we know)
        │   - Global DDD schema (Pattern as aggregate root)
        │   - UBIQUITOUS_LANGUAGE.md definitions
        │   - Knowledge graph and patterns
        │   - RAG pipeline infrastructure
        │
        └── Coordinates with: semops-dx-orchestrator [PLATFORM/DX]
            - Owns: Process (how we work)
            - Global architecture, cross-repo coordination
```

**Key Ownership Boundary:**

- This repo owns **model** - schema definitions, domain patterns, knowledge graph
- `semops-dx-orchestrator` owns **process** - workflow documentation, global architecture docs

## Core Schema Foundation

This project implements a **Domain-Driven Design (DDD) schema** based on W3C standards:

- **[schemas/UBIQUITOUS_LANGUAGE.md](schemas/UBIQUITOUS_LANGUAGE.md)** - Canonical definitions of Pattern, Entity, Edge, Surface, Delivery
- **[schemas/phase2-schema.sql](schemas/phase2-schema.sql)** - PostgreSQL schema with SKOS and PROV-O support
- **[schemas/SCHEMA_CHANGELOG.md](schemas/SCHEMA_CHANGELOG.md)** - Schema evolution history

**Schema changes are high-impact** and affect all connected SemOps repositories. Always review the ubiquitous language before modifying schemas.

## Development Environment

**Services Stack:**
- **Supabase** (PostgreSQL + PostgREST + Auth + Storage + Studio)
- **pgvector** for RAG embeddings
- **Docling** (document processing)
- **Neo4j** (graph database)
- **Qdrant** (vector storage)
- **n8n** (workflow automation)
- **Ollama** (local LLM/embeddings)

**Starting Services:**
```bash
python start_services.py --skip-clone
```

**Service URLs:** Configure per your environment. See [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) for service descriptions.

## Key Files

- [schemas/UBIQUITOUS_LANGUAGE.md](schemas/UBIQUITOUS_LANGUAGE.md) - Domain term definitions
- [schemas/phase2-schema.sql](schemas/phase2-schema.sql) - Current schema
- [schemas/SCHEMA_REFERENCE.md](schemas/SCHEMA_REFERENCE.md) - Column specs, JSONB schemas, constraints
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture and retrieval pipeline
- [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) - Services stack and configuration
- [docs/STRATEGIC_DDD.md](docs/STRATEGIC_DDD.md) - Capability registry and domain patterns
- [docker-compose.yml](docker-compose.yml) - Infrastructure stack

## Before Schema Changes

1. Read [schemas/UBIQUITOUS_LANGUAGE.md](schemas/UBIQUITOUS_LANGUAGE.md)
2. Review [schemas/phase2-schema.sql](schemas/phase2-schema.sql)
3. Create GitHub issue for discussion
4. Update SCHEMA_CHANGELOG.md with changes
5. Consider impact on connected repositories
