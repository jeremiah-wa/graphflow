# Local development

GraphFlow should start local-first. The initial development experience should require only Docker, Python, Node, and the GitHub repository.

## Prerequisites

Recommended tools:

- Python 3.11+
- Node.js 20+
- Docker Desktop
- Git
- GitHub CLI, optional

Future tooling choices may include:

- `uv` for Python packaging and environment management
- `ruff` for linting and formatting
- `pytest` for tests
- `pnpm` for the web app

## Intended local services

The v0.1 Docker Compose stack should include:

```text
api        FastAPI service
worker     background/job runner
web        frontend app
postgres   metadata and run state
redis      queue/cache, optional initially
neo4j      graph destination
```

## Environment variables

Example `.env` values:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=graphflow
POSTGRES_USER=graphflow
POSTGRES_PASSWORD=graphflow

REDIS_URL=redis://localhost:6379/0

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

OPENAI_API_KEY=
```

LLM keys should be optional. v0.1 should run without paid APIs.

## Expected developer workflow

Once implemented, the local workflow should look like:

```bash
# Start local services
docker compose up -d

# Validate manifests
graphflow config validate examples/simple_csv

# Check Neo4j connectivity
graphflow graph ping

# Run demo pipeline
graphflow run examples/simple_csv
```

## Development principles

- The CLI and API should call `graphflow_core` rather than duplicating logic.
- The local demo should run without external paid services.
- Neo4j should be the only graph database required for v0.1.
- The first demo should be small enough to run on a modest laptop.
- Cloud/Kubernetes deployment should be deferred until the core loop works locally.

## Testing approach

Initial tests should cover:

- Manifest validation
- CSV parsing
- JSON parsing
- Structured mapping
- Graph object validation
- Neo4j sink integration with Docker

Later tests should cover:

- Fast extraction output shape
- Accurate extraction output validation
- Hybrid routing decisions
- Entity-resolution decisions
- API endpoint behaviour
- Web app smoke tests
