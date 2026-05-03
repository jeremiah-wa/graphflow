"""Unit tests for Cypher constraint rendering."""

from __future__ import annotations

from graphflow_core.manifests.ontology import OntologySpec
from graphflow_core.sinks.neo4j.cypher import render_constraint_statements


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
            "relationships": [],
        }
    )


def test_render_creates_one_unique_constraint_per_node() -> None:
    statements = render_constraint_statements(_ontology())
    cyphers = [s.cypher for s in statements]
    assert len(cyphers) == 2
    assert any("(n:Company)" in c and "n.company_number" in c for c in cyphers)
    assert any("(n:Person)" in c and "n.person_id" in c for c in cyphers)


def test_render_uses_if_not_exists_for_idempotency() -> None:
    statements = render_constraint_statements(_ontology())
    for stmt in statements:
        assert "CREATE CONSTRAINT" in stmt.cypher
        assert "IF NOT EXISTS" in stmt.cypher
        assert "IS UNIQUE" in stmt.cypher
        assert stmt.parameters == {}


def test_render_uses_stable_constraint_names() -> None:
    a = render_constraint_statements(_ontology())
    b = render_constraint_statements(_ontology())
    assert [s.cypher for s in a] == [s.cypher for s in b]
    assert "graphflow_unique_Company_company_number" in a[0].cypher
