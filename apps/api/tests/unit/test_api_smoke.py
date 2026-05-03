"""Smoke tests for the GraphFlow HTTP API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from graphflow_api.main import app

client = TestClient(app)


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_endpoint_reports_versions() -> None:
    response = client.get("/version")
    assert response.status_code == 200
    payload = response.json()
    assert "api" in payload
    assert "core" in payload
    assert payload["api"] != ""
    assert payload["core"] != ""
