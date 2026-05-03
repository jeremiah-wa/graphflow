"""Smoke tests for the graphflow_core package."""

from __future__ import annotations

import graphflow_core


def test_package_exposes_version() -> None:
    assert isinstance(graphflow_core.__version__, str)
    assert graphflow_core.__version__ != ""


def test_package_version_is_semver_like() -> None:
    parts = graphflow_core.__version__.split(".")
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts[:2])
