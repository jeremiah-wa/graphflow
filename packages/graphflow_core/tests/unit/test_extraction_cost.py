"""Unit tests for :class:`CostTracker` and :class:`CostLimitExceeded`."""

from __future__ import annotations

import pytest

from graphflow_core.extraction import CostLimitExceeded, CostTracker


def test_empty_tracker_has_zero_totals() -> None:
    t = CostTracker()
    assert t.call_count == 0
    assert t.total_input_tokens == 0
    assert t.total_output_tokens == 0
    assert t.total_cost == 0.0


def test_record_accumulates_tokens_and_cost() -> None:
    t = CostTracker(input_rate_per_1k=2.0, output_rate_per_1k=4.0)
    t.record(input_tokens=1000, output_tokens=500)
    t.record(input_tokens=500, output_tokens=250)
    assert t.call_count == 2
    assert t.total_input_tokens == 1500
    assert t.total_output_tokens == 750
    # 1000*2 + 500*4 = 2000 + 2000 = 4000  -> /1000 = 4.0
    # 500*2  + 250*4 = 1000 + 1000 = 2000  -> /1000 = 2.0
    assert t.total_cost == pytest.approx(6.0)


def test_estimate_does_not_record() -> None:
    t = CostTracker(input_rate_per_1k=1.0, output_rate_per_1k=1.0)
    estimated = t.estimate(input_tokens=2000, output_tokens=0)
    assert estimated == pytest.approx(2.0)
    assert t.call_count == 0


def test_estimate_rejects_negative_tokens() -> None:
    t = CostTracker()
    with pytest.raises(ValueError):
        t.estimate(input_tokens=-1, output_tokens=0)


def test_record_within_limit_succeeds() -> None:
    t = CostTracker(input_rate_per_1k=1.0, output_rate_per_1k=1.0, limit=1.0)
    t.record(input_tokens=400, output_tokens=400)
    assert t.total_cost == pytest.approx(0.8)


def test_record_exceeding_limit_raises_and_does_not_mutate() -> None:
    t = CostTracker(input_rate_per_1k=1.0, output_rate_per_1k=1.0, limit=1.0)
    t.record(input_tokens=400, output_tokens=400)  # total 0.8
    with pytest.raises(CostLimitExceeded) as excinfo:
        t.record(input_tokens=300, output_tokens=300)  # would push to 1.4
    assert excinfo.value.limit == 1.0
    assert excinfo.value.projected == pytest.approx(1.4)
    # State must not have been mutated.
    assert t.call_count == 1
    assert t.total_cost == pytest.approx(0.8)


def test_zero_rates_produce_zero_cost_with_limit_unaffected() -> None:
    t = CostTracker(limit=0.0001)
    t.record(input_tokens=1_000_000, output_tokens=1_000_000)
    assert t.total_cost == 0.0


def test_summary_payload_is_jsonable() -> None:
    t = CostTracker(input_rate_per_1k=1.0, output_rate_per_1k=1.0)
    t.record(input_tokens=100, output_tokens=50)
    summary = t.summary()
    assert summary == {
        "calls": 1,
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost": pytest.approx(0.15),
    }
