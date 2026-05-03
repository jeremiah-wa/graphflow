# ADR 0001: MVP architecture and product scope

- Status: Accepted
- Date: 2026-05-03
- Deciders: GraphFlow maintainers
- Related issue: #1
- Milestone: v0.1

## Context

GraphFlow aims to become a configurable, graph-native ingestion platform
("Airbyte for graph databases"). That long-term vision is too broad to build in
a single release. We need an explicit, narrow v0.1 architecture that:

- Proves the end-to-end loop from structured data to a Neo4j graph.
- Is local-first and does not require paid APIs.
- Establishes module boundaries that larger features (hybrid extraction, web
  app, additional sinks) can be layered onto later without rewrites.
- Keeps business logic out of interface layers (CLI, API, web, future MCP or
  workflow adapters).

## Decision

v0.1 is scoped to the loop:

```text
CSV / JSON -> declarative manifests -> graph objects -> Neo4j
```

### Module boundaries

The codebase is organised as a monorepo. Business logic lives in
`packages/graphflow_core`. Interface layers are thin wrappers.

```text
apps/
  api/                 # FastAPI app (thin; calls graphflow_core)
  cli/                 # Typer CLI (thin; calls graphflow_core)
  worker/              # background/job runner (thin; calls graphflow_core)
  web/                 # frontend (calls the API)

packages/
  graphflow_core/      # manifests, sources, parsers, mapping, sinks, runner

examples/
  simple_csv/          # v0.1 demo connector
  documents_to_graph/  # later document extraction demo (v0.2+)

infra/
  docker/              # Docker Compose and local development assets

docs/                  # product and technical documentation
```

`graphflow_core` owns, at minimum:

- **Manifest models** (`source`, `ontology`, `pipeline`, `connections`) as
  Pydantic v2 models.
- **Source/parser abstractions** for CSV and JSON file input.
- **Mapping engine** that converts parsed records into `GraphNode` and
  `GraphRelationship` objects according to the ontology and pipeline manifests.
- **Graph sink interface** plus a Neo4j implementation.
- **Pipeline runner** that composes: load manifests -> read source -> parse ->
  map -> validate -> write to sink -> emit run summary.
- **Validator** for duplicate keys, missing endpoints, and required properties.

### Core pipeline contract

```text
Source -> Parser -> (Extractor) -> (Entity Resolution) -> Mapper -> Validator -> Graph Sink
```

For v0.1, `Extractor` is `none` (direct structured mapping) and entity
resolution is exact-key only. The stages still exist as interfaces so v0.2 can
slot in fast/accurate/hybrid extraction and resolution strategies without
changing the runner contract.

### Graph sink

v0.1 targets Neo4j only, but the sink is defined by a `GraphSink` protocol so
future destinations (Memgraph, openCypher-compatible stores) can be added
without changing the mapper or runner.

Graph writes must be **idempotent by default** using `MERGE` with manifest-
declared node keys and relationship key strategies.

### Deployment

Local Docker Compose is the only supported v0.1 deployment target:

```text
api, worker, web, postgres, redis, neo4j
```

Kubernetes, Temporal, Dagster, and cloud-hosted SaaS are explicitly deferred.

## v0.1 non-goals

The following are explicitly out of scope for v0.1 and must not be added to
the critical path unless a later issue promotes them:

- Multi-graph database support (Memgraph, JanusGraph, RDF stores)
- LLM-based extraction (fast, accurate, hybrid)
- Entity resolution beyond exact key match
- Wikidata lookup / reference data integration
- OAuth connector builder, Airbyte protocol compatibility
- REST API / database-table / object-storage sources
- Full RDF / OWL / SHACL support
- Multi-tenant SaaS, billing, RBAC, SOC2
- Kubernetes-first deployment
- Temporal, Dagster, or MCP integrations
- Heavy graph visualisation

## First demo scenario

The v0.1 reference demo is `examples/simple_csv`: a small company-network CSV
is ingested via manifests and loaded into a local Neo4j instance, producing
`Company` and `Person` nodes joined by `OFFICER_OF` relationships. See
[`docs/demo-scenario.md`](../demo-scenario.md) for the full walkthrough.

## Consequences

Positive:

- Clear, testable module boundaries.
- Future extraction, resolution, and sink work can be added without breaking
  the core contract.
- Interface layers stay thin and swappable.
- The product can be demoed end-to-end from a laptop with no paid APIs.

Negative / trade-offs:

- Some interfaces (extractor, resolver) exist as thin seams in v0.1 and may
  look over-engineered until v0.2 fills them in. This is intentional.
- Choosing Neo4j as the only v0.1 sink means any portability guarantees for
  other graph databases are unverified until a second sink is built.

## Alternatives considered

- **Single-script MVP**: fastest path to a demo, but provides no foundation
  for hybrid extraction, web app, or additional sinks. Rejected.
- **Start with FastAPI + web app first**: would build UX before the core
  works. Rejected; UI is deferred to v0.3.
- **Adopt Dagster or Temporal immediately**: adds operational complexity
  before the core loop exists. Rejected; revisit in v0.7.
- **Support multiple graph databases from day one**: doubles sink work
  without proving the core loop. Rejected; revisit in v0.5.

## Revisit triggers

Revisit this ADR when any of the following happens:

- v0.1 demo is green and v0.2 extraction work starts.
- A second graph sink is proposed.
- The worker requires a real orchestrator.
- The web app requires direct access to core logic.
