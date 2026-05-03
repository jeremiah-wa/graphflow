"""Unit tests for :class:`CsvFileReader`."""

from __future__ import annotations

from pathlib import Path

import pytest

from graphflow_core.sources import CsvFileReader, SourceReader, SourceReadError


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_csv_reader_satisfies_source_reader_protocol(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.csv", "a,b\n1,2\n")
    reader = CsvFileReader(file, source_name="x")
    assert isinstance(reader, SourceReader)


def test_reads_basic_csv_with_header(tmp_path: Path) -> None:
    file = _write(
        tmp_path / "companies.csv",
        "company_number,company_name\n1,Foo Ltd\n2,Bar Ltd\n",
    )
    records = list(CsvFileReader(file, source_name="companies_csv").read())
    assert [r.data for r in records] == [
        {"company_number": "1", "company_name": "Foo Ltd"},
        {"company_number": "2", "company_name": "Bar Ltd"},
    ]
    assert records[0].source_format == "csv"
    assert records[0].source_name == "companies_csv"
    assert records[0].row_index == 0
    assert records[0].location == "row 2"
    assert records[1].row_index == 1
    assert records[1].location == "row 3"


def test_strips_header_whitespace(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.csv", " a , b \n1,2\n")
    record = next(CsvFileReader(file, source_name="x").read())
    assert record.data == {"a": "1", "b": "2"}


def test_empty_cells_become_empty_strings(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.csv", "a,b\n,\n")
    record = next(CsvFileReader(file, source_name="x").read())
    assert record.data == {"a": "", "b": ""}


def test_empty_file_raises(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.csv", "")
    with pytest.raises(SourceReadError, match="empty"):
        list(CsvFileReader(file, source_name="x").read())


def test_blank_header_raises(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.csv", " , , \n1,2,3\n")
    with pytest.raises(SourceReadError, match="blank header"):
        list(CsvFileReader(file, source_name="x").read())


def test_row_with_wrong_column_count_raises(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.csv", "a,b\n1,2\n3\n")
    with pytest.raises(SourceReadError, match="row 3"):
        list(CsvFileReader(file, source_name="x").read())


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceReadError, match="not found"):
        list(CsvFileReader(tmp_path / "missing.csv", source_name="x").read())


def test_reader_is_repeatable(tmp_path: Path) -> None:
    file = _write(tmp_path / "x.csv", "a\n1\n2\n")
    reader = CsvFileReader(file, source_name="x")
    first = [r.data for r in reader.read()]
    second = [r.data for r in reader.read()]
    assert first == second
