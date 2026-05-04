"""GraphFlow entity resolution.

This subpackage owns the contract between extraction output and graph
mapping input. Extractors produce
:class:`graphflow_core.extraction.CandidateEntity` instances; graph
mapping consumes :class:`graphflow_core.graph.GraphNode` instances.
Resolution is what sits between them: it deduplicates candidates that
refer to the same real-world entity, decides which matches are
confident enough to merge automatically and which need human review,
and emits :class:`ResolvedEntity` objects ready to be promoted into
graph nodes.

The output model intentionally records, for every input candidate:

- The :class:`ResolvedEntity` it was assigned to (always set, even for
  candidates that became their own new entity).
- A :data:`DecisionStatus` (``auto_link`` / ``review`` / ``no_match``)
  so review tooling can filter.
- A match ``score`` and ``alternatives`` list so a reviewer can see
  what other entities were close.
- A short ``reason`` so the decision is self-explaining when logged.

Together these form a small, durable audit trail: the resolution step
is not a black box.
"""

from __future__ import annotations

from graphflow_core.resolution.base import (
    DecisionStatus,
    ResolutionDecision,
    ResolutionResult,
    ResolvedEntity,
    Resolver,
)
from graphflow_core.resolution.errors import ResolutionError
from graphflow_core.resolution.simple import SimpleResolver

__all__ = [
    "DecisionStatus",
    "ResolutionDecision",
    "ResolutionError",
    "ResolutionResult",
    "ResolvedEntity",
    "Resolver",
    "SimpleResolver",
]
