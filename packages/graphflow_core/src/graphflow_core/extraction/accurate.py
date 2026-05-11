"""Accurate LLM-based text-to-graph extractor.

Counterpart to :class:`graphflow_core.extraction.fast.FastExtractor`:
:class:`AccurateExtractor` calls an :class:`LLMProvider` to surface
candidates the fast path cannot find (paraphrased mentions, indirect
references, multi-token compound names, ...). It is more accurate but
also more expensive, so the design pays attention to:

- **Ontology constraints.** The system prompt declares the exact set
  of node labels the model is allowed to emit. Anything outside that
  set is rejected at validation time, not silently kept.
- **Strict output validation.** The model is required to return a
  small JSON envelope. Validation uses a Pydantic model with
  ``extra='forbid'``; anything malformed raises
  :class:`ExtractionError`.
- **Caching.** Results are cached per chunk, keyed by chunk content,
  ontology, and extractor config so re-runs cost nothing.
- **Cost accounting.** Every provider call is recorded on a shared
  :class:`CostTracker`, and an optional ``cost_limit`` cuts the run
  off cleanly before the budget is blown.

The extractor satisfies the :class:`Extractor` protocol so the
hybrid router (issue #9) can mix it with the fast path without caring
which one produced any individual candidate.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from graphflow_core.extraction.base import CandidateEntity, TextChunk
from graphflow_core.extraction.cache import (
    ExtractionCache,
    InMemoryExtractionCache,
    make_cache_key,
)
from graphflow_core.extraction.cost import CostTracker
from graphflow_core.extraction.errors import ExtractionError
from graphflow_core.extraction.provider import LLMError, LLMProvider, LLMResponse
from graphflow_core.manifests.ontology import OntologySpec

_STRICT = ConfigDict(extra="forbid")
_EXTRACTOR_NAME = "accurate"
_PROMPT_VERSION = "1"

DEFAULT_SYSTEM_PROMPT = (
    "You are an entity-extraction assistant. Read the user's text and "
    "return a JSON object with a single key 'candidates' whose value is "
    "an array. Each array item must be an object with: 'label' (one of "
    "the allowed labels listed by the user), 'surface_text' (the exact "
    "substring from the text), 'confidence' (a number between 0 and 1), "
    "and optional 'properties' (a flat object of string values), "
    "'start_offset' (integer), 'end_offset' (integer). Return ONLY the "
    "JSON object, no prose."
)


class _LLMCandidate(BaseModel):
    """One candidate as returned by the model. Validated strictly."""

    model_config = _STRICT

    label: str = Field(min_length=1)
    surface_text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    properties: dict[str, str] = Field(default_factory=dict)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)


class _LLMResponseEnvelope(BaseModel):
    """Top-level envelope the model is required to return."""

    model_config = _STRICT

    candidates: list[_LLMCandidate]


class AccurateExtractor:
    """LLM-backed candidate extractor with ontology constraints, caching, and
    cost tracking.

    Args:
        provider: The :class:`LLMProvider` to call. Tests pass a fake
            provider; production passes a real one.
        model: Model identifier passed to the provider unchanged.
            Contributes to the cache key, so switching models
            invalidates cached results.
        cost_tracker: Optional :class:`CostTracker`. One is created if
            not supplied; pass an explicit instance when you want to
            enforce a ``cost_limit`` across a run that uses multiple
            extractor instances.
        cache: Optional :class:`ExtractionCache`. Defaults to a
            process-local in-memory cache so re-running the same
            chunks within one run costs nothing.
        system_prompt: Override for the default system prompt. Changes
            invalidate the cache automatically because the prompt
            contributes to the cache key.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        cost_tracker: CostTracker | None = None,
        cache: ExtractionCache | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        if not model:
            raise ExtractionError("AccurateExtractor: model must be a non-empty string")
        self._provider = provider
        self._model = model
        self._cost = cost_tracker if cost_tracker is not None else CostTracker()
        self._cache: ExtractionCache = cache if cache is not None else InMemoryExtractionCache()
        self._system_prompt = system_prompt

    @property
    def cost_tracker(self) -> CostTracker:
        """Expose the shared cost tracker for run-summary reporting."""
        return self._cost

    def extract(
        self,
        chunks: Iterable[TextChunk],
        *,
        ontology: OntologySpec,
    ) -> list[CandidateEntity]:
        """Return candidate entities found in ``chunks``.

        Behaviour:

        - For each chunk, build a cache key from chunk content,
          ontology, and config. On hit, reuse cached candidates and
          skip the provider call. On miss, call the provider, validate,
          cache, and append.
        - Skip chunks with empty text without calling the provider.
        - Preserve input chunk order in the output. Within a chunk,
          preserve the order the model returned (the model is
          responsible for stability; deterministic providers return
          stable output).

        Raises:
            ExtractionError: if the model returns malformed JSON, the
                JSON does not match the response schema, or a candidate
                references a label that is not declared in
                ``ontology``.
            CostLimitExceeded: if the configured cost limit would be
                exceeded by the next provider call.
            LLMError: if the provider itself fails.
        """
        ontology_labels = ontology.node_labels()
        if not ontology_labels:
            return []

        results: list[CandidateEntity] = []
        for chunk in chunks:
            if not chunk.text:
                continue
            cache_key = make_cache_key(
                chunk=chunk,
                ontology=ontology,
                config_fingerprint=self._config_fingerprint(),
            )
            cached = self._cache.get(cache_key)
            if cached is not None:
                results.extend(cached)
                continue

            user_prompt = self._build_user_prompt(chunk=chunk, labels=ontology_labels)
            response = self._call_provider(user_prompt=user_prompt)
            self._cost.record(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
            chunk_candidates = self._parse_response(
                response=response,
                chunk=chunk,
                ontology_labels=ontology_labels,
            )
            self._cache.set(cache_key, chunk_candidates)
            results.extend(chunk_candidates)

        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _config_fingerprint(self) -> dict[str, object]:
        return {
            "model": self._model,
            "extractor": _EXTRACTOR_NAME,
            "prompt_version": _PROMPT_VERSION,
            "system_prompt": self._system_prompt,
        }

    def _build_user_prompt(self, *, chunk: TextChunk, labels: set[str]) -> str:
        # Sorted labels make the prompt deterministic across hash-
        # randomised runs, which keeps the cache key stable.
        sorted_labels = sorted(labels)
        return (
            f"Allowed labels: {sorted_labels}\n"
            f"Chunk id: {chunk.chunk_id}\n"
            f"Chunk text:\n---\n{chunk.text}\n---\n"
            "Return JSON only."
        )

    def _call_provider(self, *, user_prompt: str) -> LLMResponse:
        try:
            return self._provider.complete(
                system=self._system_prompt,
                user=user_prompt,
                model=self._model,
            )
        except LLMError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise LLMError(f"provider call failed: {exc}") from exc

    def _parse_response(
        self,
        *,
        response: LLMResponse,
        chunk: TextChunk,
        ontology_labels: set[str],
    ) -> list[CandidateEntity]:
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ExtractionError(
                f"AccurateExtractor: model output is not valid JSON for chunk "
                f"'{chunk.chunk_id}': {exc}"
            ) from exc

        try:
            envelope = _LLMResponseEnvelope.model_validate(payload)
        except ValidationError as exc:
            raise ExtractionError(
                f"AccurateExtractor: model output failed schema validation "
                f"for chunk '{chunk.chunk_id}': {exc}"
            ) from exc

        candidates: list[CandidateEntity] = []
        for raw in envelope.candidates:
            if raw.label not in ontology_labels:
                raise ExtractionError(
                    f"AccurateExtractor: model returned label '{raw.label}' "
                    f"which is not declared in the ontology. Known labels: "
                    f"{sorted(ontology_labels)}"
                )
            candidates.append(
                CandidateEntity(
                    label=raw.label,
                    surface_text=raw.surface_text,
                    confidence=raw.confidence,
                    properties=raw.properties,
                    source_chunk_id=chunk.chunk_id,
                    source_name=chunk.source_name,
                    source_path=chunk.source_path,
                    chunk_index=chunk.chunk_index,
                    start_offset=raw.start_offset,
                    end_offset=raw.end_offset,
                    extractor=_EXTRACTOR_NAME,
                )
            )
        return candidates
