# graphflow_core

Core product logic for GraphFlow. Owns:

- Manifest models (`source`, `ontology`, `pipeline`, `connections`).
- Source and parser abstractions.
- Mapping engine (records -> graph nodes/relationships).
- Graph sink interfaces and the Neo4j implementation.
- Pipeline runner.

This package is consumed by `apps/cli`, `apps/api`, `apps/worker`, and any
future adapter (MCP, Dagster, Temporal). Interface layers must stay thin.

## Layout

```text
src/graphflow_core/   # package source
tests/unit/           # fast tests, no external services
tests/integration/    # tests that need Neo4j or other local services
tests/e2e/            # full pipeline tests via the public CLI
```

See [`docs/testing-strategy.md`](../../docs/testing-strategy.md) for the
minimum coverage expected per module.
