"""Integration test for the simple resolver against a near-duplicates
fixture, including the bridge to graph mapping.

Marked ``integration`` because it touches the filesystem (reads a
fixture file shipped in the test directory). It does not require any
external services, network access, or paid APIs - just disk - so it
runs in the same job as the other filesystem-backed integration tests.

The chain under test is:

    text fixture -> FastExtractor -> SimpleResolver -> resolved_to_graph_node

This is the full ``extraction -> resolution -> graph mapping`` pipeline
slice: extraction emits candidates, resolution collapses them, the
bridge produces graph-ready node objects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphflow_core.extraction import FastExtractor, TextChunk
from graphflow_core.graph.objects import GraphNode
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)
from graphflow_core.resolution import (
    SimpleResolver,
    resolved_to_graph_node,
)

FIXTURE = Path(__file__).parent / "fixtures" / "resolution" / "near_duplicates.txt"


def _ontology() -> OntologySpec:
    return OntologySpec(
        name="resolution_ontology",
        nodes=[
            NodeSpec(
                label="Company",
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            ),
            NodeSpec(
                label="Person",
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            ),
        ],
    )


def _chunk(text: str) -> TextChunk:
    return TextChunk(
        chunk_id="near-dups#0",
        text=text,
        source_name="news_documents",
        source_path=str(FIXTURE),
        chunk_index=0,
        location="chunk 0",
    )


def _company_node() -> NodeSpec:
    return _ontology().nodes[0]


@pytest.mark.integration
def test_fixture_file_is_present() -> None:
    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"


@pytest.mark.integration
def test_resolver_collapses_exact_and_case_punctuation_duplicates() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    extractor = FastExtractor(
        aliases={
            "Company": ["Acme Ltd", "ACME LTD", "Acme Limited", "Globex Industries"],
            "Person": ["Alice Johnson", "Bob Smith"],
        }
    )
    candidates = extractor.extract([_chunk(text)], ontology=_ontology())

    # Sanity: extraction produced multiple Acme-Ltd-shaped candidates
    # plus one each for Acme Limited and Globex Industries.
    company_surfaces = sorted(c.surface_text for c in candidates if c.label == "Company")
    assert "Acme Ltd" in company_surfaces
    assert "ACME LTD" in company_surfaces
    assert "Acme Limited" in company_surfaces
    assert "Globex Industries" in company_surfaces
    assert company_surfaces.count("Acme Ltd") >= 2

    # With a permissive review threshold, "Acme Limited" should land
    # in the review band against "Acme Ltd"; "Globex Industries"
    # should stay distinct.
    resolver = SimpleResolver(review_threshold=0.7)
    result = resolver.resolve(candidates, ontology=_ontology())

    company_entities = [e for e in result.entities if e.label == "Company"]
    company_ids = {e.entity_id for e in company_entities}

    # We expect the four-way Acme Ltd / ACME LTD duplicates to collapse
    # into a single Company:acme_ltd entity, plus a separate review
    # entity for "Acme Limited", plus Globex Industries.
    assert "Company:acme_ltd" in company_ids
    assert "Company:acme_limited" in company_ids
    assert "Company:globex_industries" in company_ids

    acme_ltd = next(e for e in company_entities if e.entity_id == "Company:acme_ltd")
    assert acme_ltd.candidate_count >= 3
    assert acme_ltd.needs_review is False

    acme_limited = next(e for e in company_entities if e.entity_id == "Company:acme_limited")
    assert acme_limited.needs_review is True


@pytest.mark.integration
def test_review_decision_records_alternatives_for_audit() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    extractor = FastExtractor(
        aliases={"Company": ["Acme Ltd", "Acme Limited", "Globex Industries"]}
    )
    candidates = extractor.extract([_chunk(text)], ontology=_ontology())
    resolver = SimpleResolver(review_threshold=0.7)
    result = resolver.resolve(candidates, ontology=_ontology())

    review_decisions = [d for d in result.decisions if d.status == "review"]
    assert review_decisions, "expected at least one review decision"
    for decision in review_decisions:
        # Every review decision must record at least one alternative
        # (the entity it almost matched). Without alternatives the
        # review record is uninterpretable to a human reviewer.
        assert decision.alternatives, decision
        assert decision.reason
        assert 0.7 <= decision.score < 1.0


@pytest.mark.integration
def test_resolution_output_feeds_graph_mapping() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    extractor = FastExtractor(aliases={"Company": ["Acme Ltd", "ACME LTD", "Globex Industries"]})
    candidates = extractor.extract([_chunk(text)], ontology=_ontology())
    resolver = SimpleResolver()
    result = resolver.resolve(candidates, ontology=_ontology())

    company_entities = [e for e in result.entities if e.label == "Company"]
    nodes = [resolved_to_graph_node(entity, _company_node()) for entity in company_entities]

    # Every resolved company entity becomes a valid graph node with
    # the ontology-declared key property and a non-empty key value.
    assert nodes
    for node in nodes:
        assert isinstance(node, GraphNode)
        assert node.label == "Company"
        assert node.key_property == "name"
        assert node.key_value
        assert node.properties.get("name") == node.key_value
        assert node.provenance is not None
        assert node.provenance.source_path == str(FIXTURE)

    # Identities are unique - if they weren't, idempotent upsert
    # would conflate distinct entities.
    identities = [n.identity() for n in nodes]
    assert len(identities) == len(set(identities))


@pytest.mark.integration
def test_resolution_run_is_repeatable() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    extractor = FastExtractor(
        aliases={
            "Company": ["Acme Ltd", "ACME LTD", "Acme Limited", "Globex Industries"],
        }
    )
    candidates = extractor.extract([_chunk(text)], ontology=_ontology())
    resolver = SimpleResolver(review_threshold=0.7)
    first = resolver.resolve(candidates, ontology=_ontology())
    second = resolver.resolve(candidates, ontology=_ontology())
    assert first == second
