# Product scope

## One-liner

GraphFlow is a configurable graph-native ingestion platform for turning files, APIs, and documents into knowledge graphs.

## Target user

The initial target user is a technical builder who understands data pipelines and wants a repeatable way to build graph datasets without hand-writing every ingestion, extraction, mapping, entity-resolution, and graph-load step.

Likely early users:

- Data engineers
- Analytics engineers
- ML engineers
- Technical analysts
- Knowledge graph builders
- GraphRAG experimenters

## Product wedge

The full market vision is broad: an "Airbyte for graph databases". The MVP should not try to solve the whole vision immediately.

The wedge is:

1. Graph-native mapping and loading.
2. Declarative manifests for source, ontology, and pipeline behaviour.
3. Hybrid extraction strategy: cheap fast mode first, accurate LLM mode only when needed.
4. Entity-resolution hooks that can combine local graph state, deterministic keys, aliases, and external reference data.
5. Developer-first self-hostable workflow.

## v0.1 scope

v0.1 proves this flow:

```text
CSV / JSON
  -> source manifest
  -> ontology manifest
  -> pipeline manifest
  -> graph objects
  -> Neo4j
```

### In scope

- Monorepo setup
- Core Python package
- CLI skeleton
- FastAPI skeleton
- Worker skeleton
- Web placeholder
- Pydantic manifest models
- CSV and JSON ingestion
- Declarative structured mapping
- Neo4j graph sink
- Docker Compose local stack
- End-to-end demo connector

### Out of scope

- Multi-graph database support
- Production SaaS hosting
- OAuth connector builder
- Full Airbyte compatibility
- Full RDF/OWL/SHACL support
- Full entity-resolution engine
- Temporal or Dagster integration
- Billing, teams, RBAC, or SOC2 controls
- Kubernetes-first deployment
- Large-scale Wikidata import

## v0.2 scope

v0.2 adds text/document intelligence:

- Fast extraction mode
- Accurate LLM extraction mode
- Hybrid extraction router
- Simple deterministic entity resolution
- Optional Wikidata candidate lookup cache
- Cost tracking and caching

## v0.3 scope

v0.3 wraps the working core in a demo-ready app:

- Project management UI
- Upload/source configuration UI
- Ontology and pipeline config editor
- Run status and logs
- Extraction review table
- Graph load summary
- Deployed showcase

## Non-goals for early MVP

GraphFlow should not begin as a general-purpose workflow orchestrator, full ETL platform, or graph visualisation product. The first goal is to prove a narrow graph-construction loop that is configurable, repeatable, and easy to demo.
