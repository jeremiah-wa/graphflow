"""Unit tests for :class:`JsonFileReader`."""

from __future__ import annotations

from pathlib import Path

import pytest

from graphflow_core.sources import JsonFileReader, SourceReader, SourceReadError


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_json_reader_satisfies_source_reader_protocol(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.json", "{}")
    reader = JsonFileReader(file, source_name="x")
    assert isinstance(reader, SourceReader)


def test_reads_top_level_object(tmp_path: Path) -> None:
    file = _write(tmp_path / "single.json", '{"a": 1, "b": "two"}')
    records = list(JsonFileReader(file, source_name="single").read())
    assert len(records) == 1
    assert records[0].data == {"a": 1, "b": "two"}
    assert records[0].source_format == "json"
    assert records[0].row_index == 0
    assert records[0].location == "object"


def test_reads_top_level_array_of_objects(tmp_path: Path) -> None:
    file = _write(
        tmp_path / "items.json",
        '[{"id": 1}, {"id": 2}, {"id": 3}]',
    )
    records = list(JsonFileReader(file, source_name="items").read())
    assert [r.data for r in records] == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert [r.row_index for r in records] == [0, 1, 2]
    assert records[2].location == "items[2]"


def test_array_of_non_objects_rejected(tmp_path: Path) -> None:
    file = _write(tmp_path / "bad.json", "[1, 2, 3]")
    with pytest.raises(SourceReadError, match=r"items\[0\]"):
        list(JsonFileReader(file, source_name="bad").read())


def test_top_level_primitive_rejected(tmp_path: Path) -> None:
    file = _write(tmp_path / "bad.json", '"just a string"')
    with pytest.raises(SourceReadError, match="object or array"):
        list(JsonFileReader(file, source_name="bad").read())


def test_invalid_json_rejected(tmp_path: Path) -> None:
    file = _write(tmp_path / "bad.json", "{not json}")
    with pytest.raises(SourceReadError, match="Invalid JSON"):
        list(JsonFileReader(file, source_name="bad").read())


def test_empty_file_rejected(tmp_path: Path) -> None:
    file = _write(tmp_path / "empty.json", "")
    with pytest.raises(SourceReadError, match="empty"):
        list(JsonFileReader(file, source_name="empty").read())


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(SourceReadError, match="not found"):
        list(JsonFileReader(tmp_path / "missing.json", source_name="x").read())


def test_reader_is_repeatable(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.json", '[{"a": 1}, {"a": 2}]')
    reader = JsonFileReader(file, source_name="x")
    first = [r.data for r in reader.read()]
    second = [r.data for r in reader.read()]
    assert first == second
