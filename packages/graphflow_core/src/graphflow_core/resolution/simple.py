"""Simple deterministic entity resolver.

The simple resolver is the cheap baseline path in the resolution
strategy: it never calls an LLM, never hits the network, and uses only
normalisation plus :mod:`difflib` similarity. Its job is to surface a
deduplicated set of canonical entities and to flag genuinely ambiguous
overlaps for human review rather than guessing.

Strategy:

- Each candidate's ``surface_text`` is normalised (NFKC + lower-case +
  punctuation stripped + whitespace collapsed). Two candidates whose
  normalised forms are identical auto-link with score ``1.0``.
- For non-identical normalised forms, similarity is computed with
  :func:`difflib.SequenceMatcher.ratio` against existing same-label
  entities. The best score is then bucketed against two thresholds:

    - ``>= auto_link_threshold`` (and only one entity at that score):
      auto-link the candidate into the winning entity.
    - ``>= review_threshold``: flag as ``review``. Create a new entity
      for the candidate and record the close alternatives on the
      decision so a reviewer can later confirm or merge.
    - otherwise: ``no_match``. Create a new entity.

- Output is sorted deterministically: entities by
  ``(label, entity_id)``, decisions in input order. Two runs over the
  same inputs always produce the same :class:`ResolutionResult`.

The resolver never silently drops candidates: every input becomes
exactly one decision, and every decision points to exactly one
:class:`ResolvedEntity` (a freshly-created one for ``review`` and
``no_match``, an existing one for ``auto_link``).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher

from graphflow_core.extraction.base import CandidateEntity
from graphflow_core.manifests.ontology import OntologySpec
from graphflow_core.resolution.base import (
    ResolutionDecision,
    ResolutionResult,
    ResolvedEntity,
)
from graphflow_core.resolution.errors import ResolutionError

DEFAULT_AUTO_LINK_THRESHOLD = 1.0
"""Default minimum similarity for automatic merging.

``1.0`` means *only* identical-after-normalisation surfaces auto-link.
Anything below that goes to review or no-match. This is conservative on
purpose: at the simple-resolver layer we'd rather under-merge and let a
human (or a more accurate downstream resolver) confirm than silently
collapse two real-world entities together.
"""

DEFAULT_REVIEW_THRESHOLD = 0.85
"""Default minimum similarity for flagging an ambiguous match.

Below this, two surfaces are different enough that we treat them as
separate entities without flagging anything. Between this and
``auto_link_threshold`` they go to review.
"""

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_RESOLVER_NAME = "simple"


def _normalize(text: str) -> str:
    """Return the comparison form used for matching.

    NFKC folds compatibility characters (e.g. half-width ``"Ｓ"`` ->
    ``"S"`` and ligatures), lowering removes case differences, the
    punctuation pass replaces every non-word non-space character with
    a space, and the whitespace pass collapses runs to a single space
    and strips the ends. The result is a stable comparison key that
    matches obvious surface variants without needing an alias table.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _entity_id(label: str, normalized: str) -> str:
    """Return the deterministic entity id for ``(label, normalized)``.

    The id is intentionally human-readable so it can appear in run
    metadata and review tooling without needing an extra lookup.
    """
    slug = normalized.replace(" ", "_") if normalized else "blank"
    return f"{label}:{slug}"


class SimpleResolver:
    """Deterministic candidate-to-entity resolver.

    Args:
        auto_link_threshold: Minimum similarity in ``[0.0, 1.0]`` at
            which a candidate's normalised surface is merged into the
            best-matching existing entity automatically. Defaults to
            ``1.0`` so only identical-after-normalisation surfaces
            auto-link.
        review_threshold: Minimum similarity at which a candidate is
            flagged for review. Must satisfy
            ``0 <= review_threshold <= auto_link_threshold <= 1``.
            Candidates below this threshold (against every existing
            same-label entity) become their own new entities with
            ``no_match`` status.

    Raises:
        ResolutionError: if the thresholds are inconsistent.
    """

    def __init__(
        self,
        *,
        auto_link_threshold: float = DEFAULT_AUTO_LINK_THRESHOLD,
        review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
    ) -> None:
        if not 0.0 <= review_threshold <= auto_link_threshold <= 1.0:
            raise ResolutionError(
                "SimpleResolver: thresholds must satisfy "
                "0 <= review_threshold <= auto_link_threshold <= 1, "
                f"got review_threshold={review_threshold}, "
                f"auto_link_threshold={auto_link_threshold}"
            )
        self._auto_link_threshold = auto_link_threshold
        self._review_threshold = review_threshold

    def resolve(
        self,
        candidates: Iterable[CandidateEntity],
        *,
        ontology: OntologySpec,
    ) -> ResolutionResult:
        """Collapse ``candidates`` into a :class:`ResolutionResult`.

        Raises:
            ResolutionError: if any candidate carries a label that is
                not declared in ``ontology``.
        """
        ontology_labels = ontology.node_labels()

        entities_by_id: dict[str, ResolvedEntity] = {}
        normalized_index: dict[tuple[str, str], str] = {}
        decisions: list[ResolutionDecision] = []

        for candidate in candidates:
            if candidate.label not in ontology_labels:
                raise ResolutionError(
                    f"SimpleResolver: candidate carries label "
                    f"'{candidate.label}' which is not declared in "
                    f"ontology '{ontology.name}'. Known labels: "
                    f"{sorted(ontology_labels)}"
                )

            normalized = _normalize(candidate.surface_text)
            decision = self._resolve_one(
                candidate=candidate,
                normalized=normalized,
                entities_by_id=entities_by_id,
                normalized_index=normalized_index,
            )
            decisions.append(decision)

        entities = sorted(
            entities_by_id.values(),
            key=lambda e: (e.label, e.entity_id),
        )
        return ResolutionResult(entities=entities, decisions=decisions)

    def _resolve_one(
        self,
        *,
        candidate: CandidateEntity,
        normalized: str,
        entities_by_id: dict[str, ResolvedEntity],
        normalized_index: dict[tuple[str, str], str],
    ) -> ResolutionDecision:
        # 1. Exact normalised match: auto-link with score 1.0.
        exact_key = (candidate.label, normalized)
        existing_id = normalized_index.get(exact_key)
        if existing_id is not None:
            entities_by_id[existing_id] = self._merge_into(
                entities_by_id[existing_id], candidate
            )
            return ResolutionDecision(
                candidate=candidate,
                status="auto_link",
                entity_id=existing_id,
                score=1.0,
                alternatives=[],
                reason=f"normalized surface matched '{normalized}'",
            )

        # 2. Fuzzy match against same-label entities.
        scored: list[tuple[float, str]] = []
        for eid, entity in entities_by_id.items():
            if entity.label != candidate.label:
                continue
            score = SequenceMatcher(
                None, normalized, _normalize(entity.canonical_surface)
            ).ratio()
            if score > 0.0:
                scored.append((score, eid))
        scored.sort(key=lambda x: (-x[0], x[1]))

        if scored:
            best_score, best_id = scored[0]
            ties_at_top = [eid for s, eid in scored if s == best_score]

            if best_score >= self._auto_link_threshold and len(ties_at_top) == 1:
                entities_by_id[best_id] = self._merge_into(
                    entities_by_id[best_id], candidate
                )
                return ResolutionDecision(
                    candidate=candidate,
                    status="auto_link",
                    entity_id=best_id,
                    score=best_score,
                    alternatives=[],
                    reason=(
                        f"similarity {best_score:.2f} >= auto_link_threshold "
                        f"({self._auto_link_threshold})"
                    ),
                )

            close_enough = [eid for s, eid in scored if s >= self._review_threshold]
            if close_enough:
                new_id = self._make_unique_id(
                    candidate.label, normalized, entities_by_id
                )
                entities_by_id[new_id] = self._new_entity(
                    entity_id=new_id,
                    candidate=candidate,
                    needs_review=True,
                )
                normalized_index[exact_key] = new_id
                shown = ", ".join(close_enough[:3])
                return ResolutionDecision(
                    candidate=candidate,
                    status="review",
                    entity_id=new_id,
                    score=best_score,
                    alternatives=close_enough,
                    reason=(
                        f"similarity {best_score:.2f} in review range "
                        f"[{self._review_threshold}, {self._auto_link_threshold}); "
                        f"alternatives: {shown}"
                    ),
                )

        # 3. No match: create a new entity.
        new_id = self._make_unique_id(candidate.label, normalized, entities_by_id)
        entities_by_id[new_id] = self._new_entity(
            entity_id=new_id,
            candidate=candidate,
            needs_review=False,
        )
        normalized_index[exact_key] = new_id
        return ResolutionDecision(
            candidate=candidate,
            status="no_match",
            entity_id=new_id,
            score=0.0,
            alternatives=[],
            reason="no existing entity above review threshold",
        )

    @staticmethod
    def _new_entity(
        *,
        entity_id: str,
        candidate: CandidateEntity,
        needs_review: bool,
    ) -> ResolvedEntity:
        return ResolvedEntity(
            entity_id=entity_id,
            label=candidate.label,
            canonical_surface=candidate.surface_text,
            properties=dict(candidate.properties),
            needs_review=needs_review,
            candidate_count=1,
            source_chunk_id=candidate.source_chunk_id,
            source_name=candidate.source_name,
            source_path=candidate.source_path,
            chunk_index=candidate.chunk_index,
        )

    @staticmethod
    def _merge_into(
        entity: ResolvedEntity,
        candidate: CandidateEntity,
    ) -> ResolvedEntity:
        # First-write-wins for property values: a candidate's value for
        # an already-set key is kept on the candidate (in the decision
        # record) but does not overwrite the resolved entity's value.
        merged_properties = dict(entity.properties)
        for key, value in candidate.properties.items():
            merged_properties.setdefault(key, value)

        # Pick the longer surface as canonical (more informative);
        # break ties alphabetically so the choice is deterministic.
        new_surface = candidate.surface_text
        old_surface = entity.canonical_surface
        if len(new_surface) > len(old_surface) or (
            len(new_surface) == len(old_surface) and new_surface < old_surface
        ):
            canonical = new_surface
        else:
            canonical = old_surface

        return entity.model_copy(
            update={
                "properties": merged_properties,
                "canonical_surface": canonical,
                "candidate_count": entity.candidate_count + 1,
            }
        )

    @staticmethod
    def _make_unique_id(
        label: str,
        normalized: str,
        entities_by_id: dict[str, ResolvedEntity],
    ) -> str:
        # Two distinct normalised forms can slug to the same id (e.g.
        # "acme ltd" and "acme_ltd" both slug to "acme_ltd"). Fall back
        # to a numeric suffix in that case so ids stay unique.
        base = _entity_id(label, normalized)
        if base not in entities_by_id:
            return base
        i = 2
        while f"{base}__{i}" in entities_by_id:
            i += 1
        return f"{base}__{i}"
