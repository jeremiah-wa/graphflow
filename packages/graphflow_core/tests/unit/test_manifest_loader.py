"""Unit tests for the connector folder loader and cross-validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from graphflow_core.manifests import (
    ConnectorManifest,
    ManifestError,
    ManifestValidationError,
    load_connector,
)

EXAMPLE_DIR = Path(__file__).resolve().parents[4] / "examples" / "simple_csv"


def test_example_simple_csv_validates() -> None:
    """Snapshot/fixture test: the bundled example must always validate."""
    connector = load_connector(EXAMPLE_DIR)
    assert isinstance(connector, ConnectorManifest)
    assert connector.source.source.name == "companies_csv"
    assert connector.ontology.ontology.name == "company_network"
    assert connector.pipeline.pipeline.name == "company_network_pipeline"
    assert "neo4j_local" in connector.connections.connections


def _write_valid_connector(folder: Path) -> None:
    (folder / "data").mkdir(parents=True, exist_ok=True)
    (folder / "data" / "companies.csv").write_text(
        "company_number,company_name\n1,Demo\n", encoding="utf-8"
    )
    (folder / "source.yaml").write_text(
        (EXAMPLE_DIR / "source.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (folder / "ontology.yaml").write_text(
        (EXAMPLE_DIR / "ontology.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (folder / "pipeline.yaml").write_text(
        (EXAMPLE_DIR / "pipeline.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (folder / "connections.yaml").write_text(
        (EXAMPLE_DIR / "connections.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )


def test_missing_folder_raises_manifest_error(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        load_connector(tmp_path / "does_not_exist")


def test_missing_file_reports_named_issue(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    (tmp_path / "ontology.yaml").unlink()
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    assert any("ontology.yaml" in issue for issue in exc_info.value.issues)


def test_invalid_yaml_reports_file(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    (tmp_path / "source.yaml").write_text(": : :\n", encoding="utf-8")
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    assert any("source.yaml" in issue for issue in exc_info.value.issues)


def test_pipeline_source_ref_must_match_source_name(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    pipeline_text = (tmp_path / "pipeline.yaml").read_text(encoding="utf-8")
    pipeline_text = pipeline_text.replace("source_ref: companies_csv", "source_ref: other_source")
    (tmp_path / "pipeline.yaml").write_text(pipeline_text, encoding="utf-8")
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    assert any("source_ref" in issue for issue in exc_info.value.issues)


def test_pipeline_ontology_ref_must_match(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    text = (tmp_path / "pipeline.yaml").read_text(encoding="utf-8")
    text = text.replace("ontology_ref: company_network", "ontology_ref: other_ontology")
    (tmp_path / "pipeline.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    assert any("ontology_ref" in issue for issue in exc_info.value.issues)


def test_unknown_connection_ref_rejected(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    text = (tmp_path / "pipeline.yaml").read_text(encoding="utf-8")
    text = text.replace("connection_ref: neo4j_local", "connection_ref: missing_conn")
    (tmp_path / "pipeline.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    assert any("connection_ref" in issue for issue in exc_info.value.issues)


def test_mapping_node_label_must_exist_in_ontology(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    text = (tmp_path / "pipeline.yaml").read_text(encoding="utf-8")
    text = text.replace("label: Company", "label: Organisation", 1)
    (tmp_path / "pipeline.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    issues = " ".join(exc_info.value.issues)
    assert "Organisation" in issues


def test_mapping_must_include_node_key_property(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    text = (tmp_path / "pipeline.yaml").read_text(encoding="utf-8")
    text = text.replace(
        "          company_number: company_number\n",
        "",
    )
    (tmp_path / "pipeline.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    issues = " ".join(exc_info.value.issues)
    assert "company_number" in issues


def test_destination_type_must_match_connection_type(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    conn_text = (tmp_path / "connections.yaml").read_text(encoding="utf-8")
    conn_text = (
        'version: "0.1"\n'
        "connections:\n"
        "  neo4j_local:\n"
        "    type: llm\n"
        "    provider: openai\n"
        "    api_key_from_env: OPENAI_API_KEY\n"
    )
    (tmp_path / "connections.yaml").write_text(conn_text, encoding="utf-8")
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    issues = " ".join(exc_info.value.issues)
    assert "destination.type" in issues or "type" in issues


def test_source_path_must_not_escape_connector_folder(tmp_path: Path) -> None:
    _write_valid_connector(tmp_path)
    text = (tmp_path / "source.yaml").read_text(encoding="utf-8")
    text = text.replace("path: data/companies.csv", "path: ../../escape.csv")
    (tmp_path / "source.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ManifestValidationError) as exc_info:
        load_connector(tmp_path)
    issues = " ".join(exc_info.value.issues)
    assert "escape" in issues or "must be relative" in issues
