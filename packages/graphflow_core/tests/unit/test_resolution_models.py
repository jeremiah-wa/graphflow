"""Unit tests for :class:`ResolvedEntity`, :class:`ResolutionDecision`,
:class:`ResolutionResult`, and :class:`ResolutionError`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from graphflow_core.extraction import CandidateEntity
from graphflow_core.resolution import (
    ResolutionDecision,
    ResolutionError,
    ResolutionResult,
    ResolvedEntity,
)

# ----------------------------- helpers -------------------------------------


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


def _resolved(**overrides: object) -> ResolvedEntity:
    base: dict[str, object] = {
        "entity_id": "Company:acme_ltd",
        "label": "Company",
        "canonical_surface": "Acme Ltd",
        "candidate_count": 1,
        "source_chunk_id": "c-0",
        "source_name": "docs",
        "source_path": "docs/acme.txt",
        "chunk_index": 0,
    }
    base.update(overrides)
    return ResolvedEntity(**base)  # type: ignore[arg-type]


def _decision(**overrides: object) -> ResolutionDecision:
    base: dict[str, object] = {
        "candidate": _candidate(),
        "status": "auto_link",
        "entity_id": "Company:acme_ltd",
        "score": 1.0,
        "reason": "exact normalized match",
    }
    base.update(overrides)
    return ResolutionDecision(**base)  # type: ignore[arg-type]


# ----------------------------- ResolvedEntity ------------------------------


def test_resolved_entity_minimal_valid() -> None:
    resolved = _resolved()
    assert resolved.entity_id == "Company:acme_ltd"
    assert resolved.label == "Company"
    assert resolved.canonical_surface == "Acme Ltd"
    assert resolved.properties == {}
    assert resolved.needs_review is False
    assert resolved.candidate_count == 1


def test_resolved_entity_with_properties_and_review_flag() -> None:
    resolved = _resolved(
        properties={"name": "Acme Ltd"},
        needs_review=True,
        candidate_count=3,
    )
    assert resolved.properties == {"name": "Acme Ltd"}
    assert resolved.needs_review is True
    assert resolved.candidate_count == 3


def test_resolved_entity_rejects_zero_candidate_count() -> None:
    # A resolved entity by definition has at least one contributing
    # candidate; a count of zero would mean we synthesised an entity
    # out of nothing.
    with pytest.raises(ValidationError):
        _resolved(candidate_count=0)


def test_resolved_entity_rejects_negative_chunk_index() -> None:
    with pytest.raises(ValidationError):
        _resolved(chunk_index=-1)


@pytest.mark.parametrize(
    "blank_field",
    [
        "entity_id",
        "label",
        "canonical_surface",
        "source_chunk_id",
        "source_name",
        "source_path",
    ],
)
def test_resolved_entity_rejects_blank_required_strings(blank_field: str) -> None:
    with pytest.raises(ValidationError):
        _resolved(**{blank_field: ""})


def test_resolved_entity_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _resolved(extra_field="nope")


# --------------------------- ResolutionDecision ----------------------------


def test_decision_minimal_valid() -> None:
    decision = _decision()
    assert decision.status == "auto_link"
    assert decision.entity_id == "Company:acme_ltd"
    assert decision.score == 1.0
    assert decision.alternatives == []
    assert decision.candidate.surface_text == "Acme Ltd"


@pytest.mark.parametrize("status", ["auto_link", "review", "no_match"])
def test_decision_accepts_known_statuses(status: str) -> None:
    _decision(status=status)


def test_decision_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        _decision(status="merged")


@pytest.mark.parametrize("score", [-0.01, 1.01, -1.0, 2.0])
def test_decision_rejects_score_out_of_range(score: float) -> None:
    with pytest.raises(ValidationError):
        _decision(score=score)


def test_decision_review_carries_alternatives() -> None:
    decision = _decision(
        status="review",
        score=0.88,
        alternatives=["Company:acme", "Company:acme_inc"],
        reason="two candidates above review threshold",
    )
    assert decision.alternatives == ["Company:acme", "Company:acme_inc"]


def test_decision_rejects_blank_reason() -> None:
    # Decisions feed run metadata, so a blank reason would defeat the
    # whole point of recording them.
    with pytest.raises(ValidationError):
        _decision(reason="")


def test_decision_rejects_blank_entity_id() -> None:
    with pytest.raises(ValidationError):
        _decision(entity_id="")


def test_decision_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _decision(weight=0.5)


# --------------------------- ResolutionResult ------------------------------


def test_result_defaults_are_empty_lists() -> None:
    result = ResolutionResult()
    assert result.entities == []
    assert result.decisions == []


def test_result_round_trip_with_entities_and_decisions() -> None:
    result = ResolutionResult(
        entities=[_resolved()],
        decisions=[_decision()],
    )
    assert len(result.entities) == 1
    assert len(result.decisions) == 1
    assert result.entities[0].label == "Company"
    assert result.decisions[0].status == "auto_link"


def test_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ResolutionResult(metadata={})  # type: ignore[call-arg]


# ---------------------------- ResolutionError ------------------------------


def test_resolution_error_is_exception_subclass() -> None:
    assert issubclass(ResolutionError, Exception)


def test_resolution_error_can_be_raised_and_caught() -> None:
    with pytest.raises(ResolutionError) as excinfo:
        raise ResolutionError("boom")
    assert "boom" in str(excinfo.value)
