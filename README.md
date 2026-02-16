# semops-core

[![GitHub](https://img.shields.io/badge/org-semops--ai-blue)](https://github.com/semops-ai)
[![Website](https://img.shields.io/badge/web-semops.ai-green)](https://semops.ai)

**The schema and infrastructure layer for SemOps** - implementing the "semantic operations" hypothesis in code.

## What is SemOps?

**Semantic Operations (SemOps)** is a framework for enabling both human and machine systems to collaborate effectively through shared semantic context.

The core thesis: **Shared semantic context enables better human+AI collaboration.**

SemOps implements three key hypotheses:
- **Strategic Data** - Data as strategic asset and AI accelerator
- **Symbiotic Architecture** - Applied DDD at organizational scale
- **Semantic Optimization** - Measuring and maintaining meaning as operational infrastructure

## This Repository

`semops-core` is the **schema owner and infrastructure provider** for the SemOps ecosystem. It contains:

- **Global DDD Schema** - Pattern as aggregate root, entity, edge, surface, delivery
- **UBIQUITOUS_LANGUAGE.md** - Canonical domain term definitions
- **Docker Infrastructure** - Supabase, Neo4j, Qdrant, n8n, Docling
- **Ingestion Pipelines** - Scripts for data capture and transformation
- **Domain Patterns** - Reusable semantic patterns (SKOS, PROV-O based)

### Role in the Architecture

```
semops-dx-orchestrator [PLATFORM/DX]
        │
        │  Owns: Process (how we work)
        │
        ▼
semops-core [SCHEMA/INFRASTRUCTURE]  ← This repo
        │
        │  Owns: Model (what we know)
        │  - Schema definitions
        │  - Knowledge graph
        │  - Infrastructure services
        │
        ├─────────────┬─────────────┐
        ▼             ▼             ▼
semops-publisher  semops-docs   semops-data
```

**Key insight:** This repo owns *model* (what we know) and *infrastructure* (shared services), while `semops-dx-orchestrator` owns *process* (how we work).

## Core Schema

The schema implements Domain-Driven Design with **Pattern as aggregate root**:

| Table | Purpose |
|-------|---------|
| **pattern** | Aggregate root - semantic structures with coherence guarantees |
| **entity** | Content artifacts (files, links) connected to patterns |
| **edge** | Typed relationships (PROV-O based predicates) |
| **surface** | Publication destinations / ingestion sources |
| **delivery** | Entity-to-surface publication records |

### Key Concepts

- **Pattern** - A bounded context with clear semantic boundaries, measurable for coherence
- **Provenance (1p/2p/3p)** - Whose semantic structure is this? (own/partnership/external)
- **SKOS relationships** - broader, narrower, related concepts
- **PROV-O predicates** - derived_from, version_of, cites

See [schemas/UBIQUITOUS_LANGUAGE.md](schemas/UBIQUITOUS_LANGUAGE.md) for complete definitions.

## Infrastructure Stack

All services run via Docker Compose:

| Service | Purpose |
|---------|---------|
| **Supabase Studio** | Database UI, API management |
| **PostgreSQL** | Primary database (via Supabase) |
| **Neo4j** | Graph database for patterns |
| **Qdrant** | Vector database for RAG |
| **n8n** | Workflow automation |
| **Docling** | Document processing (PDF, DOCX) |
| **Ollama** | Local LLM/embeddings |

See [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) for service details, health checks, and configuration.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/semops-ai/semops-core.git
cd semops-core

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start services
python start_services.py --skip-clone

# Initialize schema
source venv/bin/activate
python scripts/init_schema.py
```

**Service URLs:** Configure per your environment after starting Docker Compose.

## Documentation

### Architecture

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture and retrieval pipeline
- [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) - Services stack and configuration
- [docs/STRATEGIC_DDD.md](docs/STRATEGIC_DDD.md) - Capability registry and domain patterns
- [docs/domain-patterns/](docs/domain-patterns/) - Reusable semantic patterns

### Schema

- [schemas/UBIQUITOUS_LANGUAGE.md](schemas/UBIQUITOUS_LANGUAGE.md) - Domain term definitions
- [schemas/SCHEMA_REFERENCE.md](schemas/SCHEMA_REFERENCE.md) - Column specs, JSONB schemas, constraints
- [schemas/SCHEMA_CHANGELOG.md](schemas/SCHEMA_CHANGELOG.md) - Schema evolution history
- [schemas/SKOS_PROVO_MAPPING.md](schemas/SKOS_PROVO_MAPPING.md) - W3C standards mapping
- [schemas/phase2-schema.sql](schemas/phase2-schema.sql) - Current schema DDL

### Guides

- [docs/SEARCH_GUIDE.md](docs/SEARCH_GUIDE.md) - Query capabilities and search patterns
- [docs/INGESTION_GUIDE.md](docs/INGESTION_GUIDE.md) - Ingestion pipeline and source configuration

## W3C Standards

The schema implements W3C semantic web standards:

- **[SKOS](https://www.w3.org/TR/skos-reference/)** - Simple Knowledge Organization System for concept relationships
- **[PROV-O](https://www.w3.org/TR/prov-o/)** - Provenance Ontology for lineage tracking
- **Dublin Core** - Attribution metadata

## Related Repositories

| Repository | Role | Description |
|------------|------|-------------|
| [semops-dx-orchestrator](https://github.com/semops-ai/semops-dx-orchestrator) | Platform/DX | Process, global architecture |
| [semops-publisher](https://github.com/semops-ai/semops-publisher) | Publishing | Content workflow |
| [semops-docs](https://github.com/semops-ai/semops-docs) | Documents | Theory, framework docs |
| [semops-data](https://github.com/semops-ai/semops-data) | Product | Data eng utilities |
| [semops-sites](https://github.com/semops-ai/semops-sites) | Frontend | Websites, apps |

## Contributing

This is currently a personal project by Tim Mitchell. Contributions are welcome once the public release is complete.

## License

[TBD - License to be determined for public release]
