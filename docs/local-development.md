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
# Install the workspace and dev tools
uv sync

# Set up pre-commit hooks (optional but recommended)
uv run pre-commit install

# Run all pre-commit checks manually
uv run pre-commit run --all-files

# Or run individual checks:
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

## Test categories

GraphFlow tests are grouped by what they need to run:

| Category | Marker | External services | Runs in CI |
| --- | --- | --- | --- |
| Unit | none | none | every push / PR |
| Integration | `@pytest.mark.integration` | Neo4j, Postgres, Redis | dedicated CI job with service containers |
| End-to-end | `@pytest.mark.e2e` | full compose stack incl. future apps | manual, documented below |

Typical commands:

```bash
# Unit tests (fast, no external services, default)
uv run pytest -q -m "not integration and not e2e"

# Integration tests (requires docker compose up -d)
uv run pytest -q -m integration

# End-to-end tests (run individually as they land)
uv run pytest -q -m e2e
```

CI mirrors this split: a `lint-types-tests` job runs the unit suite,
and a separate `integration-tests` job spins up Neo4j, Postgres, and
Redis as service containers and runs the integration suite. See
`.github/workflows/ci.yml`.

## Local development stack

The bundled `docker-compose.yml` starts the three infrastructure
services the v0.1 pipeline talks to today:

```text
neo4j      graph destination (port 7687, browser at 7474)
postgres   metadata / future API run state (port 5432)
redis      future worker queue (port 6379)
```

`apps/api`, `apps/worker`, and `apps/web` services will be added to the
compose file by the issues that introduce those apps (#11, #12, #13)
so the compose file stays in sync with real, testable code.

### One-time setup

```bash
cp .env.example .env
# Adjust ports or passwords in .env if they conflict with something else
```

### Start the stack

```bash
docker compose up -d
docker compose ps
```

Each service defines a health check; wait for all three to show
`healthy` before running integration tests.

### Smoke-test reachability

From a host shell, with the stack running and `.env` loaded into your
environment:

```bash
uv run pytest -q -m integration tests/integration/test_compose_stack.py
```

This verifies that:

- Neo4j accepts a Bolt session and executes `RETURN 1`
- Postgres accepts connections and executes `SELECT 1`
- Redis answers `PING`

The same tests run in CI via service containers.

### Exercise the Neo4j sink against the local stack

```bash
uv run graphflow graph ping examples/simple_csv
uv run graphflow load examples/simple_csv
```

Both commands read `NEO4J_PASSWORD` from the environment (`.env` or
shell export).

### Stop the stack

```bash
docker compose down        # preserves named volumes
docker compose down -v     # also removes neo4j/postgres/redis data
```

## Environment variables

`.env.example` is the source of truth. Copy it to `.env` and adjust as
needed. LLM keys are optional; v0.1 runs without paid APIs.

## Expected developer workflow

```bash
# Start local services
docker compose up -d

# Validate manifests and the data they point to
uv run graphflow config validate examples/simple_csv

# Read records from the source
uv run graphflow ingest examples/simple_csv

# Map records into graph objects and surface issues
uv run graphflow map examples/simple_csv

# Confirm Neo4j is reachable
uv run graphflow graph ping examples/simple_csv

# Load the whole pipeline into Neo4j
uv run graphflow load examples/simple_csv
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
