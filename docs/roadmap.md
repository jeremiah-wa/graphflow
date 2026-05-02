# Roadmap

This roadmap is intentionally narrow. The aim is to reach a credible demo without trying to build the full long-term platform immediately.

## v0.1 - Local structured data to Neo4j MVP

Goal:

```text
CSV / JSON -> manifests -> graph objects -> Neo4j
```

Outcomes:

- A user can define a simple ontology.
- A user can define a structured source.
- A user can map records to nodes and relationships.
- A user can load the graph into Neo4j idempotently.
- The full demo can run locally.

Related issues:

- #1 Define MVP architecture and product scope
- #2 Bootstrap monorepo structure
- #3 Implement declarative manifest models
- #4 Build Neo4j graph sink
- #5 Implement CSV and JSON file ingestion
- #6 Implement structured data to graph mapping
- #14 Add Docker Compose development environment
- #15 Create end-to-end demo connector

## v0.2 - Hybrid NLP/LLM extraction and entity resolution

Goal:

```text
Text / documents -> fast extraction -> optional accurate extraction -> entity resolution -> graph
```

Outcomes:

- A user can process text chunks into candidate entities.
- A user can use optional LLM extraction for higher-accuracy cases.
- Hybrid routing can reduce unnecessary LLM calls.
- Simple entity resolution can link or flag candidate entities.
- Wikidata can optionally provide reference candidates.

Related issues:

- #7 Implement fast text-to-graph candidate extraction
- #8 Implement accurate LLM extraction mode
- #9 Implement hybrid extraction router
- #10 Add simple entity resolution
- #11 Add Wikidata lookup cache

## v0.3 - Web app demo and deployed showcase

Goal:

```text
Usable app -> upload/configure/run/review/load -> demo-ready product narrative
```

Outcomes:

- A user can create/open a project.
- A user can upload files.
- A user can view or edit manifests.
- A user can start and inspect pipeline runs.
- A user can review extraction candidates.
- A user can see graph load stats.

Related issues:

- #12 Build minimal FastAPI backend
- #13 Build minimal web app

## Later possibilities

Possible later releases:

### v0.4 - Source connector expansion

- REST API source support
- OpenAPI import
- dlt adapter
- Airbyte protocol compatibility exploration

### v0.5 - Graph database expansion

- Memgraph sink
- openCypher compatibility tests
- Destination capability matrix

### v0.6 - Better ontology import

- Existing Neo4j schema import
- JSON Schema import
- SHACL import/export
- OWL/RDF exploration

### v0.7 - Workflow integrations

- Dagster adapter
- Temporal worker
- MCP server

### v1.0 - First serious product release

- Stable manifest spec
- Stable CLI
- Stable local deployment
- Hosted demo
- Example connector library
- Clear license model

## Prioritisation rule

Prioritise the shortest path to a working graph-building loop:

```text
source -> manifest -> graph objects -> Neo4j -> demo
```

Defer anything that does not directly support that loop.
