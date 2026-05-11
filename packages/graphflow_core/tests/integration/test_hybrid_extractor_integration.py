"""Integration tests for :class:`HybridExtractor`.

Two complementary scenarios:

1. **Order test.** Verifies that fast and accurate stub extractors are
   called in the expected order: fast over every chunk, accurate only
   over the chunks the router selected, and the resulting candidate
   list is fast-then-accurate.
2. **E2E slice.** Wires the *real* :class:`FastExtractor` and
   :class:`AccurateExtractor` (the latter with a deterministic fake
   :class:`LLMProvider`) behind :class:`HybridExtractor` against a
   committed text fixture, and asserts on the final merged candidate
   stream + run summary.

Both are marked ``integration`` because they read a fixture file from
disk. Neither requires network access or paid API keys.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest

from graphflow_core.extraction import (
    AccurateExtractor,
    CandidateEntity,
    FastExtractor,
    HybridExtractor,
    HybridRouting,
    LLMResponse,
    TextChunk,
)
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)

FIXTURE = Path(__file__).parent / "fixtures" / "extraction_accurate" / "market_brief.txt"


def _ontology() -> OntologySpec:
    return OntologySpec(
        name="hybrid_ontology",
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


def _chunk(chunk_id: str, text: str) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        text=text,
        source_name="hybrid_test",
        source_path=str(FIXTURE),
        chunk_index=int(chunk_id.split("-")[-1]),
        location=f"chunk {chunk_id}",
    )


# ---------------------------------------------------------------------------
# 1. Order test: stub extractors record call order
# ---------------------------------------------------------------------------


class RecordingExtractor:
    def __init__(
        self,
        name: str,
        responses: dict[str, list[CandidateEntity]] | None = None,
    ) -> None:
        self.name = name
        self._responses = responses or {}
        self.calls: list[list[str]] = []

    def extract(
        self,
        chunks: Iterable[TextChunk],
        *,
        ontology: OntologySpec,
    ) -> list[CandidateEntity]:
        chunk_list = list(chunks)
        self.calls.append([c.chunk_id for c in chunk_list])
        out: list[CandidateEntity] = []
        for chunk in chunk_list:
            out.extend(self._responses.get(chunk.chunk_id, []))
        return out


def _candidate(
    chunk_id: str, *, label: str, surface: str, confidence: float, extractor: str
) -> CandidateEntity:
    return CandidateEntity(
        label=label,
        surface_text=surface,
        confidence=confidence,
        source_chunk_id=chunk_id,
        source_name="hybrid_test",
        source_path=str(FIXTURE),
        chunk_index=int(chunk_id.split("-")[-1]),
        extractor=extractor,
    )


@pytest.mark.integration
def test_fast_then_accurate_call_order() -> None:
    chunks = [
        _chunk("c-0", "high-confidence chunk"),
        _chunk("c-1", "low-confidence chunk"),
        _chunk("c-2", "another high-confidence chunk"),
    ]

    fast = RecordingExtractor(
        "fast",
        responses={
            "c-0": [
                _candidate(
                    "c-0",
                    label="Company",
                    surface="Acme",
                    confidence=0.95,
                    extractor="fast",
                )
            ],
            "c-1": [
                _candidate(
                    "c-1",
                    label="Company",
                    surface="X",
                    confidence=0.4,
                    extractor="fast",
                )
            ],
            "c-2": [
                _candidate(
                    "c-2",
                    label="Company",
                    surface="Globex",
                    confidence=0.95,
                    extractor="fast",
                )
            ],
        },
    )
    accurate = RecordingExtractor(
        "accurate",
        responses={
            "c-1": [
                _candidate(
                    "c-1",
                    label="Person",
                    surface="Alice",
                    confidence=0.9,
                    extractor="accurate",
                )
            ],
        },
    )

    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(min_confidence=0.7),
    )
    out = hybrid.extract(chunks, ontology=_ontology())

    # Fast was called once with all three chunks.
    assert len(fast.calls) == 1
    assert fast.calls[0] == ["c-0", "c-1", "c-2"]

    # Accurate was called only for c-1, and per-chunk (one call per
    # routed chunk) so cost-limit failures preserve partial progress.
    assert accurate.calls == [["c-1"]]

    # Output is fast-then-accurate.
    assert [c.extractor for c in out] == ["fast", "fast", "fast", "accurate"]
    assert hybrid.summary.chunks_routed_to_accurate == 1
    assert hybrid.summary.routing_reasons == {"c-1": "low_confidence"}


# ---------------------------------------------------------------------------
# 2. E2E slice: real fast + real accurate (fake provider)
# ---------------------------------------------------------------------------


class FixtureProvider:
    """Deterministic provider whose response asserts the chunks that
    needed accurate extraction in the fixture (Person mentions that the
    fast extractor cannot resolve from labels alone)."""

    def __init__(self) -> None:
        self.call_count = 0

    def complete(self, *, system: str, user: str, model: str) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            text=json.dumps(
                {
                    "candidates": [
                        {
                            "label": "Person",
                            "surface_text": "Alice Johnson",
                            "confidence": 0.92,
                            "properties": {"name": "Alice Johnson", "role": "CEO"},
                        },
                        {
                            "label": "Person",
                            "surface_text": "Bob Smith",
                            "confidence": 0.91,
                            "properties": {"name": "Bob Smith", "role": "CFO"},
                        },
                    ]
                }
            ),
            input_tokens=80,
            output_tokens=40,
            model=model,
        )


@pytest.mark.integration
def test_e2e_fast_then_accurate_with_real_extractors() -> None:
    """Drive HybridExtractor with the real FastExtractor and the real
    AccurateExtractor (fake provider) over a committed fixture.

    The fixture mentions ``Acme Limited`` / ``Globex Industries`` -
    which the fast extractor finds via the ``Company`` label - and
    ``Alice Johnson`` / ``Bob Smith``, which the fast path will only
    find if it is given Person aliases. We deliberately *don't* give
    those aliases so the missing-label rule routes the chunk to the
    accurate extractor. This exercises the recommended hybrid setup:
    fast catches what aliases cover, accurate fills the gaps.
    """
    text = FIXTURE.read_text(encoding="utf-8")
    chunk = _chunk("c-0", text)

    fast = FastExtractor(aliases={"Company": ["Acme Limited", "Globex Industries"]})
    provider = FixtureProvider()
    accurate = AccurateExtractor(provider=provider, model="fake-llm")

    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(
            min_confidence=0.0,  # disable confidence rule
            require_labels=("Company", "Person"),
        ),
    )
    out = hybrid.extract([chunk], ontology=_ontology())

    # Fast surfaced the two companies; accurate surfaced the two people.
    fast_companies = sorted(
        c.surface_text for c in out if c.extractor == "fast" and c.label == "Company"
    )
    accurate_persons = sorted(
        c.surface_text for c in out if c.extractor == "accurate" and c.label == "Person"
    )
    assert fast_companies == ["Acme Limited", "Globex Industries"]
    assert accurate_persons == ["Alice Johnson", "Bob Smith"]

    # The provider was called exactly once (only c-0 was routed).
    assert provider.call_count == 1

    summary = hybrid.summary
    assert summary.total_chunks == 1
    assert summary.chunks_routed_to_accurate == 1
    assert summary.fast_candidate_count == 2
    assert summary.accurate_candidate_count == 2
    assert summary.routing_reasons == {"c-0": "missing_label:Person"}
    assert summary.cost_limit_triggered is False


@pytest.mark.integration
def test_e2e_high_confidence_skips_accurate_entirely() -> None:
    """When fast covers everything required, accurate is never called -
    the hybrid is just a free pass-through."""
    text = FIXTURE.read_text(encoding="utf-8")
    chunk = _chunk("c-0", text)

    fast = FastExtractor(
        aliases={
            "Company": ["Acme Limited", "Globex Industries"],
            "Person": ["Alice Johnson", "Bob Smith"],
        }
    )
    provider = FixtureProvider()
    accurate = AccurateExtractor(provider=provider, model="fake-llm")

    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(
            min_confidence=0.5,
            require_labels=("Company", "Person"),
        ),
    )
    out = hybrid.extract([chunk], ontology=_ontology())

    assert provider.call_count == 0
    assert all(c.extractor == "fast" for c in out)
    assert hybrid.summary.chunks_routed_to_accurate == 0
    assert hybrid.summary.accurate_candidate_count == 0
