"""Unit tests for the resolved-entity to graph-node bridge."""

from __future__ import annotations

import pytest

from graphflow_core.graph.objects import GraphNode
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    PropertySpec,
)
from graphflow_core.resolution import (
    ResolutionError,
    ResolvedEntity,
    resolved_to_graph_node,
)


def _ontology_node(label: str = "Company", key_property: str = "name") -> NodeSpec:
    return NodeSpec(
        label=label,
        key=NodeKey(property=key_property),
        properties={key_property: PropertySpec(type="string", required=True)},
    )


def _resolved(**overrides: object) -> ResolvedEntity:
    base: dict[str, object] = {
        "entity_id": "Company:acme_ltd",
        "label": "Company",
        "canonical_surface": "Acme Ltd",
        "candidate_count": 1,
        "source_chunk_id": "c-0",
        "source_name": "news",
        "source_path": "docs/news.txt",
        "chunk_index": 2,
    }
    base.update(overrides)
    return ResolvedEntity(**base)  # type: ignore[arg-type]


def test_canonical_surface_used_as_key_value_when_property_missing() -> None:
    node = resolved_to_graph_node(_resolved(), _ontology_node())
    assert isinstance(node, GraphNode)
    assert node.label == "Company"
    assert node.key_property == "name"
    assert node.key_value == "Acme Ltd"
    # Key always appears in properties so downstream tools see a
    # consistent payload.
    assert node.properties == {"name": "Acme Ltd"}


def test_explicit_key_property_in_resolved_properties_wins() -> None:
    resolved = _resolved(properties={"name": "Acme Limited"})
    node = resolved_to_graph_node(resolved, _ontology_node())
    assert node.key_value == "Acme Limited"
    assert node.properties["name"] == "Acme Limited"


def test_other_resolved_properties_pass_through() -> None:
    resolved = _resolved(properties={"name": "Acme Ltd", "city": "Boston"})
    node = resolved_to_graph_node(resolved, _ontology_node())
    assert node.properties == {"name": "Acme Ltd", "city": "Boston"}


def test_provenance_carried_from_resolved_entity() -> None:
    resolved = _resolved(
        source_name="news",
        source_path="docs/news.txt",
        chunk_index=7,
    )
    node = resolved_to_graph_node(resolved, _ontology_node())
    assert node.provenance is not None
    assert node.provenance.source_name == "news"
    assert node.provenance.source_path == "docs/news.txt"
    assert node.provenance.location == "chunk 7"


def test_label_mismatch_raises_resolution_error() -> None:
    resolved = _resolved(label="Person", entity_id="Person:alice_johnson")
    with pytest.raises(ResolutionError) as excinfo:
        resolved_to_graph_node(resolved, _ontology_node(label="Company"))
    assert "Person" in str(excinfo.value)
    assert "Company" in str(excinfo.value)


def test_whitespace_only_key_value_raises_resolution_error() -> None:
    # canonical_surface itself can't be all-whitespace (Pydantic
    # min_length=1), but a property override could be. In that case
    # we'd produce an invalid GraphNode, so we surface it with a
    # ResolutionError instead.
    resolved = _resolved(properties={"name": "   "})
    with pytest.raises(ResolutionError) as excinfo:
        resolved_to_graph_node(resolved, _ontology_node())
    assert "empty key value" in str(excinfo.value)


def test_key_value_is_stripped() -> None:
    resolved = _resolved(properties={"name": "  Acme Ltd  "})
    node = resolved_to_graph_node(resolved, _ontology_node())
    assert node.key_value == "Acme Ltd"


def test_alternate_key_property_is_respected() -> None:
    # Ontology can declare any snake_case property as the key.
    node = resolved_to_graph_node(
        _resolved(properties={"company_id": "ACM-1", "name": "Acme Ltd"}),
        _ontology_node(key_property="company_id"),
    )
    assert node.key_property == "company_id"
    assert node.key_value == "ACM-1"
    assert node.properties == {"company_id": "ACM-1", "name": "Acme Ltd"}
