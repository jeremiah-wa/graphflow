"""LLM provider abstraction for the accurate extractor.

The accurate extractor is intentionally provider-agnostic. It does not
import an OpenAI/Anthropic/local-model client directly. Instead it
talks to anything that satisfies :class:`LLMProvider`:

    response = provider.complete(system=..., user=..., model=...)

This keeps three things easy:

- Tests can drop in a deterministic fake provider with no network or
  paid API keys.
- New providers (or self-hosted models) can be plugged in without
  touching extractor code.
- Cost accounting is uniform: every provider returns its own usage
  numbers as part of :class:`LLMResponse`, and the extractor records
  them through a single :class:`graphflow_core.extraction.cost.CostTracker`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from graphflow_core.extraction.errors import ExtractionError

_STRICT = ConfigDict(extra="forbid")


class LLMResponse(BaseModel):
    """A single completion returned by an :class:`LLMProvider`.

    Attributes:
        text: Raw text the model produced. The accurate extractor is
            responsible for parsing/validating this; providers do not
            try to be helpful with the payload.
        input_tokens: Number of tokens the provider billed for input.
            Providers that do not report usage should pass ``0``; the
            extractor will still surface the call but its cost
            estimate will be a lower bound.
        output_tokens: Number of tokens the provider billed for output.
        model: Echo of the model identifier used for the call. Useful
            for run summaries and for cache invalidation when a caller
            switches models.
    """

    model_config = _STRICT

    text: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model: str = Field(min_length=1)


class LLMError(ExtractionError):
    """Raised when an :class:`LLMProvider` call fails.

    A subclass of :class:`ExtractionError` so callers that already
    handle extraction failures (network, malformed output, cost limit)
    can keep a single ``except`` block. Provider implementations should
    wrap their underlying SDK exceptions in this.
    """


@runtime_checkable
class LLMProvider(Protocol):
    """Structural protocol for an LLM completion provider.

    The accurate extractor invokes ``complete`` once per chunk that
    misses the cache. Implementations must:

    - Be deterministic for the same ``(system, user, model)`` triple
      whenever the underlying model supports it (e.g. by passing
      ``temperature=0`` and a fixed seed). The extractor relies on
      this for repeatable runs and stable cache values.
    - Wrap any SDK or transport failure in :class:`LLMError` so the
      extractor can surface it as a :class:`ExtractionError` without
      leaking provider-specific exception types into pipeline code.
    """

    def complete(self, *, system: str, user: str, model: str) -> LLMResponse:
        """Return a completion for ``user`` with ``system`` guidance."""
        ...
