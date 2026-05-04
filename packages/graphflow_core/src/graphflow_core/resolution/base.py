"""Core resolution abstractions: :class:`ResolvedEntity`,
:class:`ResolutionDecision`, :class:`ResolutionResult`, and the
:class:`Resolver` protocol.

A :class:`Resolver` consumes :class:`CandidateEntity` instances produced
by an :class:`graphflow_core.extraction.Extractor` and collapses them
into a smaller set of canonical :class:`ResolvedEntity` instances. Each
input candidate is paired with a :class:`ResolutionDecision` that
records *what happened* (auto-linked, flagged for review, or treated as
a new entity) and *why*, so resolution becomes part of the run's
audit trail rather than an opaque step.

Resolution sits between extraction and graph mapping:

    extraction -> [CandidateEntity, ...] -> resolution
                                          -> [ResolvedEntity, ResolutionDecision, ...]
                                          -> graph mapping
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from graphflow_core.extraction.base import CandidateEntity
from graphflow_core.manifests.ontology import OntologySpec

_STRICT = ConfigDict(extra="forbid")

DecisionStatus = Literal["auto_link", "review", "no_match"]
"""Possible per-candidate resolution outcomes.

- ``auto_link``: the candidate matched an existing canonical entity
  with high enough confidence to be merged automatically.
- ``review``: the candidate had a plausible but ambiguous match and
  must be confirmed by a human (or a more accurate downstream
  resolver) before being merged.
- ``no_match``: the candidate did not match any existing canonical
  entity and was promoted into a new one. The new entity's id is
  still recorded on the decision so callers can correlate the
  decision back to it.
"""


class ResolvedEntity(BaseModel):
    """One canonical entity produced by resolution.

    A resolved entity is the deduplicated, merged form of one or more
    :class:`CandidateEntity` instances. It is intentionally close to a
    :class:`graphflow_core.graph.GraphNode` (label, key value,
    properties, provenance) but it is *not* one yet: callers can drop,
    edit, or further merge resolved entities before they reach the
    graph mapping engine.

    Attributes:
        entity_id: Stable identifier derived deterministically from
            ``(label, canonical_surface)``. Two runs over the same
            inputs produce the same id, so it can be used directly as a
            graph node key value when no other key is available.
        label: The ontology node label this entity maps to.
        canonical_surface: The chosen representative surface form. By
            convention the resolver picks the longest contributing
            surface (with ties broken alphabetically) so the
            representation tends to be the most informative one.
        properties: Properties merged from contributing candidates.
            The resolver is responsible for deciding how conflicting
            values are reconciled.
        needs_review: ``True`` when at least one contributing candidate
            was assigned ``review`` status. Surfacing this on the
            entity itself lets review tooling filter without
            re-walking the decisions list.
        candidate_count: Number of input candidates that collapsed
            into this entity. Always ``>= 1``.
        source_chunk_id: Provenance: the originating ``TextChunk`` id
            of the highest-confidence contributing candidate.
        source_name: Provenance: source name from that candidate.
        source_path: Provenance: source path from that candidate.
        chunk_index: Provenance: chunk index from that candidate.
    """

    model_config = _STRICT

    entity_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    canonical_surface: str = Field(min_length=1)
    properties: dict[str, str] = Field(default_factory=dict)
    needs_review: bool = False
    candidate_count: int = Field(ge=1)
    source_chunk_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)


class ResolutionDecision(BaseModel):
    """One reviewable resolution outcome for a single input candidate.

    Attributes:
        candidate: The input :class:`CandidateEntity` this decision is
            about. Embedded by value so a serialized decision is
            self-describing and survives independently of the input
            list.
        status: The decision outcome (see :data:`DecisionStatus`).
        entity_id: The :class:`ResolvedEntity` the candidate was
            assigned to. Always set, even for ``no_match`` candidates,
            because ``no_match`` still creates a new resolved entity
            that the candidate is the sole member of.
        score: Match score in ``[0.0, 1.0]`` against the chosen
            entity. ``1.0`` for exact-after-normalisation matches,
            lower for fuzzy matches.
        alternatives: Other entity ids that were close enough to be
            plausible matches. Populated for ``review`` decisions so
            tooling can render the choices side-by-side. Empty for
            ``auto_link`` and ``no_match``.
        reason: Short human-readable explanation, e.g. ``"normalized
            surface matched 'acme'"`` or ``"two candidates above review
            threshold"``. Reason text is surfaced in run metadata
            (issue #10) so it must be safe to log.
    """

    model_config = _STRICT

    candidate: CandidateEntity
    status: DecisionStatus
    entity_id: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    alternatives: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)


class ResolutionResult(BaseModel):
    """The full output of one resolution pass.

    Attributes:
        entities: The deduplicated set of canonical entities. Sorted
            deterministically by ``(label, entity_id)`` so two runs on
            the same inputs produce identical output.
        decisions: One decision per input candidate, in input order.
            Together with :attr:`entities` this fully describes how
            extraction output collapsed into the resolved set.
    """

    model_config = _STRICT

    entities: list[ResolvedEntity] = Field(default_factory=list)
    decisions: list[ResolutionDecision] = Field(default_factory=list)


@runtime_checkable
class Resolver(Protocol):
    """Structural protocol for entity resolvers.

    Implementations must be **deterministic for the same inputs**: two
    calls with the same candidates and the same ontology must produce
    the same :class:`ResolutionResult`. Pipeline runs and tests rely on
    this so they can compare outputs reliably.

    Implementations must also constrain output entity labels to the
    ontology: only labels declared in ``ontology`` may appear on
    returned entities. A resolver that receives a candidate with an
    unknown label should raise
    :class:`graphflow_core.resolution.ResolutionError` rather than
    silently dropping or relabelling it.
    """

    def resolve(
        self,
        candidates: Iterable[CandidateEntity],
        *,
        ontology: OntologySpec,
    ) -> ResolutionResult:
        """Collapse ``candidates`` into a :class:`ResolutionResult`."""
        ...
