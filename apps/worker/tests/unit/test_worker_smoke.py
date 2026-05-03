"""Smoke tests for the GraphFlow worker."""

from __future__ import annotations

from graphflow_worker import __version__, run_pipeline


def test_worker_exposes_version() -> None:
    assert isinstance(__version__, str)
    assert __version__ != ""


def test_run_pipeline_placeholder_returns_status() -> None:
    result = run_pipeline("examples/simple_csv")
    assert result["status"] == "not_implemented"
    assert result["pipeline"] == "examples/simple_csv"
