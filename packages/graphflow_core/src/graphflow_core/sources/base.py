"""Core source abstractions: :class:`ParsedRecord` and :class:`SourceReader`.

A :class:`SourceReader` produces an iterable of :class:`ParsedRecord`
objects. Each parsed record carries the parsed field dictionary plus
provenance metadata (source name, file path, format, and a 0-indexed
position) so downstream stages can attribute mapping/validation errors
back to a specific row or array element.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from graphflow_core.manifests.source import SourceFormat


class ParsedRecord(BaseModel):
    """One record produced by a :class:`SourceReader`.

    Attributes:
        data: The parsed field dictionary for this record.
        source_name: ``SourceSpec.name`` of the originating source.
        source_path: Filesystem path of the file the record came from,
            stored as a string for predictable serialisation.
        source_format: Format of the source file (``csv`` or ``json``).
        row_index: 0-indexed position of the record within the source.
            For CSV this is the data-row index (header excluded). For
            JSON arrays this is the array index. For a JSON object input
            it is always ``0``.
        location: Human-friendly position string, e.g. ``"row 1"`` or
            ``"items[3]"``. Useful in error messages.
    """

    model_config = ConfigDict(extra="forbid")

    data: dict[str, Any]
    source_name: str
    source_path: str
    source_format: SourceFormat
    row_index: int = Field(ge=0)
    location: str


@runtime_checkable
class SourceReader(Protocol):
    """Structural protocol for components that read records from a source.

    Implementations must be deterministic for the same input file: a
    second call to :meth:`read` should yield the same records in the
    same order, so pipeline runs are repeatable.
    """

    def read(self) -> Iterator[ParsedRecord]:
        """Yield :class:`ParsedRecord` instances from the underlying source."""
        ...
