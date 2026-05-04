"""Core extraction abstractions: :class:`TextChunk`, :class:`CandidateEntity`,
and the :class:`Extractor` protocol.

An :class:`Extractor` consumes :class:`TextChunk` instances and returns
:class:`CandidateEntity` objects. Candidates are *not* graph nodes yet;
they are reviewable suggestions that include confidence and full
provenance so a human (or the hybrid router) can accept or reject them
before they reach :mod:`graphflow_core.mapping` or the graph sink.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from graphflow_core.manifests.ontology import OntologySpec

_STRICT = ConfigDict(extra="forbid")


class TextChunk(BaseModel):
    """One unit of text fed to an extractor.

    A chunk is the smallest text region an extractor operates on. A
    document may be a single chunk, or it may be split into many chunks
    by an upstream chunker. Either way, each chunk is self-describing:
    it carries enough provenance for a candidate found in it to be
    traced back to the originating source and position.

    Attributes:
        chunk_id: Stable identifier for the chunk. The pipeline passes
            this through unchanged so candidates can reference back to
            their originating chunk without relying on object identity.
        text: The chunk's raw text.
        source_name: ``SourceSpec.name`` of the originating source.
        source_path: Filesystem path of the document the chunk came
            from, stored as a string for predictable serialisation.
        chunk_index: 0-indexed position of the chunk within the source
            document. ``0`` for single-chunk documents.
        location: Human-friendly position label for error messages,
            e.g. ``"chunk 3"`` or ``"page 2 paragraph 1"``.
    """

    model_config = _STRICT

    chunk_id: str = Field(min_length=1)
    text: str
    source_name: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    location: str = Field(min_length=1)


class CandidateEntity(BaseModel):
    """One reviewable extraction result.

    A candidate is what an extractor proposes *before* graph mapping
    happens. It is intentionally close to a graph node (it has a
    label, properties, and provenance) but it is not one yet: the
    pipeline can drop, edit, or merge candidates before they are
    promoted into :class:`graphflow_core.graph.GraphNode` instances.

    Attributes:
        label: The ontology node label this candidate maps to. Must
            match a label declared in the active
            :class:`OntologySpec`; the extractor that produced the
            candidate is responsible for that constraint.
        surface_text: The exact substring of the source chunk that
            matched. Useful for review UIs and for downstream property
            extraction.
        confidence: Score in ``[0.0, 1.0]``. ``1.0`` means the
            extractor is fully confident; ``0.0`` means no confidence.
            Hybrid routing thresholds and review UIs read this.
        properties: Optional structured properties the extractor
            captured for this candidate (e.g. ``{"name": "Acme Ltd"}``).
            The mapping engine consumes these.
        source_chunk_id: ``TextChunk.chunk_id`` of the chunk this
            candidate came from.
        source_name: Provenance: source name from the originating
            chunk, copied here so a candidate is self-describing.
        source_path: Provenance: source path from the originating
            chunk.
        chunk_index: Provenance: chunk index from the originating
            chunk.
        start_offset: 0-indexed character offset of ``surface_text``
            within ``TextChunk.text``. ``None`` when the extractor
            cannot localise the match (e.g. an LLM extractor that
            paraphrases).
        end_offset: Exclusive end offset paired with
            ``start_offset``. ``None`` whenever ``start_offset`` is
            ``None``.
        extractor: Free-form name of the extractor that produced this
            candidate (e.g. ``"fast"``). Lets the run summary count
            candidates per extractor.
    """

    model_config = _STRICT

    label: str = Field(min_length=1)
    surface_text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    properties: dict[str, str] = Field(default_factory=dict)
    source_chunk_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    extractor: str = Field(min_length=1)

    @model_validator(mode="after")
    def _offsets_are_consistent(self) -> CandidateEntity:
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("start_offset and end_offset must both be set or both be None")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset <= self.start_offset
        ):
            raise ValueError(
                f"end_offset ({self.end_offset}) must be greater than "
                f"start_offset ({self.start_offset})"
            )
        return self


@runtime_checkable
class Extractor(Protocol):
    """Structural protocol for text-to-graph extractors.

    Implementations must be **deterministic for the same inputs**: two
    calls with the same chunks and the same ontology must produce the
    same candidates in the same order. Pipeline runs and tests rely on
    this so they can compare outputs reliably.

    Implementations must also constrain candidates to ontology
    labels: only labels declared in ``ontology`` may appear in the
    returned candidates. Anything else is the extractor's bug, not the
    caller's.
    """

    def extract(
        self,
        chunks: Iterable[TextChunk],
        *,
        ontology: OntologySpec,
    ) -> list[CandidateEntity]:
        """Return candidate entities found in ``chunks``."""
        ...
