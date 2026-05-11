"""Unit tests for the :class:`Resolver` runtime-checkable protocol.

The protocol is the contract every resolver (deterministic, embedding-
based, LLM-assisted, ...) must satisfy. These tests pin that contract
so a stub implementation registered through ``isinstance`` checks is
sufficient to act as a resolver in the rest of the pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable

from graphflow_core.extraction import CandidateEntity
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)
from graphflow_core.resolution import (
    ResolutionDecision,
    ResolutionResult,
    ResolvedEntity,
    Resolver,
)


def _ontology() -> OntologySpec:
    return OntologySpec(
        name="test_ontology",
        nodes=[
            NodeSpec(
                label="Company",
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            ),
        ],
    )


def _candidate() -> CandidateEntity:
    return CandidateEntity(
        label="Company",
        surface_text="Acme Ltd",
        confidence=1.0,
        source_chunk_id="c-0",
        source_name="docs",
        source_path="docs/a.txt",
        chunk_index=0,
        extractor="fast",
    )


def test_stub_resolver_satisfies_protocol() -> None:
    class _StubResolver:
        def resolve(
            self,
            candidates: Iterable[CandidateEntity],
            *,
            ontology: OntologySpec,
        ) -> ResolutionResult:
            del candidates, ontology
            return ResolutionResult()

    assert isinstance(_StubResolver(), Resolver)


def test_object_without_resolve_does_not_satisfy_protocol() -> None:
    class _NotAResolver:
        pass

    assert not isinstance(_NotAResolver(), Resolver)


def test_stub_resolver_returns_resolution_result() -> None:
    class _Always:
        def resolve(
            self,
            candidates: Iterable[CandidateEntity],
            *,
            ontology: OntologySpec,
        ) -> ResolutionResult:
            del ontology
            entities: list[ResolvedEntity] = []
            decisions: list[ResolutionDecision] = []
            for candidate in candidates:
                entity_id = f"{candidate.label}:{candidate.surface_text.lower()}"
                entities.append(
                    ResolvedEntity(
                        entity_id=entity_id,
                        label=candidate.label,
                        canonical_surface=candidate.surface_text,
                        candidate_count=1,
                        source_chunk_id=candidate.source_chunk_id,
                        source_name=candidate.source_name,
                        source_path=candidate.source_path,
                        chunk_index=candidate.chunk_index,
                    )
                )
                decisions.append(
                    ResolutionDecision(
                        candidate=candidate,
                        status="no_match",
                        entity_id=entity_id,
                        score=1.0,
                        reason="stub: every candidate becomes its own entity",
                    )
                )
            return ResolutionResult(entities=entities, decisions=decisions)

    resolver = _Always()
    result = resolver.resolve([_candidate()], ontology=_ontology())
    assert isinstance(result, ResolutionResult)
    assert len(result.entities) == 1
    assert len(result.decisions) == 1
    assert result.entities[0].label == "Company"
    assert result.decisions[0].status == "no_match"
