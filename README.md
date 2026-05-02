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
  simple_csv/          # structured data demo
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

## Current status

This repository is in early planning/bootstrapping. The initial GitHub issues describe the first MVP epics and features.

## License

License not yet selected.

A likely future model is an open-source core for the protocol, manifests, connectors, and graph sink abstractions, with commercial features considered later if the product becomes viable.
