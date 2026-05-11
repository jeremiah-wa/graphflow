"""Bridge from :class:`ResolvedEntity` to :class:`GraphNode`.

Resolution does not replace the structured-data mapping path
(:mod:`graphflow_core.mapping`); it feeds it. This module owns the
small adapter that turns a resolved candidate-entity into a graph node
ready for upsert.

The adapter is intentionally narrow:

- The ontology node's ``key.property`` becomes the graph node's
  ``key_property``.
- Whichever value the resolved entity carries for that property
  becomes ``key_value``. When the resolved entity does not have the
  key property in its merged ``properties`` (typical for fast-
  extractor candidates that only carry ``surface_text``), the
  resolver's chosen ``canonical_surface`` is used as the key value
  *and* added to the property map so downstream tooling sees a
  consistent payload.
- All other resolved properties pass through unchanged.
- Provenance is rebuilt from the resolved entity's source fields.

Anything more sophisticated (property coercion, required-property
checks, multi-source merging) belongs in
:mod:`graphflow_core.mapping`, not here.
"""

from __future__ import annotations

from graphflow_core.graph.objects import GraphNode, RecordProvenance
from graphflow_core.manifests.ontology import NodeSpec
from graphflow_core.resolution.base import ResolvedEntity
from graphflow_core.resolution.errors import ResolutionError


def resolved_to_graph_node(
    resolved: ResolvedEntity,
    ontology_node: NodeSpec,
) -> GraphNode:
    """Convert ``resolved`` into a :class:`GraphNode`.

    Args:
        resolved: The canonical entity produced by a resolver.
        ontology_node: The ontology node spec whose label matches
            ``resolved.label``. Caller is responsible for picking the
            right :class:`NodeSpec`; this function validates the match
            but does not search for it.

    Raises:
        ResolutionError: if the labels do not match, or if the
            resolved entity ends up with an empty key value (which
            would violate :class:`GraphNode`'s non-empty key
            invariant).
    """
    if resolved.label != ontology_node.label:
        raise ResolutionError(
            f"resolved entity label '{resolved.label}' does not match "
            f"ontology node label '{ontology_node.label}'"
        )

    key_property = ontology_node.key.property
    properties: dict[str, object] = dict(resolved.properties)
    raw_key = properties.get(key_property, resolved.canonical_surface)
    key_value = str(raw_key).strip()
    if key_value == "":
        raise ResolutionError(
            f"resolved entity '{resolved.entity_id}' produced an empty "
            f"key value for property '{key_property}'"
        )
    properties.setdefault(key_property, key_value)

    return GraphNode(
        label=resolved.label,
        key_property=key_property,
        key_value=key_value,
        properties=properties,
        provenance=RecordProvenance(
            source_name=resolved.source_name,
            source_path=resolved.source_path,
            location=f"chunk {resolved.chunk_index}",
        ),
    )
