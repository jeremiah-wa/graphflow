"""Errors raised by source readers."""

from __future__ import annotations


class SourceReadError(Exception):
    """Raised when a source file cannot be read or is malformed."""
