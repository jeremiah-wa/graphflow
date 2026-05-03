"""Unit tests for :class:`GraphSink` and :class:`GraphWriteResult`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from graphflow_core.graph import GraphNode, GraphRelationship
from graphflow_core.manifests.ontology import OntologySpec
from graphflow_core.sinks import GraphSink, GraphWriteResult


def test_graph_write_result_defaults() -> None:
    result = GraphWriteResult()
    assert result.nodes_written == 0
    assert result.relationships_written == 0
    assert result.constraints_created == 0
    assert result.indexes_created == 0


def test_graph_write_result_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        GraphWriteResult(nodes_written=-1)


def test_graph_sink_protocol_is_runtime_checkable() -> None:
    class _StubSink:
        def create_constraints(self, ontology: OntologySpec) -> GraphWriteResult:
            return GraphWriteResult()

        def upsert_nodes(self, nodes: list[GraphNode]) -> GraphWriteResult:
            return GraphWriteResult(nodes_written=len(nodes))

        def upsert_relationships(self, relationships: list[GraphRelationship]) -> GraphWriteResult:
            return GraphWriteResult(relationships_written=len(relationships))

        def close(self) -> None:
            return None

    class _NotASink:
        pass

    assert isinstance(_StubSink(), GraphSink)
    assert not isinstance(_NotASink(), GraphSink)
