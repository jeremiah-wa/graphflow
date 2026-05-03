"""CLI tests for ``graphflow ingest``."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from graphflow_cli.main import app

runner = CliRunner()

EXAMPLES_DIR = Path(__file__).resolve().parents[4] / "examples"


def test_ingest_reports_parsed_records_for_example_connector() -> None:
    folder = EXAMPLES_DIR / "simple_csv"
    result = runner.invoke(app, ["ingest", str(folder)])
    assert result.exit_code == 0, result.output
    assert "Source: companies_csv" in result.output
    assert "Format: csv" in result.output
    assert "Records: 2" in result.output
    assert "row 2" in result.output


def test_ingest_with_limit_zero_hides_records() -> None:
    folder = EXAMPLES_DIR / "simple_csv"
    result = runner.invoke(app, ["ingest", str(folder), "--limit", "0"])
    assert result.exit_code == 0, result.output
    assert "Records: 2" in result.output
    assert "row 2" not in result.output


def test_ingest_reports_invalid_manifests(tmp_path: Path) -> None:
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "source.yaml").write_text("", encoding="utf-8")
    (folder / "ontology.yaml").write_text("", encoding="utf-8")
    (folder / "pipeline.yaml").write_text("", encoding="utf-8")
    (folder / "connections.yaml").write_text("", encoding="utf-8")

    result = runner.invoke(app, ["ingest", str(folder)])
    assert result.exit_code == 1
    assert "Invalid manifests" in result.output
