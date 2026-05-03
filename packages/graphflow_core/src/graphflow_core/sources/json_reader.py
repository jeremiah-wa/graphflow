"""JSON file reader.

Reads a UTF-8 JSON file as :class:`ParsedRecord` instances.

Two top-level shapes are supported:

- A JSON **array** of objects: each element becomes one record. The
  ``row_index`` matches the array position; ``location`` is
  ``"items[N]"``.
- A JSON **object**: the file produces a single record. The
  ``row_index`` is ``0`` and ``location`` is ``"object"``.

Any other shape (top-level primitive, array of non-objects, ...) raises
:class:`SourceReadError`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from graphflow_core.sources.base import ParsedRecord
from graphflow_core.sources.errors import SourceReadError


class JsonFileReader:
    """Read a single JSON file as :class:`ParsedRecord` instances."""

    def __init__(self, path: Path, *, source_name: str) -> None:
        self._path = Path(path)
        self._source_name = source_name

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Iterator[ParsedRecord]:
        if not self._path.exists():
            raise SourceReadError(f"JSON file not found: {self._path}")
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise SourceReadError(f"Could not read {self._path}: {exc}") from exc

        if text.strip() == "":
            raise SourceReadError(f"JSON file {self._path} is empty")

        try:
            payload: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SourceReadError(f"Invalid JSON in {self._path}: {exc}") from exc

        if isinstance(payload, dict):
            yield self._record(payload, row_index=0, location="object")
            return

        if isinstance(payload, list):
            for index, element in enumerate(payload):
                if not isinstance(element, dict):
                    raise SourceReadError(
                        f"{self._path} items[{index}] must be a JSON object, "
                        f"got {type(element).__name__}"
                    )
                yield self._record(element, row_index=index, location=f"items[{index}]")
            return

        raise SourceReadError(
            f"{self._path} top-level JSON must be an object or array of "
            f"objects, got {type(payload).__name__}"
        )

    def _record(self, data: dict[str, Any], *, row_index: int, location: str) -> ParsedRecord:
        return ParsedRecord(
            data=data,
            source_name=self._source_name,
            source_path=str(self._path),
            source_format="json",
            row_index=row_index,
            location=location,
        )
