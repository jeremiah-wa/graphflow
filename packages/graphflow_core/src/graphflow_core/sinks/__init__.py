"""GraphFlow graph sinks.

A *graph sink* writes :class:`graphflow_core.graph.GraphNode` and
:class:`graphflow_core.graph.GraphRelationship` objects into a graph
destination (Neo4j today, possibly Memgraph or RDF stores later). Sinks
must implement the :class:`GraphSink` protocol so the pipeline runner
can stay vendor-neutral.
"""

from __future__ import annotations

from graphflow_core.sinks.base import (
    GraphSink,
    GraphSinkError,
    GraphWriteResult,
)
from graphflow_core.sinks.neo4j import Neo4jGraphSink

__all__ = [
    "GraphSink",
    "GraphSinkError",
    "GraphWriteResult",
    "Neo4jGraphSink",
]
