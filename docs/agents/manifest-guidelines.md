# Manifest guidelines

GraphFlow manifests are the main product interface. They should be predictable, declarative, and easy to validate.

## Manifest files

The initial manifest set is:

```text
source.yaml
ontology.yaml
pipeline.yaml
connections.yaml
```

A reusable connector folder may contain all four files plus examples and tests:

```text
connectors/company_network/
  source.yaml
  ontology.yaml
  pipeline.yaml
  connections.example.yaml
  data/
  tests/
```

## General rules

- Always include a `version` field.
- Use explicit names for sources, ontologies, and pipelines.
- Prefer clear fields over magic inference.
- Avoid embedding secrets.
- Validate references across manifests.
- Keep defaults conservative.

## Naming conventions

Use snake_case for manifest names and field references:

```yaml
source:
  name: companies_csv
```

Use PascalCase for node labels:

```yaml
label: Company
```

Use SCREAMING_SNAKE_CASE for relationship types:

```yaml
type: OFFICER_OF
```

Use snake_case for properties:

```yaml
properties:
  company_number:
    type: string
```

## `source.yaml` conventions

Source manifests should describe reading data, not graph semantics.

Good:

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

Avoid mixing graph mapping into source manifests.

## `ontology.yaml` conventions

Ontology manifests should describe the valid graph model.

They should include:

- Node labels
- Relationship types
- Key properties
- Property names and types
- Required flags
- Optional aliases
- Optional reference ontology hints

Good:

```yaml
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
```

## `pipeline.yaml` conventions

Pipeline manifests should describe how data becomes graph objects.

They may include:

- Parsing mode
- Extraction mode
- Entity-resolution strategies
- Mapping rules
- Destination settings
- Cost limits
- Cache settings

Good:

```yaml
extraction:
  mode: none
```

Good for later hybrid extraction:

```yaml
extraction:
  mode: hybrid
  fast:
    confidence_threshold: 0.82
  accurate:
    max_cost_usd_per_run: 2.00
```

## `connections.yaml` conventions

Connections should reference environment variables for secrets.

Good:

```yaml
connections:
  neo4j_local:
    type: neo4j
    uri: bolt://localhost:7687
    username: neo4j
    password_from_env: NEO4J_PASSWORD
```

Bad:

```yaml
password: real-production-password
```

## Validation expectations

Manifest validation should catch:

- Unknown node labels
- Unknown relationship types
- Missing required fields
- Duplicate node keys
- Invalid property types
- Missing connection references
- Mapping references to fields that do not exist when schema is known
- Relationship endpoints that cannot be resolved

## Avoid YAML as a programming language

Do not add complex branching, loops, or procedural transformation logic to YAML.

If needed later, add Python hooks:

```yaml
hooks:
  pre_extract: "plugins.clean_text:clean"
  post_extract: "plugins.normalize_entities:normalize"
```

Hooks should be explicit, optional, and isolated from the core happy path.
