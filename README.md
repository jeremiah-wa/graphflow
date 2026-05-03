# GraphFlow

GraphFlow is a configurable, graph-native ingestion platform for turning files, APIs, and documents into knowledge graphs.

The long-term idea is an "Airbyte for graph databases": users define sources, schemas or ontologies, extraction strategies, entity-resolution rules, and graph destinations using declarative manifests. The v0.1 focus is deliberately narrower: prove the end-to-end loop from structured data to Neo4j using a self-hostable developer workflow.

## Product vision

GraphFlow should let a user:

1. Define or import a graph schema/ontology.
2. Connect a source such as a file, REST API, or document collection.
3. Choose an extraction mode: direct mapping, fast extraction, accurate extraction, or hybrid extraction.
4. Resolve and review entities.
5. Load the resulting graph into a graph database.
6. Inspect the run, costs, extracted entities, and graph-load summary.

## v0.1 goal

The first working slice is:

```text
CSV / JSON files
    -> declarative YAML manifests
    -> structured node/relationship mapping
    -> Neo4j graph sink
    -> repeatable local demo
```

This keeps the first milestone cheap, local-first, and achievable before adding LLM extraction or multiple graph database destinations.

## Planned capabilities

### v0.1 - Local structured data to Neo4j MVP

- Monorepo project skeleton
- Pydantic-based manifest models
- CSV and JSON ingestion
- Structured data to graph mapping
- Neo4j graph sink
- Docker Compose development environment
- End-to-end demo connector

### v0.2 - Hybrid NLP/LLM extraction

- Fast text-to-graph candidate extraction
- Accurate LLM extraction mode
- Hybrid routing with cost controls
- Simple entity resolution
- Optional Wikidata lookup cache

### v0.3 - Web app demo

- Minimal FastAPI backend
- Minimal web app
- Upload, configure, run, review, and load flow
- Demo-ready deployed showcase

## Repository structure

The intended monorepo shape is:

```text
apps/
  api/                 # FastAPI app
  cli/                 # Typer CLI
  worker/              # background/job runner
  web/                 # frontend web app

packages/
  graphflow_core/      # shared product/domain logic

examples/
  simple_csv/          # basic CSV to graph demo
  company_officers/    # denormalized CSV to normalized graph demo
  documents_to_graph/  # later document extraction demo

infra/
  docker/              # Docker and local development assets

docs/                  # product and technical documentation
```

The key rule is that business logic should live in `graphflow_core`, not inside `cli.py`, API routes, web handlers, or workflow adapters. This keeps the platform extensible for future layers such as MCP, Dagster, or Temporal.

## Manifest concept

GraphFlow is built around declarative manifests:

- `source.yaml` - where data comes from and how to read it
- `ontology.yaml` - what graph entities, relationships, properties, and identifiers are valid
- `pipeline.yaml` - how to parse, extract, resolve, map, and load data
- `connections.yaml` - local or environment-backed connection references

See [`docs/manifests.md`](docs/manifests.md) for examples.

## Documentation

- [Product scope](docs/product-scope.md)
- [Architecture](docs/architecture.md)
- [Manifest design](docs/manifests.md)
- [Local development](docs/local-development.md)
- [Roadmap](docs/roadmap.md)
- [First demo scenario](docs/demo-scenario.md)
- [Testing strategy](docs/testing-strategy.md)
- [Architecture decisions](docs/decisions/0001-mvp-architecture.md)

## Quick start

The repo is a `uv` workspace. To install and run the unit test suite:

```bash
uv sync
uv run ruff check .
uv run mypy
uv run pytest -q -m "not integration and not e2e"
uv run graphflow version
```

To also run the integration tests (Neo4j, Postgres, Redis), start the
bundled development stack first:

```bash
cp .env.example .env
docker compose up -d
uv run pytest -q -m integration
docker compose down -v
```

See [`docs/local-development.md`](docs/local-development.md) for details,
including which tests run where in CI.

## Try the demo

GraphFlow includes a complete end-to-end demo showing how to transform
denormalized CSV data into a knowledge graph:

```bash
# Start services and set password
docker compose up -d
export GRAPHFLOW_NEO4J_PASSWORD="your-local-password"

# Run the automated demo
./scripts/run_demo.sh  # or run_demo.ps1 on Windows

# Or run manually:
graphflow config validate examples/company_officers
graphflow ingest examples/company_officers --limit 5
graphflow map examples/company_officers
graphflow load examples/company_officers

# Query in Neo4j Browser (http://localhost:7474)
MATCH (p:Person)-[r:OFFICER_OF]->(c:Company)
RETURN p, r, c
```

The demo creates a graph of UK companies and their officers, demonstrating:
- Denormalized CSV → normalized graph transformation
- Idempotent loading (safe to re-run)
- Multiple node types from a single source
- Relationship extraction from foreign keys

See [`docs/demo-scenario.md`](docs/demo-scenario.md) for the full walkthrough.

## Current status

This repository is in early planning/bootstrapping. The monorepo skeleton
(core package and CLI/API/worker app skeletons with smoke tests and CI) is
in place. Subsequent issues add manifests, ingestion, mapping, and the
Neo4j sink.

## License

License not yet selected.

A likely future model is an open-source core for the protocol, manifests, connectors, and graph sink abstractions, with commercial features considered later if the product becomes viable.
