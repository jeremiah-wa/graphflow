"""Smoke tests for the GraphFlow CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from graphflow_cli.main import app

runner = CliRunner()


def test_cli_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "GraphFlow" in result.stdout


def test_cli_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "graphflow-cli" in result.stdout
    assert "graphflow-core" in result.stdout
