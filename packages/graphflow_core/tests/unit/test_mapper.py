"""Unit tests for :class:`Mapper` and :class:`MappingResult`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from graphflow_core.manifests.connections import ConnectionsManifest
from graphflow_core.manifests.loader import (
    ConnectorManifest,
    load_connector,
    load_ontology,
    load_pipeline,
    load_source,
)
from graphflow_core.manifests.ontology import OntologyManifest
from graphflow_core.manifests.pipeline import PipelineManifest
from graphflow_core.manifests.source import SourceManifest
from graphflow_core.mapping import Mapper
from graphflow_core.sources.base import ParsedRecord

EXAMPLE_DIR = Path(__file__).resolve().parents[4] / "examples" / "simple_csv"


def _record(**overrides: Any) -> ParsedRecord:
    base: dict[str, Any] = {
        "data": {
            "company_number": "00000001",
            "company_name": "Example Holdings Ltd",
            "company_status": "active",
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


def test_mapper_emits_one_node_per_record_for_simple_csv() -> None:
    connector = load_connector(EXAMPLE_DIR)
    mapper = Mapper(connector)

    records = [
        _record(),
        _record(
            row_index=1,
            location="row 3",
            data={
                "company_number": "00000002",
                "company_name": "Demo Trading Ltd",
                "company_status": "dissolved",
            },
        ),
    ]
    result = mapper.map(records)
    assert not result.has_errors()
    assert [node.key_value for node in result.nodes] == ["00000001", "00000002"]
    assert result.relationships == []


def test_mapper_collects_issues_without_aborting() -> None:
    connector = load_connector(EXAMPLE_DIR)
    mapper = Mapper(connector)

    good = _record()
    bad = _record(row_index=1, location="row 3", data={"company_name": ""})

    result = mapper.map([good, bad])
    assert len(result.nodes) == 1
    assert result.has_errors()
    assert any(i.location == "row 3" for i in result.issues)


def _connector_with_relationships() -> ConnectorManifest:
    """Build a small in-memory connector that exercises relationship mapping."""
    source = SourceManifest.model_validate(
        {
            "version": "0.1",
            "source": {
                "name": "officers_csv",
                "type": "file",
                "format": "csv",
                "path": "data/officers.csv",
                "primary_key": ["person_id"],
            },
        }
    )
    ontology = OntologyManifest.model_validate(
        {
            "version": "0.1",
            "ontology": {
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
                        "properties": {"role": {"type": "string"}},
                    }
                ],
            },
        }
    )
    pipeline = PipelineManifest.model_validate(
        {
            "version": "0.1",
            "pipeline": {
                "name": "officers_pipeline",
                "source_ref": "officers_csv",
                "ontology_ref": "company_network",
                "extraction": {"mode": "none"},
                "mapping": {
                    "nodes": [],
                    "relationships": [
                        {
                            "type": "OFFICER_OF",
                            "source": "rows[]",
                            "from": {"label": "Person", "from_field": "person_id"},
                            "to": {
                                "label": "Company",
                                "from_field": "company_number",
                            },
                            "properties": {"role": "role"},
                        }
                    ],
                },
                "destination": {
                    "type": "neo4j",
                    "connection_ref": "neo4j_local",
                    "write_mode": "merge",
                    "batch_size": 1000,
                },
            },
        }
    )
    connections = ConnectionsManifest.model_validate(
        {
            "version": "0.1",
            "connections": {
                "neo4j_local": {
                    "type": "neo4j",
                    "uri": "bolt://localhost:7687",
                    "username": "neo4j",
                    "password_from_env": "NEO4J_PASSWORD",
                }
            },
        }
    )
    return ConnectorManifest(
        source=source,
        ontology=ontology,
        pipeline=pipeline,
        connections=connections,
    )


def test_mapper_emits_relationships() -> None:
    connector = _connector_with_relationships()
    mapper = Mapper(connector)
    record = ParsedRecord.model_validate(
        {
            "data": {
                "person_id": "P-1",
                "company_number": "00000001",
                "role": "director",
            },
            "source_name": "officers_csv",
            "source_path": "data/officers.csv",
            "source_format": "csv",
            "row_index": 0,
            "location": "row 2",
        }
    )
    result = mapper.map([record])
    assert result.nodes == []
    assert len(result.relationships) == 1
    assert result.relationships[0].type == "OFFICER_OF"
    # Orphan-relationship detection runs over the whole result, so the
    # relationship without matching nodes is reported as an error issue
    # while the relationship object itself is still returned for the
    # caller to inspect or drop.
    assert any("unknown" in issue.message for issue in result.issues)


def test_loaders_are_used_to_back_the_test() -> None:
    # Sanity: the example connector loaders still work and produce a
    # ConnectorManifest the Mapper accepts.
    source = load_source(EXAMPLE_DIR / "source.yaml")
    ontology = load_ontology(EXAMPLE_DIR / "ontology.yaml")
    pipeline = load_pipeline(EXAMPLE_DIR / "pipeline.yaml")
    assert source.source.name == "companies_csv"
    assert ontology.ontology.name == "company_network"
    assert pipeline.pipeline.name == "company_network_pipeline"
