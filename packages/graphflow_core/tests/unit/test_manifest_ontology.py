"""Unit tests for ``OntologySpec`` / ``OntologyManifest``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from graphflow_core.manifests import OntologyManifest, OntologySpec


def _valid_payload() -> dict[str, Any]:
    return {
        "version": "0.1",
        "ontology": {
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
                    "properties": {"role": {"type": "string"}},
                }
            ],
        },
    }


def test_valid_ontology_parses() -> None:
    manifest = OntologyManifest.model_validate(_valid_payload())
    onto = manifest.ontology
    assert isinstance(onto, OntologySpec)
    assert onto.node_labels() == {"Company", "Person"}
    assert onto.relationship_types() == {"OFFICER_OF"}


def test_node_label_must_be_pascal_case() -> None:
    payload = deepcopy(_valid_payload())
    payload["ontology"]["nodes"][0]["label"] = "company"
    with pytest.raises(ValidationError):
        OntologyManifest.model_validate(payload)


def test_relationship_type_must_be_screaming() -> None:
    payload = deepcopy(_valid_payload())
    payload["ontology"]["relationships"][0]["type"] = "officer_of"
    with pytest.raises(ValidationError):
        OntologyManifest.model_validate(payload)


def test_node_key_property_must_exist_in_properties() -> None:
    payload = deepcopy(_valid_payload())
    payload["ontology"]["nodes"][0]["key"]["property"] = "missing"
    with pytest.raises(ValidationError) as exc_info:
        OntologyManifest.model_validate(payload)
    assert "key.property" in str(exc_info.value)


def test_relationship_endpoint_must_be_known_label() -> None:
    payload = deepcopy(_valid_payload())
    payload["ontology"]["relationships"][0]["to"] = "Organisation"
    with pytest.raises(ValidationError) as exc_info:
        OntologyManifest.model_validate(payload)
    assert "Organisation" in str(exc_info.value)


def test_duplicate_node_labels_rejected() -> None:
    payload = deepcopy(_valid_payload())
    payload["ontology"]["nodes"].append(deepcopy(payload["ontology"]["nodes"][0]))
    with pytest.raises(ValidationError) as exc_info:
        OntologyManifest.model_validate(payload)
    assert "duplicate" in str(exc_info.value).lower()


def test_invalid_property_type_rejected() -> None:
    payload = deepcopy(_valid_payload())
    payload["ontology"]["nodes"][0]["properties"]["name"]["type"] = "uuid"
    with pytest.raises(ValidationError):
        OntologyManifest.model_validate(payload)


def test_relationship_explicit_property_strategy_requires_property() -> None:
    payload = deepcopy(_valid_payload())
    payload["ontology"]["relationships"][0]["key"] = {"strategy": "explicit_property"}
    with pytest.raises(ValidationError):
        OntologyManifest.model_validate(payload)


def test_endpoints_and_type_strategy_must_not_set_property() -> None:
    payload = deepcopy(_valid_payload())
    payload["ontology"]["relationships"][0]["key"] = {
        "strategy": "endpoints_and_type",
        "property": "id",
    }
    with pytest.raises(ValidationError):
        OntologyManifest.model_validate(payload)
