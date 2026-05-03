"""Unit tests for Cypher node-upsert rendering."""

from __future__ import annotations

from graphflow_core.graph import GraphNode
from graphflow_core.sinks.neo4j.cypher import render_node_upsert_statements


def _node(**overrides: object) -> GraphNode:
    base: dict[str, object] = {
        "label": "Company",
        "key_property": "company_number",
        "key_value": "1",
        "properties": {"company_number": "1", "name": "Foo"},
    }
    base.update(overrides)
    return GraphNode.model_validate(base)


def test_empty_input_returns_no_statements() -> None:
    assert render_node_upsert_statements([]) == []


def test_single_group_uses_unwind_with_rows_parameter() -> None:
    statements = render_node_upsert_statements([_node()])
    assert len(statements) == 1
    stmt = statements[0]
    assert "UNWIND $rows AS row" in stmt.cypher
    assert "MERGE (n:Company {company_number: row.key})" in stmt.cypher
    assert "SET n += row.props" in stmt.cypher
    assert stmt.parameters == {
        "rows": [{"key": "1", "props": {"company_number": "1", "name": "Foo"}}]
    }


def test_multiple_nodes_share_one_statement_per_label_key() -> None:
    statements = render_node_upsert_statements(
        [
            _node(key_value="1"),
            _node(key_value="2", properties={"company_number": "2", "name": "Bar"}),
        ]
    )
    assert len(statements) == 1
    rows = statements[0].parameters["rows"]
    assert [row["key"] for row in rows] == ["1", "2"]


def test_different_labels_produce_distinct_statements() -> None:
    statements = render_node_upsert_statements(
        [
            _node(label="Company"),
            _node(
                label="Person",
                key_property="person_id",
                key_value="P-1",
                properties={"person_id": "P-1", "name": "Alice"},
            ),
        ]
    )
    assert len(statements) == 2
    cyphers = [s.cypher for s in statements]
    assert any("(n:Company" in c for c in cyphers)
    assert any("(n:Person" in c for c in cyphers)
