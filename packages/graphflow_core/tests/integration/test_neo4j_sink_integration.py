"""Integration tests for :class:`Neo4jGraphSink` against a live Neo4j.

These tests are marked ``integration`` and skipped unless the
``GRAPHFLOW_NEO4J_URI`` env var is set, so the default test run stays
fast and external-service-free.

Run them locally against a Neo4j instance you have started separately
(for example, via ``docker compose up -d neo4j`` using the stack in
``docker-compose.yml``). Export the Bolt URI, username, and the name
of the env var that holds your password; the test code reads them
from the environment so this docstring does not contain any
credentials.

```bash
export GRAPHFLOW_NEO4J_URI=bolt://localhost:7687
export GRAPHFLOW_NEO4J_USERNAME=neo4j
export GRAPHFLOW_NEO4J_PASSWORD=...   # your local dev password
uv run pytest -m integration packages/graphflow_core
```

Each test runs against an isolated logical database name so they can
run in parallel if desired.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from graphflow_core.graph import GraphNode, GraphRelationship
from graphflow_core.manifests.ontology import OntologySpec
from graphflow_core.sinks import Neo4jGraphSink

pytestmark = pytest.mark.integration


def _neo4j_env() -> dict[str, str] | None:
    uri = os.environ.get("GRAPHFLOW_NEO4J_URI")
    password = os.environ.get("GRAPHFLOW_NEO4J_PASSWORD")
    if not uri or not password:
        return None
    return {
        "uri": uri,
        "username": os.environ.get("GRAPHFLOW_NEO4J_USERNAME", "neo4j"),
        "password": password,
    }


@pytest.fixture(scope="module")
def neo4j_driver() -> Iterator[Any]:
    env = _neo4j_env()
    if env is None:
        pytest.skip(
            "GRAPHFLOW_NEO4J_URI and GRAPHFLOW_NEO4J_PASSWORD must be set to run "
            "Neo4j integration tests"
        )
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(env["uri"], auth=(env["username"], env["password"]))
    try:
        yield driver
    finally:
        driver.close()


@pytest.fixture
def clean_run_label() -> str:
    """Unique label suffix per test so tests don't collide on a shared DB."""
    return f"GraphFlowTest{uuid.uuid4().hex[:8]}"


def _ontology_with_label(node_label: str, rel_type: str) -> OntologySpec:
    return OntologySpec.model_validate(
        {
            "name": "integration_ontology",
            "graph_model": "property_graph",
            "nodes": [
                {
                    "label": node_label,
                    "key": {"property": "key"},
                    "properties": {
                        "key": {"type": "string", "required": True},
                        "name": {"type": "string", "required": False},
                    },
                },
            ],
            "relationships": [
                {
                    "type": rel_type,
                    "from": node_label,
                    "to": node_label,
                    "key": {"strategy": "endpoints_and_type"},
                    "properties": {"role": {"type": "string"}},
                }
            ],
        }
    )


def _node(label: str, key: str, name: str) -> GraphNode:
    return GraphNode(
        label=label,
        key_property="key",
        key_value=key,
        properties={"key": key, "name": name},
    )


def _rel(label: str, rel_type: str, from_key: str, to_key: str) -> GraphRelationship:
    return GraphRelationship(
        type=rel_type,
        from_label=label,
        from_key_property="key",
        from_key_value=from_key,
        to_label=label,
        to_key_property="key",
        to_key_value=to_key,
        properties={"role": "director"},
    )


def _count_nodes(driver: Any, label: str) -> int:
    with driver.session() as session:
        record = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
        return int(record["c"])


def _count_rels(driver: Any, rel_type: str) -> int:
    with driver.session() as session:
        record = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS c").single()
        return int(record["c"])


def _drop(driver: Any, label: str, rel_type: str) -> None:
    with driver.session() as session:
        session.run(f"MATCH (n:{label}) DETACH DELETE n")
        constraint_name = f"graphflow_unique_{label}_key"
        session.run(f"DROP CONSTRAINT {constraint_name} IF EXISTS")
        # rel_type kept in signature for symmetry/future use.
        _ = rel_type


def test_create_constraints_is_idempotent(neo4j_driver: Any, clean_run_label: str) -> None:
    label = clean_run_label
    rel_type = "INTEG_REL"
    sink = Neo4jGraphSink(neo4j_driver)
    try:
        ontology = _ontology_with_label(label, rel_type)
        first = sink.create_constraints(ontology)
        second = sink.create_constraints(ontology)
        assert first.constraints_created == 1
        assert second.constraints_created == 1
    finally:
        _drop(neo4j_driver, label, rel_type)


def test_upsert_nodes_is_idempotent(neo4j_driver: Any, clean_run_label: str) -> None:
    label = clean_run_label
    rel_type = "INTEG_REL"
    sink = Neo4jGraphSink(neo4j_driver)
    try:
        ontology = _ontology_with_label(label, rel_type)
        sink.create_constraints(ontology)
        nodes = [_node(label, "1", "Foo"), _node(label, "2", "Bar")]
        sink.upsert_nodes(nodes)
        sink.upsert_nodes(nodes)  # re-run same input
        assert _count_nodes(neo4j_driver, label) == 2
    finally:
        _drop(neo4j_driver, label, rel_type)


def test_upsert_relationships_is_idempotent(neo4j_driver: Any, clean_run_label: str) -> None:
    label = clean_run_label
    rel_type = "INTEG_REL"
    sink = Neo4jGraphSink(neo4j_driver)
    try:
        ontology = _ontology_with_label(label, rel_type)
        sink.create_constraints(ontology)
        sink.upsert_nodes([_node(label, "1", "Foo"), _node(label, "2", "Bar")])
        rels = [_rel(label, rel_type, "1", "2")]
        sink.upsert_relationships(rels)
        sink.upsert_relationships(rels)  # re-run
        assert _count_rels(neo4j_driver, rel_type) == 1
    finally:
        _drop(neo4j_driver, label, rel_type)


def test_upsert_nodes_updates_existing_properties(neo4j_driver: Any, clean_run_label: str) -> None:
    label = clean_run_label
    rel_type = "INTEG_REL"
    sink = Neo4jGraphSink(neo4j_driver)
    try:
        ontology = _ontology_with_label(label, rel_type)
        sink.create_constraints(ontology)
        sink.upsert_nodes([_node(label, "1", "Foo")])
        sink.upsert_nodes([_node(label, "1", "Foo (renamed)")])
        with neo4j_driver.session() as session:
            record = session.run(f"MATCH (n:{label} {{key: '1'}}) RETURN n.name AS name").single()
            assert record["name"] == "Foo (renamed)"
    finally:
        _drop(neo4j_driver, label, rel_type)
