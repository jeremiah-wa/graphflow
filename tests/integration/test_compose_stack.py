"""Infrastructure smoke tests for the docker-compose stack.

These tests verify that each service published by ``docker-compose.yml``
is reachable from the host and speaks its expected protocol. They are
marked ``integration`` and skipped unless the matching
``GRAPHFLOW_*`` env var is set, so the default unit-test run stays
external-service-free.

Run locally with::

    docker compose up -d
    # .env already sets the GRAPHFLOW_* variables
    uv run pytest -q -m integration tests/integration

In CI they run in a dedicated job that spins up the same three
services as GitHub Actions service containers (see
``.github/workflows/ci.yml``).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _skip_unless(env_var: str) -> str:
    value = os.environ.get(env_var)
    if not value:
        pytest.skip(f"{env_var} not set; skipping compose-stack integration test")
    return value


def test_neo4j_accepts_bolt_queries() -> None:
    uri = _skip_unless("GRAPHFLOW_NEO4J_URI")
    username = os.environ.get("GRAPHFLOW_NEO4J_USERNAME", "neo4j")
    password = _skip_unless("GRAPHFLOW_NEO4J_PASSWORD")

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        with driver.session() as session:
            record = session.run("RETURN 1 AS n").single()
            assert record is not None
            assert record["n"] == 1
    finally:
        driver.close()


def test_postgres_accepts_connections() -> None:
    dsn = _skip_unless("GRAPHFLOW_POSTGRES_DSN")

    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1


def test_redis_accepts_ping() -> None:
    url = _skip_unless("GRAPHFLOW_REDIS_URL")

    import redis

    client = redis.Redis.from_url(url)
    try:
        assert client.ping() is True
    finally:
        client.close()
