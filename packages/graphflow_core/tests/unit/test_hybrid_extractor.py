"""Unit tests for :class:`HybridExtractor` and :class:`HybridRouting`.

The tests use deterministic in-test stubs for the fast and accurate
extractors. The router does not care about the provenance of its
inputs, only that they satisfy the :class:`Extractor` protocol.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from pydantic import ValidationError

from graphflow_core.extraction import (
    CandidateEntity,
    CostLimitExceeded,
    Extractor,
    HybridExtractor,
    HybridRouting,
    HybridRunSummary,
    TextChunk,
)
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _ontology(*labels: str) -> OntologySpec:
    chosen = labels or ("Company", "Person")
    return OntologySpec(
        name="hybrid_ontology",
        nodes=[
            NodeSpec(
                label=label,
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            )
            for label in chosen
        ],
    )


def _chunk(chunk_id: str = "c-0", text: str = "some text") -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        text=text,
        source_name="src",
        source_path="docs/x.txt",
        chunk_index=int(chunk_id.split("-")[-1]) if "-" in chunk_id else 0,
        location=f"chunk {chunk_id}",
    )


def _candidate(
    *,
    chunk_id: str,
    label: str = "Company",
    surface: str = "Acme",
    confidence: float = 0.9,
    extractor: str = "fast",
) -> CandidateEntity:
    return CandidateEntity(
        label=label,
        surface_text=surface,
        confidence=confidence,
        source_chunk_id=chunk_id,
        source_name="src",
        source_path="docs/x.txt",
        chunk_index=0,
        extractor=extractor,
    )


class StubExtractor:
    """Deterministic fake extractor.

    Returns ``responses[chunk_id]`` per chunk and records every call
    so tests can assert on which chunks were routed where.
    """

    def __init__(
        self,
        responses: dict[str, list[CandidateEntity]] | None = None,
        *,
        raise_on: dict[str, Exception] | None = None,
    ) -> None:
        self._responses = responses or {}
        self._raise_on = raise_on or {}
        self.received_chunk_ids: list[str] = []

    def extract(
        self,
        chunks: Iterable[TextChunk],
        *,
        ontology: OntologySpec,
    ) -> list[CandidateEntity]:
        out: list[CandidateEntity] = []
        for chunk in chunks:
            self.received_chunk_ids.append(chunk.chunk_id)
            if chunk.chunk_id in self._raise_on:
                raise self._raise_on[chunk.chunk_id]
            out.extend(self._responses.get(chunk.chunk_id, []))
        return out


# ---------------------------------------------------------------------------
# Routing model
# ---------------------------------------------------------------------------


def test_hybrid_routing_defaults() -> None:
    r = HybridRouting()
    assert r.min_confidence == 0.7
    assert r.require_labels == ()
    assert r.force_chunk_ids == frozenset()
    assert r.continue_on_cost_limit is False


def test_hybrid_routing_loadable_from_dict() -> None:
    """Mirrors what loading from pipeline.yaml will look like."""
    r = HybridRouting.model_validate(
        {
            "min_confidence": 0.5,
            "require_labels": ["Company", "Person"],
            "force_chunk_ids": ["c-2"],
            "continue_on_cost_limit": True,
        }
    )
    assert r.min_confidence == 0.5
    assert r.require_labels == ("Company", "Person")
    assert r.force_chunk_ids == frozenset({"c-2"})
    assert r.continue_on_cost_limit is True


def test_hybrid_routing_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        HybridRouting.model_validate({"min_confidence": 0.5, "typo": True})


def test_hybrid_routing_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValidationError):
        HybridRouting(min_confidence=1.5)
    with pytest.raises(ValidationError):
        HybridRouting(min_confidence=-0.1)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


def test_hybrid_extractor_satisfies_extractor_protocol() -> None:
    fast = StubExtractor()
    accurate = StubExtractor()
    hybrid = HybridExtractor(fast=fast, accurate=accurate)
    assert isinstance(hybrid, Extractor)


# ---------------------------------------------------------------------------
# Routing rule: confidence
# ---------------------------------------------------------------------------


def test_high_confidence_chunk_stays_on_fast_path() -> None:
    chunk = _chunk("c-0")
    fast = StubExtractor({"c-0": [_candidate(chunk_id="c-0", confidence=0.95)]})
    accurate = StubExtractor()
    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(min_confidence=0.7),
    )
    out = hybrid.extract([chunk], ontology=_ontology())
    assert len(out) == 1
    assert accurate.received_chunk_ids == []
    assert hybrid.summary.chunks_routed_to_accurate == 0
    assert hybrid.summary.routing_reasons == {}


def test_low_confidence_chunk_routed_to_accurate() -> None:
    chunk = _chunk("c-0")
    fast = StubExtractor({"c-0": [_candidate(chunk_id="c-0", confidence=0.3)]})
    accurate = StubExtractor(
        {
            "c-0": [
                _candidate(
                    chunk_id="c-0",
                    surface="Globex",
                    confidence=0.92,
                    extractor="accurate",
                )
            ]
        }
    )
    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(min_confidence=0.7),
    )
    out = hybrid.extract([chunk], ontology=_ontology())
    assert accurate.received_chunk_ids == ["c-0"]
    extractors_seen = {c.extractor for c in out}
    assert extractors_seen == {"fast", "accurate"}
    assert hybrid.summary.routing_reasons["c-0"] == "low_confidence"


def test_chunk_with_no_fast_candidates_routes_on_zero_confidence() -> None:
    """No fast candidates -> max confidence is 0 -> below threshold."""
    chunk = _chunk("c-0")
    fast = StubExtractor({})  # nothing for c-0
    accurate = StubExtractor({"c-0": [_candidate(chunk_id="c-0", extractor="accurate")]})
    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(min_confidence=0.5),
    )
    hybrid.extract([chunk], ontology=_ontology())
    assert accurate.received_chunk_ids == ["c-0"]
    assert hybrid.summary.routing_reasons["c-0"] == "low_confidence"


# ---------------------------------------------------------------------------
# Routing rule: required labels missing
# ---------------------------------------------------------------------------


def test_required_label_present_keeps_fast_path() -> None:
    chunk = _chunk("c-0")
    fast = StubExtractor(
        {
            "c-0": [
                _candidate(chunk_id="c-0", label="Company", confidence=0.95),
                _candidate(chunk_id="c-0", label="Person", confidence=0.95),
            ]
        }
    )
    accurate = StubExtractor()
    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(require_labels=("Company", "Person")),
    )
    hybrid.extract([chunk], ontology=_ontology())
    assert accurate.received_chunk_ids == []


def test_missing_required_label_routes_to_accurate() -> None:
    chunk = _chunk("c-0")
    fast = StubExtractor(
        {
            "c-0": [
                _candidate(chunk_id="c-0", label="Company", confidence=0.95),
            ]
        }
    )
    accurate = StubExtractor(
        {
            "c-0": [
                _candidate(
                    chunk_id="c-0",
                    label="Person",
                    surface="Alice",
                    confidence=0.9,
                    extractor="accurate",
                ),
            ]
        }
    )
    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(
            min_confidence=0.0,  # disable confidence rule
            require_labels=("Company", "Person"),
        ),
    )
    hybrid.extract([chunk], ontology=_ontology())
    assert accurate.received_chunk_ids == ["c-0"]
    assert hybrid.summary.routing_reasons["c-0"] == "missing_label:Person"


# ---------------------------------------------------------------------------
# Routing rule: forced chunks
# ---------------------------------------------------------------------------


def test_force_chunk_ids_overrides_high_confidence() -> None:
    chunk = _chunk("c-0")
    # Fast confidence is excellent; would normally stay on fast path.
    fast = StubExtractor({"c-0": [_candidate(chunk_id="c-0", confidence=1.0)]})
    accurate = StubExtractor({"c-0": [_candidate(chunk_id="c-0", extractor="accurate")]})
    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(force_chunk_ids=frozenset({"c-0"})),
    )
    hybrid.extract([chunk], ontology=_ontology())
    assert accurate.received_chunk_ids == ["c-0"]
    assert hybrid.summary.routing_reasons["c-0"] == "forced"


def test_forced_reason_takes_precedence_over_other_reasons() -> None:
    """When multiple rules would fire, `forced` is recorded."""
    chunk = _chunk("c-0")
    fast = StubExtractor({"c-0": []})  # would also trigger low_confidence
    accurate = StubExtractor({"c-0": [_candidate(chunk_id="c-0", extractor="accurate")]})
    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(
            min_confidence=0.7,
            require_labels=("Company",),
            force_chunk_ids=frozenset({"c-0"}),
        ),
    )
    hybrid.extract([chunk], ontology=_ontology())
    assert hybrid.summary.routing_reasons["c-0"] == "forced"


# ---------------------------------------------------------------------------
# Output composition + summary
# ---------------------------------------------------------------------------


def test_output_concatenates_fast_then_accurate() -> None:
    chunks = [_chunk("c-0"), _chunk("c-1")]
    fast = StubExtractor(
        {
            "c-0": [_candidate(chunk_id="c-0", confidence=0.95)],
            "c-1": [_candidate(chunk_id="c-1", confidence=0.3)],
        }
    )
    accurate = StubExtractor(
        {
            "c-1": [
                _candidate(
                    chunk_id="c-1",
                    surface="Globex",
                    confidence=0.9,
                    extractor="accurate",
                )
            ]
        }
    )
    hybrid = HybridExtractor(fast=fast, accurate=accurate)
    out = hybrid.extract(chunks, ontology=_ontology())
    assert [c.extractor for c in out] == ["fast", "fast", "accurate"]


def test_summary_records_counts() -> None:
    chunks = [_chunk("c-0"), _chunk("c-1"), _chunk("c-2")]
    fast = StubExtractor(
        {
            "c-0": [_candidate(chunk_id="c-0", confidence=0.95)],
            "c-1": [_candidate(chunk_id="c-1", confidence=0.4)],
            # c-2: no fast candidates
        }
    )
    accurate = StubExtractor(
        {
            "c-1": [_candidate(chunk_id="c-1", extractor="accurate")],
            "c-2": [
                _candidate(chunk_id="c-2", extractor="accurate"),
                _candidate(
                    chunk_id="c-2",
                    surface="Globex",
                    extractor="accurate",
                ),
            ],
        }
    )
    hybrid = HybridExtractor(fast=fast, accurate=accurate)
    hybrid.extract(chunks, ontology=_ontology())

    summary = hybrid.summary
    assert isinstance(summary, HybridRunSummary)
    assert summary.total_chunks == 3
    assert summary.chunks_routed_to_accurate == 2
    assert summary.fast_candidate_count == 2
    assert summary.accurate_candidate_count == 3
    assert summary.cost_limit_triggered is False
    assert set(summary.routing_reasons.keys()) == {"c-1", "c-2"}


def test_summary_resets_between_runs() -> None:
    fast = StubExtractor()
    accurate = StubExtractor()
    hybrid = HybridExtractor(fast=fast, accurate=accurate)

    hybrid.extract([_chunk("c-0"), _chunk("c-1")], ontology=_ontology())
    assert hybrid.summary.total_chunks == 2

    hybrid.extract([_chunk("c-9")], ontology=_ontology())
    # Not 3, not 2 + 1.
    assert hybrid.summary.total_chunks == 1


def test_summary_as_dict_is_jsonable() -> None:
    fast = StubExtractor()
    accurate = StubExtractor()
    hybrid = HybridExtractor(fast=fast, accurate=accurate)
    hybrid.extract([_chunk("c-0")], ontology=_ontology())
    payload = hybrid.summary.as_dict()
    # All values are JSON-friendly primitives.
    import json

    json.dumps(payload)


# ---------------------------------------------------------------------------
# Cost-limit handling
# ---------------------------------------------------------------------------


def test_cost_limit_propagates_by_default() -> None:
    chunks = [_chunk("c-0"), _chunk("c-1")]
    fast = StubExtractor()  # no fast candidates -> both routed to accurate
    accurate = StubExtractor(
        responses={"c-0": [_candidate(chunk_id="c-0", extractor="accurate")]},
        raise_on={"c-1": CostLimitExceeded(limit=1.0, projected=2.0)},
    )
    hybrid = HybridExtractor(fast=fast, accurate=accurate)
    with pytest.raises(CostLimitExceeded):
        hybrid.extract(chunks, ontology=_ontology())
    assert hybrid.summary.cost_limit_triggered is True


def test_cost_limit_with_continue_returns_partial_results() -> None:
    chunks = [_chunk("c-0"), _chunk("c-1"), _chunk("c-2")]
    fast = StubExtractor()  # everything routed
    accurate = StubExtractor(
        responses={"c-0": [_candidate(chunk_id="c-0", extractor="accurate")]},
        raise_on={"c-1": CostLimitExceeded(limit=1.0, projected=2.0)},
    )
    hybrid = HybridExtractor(
        fast=fast,
        accurate=accurate,
        routing=HybridRouting(continue_on_cost_limit=True),
    )
    out = hybrid.extract(chunks, ontology=_ontology())
    # Got the c-0 result before the limit hit; c-2 was never attempted.
    assert len(out) == 1
    assert out[0].source_chunk_id == "c-0"
    assert hybrid.summary.cost_limit_triggered is True
    # c-2 was not visited by accurate after the limit triggered.
    assert "c-2" not in accurate.received_chunk_ids


# ---------------------------------------------------------------------------
# No-op cases
# ---------------------------------------------------------------------------


def test_empty_chunks_returns_empty_without_calling_either() -> None:
    fast = StubExtractor()
    accurate = StubExtractor()
    hybrid = HybridExtractor(fast=fast, accurate=accurate)
    out = hybrid.extract([], ontology=_ontology())
    assert out == []
    assert fast.received_chunk_ids == []
    assert accurate.received_chunk_ids == []
    assert hybrid.summary.total_chunks == 0


def test_no_chunks_routed_means_accurate_never_called() -> None:
    chunks = [_chunk("c-0"), _chunk("c-1")]
    fast = StubExtractor(
        {
            "c-0": [_candidate(chunk_id="c-0", confidence=1.0)],
            "c-1": [_candidate(chunk_id="c-1", confidence=1.0)],
        }
    )
    accurate = StubExtractor()
    hybrid = HybridExtractor(fast=fast, accurate=accurate)
    hybrid.extract(chunks, ontology=_ontology())
    assert accurate.received_chunk_ids == []
