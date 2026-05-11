"""Unit tests for :class:`AccurateExtractor`.

Uses a deterministic fake :class:`LLMProvider` so the suite never
requires network or paid API keys.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from graphflow_core.extraction import (
    AccurateExtractor,
    CostLimitExceeded,
    CostTracker,
    ExtractionError,
    Extractor,
    InMemoryExtractionCache,
    LLMError,
    LLMResponse,
    TextChunk,
)
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------


def _ontology(*labels: str) -> OntologySpec:
    chosen = labels or ("Company", "Person")
    return OntologySpec(
        name="extraction_ontology",
        nodes=[
            NodeSpec(
                label=label,
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            )
            for label in chosen
        ],
    )


def _chunk(chunk_id: str = "c-0", text: str = "Acme Ltd hired Alice Johnson.") -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        text=text,
        source_name="news",
        source_path="docs/news.txt",
        chunk_index=0,
        location="chunk 0",
    )


class FakeProvider:
    """Deterministic provider driven by a per-call response factory.

    Records every (system, user, model) call so tests can assert on
    prompt construction.
    """

    def __init__(
        self,
        responder: Callable[[str, str, str], LLMResponse] | None = None,
    ) -> None:
        self._responder = responder or (
            lambda system, user, model: LLMResponse(
                text='{"candidates": []}',
                input_tokens=10,
                output_tokens=2,
                model=model,
            )
        )
        self.calls: list[tuple[str, str, str]] = []

    def complete(self, *, system: str, user: str, model: str) -> LLMResponse:
        self.calls.append((system, user, model))
        return self._responder(system, user, model)


def _candidate_payload(
    label: str = "Company", surface: str = "Acme Ltd", confidence: float = 0.9
) -> dict[str, object]:
    return {
        "label": label,
        "surface_text": surface,
        "confidence": confidence,
        "properties": {"name": surface},
        "start_offset": 0,
        "end_offset": len(surface),
    }


# ---------------------------------------------------------------------------
# Protocol & construction
# ---------------------------------------------------------------------------


def test_accurate_extractor_satisfies_extractor_protocol() -> None:
    extractor = AccurateExtractor(provider=FakeProvider(), model="m")
    assert isinstance(extractor, Extractor)


def test_empty_model_raises_extraction_error() -> None:
    with pytest.raises(ExtractionError):
        AccurateExtractor(provider=FakeProvider(), model="")


# ---------------------------------------------------------------------------
# Prompt construction (ontology-constrained)
# ---------------------------------------------------------------------------


def test_user_prompt_includes_sorted_ontology_labels_and_chunk_text() -> None:
    provider = FakeProvider()
    extractor = AccurateExtractor(provider=provider, model="m")
    extractor.extract([_chunk(text="hello")], ontology=_ontology("Person", "Company"))
    assert len(provider.calls) == 1
    _, user_prompt, _ = provider.calls[0]
    # Sorted alphabetically -> Company before Person.
    assert "['Company', 'Person']" in user_prompt
    assert "hello" in user_prompt
    assert "c-0" in user_prompt


def test_system_prompt_passed_through_to_provider() -> None:
    provider = FakeProvider()
    extractor = AccurateExtractor(provider=provider, model="m", system_prompt="CUSTOM SYSTEM")
    extractor.extract([_chunk(text="x")], ontology=_ontology())
    assert provider.calls[0][0] == "CUSTOM SYSTEM"


def test_model_passed_through_to_provider() -> None:
    provider = FakeProvider()
    extractor = AccurateExtractor(provider=provider, model="gpt-test")
    extractor.extract([_chunk(text="x")], ontology=_ontology())
    assert provider.calls[0][2] == "gpt-test"


def test_empty_chunk_text_skips_provider_call() -> None:
    provider = FakeProvider()
    extractor = AccurateExtractor(provider=provider, model="m")
    out = extractor.extract([_chunk(text="")], ontology=_ontology())
    assert out == []
    assert provider.calls == []


def test_empty_ontology_returns_no_candidates_without_calling_provider() -> None:
    provider = FakeProvider()
    extractor = AccurateExtractor(provider=provider, model="m")
    empty = OntologySpec(name="empty", nodes=[])
    out = extractor.extract([_chunk(text="x")], ontology=empty)
    assert out == []
    assert provider.calls == []


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------


def _provider_returning(text: str) -> FakeProvider:
    return FakeProvider(
        lambda system, user, model: LLMResponse(
            text=text, input_tokens=5, output_tokens=5, model=model
        )
    )


def test_valid_output_produces_candidates_with_chunk_provenance() -> None:
    provider = _provider_returning(json.dumps({"candidates": [_candidate_payload()]}))
    extractor = AccurateExtractor(provider=provider, model="m")
    out = extractor.extract([_chunk()], ontology=_ontology())
    assert len(out) == 1
    cand = out[0]
    assert cand.label == "Company"
    assert cand.surface_text == "Acme Ltd"
    assert cand.confidence == 0.9
    assert cand.properties == {"name": "Acme Ltd"}
    assert cand.source_chunk_id == "c-0"
    assert cand.source_name == "news"
    assert cand.source_path == "docs/news.txt"
    assert cand.chunk_index == 0
    assert cand.extractor == "accurate"


def test_malformed_json_raises_extraction_error() -> None:
    provider = _provider_returning("not json at all")
    extractor = AccurateExtractor(provider=provider, model="m")
    with pytest.raises(ExtractionError, match="not valid JSON"):
        extractor.extract([_chunk()], ontology=_ontology())


def test_schema_violation_raises_extraction_error() -> None:
    # Missing the required ``candidates`` key.
    provider = _provider_returning(json.dumps({"items": []}))
    extractor = AccurateExtractor(provider=provider, model="m")
    with pytest.raises(ExtractionError, match="schema validation"):
        extractor.extract([_chunk()], ontology=_ontology())


def test_unknown_label_raises_extraction_error() -> None:
    provider = _provider_returning(
        json.dumps({"candidates": [_candidate_payload(label="Vehicle")]})
    )
    extractor = AccurateExtractor(provider=provider, model="m")
    with pytest.raises(ExtractionError, match="not declared in the ontology"):
        extractor.extract([_chunk()], ontology=_ontology("Company", "Person"))


def test_invalid_confidence_raises_extraction_error() -> None:
    bad = _candidate_payload(confidence=1.5)
    provider = _provider_returning(json.dumps({"candidates": [bad]}))
    extractor = AccurateExtractor(provider=provider, model="m")
    with pytest.raises(ExtractionError):
        extractor.extract([_chunk()], ontology=_ontology())


def test_extra_fields_in_candidate_are_rejected() -> None:
    bad = {**_candidate_payload(), "unknown_field": "x"}
    provider = _provider_returning(json.dumps({"candidates": [bad]}))
    extractor = AccurateExtractor(provider=provider, model="m")
    with pytest.raises(ExtractionError):
        extractor.extract([_chunk()], ontology=_ontology())


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_second_call_with_same_chunk_hits_cache() -> None:
    provider = _provider_returning(json.dumps({"candidates": [_candidate_payload()]}))
    extractor = AccurateExtractor(provider=provider, model="m")
    ontology = _ontology()
    first = extractor.extract([_chunk()], ontology=ontology)
    second = extractor.extract([_chunk()], ontology=ontology)
    assert first == second
    # Provider was called once; the second call hit the cache.
    assert len(provider.calls) == 1


def test_changing_chunk_text_misses_cache() -> None:
    provider = _provider_returning(json.dumps({"candidates": [_candidate_payload()]}))
    extractor = AccurateExtractor(provider=provider, model="m")
    ontology = _ontology()
    extractor.extract([_chunk(text="alpha")], ontology=ontology)
    extractor.extract([_chunk(text="beta")], ontology=ontology)
    assert len(provider.calls) == 2


def test_changing_model_misses_cache() -> None:
    provider = _provider_returning(json.dumps({"candidates": [_candidate_payload()]}))
    cache = InMemoryExtractionCache()
    a = AccurateExtractor(provider=provider, model="m1", cache=cache)
    b = AccurateExtractor(provider=provider, model="m2", cache=cache)
    ontology = _ontology()
    a.extract([_chunk()], ontology=ontology)
    b.extract([_chunk()], ontology=ontology)
    assert len(provider.calls) == 2


def test_changing_ontology_misses_cache() -> None:
    provider = _provider_returning(json.dumps({"candidates": [_candidate_payload()]}))
    extractor = AccurateExtractor(provider=provider, model="m")
    extractor.extract([_chunk()], ontology=_ontology("Company"))
    extractor.extract([_chunk()], ontology=_ontology("Company", "Person"))
    assert len(provider.calls) == 2


def test_changing_system_prompt_misses_cache() -> None:
    provider = _provider_returning(json.dumps({"candidates": [_candidate_payload()]}))
    cache = InMemoryExtractionCache()
    a = AccurateExtractor(provider=provider, model="m", cache=cache, system_prompt="A")
    b = AccurateExtractor(provider=provider, model="m", cache=cache, system_prompt="B")
    ontology = _ontology()
    a.extract([_chunk()], ontology=ontology)
    b.extract([_chunk()], ontology=ontology)
    assert len(provider.calls) == 2


# ---------------------------------------------------------------------------
# Cost accounting
# ---------------------------------------------------------------------------


def test_cost_tracker_records_each_provider_call() -> None:
    provider = FakeProvider(
        lambda system, user, model: LLMResponse(
            text='{"candidates": []}',
            input_tokens=100,
            output_tokens=20,
            model=model,
        )
    )
    tracker = CostTracker(input_rate_per_1k=1.0, output_rate_per_1k=2.0)
    extractor = AccurateExtractor(provider=provider, model="m", cost_tracker=tracker)
    ontology = _ontology()
    extractor.extract(
        [_chunk(chunk_id="a", text="x"), _chunk(chunk_id="b", text="y")], ontology=ontology
    )
    assert tracker.call_count == 2
    assert tracker.total_input_tokens == 200
    assert tracker.total_output_tokens == 40
    # 200*1 + 40*2 = 280 -> /1000 = 0.28
    assert tracker.total_cost == pytest.approx(0.28)


def test_cache_hit_does_not_record_cost() -> None:
    provider = FakeProvider(
        lambda system, user, model: LLMResponse(
            text='{"candidates": []}',
            input_tokens=50,
            output_tokens=10,
            model=model,
        )
    )
    tracker = CostTracker(input_rate_per_1k=1.0, output_rate_per_1k=1.0)
    extractor = AccurateExtractor(provider=provider, model="m", cost_tracker=tracker)
    ontology = _ontology()
    extractor.extract([_chunk()], ontology=ontology)
    extractor.extract([_chunk()], ontology=ontology)  # cache hit
    assert tracker.call_count == 1


def test_cost_limit_exceeded_aborts_run() -> None:
    provider = FakeProvider(
        lambda system, user, model: LLMResponse(
            text='{"candidates": []}',
            input_tokens=1000,
            output_tokens=1000,
            model=model,
        )
    )
    tracker = CostTracker(input_rate_per_1k=1.0, output_rate_per_1k=1.0, limit=1.0)
    extractor = AccurateExtractor(provider=provider, model="m", cost_tracker=tracker)
    ontology = _ontology()
    chunks = [_chunk(chunk_id=f"c-{i}", text=f"text {i}") for i in range(3)]
    with pytest.raises(CostLimitExceeded):
        extractor.extract(chunks, ontology=ontology)


def test_cost_tracker_property_exposed_for_run_summary() -> None:
    extractor = AccurateExtractor(provider=FakeProvider(), model="m")
    assert isinstance(extractor.cost_tracker, CostTracker)


# ---------------------------------------------------------------------------
# Provider failure surfaces as ExtractionError (LLMError subclass)
# ---------------------------------------------------------------------------


def test_provider_llm_error_propagates_as_extraction_error() -> None:
    def explode(system: str, user: str, model: str) -> LLMResponse:
        raise LLMError("provider unavailable")

    extractor = AccurateExtractor(provider=FakeProvider(explode), model="m")
    with pytest.raises(LLMError, match="provider unavailable"):
        extractor.extract([_chunk()], ontology=_ontology())
    # And it's catchable as ExtractionError.
    extractor2 = AccurateExtractor(provider=FakeProvider(explode), model="m")
    with pytest.raises(ExtractionError):
        extractor2.extract([_chunk()], ontology=_ontology())


def test_unexpected_provider_exception_wrapped_in_llm_error() -> None:
    def explode(system: str, user: str, model: str) -> LLMResponse:
        raise RuntimeError("network reset")

    extractor = AccurateExtractor(provider=FakeProvider(explode), model="m")
    with pytest.raises(LLMError, match="provider call failed"):
        extractor.extract([_chunk()], ontology=_ontology())
