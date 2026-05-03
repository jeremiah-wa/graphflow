"""Unit tests for :class:`ParsedRecord` and the :class:`SourceReader` protocol."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from graphflow_core.sources import ParsedRecord, SourceReader


def _record(**overrides: object) -> ParsedRecord:
    base: dict[str, object] = {
        "data": {"id": "1"},
        "source_name": "companies_csv",
        "source_path": "data/companies.csv",
        "source_format": "csv",
        "row_index": 0,
        "location": "row 1",
    }
    base.update(overrides)
    return ParsedRecord.model_validate(base)


def test_parsed_record_round_trips() -> None:
    record = _record()
    assert record.data == {"id": "1"}
    assert record.source_format == "csv"
    assert record.row_index == 0


def test_parsed_record_rejects_negative_row_index() -> None:
    with pytest.raises(ValidationError):
        _record(row_index=-1)


def test_parsed_record_rejects_unknown_format() -> None:
    with pytest.raises(ValidationError):
        _record(source_format="xml")


def test_parsed_record_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _record(unexpected="boom")


def test_source_reader_protocol_is_runtime_checkable() -> None:
    class StubReader:
        def read(self) -> Iterator[ParsedRecord]:
            yield _record()

    class NotAReader:
        pass

    assert isinstance(StubReader(), SourceReader)
    assert not isinstance(NotAReader(), SourceReader)
