"""Neo4j graph sink package.

Cypher rendering helpers live in submodules so they can be unit-tested
without a running Neo4j. The :class:`Neo4jGraphSink` (added in a later
slice) wires the renderers behind the :class:`GraphSink` protocol.
"""

from __future__ import annotations

from graphflow_core.sinks.neo4j.cypher import (
    CypherStatement,
    render_constraint_statements,
)

__all__ = [
    "CypherStatement",
    "render_constraint_statements",
]
