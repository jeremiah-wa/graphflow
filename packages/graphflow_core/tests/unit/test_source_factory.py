"""Unit tests for :func:`graphflow_core.sources.open_source`."""

from __future__ import annotations

from pathlib import Path

import pytest

from graphflow_core.manifests.source import SourceSpec
from graphflow_core.sources import (
    CsvFileReader,
    JsonFileReader,
    SourceReadError,
    open_source,
)


def _spec(**overrides: object) -> SourceSpec:
    base: dict[str, object] = {
        "name": "demo",
        "type": "file",
        "format": "csv",
        "path": "data/x.csv",
        "primary_key": [],
    }
    base.update(overrides)
    return SourceSpec.model_validate(base)


def test_open_source_returns_csv_reader_for_csv_format(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.csv").write_text("a\n1\n", encoding="utf-8")
    reader = open_source(_spec(format="csv", path="data/x.csv"), base_dir=tmp_path)
    assert isinstance(reader, CsvFileReader)
    records = list(reader.read())
    assert records[0].data == {"a": "1"}


def test_open_source_returns_json_reader_for_json_format(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.json").write_text('[{"a": 1}]', encoding="utf-8")
    reader = open_source(_spec(format="json", path="data/x.json"), base_dir=tmp_path)
    assert isinstance(reader, JsonFileReader)
    records = list(reader.read())
    assert records[0].data == {"a": 1}


def test_open_source_rejects_path_escaping_base_dir(tmp_path: Path) -> None:
    spec = _spec(path="../../etc/passwd")
    with pytest.raises(SourceReadError, match="escape"):
        open_source(spec, base_dir=tmp_path)


def test_open_source_resolves_path_relative_to_base_dir(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.csv").write_text("a\n1\n", encoding="utf-8")
    reader = open_source(_spec(path="data/x.csv"), base_dir=tmp_path)
    assert isinstance(reader, CsvFileReader)
    assert reader.path == (tmp_path / "data" / "x.csv").resolve()
