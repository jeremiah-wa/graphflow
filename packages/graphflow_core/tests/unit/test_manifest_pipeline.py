"""Unit tests for ``PipelineSpec`` / ``PipelineManifest``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from graphflow_core.manifests import PipelineManifest, PipelineSpec


def _valid_payload() -> dict[str, Any]:
    return {
        "version": "0.1",
        "pipeline": {
            "name": "company_network_pipeline",
            "source_ref": "companies_csv",
            "ontology_ref": "company_network",
            "extraction": {"mode": "none"},
            "mapping": {
                "nodes": [
                    {
                        "label": "Company",
                        "source": "rows[]",
                        "key": {"from_field": "company_number"},
                        "properties": {
                            "company_number": "company_number",
                            "name": "company_name",
                        },
                    }
                ],
                "relationships": [],
            },
            "destination": {
                "type": "neo4j",
                "connection_ref": "neo4j_local",
                "write_mode": "merge",
                "batch_size": 500,
            },
        },
    }


def test_valid_pipeline_parses() -> None:
    manifest = PipelineManifest.model_validate(_valid_payload())
    assert isinstance(manifest.pipeline, PipelineSpec)
    assert manifest.pipeline.destination.batch_size == 500


def test_extraction_mode_must_be_known() -> None:
    payload = deepcopy(_valid_payload())
    payload["pipeline"]["extraction"]["mode"] = "smart"
    with pytest.raises(ValidationError):
        PipelineManifest.model_validate(payload)


def test_destination_type_must_be_known() -> None:
    payload = deepcopy(_valid_payload())
    payload["pipeline"]["destination"]["type"] = "memgraph"
    with pytest.raises(ValidationError):
        PipelineManifest.model_validate(payload)


def test_destination_write_mode_must_be_known() -> None:
    payload = deepcopy(_valid_payload())
    payload["pipeline"]["destination"]["write_mode"] = "upsert"
    with pytest.raises(ValidationError):
        PipelineManifest.model_validate(payload)


def test_destination_batch_size_must_be_positive() -> None:
    payload = deepcopy(_valid_payload())
    payload["pipeline"]["destination"]["batch_size"] = 0
    with pytest.raises(ValidationError):
        PipelineManifest.model_validate(payload)


def test_missing_required_field_fails() -> None:
    payload = deepcopy(_valid_payload())
    del payload["pipeline"]["destination"]
    with pytest.raises(ValidationError):
        PipelineManifest.model_validate(payload)


def test_default_write_mode_is_merge() -> None:
    payload = deepcopy(_valid_payload())
    del payload["pipeline"]["destination"]["write_mode"]
    manifest = PipelineManifest.model_validate(payload)
    assert manifest.pipeline.destination.write_mode == "merge"


def test_pipeline_relationship_mapping_uses_from_to_aliases() -> None:
    payload = deepcopy(_valid_payload())
    payload["pipeline"]["mapping"]["relationships"] = [
        {
            "type": "OFFICER_OF",
            "source": "rows[]",
            "from": {"label": "Person", "from_field": "person_id"},
            "to": {"label": "Company", "from_field": "company_number"},
            "properties": {},
        }
    ]
    manifest = PipelineManifest.model_validate(payload)
    rel = manifest.pipeline.mapping.relationships[0]
    assert rel.from_node.label == "Person"
    assert rel.to_node.label == "Company"
