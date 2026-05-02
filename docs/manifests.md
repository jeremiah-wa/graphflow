# Manifest design

GraphFlow uses declarative manifests to describe how data becomes a graph.

The initial design separates manifests into four files:

```text
source.yaml       # where the data comes from
ontology.yaml     # what graph model is valid
pipeline.yaml     # how to parse, extract, resolve, map, and load
connections.yaml  # named connections and secret references
```

These files can later be packaged as a reusable "graph connector".

## Design goals

- Keep common use cases declarative.
- Avoid making YAML a programming language.
- Validate manifests with Pydantic models.
- Allow Python hooks later for advanced edge cases.
- Make manifests usable from CLI, API, UI, and future MCP/workflow integrations.

## `source.yaml`

The source manifest describes where data comes from and how to read it.

```yaml
version: "0.1"

source:
  name: companies_csv
  type: file
  format: csv
  path: data/companies.csv
  primary_key:
    - company_number
```

Future source types may include:

- `file`
- `folder`
- `rest_api`
- `object_storage`
- `database_table`
- `airbyte`
- `dlt`

## `ontology.yaml`

The ontology manifest describes valid node labels, relationship types, properties, identifiers, and optional external reference sources.

```yaml
version: "0.1"

ontology:
  name: company_network
  graph_model: property_graph

  nodes:
    - label: Company
      key:
        property: company_number
      properties:
        company_number:
          type: string
          required: true
        name:
          type: string
          required: true
        status:
          type: string
          required: false

    - label: Person
      key:
        property: person_id
      properties:
        person_id:
          type: string
          required: true
        name:
          type: string
          required: true

  relationships:
    - type: OFFICER_OF
      from: Person
      to: Company
      key:
        strategy: endpoints_and_type
      properties:
        role:
          type: string
        appointed_on:
          type: date
```

## `pipeline.yaml`

The pipeline manifest describes how the source should be processed.

```yaml
version: "0.1"

pipeline:
  name: company_network_pipeline

  source_ref: companies_csv
  ontology_ref: company_network

  extraction:
    mode: none

  mapping:
    nodes:
      - label: Company
        source: rows[]
        key:
          from_field: company_number
        properties:
          company_number: company_number
          name: company_name
          status: company_status

    relationships: []

  destination:
    type: neo4j
    connection_ref: neo4j_local
    write_mode: merge
    batch_size: 1000
```

## Hybrid extraction example

Hybrid extraction should run a cheap fast path first, then use accurate extraction only when configured rules are triggered.

```yaml
version: "0.1"

pipeline:
  name: documents_to_graph

  extraction:
    mode: hybrid

    fast:
      engine: gliner
      confidence_threshold: 0.82

    accurate:
      engine: llm_graph_transformer
      provider: openai
      model: gpt-4o-mini
      run_when:
        - fast_confidence_below: 0.82
        - relationship_missing: true
      max_cost_usd_per_run: 2.00
      cache:
        enabled: true
        key_strategy: chunk_hash_plus_ontology_hash
```

## `connections.yaml`

Connection manifests should reference environment variables instead of storing secrets directly.

```yaml
version: "0.1"

connections:
  neo4j_local:
    type: neo4j
    uri: bolt://localhost:7687
    username: neo4j
    password_from_env: NEO4J_PASSWORD

  openai_default:
    type: llm
    provider: openai
    api_key_from_env: OPENAI_API_KEY
```

## Future import formats

Native YAML should come first. Later imports may include:

- OpenAPI for API source bootstrapping
- JSON Schema for structured source schemas
- Existing Neo4j schema inspection
- SHACL for RDF-style validation
- OWL/RDF for semantic-web users
- User-provided seed entity CSVs
- Wikidata lookup/cache for reference candidates

## Escape hatches

Do not put complex procedural logic in YAML. Use Python hooks later for advanced cases:

```yaml
hooks:
  pre_extract: "plugins.clean_text:clean"
  post_extract: "plugins.normalize_entities:normalize"
  pre_load: "plugins.validate_graph:validate"
```
