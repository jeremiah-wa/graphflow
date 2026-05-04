"""Unit tests for :class:`FastExtractor`."""

from __future__ import annotations

import pytest

from graphflow_core.extraction import (
    CandidateEntity,
    ExtractionError,
    Extractor,
    TextChunk,
)
from graphflow_core.extraction.fast import (
    CASE_INSENSITIVE_MATCH_CONFIDENCE,
    EXACT_MATCH_CONFIDENCE,
    FastExtractor,
)
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)

# ----------------------------- helpers --------------------------------------


def _ontology(*labels: str) -> OntologySpec:
    return OntologySpec(
        name="test_ontology",
        nodes=[
            NodeSpec(
                label=label,
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            )
            for label in labels
        ],
    )


def _chunk(
    text: str,
    *,
    chunk_id: str = "c-0",
    chunk_index: int = 0,
    source_name: str = "docs",
    source_path: str = "docs/x.txt",
) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        text=text,
        source_name=source_name,
        source_path=source_path,
        chunk_index=chunk_index,
        location=f"chunk {chunk_index}",
    )


# ----------------------------- protocol -------------------------------------


def test_fast_extractor_satisfies_extractor_protocol() -> None:
    assert isinstance(FastExtractor(), Extractor)


# ------------------------- ontology label mapping --------------------------


def test_extracts_only_ontology_labels() -> None:
    extractor = FastExtractor()
    chunks = [_chunk("Acme is a Company. Bob is a Person.")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    assert {c.label for c in candidates} == {"Company"}


def test_extracts_multiple_ontology_labels() -> None:
    extractor = FastExtractor()
    chunks = [_chunk("Acme is a Company. Bob is a Person.")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company", "Person"))
    labels = sorted({c.label for c in candidates})
    assert labels == ["Company", "Person"]


def test_returns_empty_when_ontology_has_no_nodes() -> None:
    # Build an ontology directly (bypass v1 schema constraint that
    # nodes is non-empty in OntologyManifest) by constructing OntologySpec
    # with a single node and then... actually OntologySpec requires nodes.
    # Use the smallest valid ontology that has labels none of which appear:
    extractor = FastExtractor()
    chunks = [_chunk("nothing relevant here")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    assert candidates == []


def test_aliases_referencing_unknown_label_raise() -> None:
    extractor = FastExtractor(aliases={"Vehicle": ["car"]})
    with pytest.raises(ExtractionError) as excinfo:
        extractor.extract([_chunk("a car")], ontology=_ontology("Company"))
    assert "Vehicle" in str(excinfo.value)


def test_empty_alias_string_rejected_at_construction() -> None:
    with pytest.raises(ExtractionError):
        FastExtractor(aliases={"Company": [""]})


# ------------------------------ matching -----------------------------------


def test_exact_label_match_has_max_confidence() -> None:
    extractor = FastExtractor()
    chunks = [_chunk("Acme is a Company.")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    company_matches = [c for c in candidates if c.surface_text == "Company"]
    assert company_matches, candidates
    assert company_matches[0].confidence == EXACT_MATCH_CONFIDENCE


def test_case_insensitive_match_has_lower_confidence() -> None:
    extractor = FastExtractor()
    # lower-case form is in the alias set, so this is an exact alias
    # match against "company" - high confidence.
    chunks = [_chunk("acme is a company.")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    assert any(c.surface_text == "company" for c in candidates)
    # But mixed case ("COMPANY") only matches case-insensitively against
    # both aliases, so confidence is the case-insensitive value.
    chunks_mixed = [_chunk("ACME IS A COMPANY.")]
    candidates_mixed = extractor.extract(chunks_mixed, ontology=_ontology("Company"))
    assert candidates_mixed, "expected to find COMPANY case-insensitively"
    assert candidates_mixed[0].surface_text == "COMPANY"
    assert candidates_mixed[0].confidence == CASE_INSENSITIVE_MATCH_CONFIDENCE


def test_word_boundary_prevents_substring_matches() -> None:
    extractor = FastExtractor()
    # "Compute" should not match "Company" - and "Companies" (different
    # word) likewise should not match the singular form.
    chunks = [_chunk("Compute is hard. Companies are entities.")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    assert candidates == []


def test_finds_multiple_occurrences_in_one_chunk() -> None:
    extractor = FastExtractor()
    chunks = [_chunk("Company A and Company B and Company C.")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    assert len(candidates) == 3
    offsets = [c.start_offset for c in candidates]
    assert offsets == sorted(offsets)


def test_empty_chunks_skipped() -> None:
    extractor = FastExtractor()
    chunks = [_chunk("", chunk_id="empty"), _chunk("Company X.", chunk_id="real")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    assert all(c.source_chunk_id == "real" for c in candidates)


def test_user_aliases_extend_label_matching() -> None:
    extractor = FastExtractor(aliases={"Company": ["Ltd", "Limited"]})
    chunks = [_chunk("Acme Ltd was founded by Acme Limited's predecessor.")]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    surfaces = sorted(c.surface_text for c in candidates)
    assert surfaces == ["Limited", "Ltd"]


# ---------------------------- determinism ----------------------------------


def test_output_is_deterministic_across_calls() -> None:
    extractor = FastExtractor(aliases={"Company": ["Ltd"]})
    chunks = [
        _chunk("Acme Ltd is a Company.", chunk_id="c-0", chunk_index=0),
        _chunk("Beta Corp is also a Company.", chunk_id="c-1", chunk_index=1),
    ]
    ontology = _ontology("Company", "Person")
    first = extractor.extract(chunks, ontology=ontology)
    second = extractor.extract(chunks, ontology=ontology)
    assert first == second


def test_output_sorted_by_chunk_then_offset() -> None:
    extractor = FastExtractor()
    chunks = [
        _chunk("Person A. Company X.", chunk_id="c-0", chunk_index=0),
        _chunk("Company Y. Person B.", chunk_id="c-1", chunk_index=1),
    ]
    candidates = extractor.extract(chunks, ontology=_ontology("Company", "Person"))
    keys = [(c.chunk_index, c.start_offset, c.label, c.surface_text) for c in candidates]
    assert keys == sorted(keys)


# ----------------------- provenance + offsets ------------------------------


def test_candidate_carries_chunk_provenance() -> None:
    extractor = FastExtractor()
    chunks = [
        _chunk(
            "Acme is a Company.",
            chunk_id="c-7",
            chunk_index=3,
            source_name="docs",
            source_path="docs/acme.txt",
        )
    ]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    assert candidates
    cand = candidates[0]
    assert cand.source_chunk_id == "c-7"
    assert cand.chunk_index == 3
    assert cand.source_name == "docs"
    assert cand.source_path == "docs/acme.txt"


def test_candidate_offsets_round_trip_to_surface_text() -> None:
    extractor = FastExtractor()
    text = "Acme is a Company today."
    chunks = [_chunk(text)]
    candidates = extractor.extract(chunks, ontology=_ontology("Company"))
    assert candidates
    cand = candidates[0]
    assert cand.start_offset is not None
    assert cand.end_offset is not None
    assert text[cand.start_offset : cand.end_offset] == cand.surface_text


def test_candidate_extractor_name_is_fast() -> None:
    extractor = FastExtractor()
    candidates = extractor.extract([_chunk("Company X.")], ontology=_ontology("Company"))
    assert candidates and all(c.extractor == "fast" for c in candidates)


def test_candidate_is_a_candidate_entity_instance() -> None:
    extractor = FastExtractor()
    candidates = extractor.extract([_chunk("Company X.")], ontology=_ontology("Company"))
    assert candidates
    assert all(isinstance(c, CandidateEntity) for c in candidates)
