"""Unit tests for :class:`TextChunk`, :class:`CandidateEntity`, and
:class:`ExtractionError`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from graphflow_core.extraction import CandidateEntity, ExtractionError, TextChunk

# ----------------------------- TextChunk ------------------------------------


def test_text_chunk_minimal_valid() -> None:
    chunk = TextChunk(
        chunk_id="c-0",
        text="Acme Ltd was founded in 2010.",
        source_name="docs",
        source_path="docs/acme.txt",
        chunk_index=0,
        location="chunk 0",
    )
    assert chunk.chunk_id == "c-0"
    assert chunk.chunk_index == 0


def test_text_chunk_allows_empty_text() -> None:
    # An empty chunk is uninteresting but not invalid; an extractor will
    # simply yield no candidates for it. This is symmetric with the way
    # ParsedRecord allows empty data dicts.
    TextChunk(
        chunk_id="c-0",
        text="",
        source_name="docs",
        source_path="docs/empty.txt",
        chunk_index=0,
        location="chunk 0",
    )


def test_text_chunk_rejects_negative_chunk_index() -> None:
    with pytest.raises(ValidationError):
        TextChunk(
            chunk_id="c-0",
            text="hello",
            source_name="docs",
            source_path="docs/x.txt",
            chunk_index=-1,
            location="chunk -1",
        )


def test_text_chunk_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        TextChunk(
            chunk_id="c-0",
            text="hello",
            source_name="docs",
            source_path="docs/x.txt",
            chunk_index=0,
            location="chunk 0",
            extra_field="nope",  # type: ignore[call-arg]
        )


@pytest.mark.parametrize("blank_field", ["chunk_id", "source_name", "source_path", "location"])
def test_text_chunk_rejects_blank_required_strings(blank_field: str) -> None:
    kwargs = {
        "chunk_id": "c-0",
        "text": "hello",
        "source_name": "docs",
        "source_path": "docs/x.txt",
        "chunk_index": 0,
        "location": "chunk 0",
    }
    kwargs[blank_field] = ""
    with pytest.raises(ValidationError):
        TextChunk(**kwargs)  # type: ignore[arg-type]


# ---------------------------- CandidateEntity -------------------------------


def _candidate(**overrides: object) -> CandidateEntity:
    base: dict[str, object] = {
        "label": "Company",
        "surface_text": "Acme Ltd",
        "confidence": 0.9,
        "source_chunk_id": "c-0",
        "source_name": "docs",
        "source_path": "docs/acme.txt",
        "chunk_index": 0,
        "extractor": "fast",
    }
    base.update(overrides)
    return CandidateEntity(**base)  # type: ignore[arg-type]


def test_candidate_minimal_valid() -> None:
    cand = _candidate()
    assert cand.label == "Company"
    assert cand.confidence == 0.9
    assert cand.properties == {}
    assert cand.start_offset is None
    assert cand.end_offset is None


def test_candidate_with_offsets() -> None:
    cand = _candidate(start_offset=0, end_offset=8)
    assert cand.start_offset == 0
    assert cand.end_offset == 8


def test_candidate_with_properties() -> None:
    cand = _candidate(properties={"name": "Acme Ltd"})
    assert cand.properties == {"name": "Acme Ltd"}


@pytest.mark.parametrize("confidence", [-0.01, 1.01, -1.0, 2.0])
def test_candidate_rejects_confidence_out_of_range(confidence: float) -> None:
    with pytest.raises(ValidationError):
        _candidate(confidence=confidence)


def test_candidate_rejects_only_start_offset() -> None:
    with pytest.raises(ValidationError):
        _candidate(start_offset=0)


def test_candidate_rejects_only_end_offset() -> None:
    with pytest.raises(ValidationError):
        _candidate(end_offset=8)


def test_candidate_rejects_inverted_offsets() -> None:
    with pytest.raises(ValidationError):
        _candidate(start_offset=10, end_offset=5)


def test_candidate_rejects_zero_length_offsets() -> None:
    with pytest.raises(ValidationError):
        _candidate(start_offset=5, end_offset=5)


def test_candidate_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _candidate(probability=0.5)


# ---------------------------- ExtractionError -------------------------------


def test_extraction_error_is_exception_subclass() -> None:
    assert issubclass(ExtractionError, Exception)


def test_extraction_error_can_be_raised_and_caught() -> None:
    with pytest.raises(ExtractionError) as excinfo:
        raise ExtractionError("boom")
    assert "boom" in str(excinfo.value)
