"""``source.yaml`` manifest models.

A source manifest describes *where* data comes from and *how* to read it.
It must not contain graph mapping semantics; those belong in the pipeline
manifest.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from graphflow_core.manifests.common import (
    STRICT_MODEL_CONFIG,
    ManifestVersion,
    is_snake_case,
)

SourceType = Literal["file"]
"""Supported source types for v0.1. Future: ``rest_api``, ``object_storage``..."""

SourceFormat = Literal["csv", "json"]
"""Supported source formats for v0.1."""


class SourceSpec(BaseModel):
    """Description of a single source of records."""

    model_config = STRICT_MODEL_CONFIG

    name: str = Field(description="snake_case identifier referenced by pipeline.source_ref")
    type: SourceType
    format: SourceFormat
    path: str = Field(description="Path to the source file, relative to the manifest folder")
    primary_key: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_is_snake_case(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(
                f"source.name '{value}' must be snake_case "
                "(lowercase letters, digits, underscores; start with a letter)"
            )
        return value

    @field_validator("primary_key")
    @classmethod
    def _primary_key_fields_are_snake_case(cls, value: list[str]) -> list[str]:
        for field in value:
            if not is_snake_case(field):
                raise ValueError(f"source.primary_key entry '{field}' must be snake_case")
        return value


class SourceManifest(BaseModel):
    """Top-level model for ``source.yaml``."""

    model_config = STRICT_MODEL_CONFIG

    version: ManifestVersion
    source: SourceSpec
