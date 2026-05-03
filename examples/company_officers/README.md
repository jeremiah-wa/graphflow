# Company Officers Demo

This example demonstrates GraphFlow's ability to ingest denormalized CSV data and build a knowledge graph of companies and their officers.

## Graph Model

**Nodes:**
- `Company` - UK registered companies
- `Person` - Company officers (directors, secretaries)

**Relationships:**
- `Person -[OFFICER_OF]-> Company` - Officer appointments with role and dates

## Data

The demo uses a single denormalized CSV file (`data/company_officers.csv`) containing:
- 4 companies (TechCorp Limited, Global Innovations PLC, DataFlow Systems Ltd, CloudBase Holdings)
- 5 people serving as officers
- 8 officer appointments

## Running the Demo

```bash
# Validate the connector configuration
graphflow config validate examples/company_officers

# Preview the data ingestion
graphflow ingest examples/company_officers --limit 5

# Run the mapping engine to see graph objects
graphflow map examples/company_officers

# Load into Neo4j (requires local Neo4j running)
export GRAPHFLOW_NEO4J_PASSWORD="your-password"
graphflow load examples/company_officers
```

## Expected Results

After loading, Neo4j should contain:
- 4 Company nodes
- 5 Person nodes  
- 8 OFFICER_OF relationships

The graph reveals:
- Sarah Johnson (P001) serves as director of both TechCorp and Global Innovations
- Emma Williams (P003) moved from TechCorp to DataFlow Systems
- Michael Chen (P002) served at both TechCorp and the now-dissolved CloudBase Holdings
