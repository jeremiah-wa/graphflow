"""Unit tests for ``SourceSpec`` / ``SourceManifest``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from graphflow_core.manifests import SourceManifest, SourceSpec


def _valid_payload() -> dict[str, object]:
    return {
        "version": "0.1",
        "source": {
            "name": "companies_csv",
            "type": "file",
            "format": "csv",
            "path": "data/companies.csv",
            "primary_key": ["company_number"],
        },
    }


def test_valid_source_manifest_parses() -> None:
    manifest = SourceManifest.model_validate(_valid_payload())
    assert isinstance(manifest.source, SourceSpec)
    assert manifest.source.name == "companies_csv"
    assert manifest.source.format == "csv"
    assert manifest.source.primary_key == ["company_number"]


def test_missing_required_source_field_fails() -> None:
    payload = _valid_payload()
    del payload["source"]  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(payload)


def test_unknown_source_type_fails() -> None:
    payload = _valid_payload()
    payload["source"]["type"] = "magic"  # type: ignore[index]
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(payload)


def test_unknown_source_format_fails() -> None:
    payload = _valid_payload()
    payload["source"]["format"] = "parquet"  # type: ignore[index]
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(payload)


def test_non_snake_case_name_rejected() -> None:
    payload = _valid_payload()
    payload["source"]["name"] = "CompaniesCSV"  # type: ignore[index]
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(payload)


def test_unknown_extra_field_rejected() -> None:
    payload = _valid_payload()
    payload["source"]["unexpected"] = True  # type: ignore[index]
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(payload)


def test_unknown_version_rejected() -> None:
    payload = _valid_payload()
    payload["version"] = "0.2"
    with pytest.raises(ValidationError):
        SourceManifest.model_validate(payload)
