# Local development

GraphFlow should start local-first. The initial development experience should require only Docker, Python, Node, and the GitHub repository.

## Prerequisites

Required tools:

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for Python packaging and the workspace
- Git

Optional tools (needed later):

- Docker Desktop (for Neo4j and the full Compose stack)
- Node.js 20+ and `pnpm` (for the v0.3 web app)
- GitHub CLI

The repo currently uses:

- `uv` workspaces for the Python monorepo
- `ruff` for lint and format
- `mypy` for type checking
- `pytest` for tests

## Install and run

```bash
# Install the workspace and dev tools into a local .venv
uv sync

# Lint and format check
uv run ruff check .
uv run ruff format --check .

# Type check
uv run mypy

# Unit tests (fast, no external services)
uv run pytest -q -m "not integration and not e2e"

# Try the CLI skeleton
uv run graphflow version

# Validate the bundled example connectors
uv run graphflow config validate examples/simple_csv
uv run graphflow config validate examples/simple_json

# Read records from a connector source
uv run graphflow ingest examples/simple_csv
uv run graphflow ingest examples/simple_json --limit 0

# Map records into graph objects and surface validation issues
uv run graphflow map examples/simple_csv
uv run graphflow map examples/simple_json --show-issues
```

## Loading into Neo4j

The Neo4j graph sink lives in `graphflow_core.sinks.neo4j`. The CLI
exposes two commands that talk to a real Neo4j:

```bash
# Verify the connection declared in connections.yaml
$env:NEO4J_PASSWORD = "graphflow"
uv run graphflow graph ping examples/simple_csv

# Parse, map, and load the connector into Neo4j
uv run graphflow load examples/simple_csv
```

A single Docker container is enough for local development:

```bash
docker run --rm -d --name gf-neo4j -p 7687:7687 -p 7474:7474 `
    -e NEO4J_AUTH=neo4j/graphflow neo4j:5
```

Then run the sink integration tests against it:

```bash
$env:GRAPHFLOW_NEO4J_URI = "bolt://localhost:7687"
$env:GRAPHFLOW_NEO4J_USERNAME = "neo4j"
$env:GRAPHFLOW_NEO4J_PASSWORD = "graphflow"
uv run pytest -q -m integration packages/graphflow_core
```

CI excludes `integration` and `e2e` tests by default; they run only
when the `GRAPHFLOW_NEO4J_*` env vars are set.

Integration and E2E tests are marked with `@pytest.mark.integration` and
`@pytest.mark.e2e`. They will require Neo4j (and possibly other services)
once the corresponding modules land; see
[`docs/testing-strategy.md`](testing-strategy.md).

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
