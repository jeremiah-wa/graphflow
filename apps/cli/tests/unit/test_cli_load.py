"""CLI tests for ``graphflow load`` (driver-less paths)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from graphflow_cli.main import app

runner = CliRunner()

EXAMPLES_DIR = Path(__file__).resolve().parents[4] / "examples"


def test_load_aborts_on_mapping_errors_without_force(tmp_path: Path) -> None:
    src = EXAMPLES_DIR / "simple_csv"
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "data").mkdir()
    # Required `company_name` column is blank, mapping must error.
    (folder / "data" / "companies.csv").write_text(
        "company_number,company_name,company_status\n1,,active\n",
        encoding="utf-8",
    )
    for name in ("source.yaml", "ontology.yaml", "pipeline.yaml", "connections.yaml"):
        (folder / name).write_text((src / name).read_text(encoding="utf-8"), encoding="utf-8")
    result = runner.invoke(app, ["load", str(folder)], env={})
    assert result.exit_code == 1
    assert "Refusing to write" in result.output


def test_load_reports_missing_password_env_var() -> None:
    # Mapping succeeds on the bundled example; load then needs the env
    # var to construct the driver. Without it, the sink factory should
    # fail with a clear error before any network call is attempted.
    folder = EXAMPLES_DIR / "simple_csv"
    result = runner.invoke(app, ["load", str(folder)], env={})
    assert result.exit_code == 1
    assert "NEO4J_PASSWORD" in result.output


def test_load_reports_invalid_connector(tmp_path: Path) -> None:
    folder = tmp_path / "broken"
    folder.mkdir()
    for name in ("source.yaml", "ontology.yaml", "pipeline.yaml", "connections.yaml"):
        (folder / name).write_text("", encoding="utf-8")
    result = runner.invoke(app, ["load", str(folder)])
    assert result.exit_code == 1
    assert "Invalid manifests" in result.output
