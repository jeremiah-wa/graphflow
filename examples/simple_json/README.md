# simple_json example connector

A small JSON-array fixture mirroring `examples/simple_csv` for the
JSON ingestion path.

```bash
uv run graphflow config validate examples/simple_json
uv run graphflow ingest examples/simple_json
```
