# Changelog

All notable changes to GraphFlow are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-04

First public milestone: **Local structured data to Neo4j MVP**.

GraphFlow v0.1.0 can take a local CSV or JSON file, validate a declarative
manifest set, map records into a graph, and load the result idempotently
into a Neo4j instance started from the bundled Docker Compose stack.

### Added

- **Architecture and product scope** documented in `docs/` (#1).
- **Monorepo skeleton** with `packages/graphflow_core`, `apps/cli`, `apps/api`,
  `apps/worker`, `tests/`, and `examples/` (#2).
- **Declarative manifest models** (Pydantic): `SourceSpec`, `OntologySpec`,
  `PipelineSpec`, `ConnectionSpec`, a YAML connector loader, and
  `graphflow validate` CLI command (#3).
- **Neo4j graph sink** with Bolt connectivity, ontology-driven constraint
  and index creation, and idempotent batch node/relationship merges (#4).
- **CSV and JSON file ingestion** with parsed-record source metadata and
  example datasets under `examples/simple_csv/` and `examples/simple_json/`
  (#5).
- **Structured-to-graph mapping** with node, relationship, and property
  mapping, simple transforms (`trim`, `lower`, `hash`, `date_parse`), and
  pre-load validation for required properties, duplicate keys, and orphan
  relationships (#6).
- **Docker Compose development stack** (infrastructure services: Neo4j,
  Postgres, Redis) with integration tests that exercise each datastore
  from the host (#14, infra delivered by #27).
- **End-to-end demo connector** in `examples/company_officers/` that
  transforms denormalized UK company/officer CSV data into a normalized
  Neo4j graph, plus `scripts/run_demo.{ps1,sh}` automation, a CLI
  walkthrough in `docs/demo-scenario.md`, and a full E2E test
  (`tests/e2e/test_company_officers_demo.py`) wired into a dedicated
  `e2e-tests` CI job (#15).

### Package versions

- `graphflow-core` 0.1.0
- `graphflow-cli` 0.1.0
- `graphflow-api` 0.1.0 (skeleton; full API surface lands in v0.3)
- `graphflow-worker` 0.1.0 (skeleton; full worker lands post-v0.1)

### Known limitations

- `apps/api`, `apps/worker`, and `apps/web` ship as skeletons only.
  The `api`, `worker`, and `web` services are intentionally absent from
  `docker-compose.yml` until their apps gain runnable entrypoints
  (tracked in #28, #29, and #30).
- No extraction from unstructured text yet (tracked in v0.2: #7, #8, #9).
- No entity resolution beyond exact key matching in user-defined
  mappings (tracked in v0.2: #10, #11).

[0.1.0]: https://github.com/jeremiah-wa/graphflow/releases/tag/v0.1.0
