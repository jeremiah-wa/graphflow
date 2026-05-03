"""Construct a :class:`SourceReader` from a validated :class:`SourceSpec`.

This is the single entry point that ties manifest models to concrete
readers. ``base_dir`` is the connector folder; the reader resolves
``SourceSpec.path`` relative to it.
"""

from __future__ import annotations

from pathlib import Path

from graphflow_core.manifests.source import SourceSpec
from graphflow_core.sources.base import SourceReader
from graphflow_core.sources.csv_reader import CsvFileReader
from graphflow_core.sources.errors import SourceReadError
from graphflow_core.sources.json_reader import JsonFileReader


def open_source(spec: SourceSpec, *, base_dir: Path) -> SourceReader:
    """Return a :class:`SourceReader` for the given source spec.

    Raises:
        SourceReadError: if the source type or format is not supported,
            or if the resolved path escapes ``base_dir``.
    """
    if spec.type != "file":
        raise SourceReadError(f"Unsupported source type '{spec.type}'. v0.1 supports: 'file'")

    base = Path(base_dir).resolve()
    candidate = (base / spec.path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise SourceReadError(
            f"source.path '{spec.path}' must not escape the connector folder"
        ) from exc

    if spec.format == "csv":
        return CsvFileReader(candidate, source_name=spec.name)
    if spec.format == "json":
        return JsonFileReader(candidate, source_name=spec.name)

    raise SourceReadError(  # pragma: no cover - guarded by manifest Literal
        f"Unsupported source format '{spec.format}'"
    )
