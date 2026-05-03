# Testing strategy

GraphFlow is infrastructure-shaped: manifests in, graph writes out. Regressions
are expensive once users trust their pipelines. This document defines the v0.1
test strategy across unit, integration, and end-to-end (E2E) layers, the
minimum coverage each v0.1 module must ship with, and what CI must run.

## Test layers

### Unit tests

- Scope: a single module or function, no network, no Docker, no filesystem
  beyond temporary paths and committed fixtures.
- Tooling: `pytest`, `pytest-asyncio` where relevant, `pydantic` validation
  errors asserted directly.
- Speed target: whole unit suite under 10 seconds locally.
- Must be runnable with `pytest packages/graphflow_core/tests/unit` (or
  equivalent once the package exists).

### Integration tests

- Scope: two or more modules composed together, or a single module against a
  real external service started locally.
- Allowed dependencies: Neo4j (via Docker or service container), local
  Postgres/Redis only if a test truly needs them.
- Must never depend on paid APIs.
- Speed target: whole integration suite under 2 minutes locally.
- Marked with a `pytest` marker (e.g. `@pytest.mark.integration`) so they can
  be selected or skipped.

### End-to-end (E2E) tests

- Scope: the full `graphflow run <example>` path, from manifests on disk to
  data in Neo4j, driven through the public CLI entry point.
- Must use the committed `examples/simple_csv/` demo as the canonical fixture.
- Must assert both *what* ends up in Neo4j (via Cypher queries) and
  idempotency on a second run.
- Marked with `@pytest.mark.e2e`.

## Minimum v0.1 module expectations

Every v0.1 module must ship with at least the tests listed below before the
module is considered "done" for the milestone.

### `graphflow_core.manifests`

- Unit: valid `source`, `ontology`, `pipeline`, `connections` manifests load
  into Pydantic models.
- Unit: invalid manifests raise `ValidationError` with a field-specific
  message (missing required field, wrong type, unknown node label
  referenced).
- Unit: cross-manifest references resolve (`pipeline.source_ref` matches a
  declared source; `pipeline.ontology_ref` matches the ontology name).

### `graphflow_core.sources` (CSV and JSON)

- Unit: CSV parser yields one record per data row, preserves column names,
  handles quoted fields and UTF-8.
- Unit: JSON parser handles both a top-level array and newline-delimited
  JSON.
- Unit: missing file, empty file, and malformed rows produce actionable
  errors.

### `graphflow_core.mapping`

- Unit: records map to `GraphNode` objects with the correct label, key, and
  declared properties.
- Unit: duplicate node keys within a batch are detected and reported.
- Unit: a relationship whose endpoint refers to a missing node key is
  flagged as an orphan.
- Unit: relationships inherit `from`/`to` labels from the ontology and fail
  fast if the record violates them.

### `graphflow_core.sinks.neo4j`

- Unit: query builder emits `MERGE` statements keyed by the declared node
  key and relationship strategy; parameters are bound, not interpolated.
- Unit: `create_constraints` produces one uniqueness constraint per node
  key declared in the ontology.
- Integration (Neo4j required): `upsert_nodes` and `upsert_relationships`
  write the expected data and are idempotent on re-run.
- Integration: a `ping` / connectivity check returns a clear error for bad
  credentials or unreachable host without leaking secrets.

### `graphflow_core.runner`

- Unit: runner wires source -> parser -> mapper -> validator -> sink in
  order and short-circuits on validator errors.
- Unit: a validation error prevents any sink write (no partial loads).
- Unit: the runner emits a structured run summary with node/relationship
  counts.

### `apps.cli`

- Unit: `graphflow config validate` returns non-zero and prints a helpful
  message on invalid manifests.
- Unit: `graphflow run` delegates to `graphflow_core` and does not contain
  business logic.

## E2E scope for the structured-data -> Neo4j flow

A single canonical E2E test is required for v0.1. It must:

- Use `examples/simple_csv/` as the fixture.
- Start (or connect to) a Neo4j instance via Docker or a CI service
  container.
- Run `graphflow run examples/simple_csv` through the public CLI entry
  point.
- Assert, via Cypher, that:
  - Every input `Company` row produced exactly one `Company` node.
  - Every input `Person` row produced exactly one `Person` node.
  - Every input officer row produced exactly one `OFFICER_OF`
    relationship with the expected `role` and `appointed_on`.
  - Uniqueness constraints exist for each declared node key.
- Re-run the same command and assert:
  - Zero new nodes or relationships are created.
  - Node and relationship counts are unchanged.
- Run a negative case with a deliberately broken manifest and assert:
  - CLI exits non-zero.
  - No writes occurred in Neo4j.

This E2E test is the sign-off gate for v0.1.

## CI expectations

Every pull request must run, at minimum:

- `ruff` (lint + format check).
- `mypy` (or equivalent type check) on `packages/graphflow_core`.
- The full unit test suite.
- The Neo4j-backed integration suite, using a Neo4j service container in
  GitHub Actions.
- The single E2E demo test described above.

Additional rules:

- Tests must not require paid API keys. Any LLM-dependent tests (v0.2+)
  must be skipped by default in CI unless an explicit opt-in flag and
  secret are present.
- The E2E test must block merges if it fails.
- CI must fail if a new module is added under `packages/graphflow_core`
  without a corresponding `tests/` directory.
- Coverage is tracked but not gated in v0.1; a coverage threshold may be
  introduced once the module set stabilises.

## Out of scope for v0.1 testing

- Load and performance testing.
- Property-based / fuzz testing of manifests (may be added in v0.2).
- Visual regression tests for the web app (web UI is v0.3).
- Multi-sink compatibility tests (only Neo4j exists in v0.1).
