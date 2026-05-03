"""CLI tests for ``graphflow map``."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from graphflow_cli.main import app

runner = CliRunner()

EXAMPLES_DIR = Path(__file__).resolve().parents[4] / "examples"


def test_map_runs_against_simple_csv() -> None:
    folder = EXAMPLES_DIR / "simple_csv"
    result = runner.invoke(app, ["map", str(folder)])
    assert result.exit_code == 0, result.output
    assert "Records read: 2" in result.output
    assert "Nodes produced: 2" in result.output
    assert "Relationships produced: 0" in result.output
    assert "0 error(s)" in result.output


def test_map_runs_against_simple_json() -> None:
    folder = EXAMPLES_DIR / "simple_json"
    result = runner.invoke(app, ["map", str(folder)])
    assert result.exit_code == 0, result.output
    assert "Nodes produced: 2" in result.output
    assert "0 error(s)" in result.output


def test_map_exits_non_zero_when_required_field_missing(tmp_path: Path) -> None:
    src = EXAMPLES_DIR / "simple_csv"
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "data").mkdir()
    # Source has the required `company_name` column blanked out.
    (folder / "data" / "companies.csv").write_text(
        "company_number,company_name,company_status\n1,,active\n",
        encoding="utf-8",
    )
    for name in ("source.yaml", "ontology.yaml", "pipeline.yaml", "connections.yaml"):
        (folder / name).write_text((src / name).read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(app, ["map", str(folder)])
    assert result.exit_code == 1, result.output
    assert "Nodes produced: 0" in result.output
    assert "0 error(s)" not in result.output
