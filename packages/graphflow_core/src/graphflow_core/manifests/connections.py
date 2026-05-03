"""``connections.yaml`` manifest models.

Connections describe named, reusable references to external systems
(graph databases, LLM providers, ...). Secrets must be sourced from
environment variables, never from the YAML file itself.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from graphflow_core.manifests.common import (
    STRICT_MODEL_CONFIG,
    ManifestVersion,
    is_snake_case,
)

ConnectionType = Literal["neo4j", "llm"]


class ConnectionSpec(BaseModel):
    """One named connection.

    A single-model approach is used (rather than a discriminated union of
    subclasses) so that ``ConnectionSpec`` is itself the public type.
    Type-specific required fields are enforced by a model validator.
    """

    model_config = STRICT_MODEL_CONFIG

    type: ConnectionType

    # neo4j fields. ``password_from_env`` and ``api_key_from_env`` hold the
    # *name* of an environment variable to read the secret from at runtime;
    # they never contain the secret value itself.
    uri: str | None = None
    username: str | None = None
    password_from_env: str | None = None  # ggignore - env var name, not a secret  # noqa: S105

    # llm fields
    provider: str | None = None
    api_key_from_env: str | None = None  # ggignore - env var name, not a secret  # noqa: S105

    @field_validator("password_from_env", "api_key_from_env")
    @classmethod
    def _env_var_name_is_screaming(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value or not value.replace("_", "").isalnum() or not value[0].isalpha():
            raise ValueError(
                f"env var reference '{value}' must look like an environment "
                "variable name (letters, digits, underscores; starts with a letter)"
            )
        return value

    @model_validator(mode="after")
    def _check_required_fields_for_type(self) -> Self:
        neo4j_fields = ("uri", "username", "password_from_env")
        llm_fields = ("provider", "api_key_from_env")
        if self.type == "neo4j":
            missing = [f for f in neo4j_fields if getattr(self, f) is None]
            if missing:
                raise ValueError(f"neo4j connection is missing required fields: {missing}")
            extra = [f for f in llm_fields if getattr(self, f) is not None]
            if extra:
                raise ValueError(f"neo4j connection must not set llm-only fields: {extra}")
        elif self.type == "llm":
            missing = [f for f in llm_fields if getattr(self, f) is None]
            if missing:
                raise ValueError(f"llm connection is missing required fields: {missing}")
            extra = [f for f in neo4j_fields if getattr(self, f) is not None]
            if extra:
                raise ValueError(f"llm connection must not set neo4j-only fields: {extra}")
        return self


class ConnectionsManifest(BaseModel):
    """Top-level model for ``connections.yaml``."""

    model_config = STRICT_MODEL_CONFIG

    version: ManifestVersion
    connections: dict[str, ConnectionSpec] = Field(default_factory=dict)

    @field_validator("connections")
    @classmethod
    def _names_are_snake_case(cls, value: dict[str, ConnectionSpec]) -> dict[str, ConnectionSpec]:
        for name in value:
            if not is_snake_case(name):
                raise ValueError(f"connection name '{name}' must be snake_case")
        return value
