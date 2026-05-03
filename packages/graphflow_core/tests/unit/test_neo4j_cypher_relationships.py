"""Unit tests for Cypher relationship-upsert rendering."""

from __future__ import annotations

from typing import Any

import pytest

from graphflow_core.graph import GraphRelationship
from graphflow_core.manifests.ontology import OntologySpec
from graphflow_core.sinks.neo4j.cypher import render_relationship_upsert_statements


def _ontology(strategy: str = "endpoints_and_type") -> OntologySpec:
    rel_key: dict[str, Any] = {"strategy": strategy}
    if strategy == "explicit_property":
        rel_key["property"] = "officer_id"
    return OntologySpec.model_validate(
        {
            "name": "company_network",
            "graph_model": "property_graph",
            "nodes": [
                {
                    "label": "Person",
                    "key": {"property": "person_id"},
                    "properties": {
                        "person_id": {"type": "string", "required": True},
                        "name": {"type": "string", "required": True},
                    },
                },
                {
                    "label": "Company",
                    "key": {"property": "company_number"},
                    "properties": {
                        "company_number": {"type": "string", "required": True},
                        "name": {"type": "string", "required": True},
                    },
                },
            ],
            "relationships": [
                {
                    "type": "OFFICER_OF",
                    "from": "Person",
                    "to": "Company",
                    "key": rel_key,
                    "properties": {"role": {"type": "string"}},
                }
            ],
        }
    )


def _rel(**overrides: Any) -> GraphRelationship:
    base: dict[str, Any] = {
        "type": "OFFICER_OF",
        "from_label": "Person",
        "from_key_property": "person_id",
        "from_key_value": "P-1",
        "to_label": "Company",
        "to_key_property": "company_number",
        "to_key_value": "1",
        "properties": {"role": "director"},
    }
    base.update(overrides)
    return GraphRelationship.model_validate(base)


def test_empty_returns_no_statements() -> None:
    assert render_relationship_upsert_statements([], _ontology()) == []


def test_endpoints_and_type_strategy_renders_basic_merge() -> None:
    statements = render_relationship_upsert_statements([_rel()], _ontology())
    assert len(statements) == 1
    cypher = statements[0].cypher
    assert "MATCH (a:Person {person_id: row.from_key})" in cypher
    assert "MATCH (b:Company {company_number: row.to_key})" in cypher
    assert "MERGE (a)-[r:OFFICER_OF]->(b)" in cypher
    assert "SET r += row.props" in cypher
    rows = statements[0].parameters["rows"]
    assert rows == [{"from_key": "P-1", "to_key": "1", "props": {"role": "director"}}]


def test_explicit_property_strategy_keys_on_named_property() -> None:
    rel = _rel(properties={"officer_id": "OFC-1", "role": "director"})
    statements = render_relationship_upsert_statements([rel], _ontology("explicit_property"))
    cypher = statements[0].cypher
    assert "MERGE (a)-[r:OFFICER_OF {officer_id: row.rel_key}]->(b)" in cypher
    rows = statements[0].parameters["rows"]
    assert rows[0]["rel_key"] == "OFC-1"
    # The keying property is stripped from the props dict so SET r += row.props
    # does not double-write it.
    assert rows[0]["props"] == {"role": "director"}


def test_unknown_relationship_type_is_an_error() -> None:
    rel = _rel(type="MISSING_REL")
    with pytest.raises(ValueError, match="not declared"):
        render_relationship_upsert_statements([rel], _ontology())


def test_multiple_types_produce_one_statement_per_type() -> None:
    onto = OntologySpec.model_validate(
        {
            "name": "company_network",
            "graph_model": "property_graph",
            "nodes": [
                {
                    "label": "Person",
                    "key": {"property": "person_id"},
                    "properties": {
                        "person_id": {"type": "string", "required": True},
                        "name": {"type": "string", "required": True},
                    },
                },
                {
                    "label": "Company",
                    "key": {"property": "company_number"},
                    "properties": {
                        "company_number": {"type": "string", "required": True},
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
                },
                {
                    "type": "WORKS_AT",
                    "from": "Person",
                    "to": "Company",
                    "key": {"strategy": "endpoints_and_type"},
                    "properties": {},
                },
            ],
        }
    )
    rels = [_rel(properties={}), _rel(type="WORKS_AT", properties={})]
    statements = render_relationship_upsert_statements(rels, onto)
    assert len(statements) == 2
    cyphers = [s.cypher for s in statements]
    assert any("MERGE (a)-[r:OFFICER_OF]->(b)" in c for c in cyphers)
    assert any("MERGE (a)-[r:WORKS_AT]->(b)" in c for c in cyphers)
