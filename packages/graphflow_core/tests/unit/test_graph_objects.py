"""Unit tests for :class:`GraphNode` and :class:`GraphRelationship`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from graphflow_core.graph import GraphNode, GraphRelationship, RecordProvenance


def _node(**overrides: object) -> GraphNode:
    base: dict[str, object] = {
        "label": "Company",
        "key_property": "company_number",
        "key_value": "00000001",
        "properties": {"name": "Example Holdings Ltd"},
    }
    base.update(overrides)
    return GraphNode.model_validate(base)


def _rel(**overrides: object) -> GraphRelationship:
    base: dict[str, object] = {
        "type": "OFFICER_OF",
        "from_label": "Person",
        "from_key_property": "person_id",
        "from_key_value": "P-1",
        "to_label": "Company",
        "to_key_property": "company_number",
        "to_key_value": "00000001",
        "properties": {"role": "director"},
    }
    base.update(overrides)
    return GraphRelationship.model_validate(base)


def test_graph_node_round_trips() -> None:
    node = _node()
    assert node.identity() == ("Company", "company_number", "00000001")
    assert node.properties == {"name": "Example Holdings Ltd"}


def test_graph_node_label_must_be_pascal_case() -> None:
    with pytest.raises(ValidationError):
        _node(label="company")


def test_graph_node_key_property_must_be_snake_case() -> None:
    with pytest.raises(ValidationError):
        _node(key_property="CompanyNumber")


def test_graph_node_key_value_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        _node(key_value="")


def test_graph_node_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _node(unknown="boom")


def test_graph_relationship_round_trips() -> None:
    rel = _rel()
    assert rel.from_identity() == ("Person", "person_id", "P-1")
    assert rel.to_identity() == ("Company", "company_number", "00000001")


def test_graph_relationship_type_must_be_screaming() -> None:
    with pytest.raises(ValidationError):
        _rel(type="officer_of")


def test_graph_relationship_endpoint_labels_must_be_pascal() -> None:
    with pytest.raises(ValidationError):
        _rel(from_label="person")


def test_graph_relationship_endpoint_key_values_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        _rel(to_key_value="")


def test_record_provenance_round_trips() -> None:
    prov = RecordProvenance(
        source_name="companies_csv",
        source_path="data/companies.csv",
        location="row 2",
    )
    node = _node(provenance=prov)
    assert node.provenance == prov
