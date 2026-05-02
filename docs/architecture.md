# Architecture

## Architectural principles

GraphFlow should be designed around a small graph-native core that can be operated through different interfaces.

Principles:

1. Keep business logic out of the CLI and API layer.
2. Make manifests the primary product interface.
3. Make graph loading idempotent by default.
4. Treat LLM extraction as optional and cost-controlled.
5. Keep v0.1 local-first and cloud-portable.
6. Prefer adapters over hard dependencies on heavy platforms.

## High-level architecture

```text
                 Web App
                   |
                 FastAPI
                   |
              graphflow_core
                   |
  +----------------+----------------+
  |                |                |
Sources         Extraction       GraphSink
  |                |                |
Files/APIs     Fast/LLM/Hybrid    Neo4j
```

## Runtime components

### `graphflow_core`

Shared Python package containing product logic:

- Config loading and validation
- Source abstractions
- Parsing abstractions
- Ontology models
- Extraction interfaces
- Entity-resolution interfaces
- Mapping engine
- Graph sink interfaces
- Pipeline runner
- Run metadata events

### CLI

The CLI should be a thin wrapper over `graphflow_core`.

Example future commands:

```bash
graphflow config validate examples/simple_csv
graphflow graph ping
graphflow ingest examples/simple_csv/data/companies.csv
graphflow run examples/simple_csv
```

### API

The API should expose project, upload, config validation, pipeline run, run status, and review endpoints. It should not contain core transformation logic.

### Worker

The worker should execute pipeline runs. In v0.1 this can be simple. Later it can be backed by Redis, Celery, Dramatiq, Temporal, Dagster, or cloud job runners.

### Web app

The web app should make manifests easier to create and operate. It should not be the only way to use the product.

## Core pipeline

```text
Source
  -> Parser
  -> Extractor
  -> Entity Resolution
  -> Mapper
  -> Validator
  -> Graph Sink
```

### Source

Reads data from files, APIs, object storage, or future connector frameworks.

### Parser

Turns raw source data into structured records or text chunks.

### Extractor

Produces candidate graph entities and relationships. Modes:

- `none`: direct structured mapping
- `fast`: local NLP/text extraction
- `accurate`: LLM-backed extraction
- `hybrid`: fast mode first, accurate mode only when needed

### Entity resolution

Links candidate entities to existing graph entities or external reference entities.

Initial strategies:

- Exact key match
- Normalized string match
- Optional Wikidata lookup

### Mapper

Maps records or extracted candidates to graph nodes and relationships using the ontology and pipeline manifests.

### Validator

Checks required properties, duplicate keys, missing endpoints, and invalid relationship types before loading.

### Graph sink

Writes graph objects to a destination database. v0.1 supports Neo4j only, but should define a destination interface that allows Memgraph later.

## Initial deployment model

v0.1 should use Docker Compose:

```text
api
worker
web
postgres
redis
neo4j
```

Kubernetes should be deferred until the product has a working demo and enough service complexity to justify it.

## Future adapters

The core package should make it possible to add:

- MCP server
- Dagster integration
- Temporal worker
- Airbyte-compatible source adapter
- dlt adapter
- Memgraph graph sink
- Cloud job runner
