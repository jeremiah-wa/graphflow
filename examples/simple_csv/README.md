# simple_csv example connector

This connector demonstrates the v0.1 happy path: a small CSV is
ingested, mapped to a `Company` node label, and loaded into Neo4j.

Validate the manifests:

```bash
uv run graphflow config validate examples/simple_csv
```
