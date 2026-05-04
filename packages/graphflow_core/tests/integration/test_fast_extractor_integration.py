"""Integration test for the fast extractor against a committed text fixture.

Marked ``integration`` because it touches the filesystem (reads a
fixture file shipped in the test directory). It does not require any
external services, network access, or paid APIs - just disk - so it
runs in the same job as the other filesystem-backed integration tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphflow_core.extraction import FastExtractor, TextChunk
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)

FIXTURE = Path(__file__).parent / "fixtures" / "extraction" / "company_news.txt"


def _ontology() -> OntologySpec:
    return OntologySpec(
        name="news_ontology",
        nodes=[
            NodeSpec(
                label="Company",
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            ),
            NodeSpec(
                label="Person",
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            ),
        ],
    )


@pytest.mark.integration
def test_fixture_file_is_present() -> None:
    # Cheap guard: if the fixture is missing we want a clearer failure
    # than "no candidates returned".
    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"


@pytest.mark.integration
def test_fast_extractor_runs_against_committed_text_fixture() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    chunk = TextChunk(
        chunk_id=f"{FIXTURE.name}#0",
        text=text,
        source_name="news_documents",
        source_path=str(FIXTURE),
        chunk_index=0,
        location=f"{FIXTURE.name} chunk 0",
    )

    extractor = FastExtractor(
        aliases={
            "Company": ["Corporation"],
            "Person": ["Alice Johnson", "Bob Smith"],
        }
    )
    candidates = extractor.extract([chunk], ontology=_ontology())

    # The extractor must surface at least one Company and one Person
    # from the fixture; we are deliberately not asserting an exact
    # count so the fixture can be tweaked later without rewriting the
    # test, but we do pin the qualitative behaviour: known names are
    # found, every candidate carries provenance, and offsets round-
    # trip back to the fixture text.
    assert any(c.label == "Company" for c in candidates), candidates
    assert any(c.label == "Person" for c in candidates), candidates

    for candidate in candidates:
        assert candidate.source_name == "news_documents"
        assert candidate.source_path == str(FIXTURE)
        assert candidate.chunk_index == 0
        assert candidate.extractor == "fast"
        assert candidate.start_offset is not None
        assert candidate.end_offset is not None
        assert text[candidate.start_offset : candidate.end_offset] == candidate.surface_text

    surface_texts = {c.surface_text for c in candidates}
    assert {"Alice Johnson", "Bob Smith"}.issubset(surface_texts)
    assert "Corporation" in surface_texts


@pytest.mark.integration
def test_fast_extractor_run_is_repeatable() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    chunk = TextChunk(
        chunk_id="news#0",
        text=text,
        source_name="news_documents",
        source_path=str(FIXTURE),
        chunk_index=0,
        location="chunk 0",
    )
    extractor = FastExtractor(aliases={"Person": ["Alice Johnson", "Bob Smith"]})
    ontology = _ontology()
    first = extractor.extract([chunk], ontology=ontology)
    second = extractor.extract([chunk], ontology=ontology)
    assert first == second
