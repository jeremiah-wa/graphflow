"""Integration test for :class:`AccurateExtractor` against a deterministic
fake provider.

Marked ``integration`` because it touches the filesystem (reads a
fixture file shipped in the test directory). It does NOT call any
real LLM, hit the network, or require API keys: the provider is a
test double driven by hard-coded responses keyed off chunk text.

The slice exercised is:

    text fixture -> AccurateExtractor -> CandidateEntity list

with full cache + cost-tracking behaviour observable from the test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphflow_core.extraction import (
    AccurateExtractor,
    CostTracker,
    InMemoryExtractionCache,
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
        name="market_ontology",
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


def _chunk(text: str) -> TextChunk:
    return TextChunk(
        chunk_id="market-brief#0",
        text=text,
        source_name="market_brief",
        source_path=str(FIXTURE),
        chunk_index=0,
        location="chunk 0",
    )


class FixtureProvider:
    """Deterministic provider: returns hard-coded candidates discovered
    in the fixture text. The point is to verify the extractor's
    plumbing (validation, provenance, caching, cost) end-to-end without
    a real model."""

    def __init__(self, *, input_tokens: int = 120, output_tokens: int = 60) -> None:
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.call_count = 0

    def complete(self, *, system: str, user: str, model: str) -> LLMResponse:
        self.call_count += 1
        # The fixture mentions Acme Limited, Globex Industries,
        # Alice Johnson, Bob Smith. We pretend the model surfaced all
        # four with reasonable confidences and properties.
        text = json.dumps(
            {
                "candidates": [
                    {
                        "label": "Company",
                        "surface_text": "Acme Limited",
                        "confidence": 0.95,
                        "properties": {"name": "Acme Limited", "city": "Boston"},
                    },
                    {
                        "label": "Company",
                        "surface_text": "Globex Industries",
                        "confidence": 0.93,
                        "properties": {"name": "Globex Industries"},
                    },
                    {
                        "label": "Person",
                        "surface_text": "Alice Johnson",
                        "confidence": 0.9,
                        "properties": {"name": "Alice Johnson", "role": "CEO"},
                    },
                    {
                        "label": "Person",
                        "surface_text": "Bob Smith",
                        "confidence": 0.88,
                        "properties": {"name": "Bob Smith", "role": "CFO"},
                    },
                ]
            }
        )
        return LLMResponse(
            text=text,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            model=model,
        )


@pytest.mark.integration
def test_fixture_file_is_present() -> None:
    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"


@pytest.mark.integration
def test_extractor_produces_validated_candidates_with_provenance() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    provider = FixtureProvider()
    tracker = CostTracker(input_rate_per_1k=2.0, output_rate_per_1k=4.0)
    extractor = AccurateExtractor(provider=provider, model="fake-llm-1", cost_tracker=tracker)

    candidates = extractor.extract([_chunk(text)], ontology=_ontology())

    # All four labelled candidates surface, all carry full provenance
    # back to the fixture, and all are tagged as produced by the
    # accurate extractor.
    assert len(candidates) == 4
    labels = sorted(c.label for c in candidates)
    assert labels == ["Company", "Company", "Person", "Person"]
    for cand in candidates:
        assert cand.source_chunk_id == "market-brief#0"
        assert cand.source_name == "market_brief"
        assert cand.source_path == str(FIXTURE)
        assert cand.chunk_index == 0
        assert cand.extractor == "accurate"
        assert 0.0 <= cand.confidence <= 1.0

    company_props = next(c.properties for c in candidates if c.surface_text == "Acme Limited")
    assert company_props == {"name": "Acme Limited", "city": "Boston"}

    # Provider was called exactly once for the single chunk.
    assert provider.call_count == 1

    # Cost tracker recorded one billed call. Estimated cost:
    # 120*2 + 60*4 = 240 + 240 = 480 -> /1000 = 0.48
    summary = tracker.summary()
    assert summary["calls"] == 1
    assert summary["input_tokens"] == 120
    assert summary["output_tokens"] == 60
    assert summary["estimated_cost"] == pytest.approx(0.48)


@pytest.mark.integration
def test_second_run_with_same_chunk_hits_cache_and_zero_additional_cost() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    provider = FixtureProvider()
    tracker = CostTracker(input_rate_per_1k=1.0, output_rate_per_1k=1.0)
    cache = InMemoryExtractionCache()
    extractor = AccurateExtractor(
        provider=provider, model="fake-llm-1", cost_tracker=tracker, cache=cache
    )

    first = extractor.extract([_chunk(text)], ontology=_ontology())
    cost_after_first = tracker.total_cost
    second = extractor.extract([_chunk(text)], ontology=_ontology())

    # Same outputs, no new provider calls, no new cost.
    assert first == second
    assert provider.call_count == 1
    assert tracker.call_count == 1
    assert tracker.total_cost == cost_after_first


@pytest.mark.integration
def test_unknown_label_in_provider_output_aborts_run() -> None:
    text = FIXTURE.read_text(encoding="utf-8")

    class BadLabelProvider:
        def complete(self, *, system: str, user: str, model: str) -> LLMResponse:
            return LLMResponse(
                text=json.dumps(
                    {
                        "candidates": [
                            {
                                "label": "Vehicle",  # not in ontology
                                "surface_text": "Car",
                                "confidence": 0.9,
                            }
                        ]
                    }
                ),
                input_tokens=10,
                output_tokens=5,
                model=model,
            )

    extractor = AccurateExtractor(provider=BadLabelProvider(), model="x")
    with pytest.raises(Exception, match="not declared in the ontology"):
        extractor.extract([_chunk(text)], ontology=_ontology())
