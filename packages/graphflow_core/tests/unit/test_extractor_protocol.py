"""Unit tests for the :class:`Extractor` runtime-checkable protocol.

The protocol is the contract every extractor (fast, accurate LLM,
hybrid router, ...) must satisfy. These tests pin that contract so a
stub implementation registered through ``isinstance`` checks is
sufficient to act as an extractor in the rest of the pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable

from graphflow_core.extraction import CandidateEntity, Extractor, TextChunk
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)


def _ontology() -> OntologySpec:
    return OntologySpec(
        name="test_ontology",
        nodes=[
            NodeSpec(
                label="Company",
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            ),
        ],
    )


def test_stub_extractor_satisfies_protocol() -> None:
    class _StubExtractor:
        def extract(
            self,
            chunks: Iterable[TextChunk],
            *,
            ontology: OntologySpec,
        ) -> list[CandidateEntity]:
            del chunks, ontology
            return []

    assert isinstance(_StubExtractor(), Extractor)


def test_object_without_extract_does_not_satisfy_protocol() -> None:
    class _NotAnExtractor:
        pass

    assert not isinstance(_NotAnExtractor(), Extractor)


def test_stub_extractor_returns_candidate_list() -> None:
    class _Always:
        def extract(
            self,
            chunks: Iterable[TextChunk],
            *,
            ontology: OntologySpec,
        ) -> list[CandidateEntity]:
            del ontology
            return [
                CandidateEntity(
                    label="Company",
                    surface_text="Acme",
                    confidence=1.0,
                    source_chunk_id=chunk.chunk_id,
                    source_name=chunk.source_name,
                    source_path=chunk.source_path,
                    chunk_index=chunk.chunk_index,
                    extractor="stub",
                )
                for chunk in chunks
            ]

    extractor = _Always()
    chunks = [
        TextChunk(
            chunk_id="c-0",
            text="Acme is a company",
            source_name="docs",
            source_path="docs/a.txt",
            chunk_index=0,
            location="chunk 0",
        ),
    ]

    candidates = extractor.extract(chunks, ontology=_ontology())
    assert len(candidates) == 1
    assert candidates[0].label == "Company"
    assert candidates[0].source_chunk_id == "c-0"
    assert candidates[0].extractor == "stub"
