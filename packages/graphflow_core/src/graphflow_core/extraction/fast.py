"""Fast deterministic text-to-graph extractor.

The fast extractor is the cheap baseline path in the hybrid extraction
strategy: it never calls an LLM, never hits the network, and uses only
information already declared in the active
:class:`graphflow_core.manifests.OntologySpec`. Its job is to surface
*candidates* that more accurate (and more expensive) extractors can
later confirm, edit, or replace.

Strategy:

- For each ontology node label, build an alias set that includes the
  label itself and a lower-case form. Optional caller-provided aliases
  (e.g. ``{"Company": ["Ltd", "Limited"]}``) are added on top.
- Each alias is matched against each chunk's text using a
  case-insensitive, word-bounded regex so partial matches inside
  larger words ("Comp" inside "Compute") never produce candidates.
- Candidates are emitted with confidence ``1.0`` when the matched
  text equals an alias exactly, and ``0.7`` otherwise (for example
  when the alias was ``"Company"`` and the text contained
  ``"company"``). A simple two-tier scheme is enough at the
  fast-path layer; finer-grained scoring is the LLM extractor's job.
- Output is sorted deterministically by
  ``(chunk_index, start_offset, label, surface_text)`` so two runs on
  the same inputs always produce the same list. Overlapping matches
  for the same ``(label, start_offset, end_offset)`` are de-duplicated.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from graphflow_core.extraction.base import CandidateEntity, TextChunk
from graphflow_core.extraction.errors import ExtractionError
from graphflow_core.manifests.ontology import OntologySpec

EXACT_MATCH_CONFIDENCE = 1.0
"""Confidence assigned when matched text equals an alias verbatim."""

CASE_INSENSITIVE_MATCH_CONFIDENCE = 0.7
"""Confidence assigned when the match only succeeds case-insensitively."""

_EXTRACTOR_NAME = "fast"


class FastExtractor:
    """Deterministic, ontology-driven candidate extractor.

    Args:
        aliases: Optional per-label list of additional surface forms
            to recognise. Keys must be node labels declared in the
            ontology used at ``extract`` time; unknown labels raise
            :class:`ExtractionError`. Each alias must be a non-empty
            string. Aliases are matched in addition to the label
            itself and its lower-case form, never replacing them.
    """

    def __init__(self, *, aliases: Mapping[str, list[str]] | None = None) -> None:
        self._aliases: dict[str, tuple[str, ...]] = {
            label: tuple(values) for label, values in (aliases or {}).items()
        }
        for label, values in self._aliases.items():
            for value in values:
                if not value:
                    raise ExtractionError(
                        f"FastExtractor: empty alias for label '{label}' is not allowed"
                    )

    def extract(
        self,
        chunks: Iterable[TextChunk],
        *,
        ontology: OntologySpec,
    ) -> list[CandidateEntity]:
        """Return candidate entities found in ``chunks``.

        Raises:
            ExtractionError: if ``aliases`` reference a label that does
                not exist in ``ontology``.
        """
        ontology_labels = ontology.node_labels()
        unknown = sorted(set(self._aliases) - ontology_labels)
        if unknown:
            raise ExtractionError(
                "FastExtractor: aliases reference unknown ontology labels: "
                f"{unknown}. Known labels: {sorted(ontology_labels)}"
            )

        # Build the search index once per call; ontology can change
        # between calls so we cannot cache it on the instance.
        search_index = self._build_search_index(ontology_labels)
        if not search_index:
            return []

        results: list[CandidateEntity] = []
        seen: set[tuple[str, str, int, int, int]] = set()

        for chunk in chunks:
            if not chunk.text:
                continue
            for label, patterns in search_index.items():
                for alias, pattern in patterns:
                    for match in pattern.finditer(chunk.text):
                        start, end = match.start(), match.end()
                        surface = chunk.text[start:end]
                        key = (chunk.chunk_id, label, chunk.chunk_index, start, end)
                        if key in seen:
                            continue
                        seen.add(key)
                        confidence = (
                            EXACT_MATCH_CONFIDENCE
                            if surface == alias
                            else CASE_INSENSITIVE_MATCH_CONFIDENCE
                        )
                        results.append(
                            CandidateEntity(
                                label=label,
                                surface_text=surface,
                                confidence=confidence,
                                source_chunk_id=chunk.chunk_id,
                                source_name=chunk.source_name,
                                source_path=chunk.source_path,
                                chunk_index=chunk.chunk_index,
                                start_offset=start,
                                end_offset=end,
                                extractor=_EXTRACTOR_NAME,
                            )
                        )

        results.sort(
            key=lambda c: (
                c.chunk_index,
                # start_offset is always set by this extractor, but the
                # field is Optional on the model so guard for the type
                # checker.
                c.start_offset if c.start_offset is not None else 0,
                c.label,
                c.surface_text,
            )
        )
        return results

    def _build_search_index(
        self, ontology_labels: set[str]
    ) -> dict[str, list[tuple[str, re.Pattern[str]]]]:
        """Return ``{label: [(alias, compiled_pattern), ...]}``.

        The label itself and its lower-case form are always included.
        Configured aliases are appended in declaration order, with
        duplicates removed while preserving order so the search is
        deterministic across Python's hash randomisation.
        """
        index: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
        for label in sorted(ontology_labels):
            ordered_aliases: list[str] = []
            seen_aliases: set[str] = set()
            for alias in (label, label.lower(), *self._aliases.get(label, ())):
                if alias in seen_aliases:
                    continue
                seen_aliases.add(alias)
                ordered_aliases.append(alias)
            index[label] = [
                (alias, re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE))
                for alias in ordered_aliases
            ]
        return index
