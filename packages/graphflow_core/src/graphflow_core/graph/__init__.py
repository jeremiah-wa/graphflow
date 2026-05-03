"""GraphFlow graph-object models.

This subpackage owns the typed in-memory representation of nodes and
relationships that flows from the mapping engine into a graph sink. It
is intentionally independent of any specific destination (Neo4j,
Memgraph, ...). Sinks consume these models; they do not own them.
"""

from __future__ import annotations

from graphflow_core.graph.objects import (
    GraphNode,
    GraphRelationship,
    RecordProvenance,
)

__all__ = [
    "GraphNode",
    "GraphRelationship",
    "RecordProvenance",
]
