"""Manifest loading and validation errors."""

from __future__ import annotations

from pathlib import Path


class ManifestError(Exception):
    """Base error for manifest loading and validation."""


class ManifestValidationError(ManifestError):
    """Raised when one or more manifests fail validation.

    The exception carries a list of human-readable issue strings, each of
    which should explain *what* failed, *which* manifest/field caused it,
    and *how* a user could fix it.
    """

    def __init__(self, issues: list[str], *, path: Path | None = None) -> None:
        self.issues = list(issues)
        self.path = path
        header = f"Invalid manifests at {path}:" if path is not None else "Invalid manifests:"
        message = "\n".join([header, *(f"- {issue}" for issue in self.issues)])
        super().__init__(message)
