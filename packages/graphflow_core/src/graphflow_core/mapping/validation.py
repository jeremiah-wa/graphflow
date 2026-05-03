"""Post-mapping validation.

The :class:`Mapper` produces a :class:`MappingResult` containing the
nodes and relationships derived from individual records. Two further
correctness checks span the whole result:

- **Duplicate node keys**: two distinct records produced different
  property values for the same ``(label, key_property, key_value)``.
  The first occurrence is kept; subsequent ones are recorded as an
  error issue.
- **Orphan relationships**: a relationship references an endpoint
  identity that no produced node carries. This is recorded as an error
  issue; the relationship is left in the result so callers can decide
  whether to drop it.

These checks live separately from per-record mapping because they
require seeing the whole set of produced graph objects.
"""

from __future__ import annotations

from graphflow_core.graph.objects import GraphNode, GraphRelationship
from graphflow_core.mapping.issues import MappingIssue


def detect_duplicate_node_keys(
    nodes: list[GraphNode],
) -> tuple[list[GraphNode], list[MappingIssue]]:
    """Drop later duplicates and return them as issues.

    Two nodes with the same identity but identical properties are
    considered the same logical record and silently deduplicated. Two
    nodes with the same identity but conflicting properties produce an
    error.
    """
    seen: dict[tuple[str, str, str], GraphNode] = {}
    issues: list[MappingIssue] = []
    deduped: list[GraphNode] = []

    for node in nodes:
        identity = node.identity()
        if identity not in seen:
            seen[identity] = node
            deduped.append(node)
            continue
        existing = seen[identity]
        if existing.properties == node.properties:
            # Same record observed twice; silently deduplicate.
            continue
        issues.append(
            MappingIssue(
                severity="error",
                message=(
                    f"duplicate node key for {node.label}.{node.key_property}="
                    f"'{node.key_value}': conflicting properties "
                    f"{sorted(existing.properties)} vs {sorted(node.properties)}"
                ),
                source_name=node.provenance.source_name if node.provenance else "",
                location=node.provenance.location if node.provenance else "",
                target=f"{node.label}.{node.key_property}",
            )
        )
    return deduped, issues


def detect_orphan_relationships(
    nodes: list[GraphNode],
    relationships: list[GraphRelationship],
) -> list[MappingIssue]:
    """Return one issue per relationship whose endpoint is unknown."""
    known: set[tuple[str, str, str]] = {node.identity() for node in nodes}
    issues: list[MappingIssue] = []

    for rel in relationships:
        for side, identity in (("from", rel.from_identity()), ("to", rel.to_identity())):
            if identity not in known:
                label, key_property, key_value = identity
                issues.append(
                    MappingIssue(
                        severity="error",
                        message=(
                            f"relationship '{rel.type}' has unknown {side} "
                            f"endpoint {label}.{key_property}='{key_value}'"
                        ),
                        source_name=rel.provenance.source_name if rel.provenance else "",
                        location=rel.provenance.location if rel.provenance else "",
                        target=f"{rel.type}.{side}",
                    )
                )
    return issues
