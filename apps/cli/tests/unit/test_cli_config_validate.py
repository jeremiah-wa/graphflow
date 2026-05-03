"""CLI integration tests for ``graphflow config validate``."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from graphflow_cli.main import app

runner = CliRunner()

EXAMPLES_DIR = Path(__file__).resolve().parents[4] / "examples"


def test_config_validate_succeeds_on_example_connector() -> None:
    folder = EXAMPLES_DIR / "simple_csv"
    result = runner.invoke(app, ["config", "validate", str(folder)])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "companies_csv" in result.output


def test_config_validate_reports_invalid_connector(tmp_path: Path) -> None:
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "source.yaml").write_text(
        'version: "0.1"\nsource:\n  name: BadName\n  type: file\n'
        "  format: csv\n  path: data/x.csv\n",
        encoding="utf-8",
    )
    (folder / "ontology.yaml").write_text("", encoding="utf-8")
    (folder / "pipeline.yaml").write_text("", encoding="utf-8")
    (folder / "connections.yaml").write_text("", encoding="utf-8")

    result = runner.invoke(app, ["config", "validate", str(folder)])
    assert result.exit_code == 1
    assert "Invalid manifests" in result.output


def test_config_validate_rejects_missing_folder() -> None:
    result = runner.invoke(app, ["config", "validate", "does/not/exist"])
    assert result.exit_code != 0
