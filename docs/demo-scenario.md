# First demo scenario

The v0.1 reference demo proves the GraphFlow loop end-to-end using only local
services and no paid APIs. It lives at `examples/simple_csv/`.

## Narrative

A user wants to build a small "company network" graph from a CSV export of
companies and their officers. They:

1. Point GraphFlow at two CSV files.
2. Describe the graph shape in an ontology manifest.
3. Describe how CSV rows become nodes and relationships in a pipeline manifest.
4. Run GraphFlow, which loads the graph into a local Neo4j instance
   idempotently.
5. Open Neo4j Browser and run a Cypher query that returns the expected graph.

## Inputs

Two CSV files under `examples/simple_csv/data/`:

- `companies.csv`
  - Columns: `company_number`, `company_name`, `company_status`
- `officers.csv`
  - Columns: `person_id`, `person_name`, `company_number`, `role`,
    `appointed_on`

## Manifests

Under `examples/simple_csv/`:

- `source.yaml` - declares two `file` sources of `format: csv`, one per CSV.
- `ontology.yaml` - declares `Company` and `Person` nodes plus an
  `OFFICER_OF` relationship from `Person` to `Company`.
- `pipeline.yaml` - extraction mode `none`, structured mapping from rows to
  nodes and relationships, Neo4j destination with `write_mode: merge`.
- `connections.yaml` - single `neo4j_local` connection reading credentials
  from environment variables.

See [`docs/manifests.md`](manifests.md) for the manifest shapes.

## Expected graph

After a successful run:

- `N` `Company` nodes keyed by `company_number`.
- `M` `Person` nodes keyed by `person_id`.
- `K` `OFFICER_OF` relationships with `role` and `appointed_on` properties.

Example verification Cypher:

```cypher
MATCH (p:Person)-[r:OFFICER_OF]->(c:Company)
RETURN p.name AS person, r.role AS role, c.name AS company
ORDER BY company, person
LIMIT 25;
```

## Expected developer workflow

```bash
# 1. Start local services (Neo4j at minimum)
docker compose up -d neo4j

# 2. Validate manifests
graphflow config validate examples/simple_csv

# 3. Check Neo4j connectivity
graphflow graph ping

# 4. Run the demo pipeline
graphflow run examples/simple_csv
```

A successful run must:

- Exit with status 0.
- Print a run summary with counts of nodes created/merged, relationships
  created/merged, and any validation warnings.
- Produce the same graph when re-run with unchanged inputs (idempotent).

## Success criteria

The demo is considered working when:

- Fresh checkout + `docker compose up -d neo4j` + `graphflow run
  examples/simple_csv` yields the expected Cypher result on the first run.
- Running the same command a second time yields the same result and reports
  zero new nodes/relationships created (merges only).
- Running with a deliberately malformed manifest fails fast with a clear
  validation error and writes nothing to Neo4j.
- An end-to-end test in CI exercises this flow against a Neo4j service
  container (see [`docs/testing-strategy.md`](testing-strategy.md)).

## Out of scope for the first demo

- Document / text extraction.
- LLM calls of any kind.
- REST API sources.
- Any graph database other than Neo4j.
- Web UI.
