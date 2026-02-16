# Domain Patterns

Domain patterns are documented in `semops-dx-orchestrator`, which owns process documentation and cross-repo pattern definitions.

**Public repo:** [semops-dx-orchestrator/docs/domain-patterns](https://github.com/semops-ai/semops-dx-orchestrator/tree/main/docs/domain-patterns)

## Pattern Registry

The canonical pattern registry is the YAML manifest at [`schemas/pattern_v1.yaml`](https://github.com/semops-ai/semops-dx-orchestrator/blob/main/schemas/pattern_v1.yaml) in `semops-dx-orchestrator`.

## Schema Integration

Domain patterns are stored in the `pattern` table (see [UBIQUITOUS_LANGUAGE.md](../../schemas/UBIQUITOUS_LANGUAGE.md) and [SCHEMA_REFERENCE.md](../../schemas/SCHEMA_REFERENCE.md)) with SKOS relationships tracked via `pattern_edge`.

The capability registry in [STRATEGIC_DDD.md](../STRATEGIC_DDD.md) traces every system capability to the patterns it implements.
