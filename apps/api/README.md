# graphflow-api

Thin FastAPI app for GraphFlow. Calls into `graphflow_core` and must not
contain business logic.

## Available endpoints (skeleton)

- `GET /healthz` - liveness probe.
- `GET /version` - reports installed API and core versions.

## Run locally

```bash
uv run uvicorn graphflow_api.main:app --reload
```
