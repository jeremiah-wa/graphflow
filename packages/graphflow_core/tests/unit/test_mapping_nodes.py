"""Unit tests for :func:`map_record_to_node`."""

from __future__ import annotations

from typing import Any

from graphflow_core.manifests.ontology import NodeSpec
from graphflow_core.manifests.pipeline import NodeMapping
from graphflow_core.mapping import map_record_to_node
from graphflow_core.sources.base import ParsedRecord


def _node_spec(**overrides: Any) -> NodeSpec:
    base: dict[str, Any] = {
        "label": "Company",
        "key": {"property": "company_number"},
        "properties": {
            "company_number": {"type": "string", "required": True},
            "name": {"type": "string", "required": True},
            "status": {"type": "string", "required": False},
            "founded": {"type": "integer", "required": False},
        },
    }
    base.update(overrides)
    return NodeSpec.model_validate(base)


def _node_mapping(**overrides: Any) -> NodeMapping:
    base: dict[str, Any] = {
        "label": "Company",
        "source": "rows[]",
        "key": {"from_field": "company_number"},
        "properties": {
            "company_number": "company_number",
            "name": "company_name",
            "status": "company_status",
            "founded": "founded_year",
        },
    }
    base.update(overrides)
    return NodeMapping.model_validate(base)


def _record(**overrides: Any) -> ParsedRecord:
    base: dict[str, Any] = {
        "data": {
            "company_number": "00000001",
            "company_name": "Example Holdings Ltd",
            "company_status": "active",
            "founded_year": "1999",
        },
        "source_name": "companies_csv",
        "source_path": "data/companies.csv",
        "source_format": "csv",
        "row_index": 0,
        "location": "row 2",
    }
    if "data" in overrides:
        base["data"] = {**base["data"], **overrides.pop("data")}
    base.update(overrides)
    return ParsedRecord.model_validate(base)


def test_maps_happy_path() -> None:
    node, issues = map_record_to_node(_record(), _node_mapping(), _node_spec())
    assert issues == []
    assert node is not None
    assert node.label == "Company"
    assert node.key_value == "00000001"
    assert node.properties == {
        "company_number": "00000001",
        "name": "Example Holdings Ltd",
        "status": "active",
        "founded": 1999,
    }
    assert node.provenance is not None
    assert node.provenance.location == "row 2"


def test_missing_required_property_emits_error_and_returns_none() -> None:
    record = _record(data={"company_name": ""})  # company_name now blank
    node, issues = map_record_to_node(record, _node_mapping(), _node_spec())
    assert node is None
    assert any(i.severity == "error" and "name" in i.target for i in issues)


def test_missing_optional_property_is_silently_skipped() -> None:
    record = _record(
        data={"company_status": ""},  # blank optional
    )
    node, issues = map_record_to_node(record, _node_mapping(), _node_spec())
    assert node is not None
    assert "status" not in node.properties
    assert all(i.severity != "error" for i in issues)


def test_optional_property_with_bad_type_warns_and_is_omitted() -> None:
    record = _record(data={"founded_year": "not-a-year"})
    node, issues = map_record_to_node(record, _node_mapping(), _node_spec())
    assert node is not None
    assert "founded" not in node.properties
    assert any(i.severity == "warning" and "founded" in i.target for i in issues)


def test_required_property_with_bad_type_is_an_error() -> None:
    spec = _node_spec(
        properties={
            "company_number": {"type": "integer", "required": True},
            "name": {"type": "string", "required": True},
        }
    )
    mapping = _node_mapping(properties={"company_number": "company_number", "name": "company_name"})
    record = _record(data={"company_number": "abc"})
    node, issues = map_record_to_node(record, mapping, spec)
    assert node is None
    assert any(i.severity == "error" and "company_number" in i.target for i in issues)


def test_missing_key_field_returns_none_with_error() -> None:
    record = _record(data={"company_number": ""})
    node, issues = map_record_to_node(record, _node_mapping(), _node_spec())
    assert node is None
    assert any(i.severity == "error" and "company_number" in i.target for i in issues)


def test_extra_mapping_property_not_in_ontology_warns() -> None:
    spec = _node_spec(
        properties={
            "company_number": {"type": "string", "required": True},
            "name": {"type": "string", "required": True},
        }
    )
    mapping = _node_mapping(
        properties={
            "company_number": "company_number",
            "name": "company_name",
            "status": "company_status",  # not declared in this spec
        }
    )
    node, issues = map_record_to_node(_record(), mapping, spec)
    assert node is not None
    assert "status" not in node.properties
    assert any(i.severity == "warning" and "status" in i.target for i in issues)
