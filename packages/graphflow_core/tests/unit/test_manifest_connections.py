"""Unit tests for ``ConnectionSpec`` / ``ConnectionsManifest``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from graphflow_core.manifests import ConnectionsManifest, ConnectionSpec


def _valid_payload() -> dict[str, Any]:
    return {
        "version": "0.1",
        "connections": {
            "neo4j_local": {
                "type": "neo4j",
                "uri": "bolt://localhost:7687",
                "username": "neo4j",
                "password_from_env": "NEO4J_PASSWORD",
            },
            "openai_default": {
                "type": "llm",
                "provider": "openai",
                "api_key_from_env": "OPENAI_API_KEY",
            },
        },
    }


def test_valid_connections_parses() -> None:
    manifest = ConnectionsManifest.model_validate(_valid_payload())
    assert set(manifest.connections) == {"neo4j_local", "openai_default"}
    assert isinstance(manifest.connections["neo4j_local"], ConnectionSpec)


def test_neo4j_missing_password_env_rejected() -> None:
    payload = deepcopy(_valid_payload())
    del payload["connections"]["neo4j_local"]["password_from_env"]
    with pytest.raises(ValidationError) as exc_info:
        ConnectionsManifest.model_validate(payload)
    assert "password_from_env" in str(exc_info.value)


def test_neo4j_must_not_set_llm_fields() -> None:
    payload = deepcopy(_valid_payload())
    payload["connections"]["neo4j_local"]["provider"] = "openai"
    with pytest.raises(ValidationError):
        ConnectionsManifest.model_validate(payload)


def test_llm_missing_api_key_env_rejected() -> None:
    payload = deepcopy(_valid_payload())
    del payload["connections"]["openai_default"]["api_key_from_env"]
    with pytest.raises(ValidationError):
        ConnectionsManifest.model_validate(payload)


def test_unknown_connection_type_rejected() -> None:
    payload = deepcopy(_valid_payload())
    payload["connections"]["neo4j_local"]["type"] = "redis"
    with pytest.raises(ValidationError):
        ConnectionsManifest.model_validate(payload)


def test_connection_name_must_be_snake_case() -> None:
    payload = deepcopy(_valid_payload())
    payload["connections"]["Neo4jLocal"] = payload["connections"].pop("neo4j_local")
    with pytest.raises(ValidationError):
        ConnectionsManifest.model_validate(payload)


def test_invalid_env_var_name_rejected() -> None:
    payload = deepcopy(_valid_payload())
    payload["connections"]["neo4j_local"]["password_from_env"] = "1BAD-NAME"
    with pytest.raises(ValidationError):
        ConnectionsManifest.model_validate(payload)
