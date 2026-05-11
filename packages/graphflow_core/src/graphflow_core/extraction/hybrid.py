"""Hybrid extraction router.

Combines a cheap fast extractor with an expensive accurate extractor
behind a single :class:`Extractor`-shaped facade. The hybrid path is
the recommended default for production runs because it captures most
of the accurate extractor's recall while only paying its cost on the
chunks that genuinely need it.

Routing strategy:

1. The fast extractor is always run over **every** chunk. Its results
   are kept and returned alongside whatever accurate extraction
   produces.
2. Each chunk is then evaluated against the configured
   :class:`HybridRouting` rules. A chunk is routed to the accurate
   extractor when **any** of these conditions hold:

   - The chunk id is in :attr:`HybridRouting.force_chunk_ids` (user-
     selected chunks always use the accurate path).
   - The maximum fast-extractor confidence on the chunk is below
     :attr:`HybridRouting.min_confidence` (the fast path's
     confidence is too low to trust).
   - At least one label in :attr:`HybridRouting.require_labels` did
     not appear in the chunk's fast-extractor candidates (a label
     the caller knows must be present is missing).

3. Routed chunks are passed to the accurate extractor **one at a
   time** so partial progress survives a
   :class:`CostLimitExceeded`. When the limit is hit and
   :attr:`HybridRouting.continue_on_cost_limit` is ``True``, the
   router stops calling the accurate extractor and returns the
   candidates already collected; otherwise the exception propagates.

4. Fast and accurate candidates are concatenated in this order:
   all fast candidates (already deterministically sorted by the
   fast extractor) followed by accurate candidates in the order
   they were produced.

The router records counts and per-chunk routing decisions on a
:class:`HybridRunSummary` so a pipeline run summary can report
exactly how many chunks went down each path.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from graphflow_core.extraction.base import CandidateEntity, Extractor, TextChunk
from graphflow_core.extraction.cost import CostLimitExceeded
from graphflow_core.manifests.ontology import OntologySpec

_STRICT = ConfigDict(extra="forbid")
_EXTRACTOR_NAME = "hybrid"


class HybridRouting(BaseModel):
    """Per-run routing configuration for :class:`HybridExtractor`.

    Strict (``extra='forbid'``) so a typo in ``pipeline.yaml`` fails
    loudly instead of silently being ignored.

    Attributes:
        min_confidence: Threshold in ``[0.0, 1.0]``. If the maximum
            fast-extractor confidence on a chunk is strictly below
            this, the chunk is routed to the accurate path. Set to
            ``0.0`` to disable confidence-based routing. Default
            ``0.7``.
        require_labels: Tuple of ontology node labels the caller
            considers mandatory. If any of these labels is absent from
            a chunk's fast-extractor candidates, the chunk is routed
            to the accurate path. Empty tuple disables this rule.
        force_chunk_ids: Chunk ids that must always be routed to the
            accurate path regardless of fast-extractor output. Lets
            an operator pin specific high-value chunks (e.g. an
            executive summary) to the more accurate extractor.
        continue_on_cost_limit: When ``True``, a
            :class:`CostLimitExceeded` from the accurate extractor
            stops further accurate calls but lets the run finish with
            fast candidates plus whatever accurate candidates were
            already collected. When ``False`` (default), the
            exception propagates so callers cannot accidentally
            silence a budget breach.
    """

    model_config = _STRICT

    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    require_labels: tuple[str, ...] = Field(default_factory=tuple)
    force_chunk_ids: frozenset[str] = Field(default_factory=frozenset)
    continue_on_cost_limit: bool = False


@dataclass
class HybridRunSummary:
    """Counts + routing decisions for one :class:`HybridExtractor` run.

    Exposed on :attr:`HybridExtractor.summary` so the pipeline run
    summary can report fast-vs-accurate breakdowns without having to
    re-derive them.
    """

    total_chunks: int = 0
    chunks_routed_to_accurate: int = 0
    fast_candidate_count: int = 0
    accurate_candidate_count: int = 0
    cost_limit_triggered: bool = False
    routing_reasons: dict[str, str] = field(default_factory=dict)
    """Map of ``chunk_id -> reason`` for every chunk that was routed
    to the accurate extractor. Reasons are short strings: ``"forced"``,
    ``"low_confidence"``, ``"missing_label:<Label>"``."""

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-friendly view for run-summary serialisation."""
        return {
            "total_chunks": self.total_chunks,
            "chunks_routed_to_accurate": self.chunks_routed_to_accurate,
            "fast_candidate_count": self.fast_candidate_count,
            "accurate_candidate_count": self.accurate_candidate_count,
            "cost_limit_triggered": self.cost_limit_triggered,
            "routing_reasons": dict(self.routing_reasons),
        }


class HybridExtractor:
    """Routes between a fast and an accurate :class:`Extractor`.

    Args:
        fast: The cheap, deterministic extractor (typically
            :class:`FastExtractor`).
        accurate: The accurate, expensive extractor (typically
            :class:`AccurateExtractor`).
        routing: Optional :class:`HybridRouting` override. Defaults to
            ``HybridRouting()`` which routes whenever fast confidence
            is below ``0.7`` and never enforces required labels.
    """

    def __init__(
        self,
        *,
        fast: Extractor,
        accurate: Extractor,
        routing: HybridRouting | None = None,
    ) -> None:
        self._fast = fast
        self._accurate = accurate
        self._routing = routing if routing is not None else HybridRouting()
        self._summary = HybridRunSummary()

    @property
    def summary(self) -> HybridRunSummary:
        """The latest run's summary. Reset at the start of each
        :meth:`extract` call so it always describes the most recent
        run rather than a cumulative total."""
        return self._summary

    @property
    def routing(self) -> HybridRouting:
        return self._routing

    def extract(
        self,
        chunks: Iterable[TextChunk],
        *,
        ontology: OntologySpec,
    ) -> list[CandidateEntity]:
        """Run hybrid extraction over ``chunks``.

        Raises:
            CostLimitExceeded: if the accurate extractor exceeds its
                cost limit and ``routing.continue_on_cost_limit`` is
                ``False``.
        """
        chunk_list = list(chunks)
        self._summary = HybridRunSummary(total_chunks=len(chunk_list))

        fast_candidates = self._fast.extract(chunk_list, ontology=ontology)
        self._summary.fast_candidate_count = len(fast_candidates)

        fast_by_chunk: dict[str, list[CandidateEntity]] = {}
        for candidate in fast_candidates:
            fast_by_chunk.setdefault(candidate.source_chunk_id, []).append(candidate)

        routed_chunks: list[TextChunk] = []
        for chunk in chunk_list:
            reason = self._routing_reason(chunk, fast_by_chunk.get(chunk.chunk_id, []))
            if reason is not None:
                routed_chunks.append(chunk)
                self._summary.routing_reasons[chunk.chunk_id] = reason

        self._summary.chunks_routed_to_accurate = len(routed_chunks)

        accurate_candidates: list[CandidateEntity] = []
        for chunk in routed_chunks:
            try:
                accurate_candidates.extend(self._accurate.extract([chunk], ontology=ontology))
            except CostLimitExceeded:
                self._summary.cost_limit_triggered = True
                if not self._routing.continue_on_cost_limit:
                    raise
                break

        self._summary.accurate_candidate_count = len(accurate_candidates)
        return [*fast_candidates, *accurate_candidates]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _routing_reason(
        self,
        chunk: TextChunk,
        fast_candidates: list[CandidateEntity],
    ) -> str | None:
        """Return the routing reason string, or ``None`` if the chunk
        should stay on the fast path. Order matters: ``forced`` wins
        over ``low_confidence`` which wins over ``missing_label`` so
        the recorded reason describes the *first* rule that fired.
        """
        if chunk.chunk_id in self._routing.force_chunk_ids:
            return "forced"

        max_confidence = max((c.confidence for c in fast_candidates), default=0.0)
        if max_confidence < self._routing.min_confidence:
            return "low_confidence"

        found_labels = {c.label for c in fast_candidates}
        for required in self._routing.require_labels:
            if required not in found_labels:
                return f"missing_label:{required}"

        return None
