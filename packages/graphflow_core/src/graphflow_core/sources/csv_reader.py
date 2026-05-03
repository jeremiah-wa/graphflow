"""CSV file reader.

Reads UTF-8 CSV files into :class:`ParsedRecord` instances. The first
row is treated as the header. Empty cells become empty strings (not
``None``); downstream mapping/validation is responsible for typing
field values.

The reader is deliberately strict:

- Files with no header row raise :class:`SourceReadError`.
- Rows whose column count does not match the header raise
  :class:`SourceReadError` with the offending row index.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from graphflow_core.sources.base import ParsedRecord
from graphflow_core.sources.errors import SourceReadError


class CsvFileReader:
    """Read a single CSV file as :class:`ParsedRecord` instances."""

    def __init__(self, path: Path, *, source_name: str) -> None:
        self._path = Path(path)
        self._source_name = source_name

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Iterator[ParsedRecord]:
        if not self._path.exists():
            raise SourceReadError(f"CSV file not found: {self._path}")
        try:
            handle = self._path.open("r", encoding="utf-8", newline="")
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise SourceReadError(f"Could not open {self._path}: {exc}") from exc

        with handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise SourceReadError(f"CSV file {self._path} is empty (no header row)") from exc

            if not header or all(field.strip() == "" for field in header):
                raise SourceReadError(f"CSV file {self._path} has an empty or blank header row")

            normalised_header = [field.strip() for field in header]
            for row_index, row in enumerate(reader):
                if len(row) != len(normalised_header):
                    raise SourceReadError(
                        f"{self._path} row {row_index + 2}: expected "
                        f"{len(normalised_header)} columns, got {len(row)}"
                    )
                yield ParsedRecord(
                    data=dict(zip(normalised_header, row, strict=True)),
                    source_name=self._source_name,
                    source_path=str(self._path),
                    source_format="csv",
                    row_index=row_index,
                    location=f"row {row_index + 2}",
                )
