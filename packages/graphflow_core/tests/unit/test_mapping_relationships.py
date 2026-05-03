"""Unit tests for :func:`map_record_to_relationship`."""

from __future__ import annotations

from typing import Any

from graphflow_core.manifests.ontology import OntologySpec
from graphflow_core.manifests.pipeline import RelationshipMapping
from graphflow_core.mapping import map_record_to_relationship
from graphflow_core.sources.base import ParsedRecord


def _ontology() -> OntologySpec:
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
                    "key": {"strategy": "endpoints_and_type"},
                    "properties": {
                        "role": {"type": "string", "required": False},
                        "appointed_on": {"type": "date", "required": False},
                    },
                }
            ],
        }
    )


def _mapping(**overrides: Any) -> RelationshipMapping:
    base: dict[str, Any] = {
        "type": "OFFICER_OF",
        "source": "rows[]",
        "from": {"label": "Person", "from_field": "person_id"},
        "to": {"label": "Company", "from_field": "company_number"},
        "properties": {"role": "role", "appointed_on": "appointed_on"},
    }
    base.update(overrides)
    return RelationshipMapping.model_validate(base)


def _record(**overrides: Any) -> ParsedRecord:
    base: dict[str, Any] = {
        "data": {
            "person_id": "P-1",
            "company_number": "00000001",
            "role": "director",
            "appointed_on": "2020-01-01",
        },
        "source_name": "officers_csv",
        "source_path": "data/officers.csv",
        "source_format": "csv",
        "row_index": 0,
        "location": "row 2",
    }
    if "data" in overrides:
        base["data"] = {**base["data"], **overrides.pop("data")}
    base.update(overrides)
    return ParsedRecord.model_validate(base)


def test_maps_relationship_happy_path() -> None:
    onto = _ontology()
    rel_spec = onto.relationships[0]
    rel, issues = map_record_to_relationship(_record(), _mapping(), rel_spec, onto)
    assert issues == []
    assert rel is not None
    assert rel.type == "OFFICER_OF"
    assert rel.from_identity() == ("Person", "person_id", "P-1")
    assert rel.to_identity() == ("Company", "company_number", "00000001")
    assert rel.properties["role"] == "director"


def test_missing_endpoint_field_emits_error() -> None:
    onto = _ontology()
    rel_spec = onto.relationships[0]
    record = _record(data={"person_id": ""})
    rel, issues = map_record_to_relationship(record, _mapping(), rel_spec, onto)
    assert rel is None
    assert any(i.severity == "error" and "from" in i.message for i in issues)


def test_unknown_property_warns_and_is_skipped() -> None:
    onto = _ontology()
    rel_spec = onto.relationships[0]
    mapping = _mapping(
        properties={
            "role": "role",
            "appointed_on": "appointed_on",
            "salary": "salary",  # not declared in ontology
        }
    )
    rel, issues = map_record_to_relationship(_record(), mapping, rel_spec, onto)
    assert rel is not None
    assert "salary" not in rel.properties
    assert any(i.severity == "warning" and "salary" in i.target for i in issues)


def test_optional_property_with_bad_type_warns() -> None:
    onto = _ontology()
    rel_spec = onto.relationships[0]
    record = _record(data={"appointed_on": "01/01/2020"})  # not ISO
    rel, issues = map_record_to_relationship(record, _mapping(), rel_spec, onto)
    assert rel is not None
    assert "appointed_on" not in rel.properties
    assert any(i.severity == "warning" and "appointed_on" in i.target for i in issues)
