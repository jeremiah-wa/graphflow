# CLAUDE.md

This file provides project-specific instructions for Claude Code and other coding agents working in this repository.

## Project context

GraphFlow is a configurable, graph-native ingestion platform for turning files, APIs, and documents into knowledge graphs.

The long-term vision is an "Airbyte for graph databases", but the early MVP is intentionally narrow:

```text
CSV / JSON -> declarative manifests -> graph objects -> Neo4j
```

Do not overbuild the platform before the v0.1 loop works.

## Current product priorities

Prioritise work in this order:

1. Local structured data to Neo4j MVP.
2. Declarative manifest validation.
3. Idempotent graph mapping and loading.
4. End-to-end demo connector.
5. Hybrid text extraction only after the structured MVP works.
6. Web app only after the core and CLI are usable.

## Repository design rule

Business logic must live in `packages/graphflow_core`, not inside interface layers.

Interface layers should be thin wrappers:

- `apps/cli` calls `graphflow_core`
- `apps/api` calls `graphflow_core`
- `apps/worker` calls `graphflow_core`
- `apps/web` calls the API
- future MCP, Dagster, or Temporal adapters should call `graphflow_core`

## Intended repository structure

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

docs/                  # project documentation
```

## Engineering principles

- Keep the core simple and testable.
- Prefer typed Pydantic models over untyped dictionaries.
- Make pipeline runs deterministic and repeatable.
- Make graph writes idempotent by default.
- Validate before writing to Neo4j.
- Avoid paid APIs in the v0.1 happy path.
- Do not introduce Kubernetes, Temporal, Dagster, or LLM dependencies into the critical path for v0.1.
- Add escape hatches through clean interfaces, not hardcoded special cases.

## Manifest principles

GraphFlow is built around declarative manifests:

- `source.yaml` describes where data comes from.
- `ontology.yaml` describes the graph model.
- `pipeline.yaml` describes parse, extract, resolve, map, and load behaviour.
- `connections.yaml` describes named connection references and secret environment variables.

Manifest YAML should be declarative. Do not turn YAML into a programming language. If advanced procedural logic is required, design a future Python hook interface.

## v0.1 non-goals

Do not implement these unless an issue explicitly asks for them:

- Multi-tenant SaaS
- Billing
- Kubernetes deployment
- Full Airbyte compatibility
- OAuth connector builder
- Multiple graph database support
- Full RDF/OWL/SHACL support
- Full Wikidata dump import
- Production-grade entity resolution
- Temporal or Dagster integration
- Heavy graph visualisation

## Python guidance

Use modern Python practices:

- Python 3.11+
- Type hints for public functions
- Pydantic v2 for config/domain validation
- Small, focused modules
- Protocols/interfaces for pluggable components
- `pathlib.Path` instead of raw path strings where appropriate
- Explicit errors with useful messages

Prefer interfaces like:

```python
class GraphSink(Protocol):
    def create_constraints(self, ontology: OntologySpec) -> None: ...
    def upsert_nodes(self, nodes: list[GraphNode]) -> GraphWriteResult: ...
    def upsert_relationships(self, relationships: list[GraphRelationship]) -> GraphWriteResult: ...
```

## Testing guidance

Add tests for core behaviour whenever possible.

Prioritise tests for:

- Manifest loading and validation
- CSV/JSON parsing
- Record-to-graph mapping
- Duplicate node-key detection
- Orphan relationship detection
- Neo4j sink query generation or integration behaviour

Do not require paid API keys for tests.

## Documentation guidance

When adding or changing a major concept, update docs in `docs/`.

Useful docs:

- `docs/product-scope.md`
- `docs/architecture.md`
- `docs/manifests.md`
- `docs/local-development.md`
- `docs/roadmap.md`
- `docs/agents/`

## Commit and PR guidance

Keep changes small and reviewable.

Good PRs should include:

- What changed
- Why it changed
- How it was tested
- Linked issue
- Any follow-up work

Use conventional-style commit summaries where practical:

```text
Add manifest models
Implement Neo4j graph sink
Document local development workflow
```

## Agent workflow

When working as an agent:

1. Read `README.md`, `docs/roadmap.md`, and this file first.
2. Identify the relevant GitHub issue.
3. Keep the change scoped to that issue.
4. Prefer adding a small working slice over broad scaffolding.
5. Do not silently introduce new runtime dependencies.
6. Update docs if behaviour or architecture changes.
7. Leave clear TODOs only when tied to a follow-up issue.

## Safety and cost rules

- Never commit real secrets or API keys.
- Use environment variables for secrets.
- Keep LLM calls optional and cached.
- Include cost limits in accurate/hybrid extraction design.
- Avoid always-on cloud infrastructure in early development.
