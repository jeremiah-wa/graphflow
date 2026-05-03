"""Shared types for GraphFlow manifest models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict

ManifestVersion = Literal["0.1"]
"""The schema version for v0.1 manifests."""

STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", populate_by_name=True)
"""Default model config: forbid unknown keys to catch typos in YAML."""

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_SCREAMING_SNAKE_CASE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def is_snake_case(value: str) -> bool:
    """Return ``True`` if ``value`` is ``snake_case``."""
    return bool(_SNAKE_CASE_RE.fullmatch(value))


def is_pascal_case(value: str) -> bool:
    """Return ``True`` if ``value`` is ``PascalCase``."""
    return bool(_PASCAL_CASE_RE.fullmatch(value))


def is_screaming_snake_case(value: str) -> bool:
    """Return ``True`` if ``value`` is ``SCREAMING_SNAKE_CASE``."""
    return bool(_SCREAMING_SNAKE_CASE_RE.fullmatch(value))
