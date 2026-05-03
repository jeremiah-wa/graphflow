# GraphFlow Demo: Company Officers Network

The v0.1 reference demo proves the GraphFlow pipeline end-to-end using only local
services and no paid APIs. Two demo connectors are provided:

- `examples/simple_csv/` - Basic single-CSV company data (existing)
- `examples/company_officers/` - Denormalized CSV with companies and officers (new)

## Company Officers Demo

The `company_officers` demo showcases GraphFlow's ability to extract a normalized
graph from denormalized tabular data.

### Narrative

A user has a single CSV export containing both company and person data in a
denormalized format (typical of business reports). They want to:

1. Point GraphFlow at the denormalized CSV file
2. Define the target graph schema (companies, people, relationships)
3. Map the flat rows to normalized nodes and relationships
4. Load the graph into Neo4j idempotently
5. Query the resulting network structure

### Input Data

One CSV file at `examples/company_officers/data/company_officers.csv`:

```csv
company_number,company_name,incorporated_on,company_status,jurisdiction,person_id,person_name,nationality,birth_year,officer_role,appointed_on,resigned_on
12345678,TechCorp Limited,2019-03-15,active,england-wales,P001,Sarah Johnson,British,1975,director,2019-03-15,
12345678,TechCorp Limited,2019-03-15,active,england-wales,P002,Michael Chen,American,1982,secretary,2019-03-15,2021-06-30
...
```

### Manifests

Under `examples/company_officers/`:

- `source.yaml` - Single CSV source with denormalized data
- `ontology.yaml` - Defines `Company` and `Person` nodes, `OFFICER_OF` relationships
- `pipeline.yaml` - Maps flat rows to both node types and relationships
- `connections.yaml` - Neo4j connection using environment variables

### Expected Graph

After loading:

- 4 `Company` nodes (TechCorp, Global Innovations, DataFlow Systems, CloudBase Holdings)
- 5 `Person` nodes (Sarah Johnson, Michael Chen, Emma Williams, James Anderson, Maria Garcia)
- 8 `OFFICER_OF` relationships with role and date properties

Key insights revealed by the graph:
- Sarah Johnson serves as director of multiple companies
- Officer movements between companies over time
- Active vs dissolved company status

### Running the Demo

```bash
# 1. Start the local development stack
docker compose up -d
# Wait for services to be healthy

# 2. Set Neo4j password (or copy .env.example to .env)
export GRAPHFLOW_NEO4J_PASSWORD="your-local-password"

# 3. Validate the connector configuration
graphflow config validate examples/company_officers

# 4. Preview data ingestion
graphflow ingest examples/company_officers --limit 5

# 5. Run mapping to see graph objects (dry run)
graphflow map examples/company_officers

# 6. Verify Neo4j connectivity
graphflow graph ping examples/company_officers

# 7. Load the graph into Neo4j
graphflow load examples/company_officers
```

### Verification Queries

After loading, open Neo4j Browser at http://localhost:7474 and run:

```cypher
// See all officer relationships
MATCH (p:Person)-[r:OFFICER_OF]->(c:Company)
RETURN p.name AS person, r.role AS role, c.name AS company, r.appointed_date
ORDER BY c.name, p.name;

// Find people with multiple directorships
MATCH (p:Person)-[r:OFFICER_OF {role: "director"}]->(c:Company)
WITH p, COUNT(c) AS companies
WHERE companies > 1
RETURN p.name AS director, companies
ORDER BY companies DESC;

// Company timeline
MATCH (c:Company)<-[r:OFFICER_OF]-(p:Person)
RETURN c.name AS company, c.status, 
       COLLECT({person: p.name, role: r.role, appointed: r.appointed_date}) AS officers
ORDER BY c.incorporation_date;
```

### Success Criteria

✓ The demo is working when:

1. **First run**: Creates 4 Company nodes, 5 Person nodes, 8 relationships
2. **Second run**: Reports 0 new nodes/relationships (idempotent merge)
3. **Validation**: Malformed manifests fail fast before any Neo4j writes
4. **CI**: E2E test exercises the full flow automatically

### What This Demo Proves

- **Denormalized → Normalized**: Single CSV to multi-node-type graph
- **Idempotent Loading**: Safe to re-run without duplicating data
- **Relationship Extraction**: Derives edges from foreign key fields
- **Local-First**: No cloud services or API keys required
- **Production Patterns**: Same manifest structure scales to real datasets

## Out of Scope for v0.1

- Text/document extraction (v0.2)
- LLM-powered mapping suggestions (v0.2)
- REST API sources (v0.2)
- Multi-source joins within one pipeline
- Web UI (v0.3)
