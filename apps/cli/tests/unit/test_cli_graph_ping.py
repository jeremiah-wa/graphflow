"""CLI tests for ``graphflow graph ping`` (without a real Neo4j)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from graphflow_cli.main import app

runner = CliRunner()

EXAMPLES_DIR = Path(__file__).resolve().parents[4] / "examples"


def test_ping_reports_missing_password_env_var() -> None:
    folder = EXAMPLES_DIR / "simple_csv"
    # NEO4J_PASSWORD is not set in the test environment, so the sink
    # factory should fail with a clear error before any network call
    # is attempted.
    result = runner.invoke(app, ["graph", "ping", str(folder)], env={})
    assert result.exit_code == 1
    assert "NEO4J_PASSWORD" in result.output


def test_ping_reports_invalid_connector(tmp_path: Path) -> None:
    folder = tmp_path / "broken"
    folder.mkdir()
    for name in ("source.yaml", "ontology.yaml", "pipeline.yaml", "connections.yaml"):
        (folder / name).write_text("", encoding="utf-8")
    result = runner.invoke(app, ["graph", "ping", str(folder)])
    assert result.exit_code == 1
    assert "Invalid manifests" in result.output
