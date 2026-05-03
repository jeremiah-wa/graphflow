"""Graph sink protocol and result models.

A :class:`GraphSink` accepts an ontology (to set up constraints/indexes
once) and then accepts batches of nodes and relationships. Each write
returns a :class:`GraphWriteResult` describing what happened so the
pipeline runner can produce a meaningful run summary.

The protocol is intentionally narrow: it does not expose transactions,
sessions, or driver-specific objects. Concrete implementations may
batch internally; callers should treat each call as one logical
upsert operation.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from graphflow_core.graph.objects import GraphNode, GraphRelationship
from graphflow_core.manifests.ontology import OntologySpec


class GraphSinkError(Exception):
    """Raised when a graph sink cannot complete an operation."""


class GraphWriteResult(BaseModel):
    """Counts returned by a single graph sink write call."""

    model_config = ConfigDict(extra="forbid")

    nodes_written: int = Field(default=0, ge=0)
    relationships_written: int = Field(default=0, ge=0)
    constraints_created: int = Field(default=0, ge=0)
    indexes_created: int = Field(default=0, ge=0)


@runtime_checkable
class GraphSink(Protocol):
    """Structural protocol for graph destinations.

    Implementations are responsible for being **idempotent**:

    - :meth:`create_constraints` must be safe to call repeatedly.
    - :meth:`upsert_nodes` must MERGE on the node identity (label +
      key property + key value) so re-running the same input produces
      the same graph.
    - :meth:`upsert_relationships` must MERGE on the relationship's
      endpoints (and key property when the ontology requests it) so
      re-running the same input does not duplicate edges.
    """

    def create_constraints(self, ontology: OntologySpec) -> GraphWriteResult:
        """Create the schema constraints implied by ``ontology``."""
        ...

    def upsert_nodes(self, nodes: list[GraphNode]) -> GraphWriteResult:
        """Upsert a batch of nodes idempotently."""
        ...

    def upsert_relationships(self, relationships: list[GraphRelationship]) -> GraphWriteResult:
        """Upsert a batch of relationships idempotently."""
        ...

    def close(self) -> None:
        """Release any underlying resources (driver, sessions, ...)."""
        ...
