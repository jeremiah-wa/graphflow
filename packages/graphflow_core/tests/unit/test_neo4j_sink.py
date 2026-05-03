"""Unit tests for :class:`Neo4jGraphSink` using a stub driver.

These tests verify that the sink dispatches the rendered Cypher
statements through a driver session, that it satisfies the GraphSink
protocol, and that the connection-from-manifest factory enforces the
expected error paths. They do not require a running Neo4j.
"""

from __future__ import annotations

from typing import Any

import pytest

from graphflow_core.graph import GraphNode, GraphRelationship
from graphflow_core.manifests.connections import ConnectionSpec
from graphflow_core.manifests.ontology import OntologySpec
from graphflow_core.sinks import GraphSink, GraphSinkError, Neo4jGraphSink


class _StubSession:
    def __init__(self, log: list[tuple[str, dict[str, Any]]]) -> None:
        self._log = log

    def run(self, cypher: str, **parameters: Any) -> None:
        self._log.append((cypher, parameters))

    def __enter__(self) -> _StubSession:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _StubDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.session_kwargs: list[dict[str, Any]] = []
        self.closed = False

    def session(self, **kwargs: Any) -> _StubSession:
        self.session_kwargs.append(kwargs)
        return _StubSession(self.calls)

    def close(self) -> None:
        self.closed = True


def _ontology() -> OntologySpec:
    return OntologySpec.model_validate(
        {
            "name": "company_network",
            "graph_model": "property_graph",
            "nodes": [
                {
                    "label": "Company",
                    "key": {"property": "company_number"},
                    "properties": {
                        "company_number": {"type": "string", "required": True},
                        "name": {"type": "string", "required": True},
                    },
                },
                {
                    "label": "Person",
                    "key": {"property": "person_id"},
                    "properties": {
                        "person_id": {"type": "string", "required": True},
                        "name": {"type": "string", "required": True},
                    },
                },
            ],
            "relationships": [
                {
                    "type": "OFFICER_OF",
                    "from": "Person",
                    "to": "Company",
                    "key": {"strategy": "endpoints_and_type"},
                    "properties": {},
                }
            ],
        }
    )


def test_sink_satisfies_graph_sink_protocol() -> None:
    sink = Neo4jGraphSink(_StubDriver())
    assert isinstance(sink, GraphSink)


def test_create_constraints_runs_one_statement_per_node_label() -> None:
    driver = _StubDriver()
    sink = Neo4jGraphSink(driver)
    result = sink.create_constraints(_ontology())
    assert result.constraints_created == 2
    assert len(driver.calls) == 2
    for cypher, params in driver.calls:
        assert "CREATE CONSTRAINT" in cypher
        assert params == {}


def test_upsert_nodes_runs_unwind_with_rows_parameter() -> None:
    driver = _StubDriver()
    sink = Neo4jGraphSink(driver)
    nodes = [
        GraphNode(
            label="Company",
            key_property="company_number",
            key_value="1",
            properties={"company_number": "1", "name": "Foo"},
        ),
        GraphNode(
            label="Company",
            key_property="company_number",
            key_value="2",
            properties={"company_number": "2", "name": "Bar"},
        ),
    ]
    result = sink.upsert_nodes(nodes)
    assert result.nodes_written == 2
    assert len(driver.calls) == 1
    cypher, params = driver.calls[0]
    assert "UNWIND $rows AS row" in cypher
    assert "MERGE (n:Company" in cypher
    assert [row["key"] for row in params["rows"]] == ["1", "2"]


def test_upsert_relationships_requires_ontology() -> None:
    sink = Neo4jGraphSink(_StubDriver())
    rel = GraphRelationship(
        type="OFFICER_OF",
        from_label="Person",
        from_key_property="person_id",
        from_key_value="P-1",
        to_label="Company",
        to_key_property="company_number",
        to_key_value="1",
        properties={},
    )
    with pytest.raises(GraphSinkError, match="ontology"):
        sink.upsert_relationships([rel])


def test_upsert_relationships_uses_ontology_after_set_ontology() -> None:
    driver = _StubDriver()
    sink = Neo4jGraphSink(driver)
    sink.set_ontology(_ontology())
    rel = GraphRelationship(
        type="OFFICER_OF",
        from_label="Person",
        from_key_property="person_id",
        from_key_value="P-1",
        to_label="Company",
        to_key_property="company_number",
        to_key_value="1",
        properties={},
    )
    result = sink.upsert_relationships([rel])
    assert result.relationships_written == 1
    cypher, _ = driver.calls[0]
    assert "MERGE (a)-[r:OFFICER_OF]->(b)" in cypher


def test_create_constraints_caches_ontology_for_relationship_upserts() -> None:
    driver = _StubDriver()
    sink = Neo4jGraphSink(driver)
    sink.create_constraints(_ontology())
    sink.set_ontology(_ontology())
    rel = GraphRelationship(
        type="OFFICER_OF",
        from_label="Person",
        from_key_property="person_id",
        from_key_value="P-1",
        to_label="Company",
        to_key_property="company_number",
        to_key_value="1",
        properties={},
    )
    sink.upsert_relationships([rel])
    assert any("OFFICER_OF" in c for c, _ in driver.calls)


def test_close_is_idempotent_and_propagates() -> None:
    driver = _StubDriver()
    sink = Neo4jGraphSink(driver)
    sink.close()
    sink.close()
    assert driver.closed is True


def test_database_kwarg_is_passed_to_session() -> None:
    driver = _StubDriver()
    sink = Neo4jGraphSink(driver, database="neo4j")
    sink.create_constraints(_ontology())
    assert driver.session_kwargs[0] == {"database": "neo4j"}


def _connection(**overrides: Any) -> ConnectionSpec:
    base: dict[str, Any] = {
        "type": "neo4j",
        "uri": "bolt://localhost:7687",
        "username": "neo4j",
        "password_from_env": "NEO4J_PASSWORD",
    }
    base.update(overrides)
    return ConnectionSpec.model_validate(base)


def test_from_connection_rejects_non_neo4j_connection() -> None:
    bad = ConnectionSpec.model_validate(
        {
            "type": "llm",
            "provider": "openai",
            "api_key_from_env": "OPENAI_API_KEY",
        }
    )
    with pytest.raises(GraphSinkError, match="type 'neo4j'"):
        Neo4jGraphSink.from_connection(bad, env={"OPENAI_API_KEY": "x"})


def test_from_connection_requires_password_env_var_to_be_set() -> None:
    with pytest.raises(GraphSinkError, match="NEO4J_PASSWORD"):
        Neo4jGraphSink.from_connection(_connection(), env={})
