"""Token + cost accounting for LLM-based extraction.

The accurate extractor records one :class:`CostEntry` per provider
call (cache hits do not count as calls). The aggregate is exposed on
:class:`CostTracker` so a run summary can report estimated cost
without re-deriving it from individual decisions.

Cost is computed as::

    input_tokens  * input_rate_per_1k  / 1000
  + output_tokens * output_rate_per_1k / 1000

Rates are caller-supplied so we do not bake any provider-specific
pricing into the core package.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from graphflow_core.extraction.errors import ExtractionError


class CostLimitExceeded(ExtractionError):
    """Raised when a run would exceed the configured cost budget.

    Surfaced as an :class:`ExtractionError` subclass so callers that
    already handle extraction failures pick this up automatically.
    Carries the limit and the projected cost on the exception
    instance so run summaries can attribute the failure precisely.
    """

    def __init__(self, *, limit: float, projected: float) -> None:
        super().__init__(
            f"extraction would exceed cost limit: projected ${projected:.4f} > limit ${limit:.4f}"
        )
        self.limit = limit
        self.projected = projected


@dataclass(frozen=True)
class CostEntry:
    """One billed provider call."""

    input_tokens: int
    output_tokens: int
    cost: float


@dataclass
class CostTracker:
    """Mutable token + cost accumulator scoped to one extraction run.

    Args:
        input_rate_per_1k: Provider's input price per 1000 tokens.
        output_rate_per_1k: Provider's output price per 1000 tokens.
        limit: Optional cost ceiling in the same currency as the
            rates. When set, :meth:`record` raises
            :class:`CostLimitExceeded` *before* applying the new
            entry if it would push the total past ``limit``. The
            tracker state is left unchanged on failure so the caller
            can decide what to do.
    """

    input_rate_per_1k: float = 0.0
    output_rate_per_1k: float = 0.0
    limit: float | None = None
    entries: list[CostEntry] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(e.input_tokens for e in self.entries)

    @property
    def total_output_tokens(self) -> int:
        return sum(e.output_tokens for e in self.entries)

    @property
    def total_cost(self) -> float:
        return sum(e.cost for e in self.entries)

    @property
    def call_count(self) -> int:
        return len(self.entries)

    def estimate(self, *, input_tokens: int, output_tokens: int) -> float:
        """Return the cost a record(...) call would add."""
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must be non-negative")
        return (
            input_tokens * self.input_rate_per_1k + output_tokens * self.output_rate_per_1k
        ) / 1000.0

    def record(self, *, input_tokens: int, output_tokens: int) -> CostEntry:
        """Record one provider call and return the resulting entry.

        Raises:
            CostLimitExceeded: if applying this entry would push
                ``total_cost`` past ``limit``.
        """
        cost = self.estimate(input_tokens=input_tokens, output_tokens=output_tokens)
        if self.limit is not None and self.total_cost + cost > self.limit:
            raise CostLimitExceeded(limit=self.limit, projected=self.total_cost + cost)
        entry = CostEntry(input_tokens=input_tokens, output_tokens=output_tokens, cost=cost)
        self.entries.append(entry)
        return entry

    def summary(self) -> dict[str, float | int]:
        """Return a JSON-friendly summary for run metadata."""
        return {
            "calls": self.call_count,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "estimated_cost": self.total_cost,
        }
