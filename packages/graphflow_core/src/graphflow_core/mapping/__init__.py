"""GraphFlow mapping engine.

Turns :class:`graphflow_core.sources.ParsedRecord` instances into
:class:`graphflow_core.graph.GraphNode` and
:class:`graphflow_core.graph.GraphRelationship` objects, using the
:class:`graphflow_core.manifests.PipelineSpec.mapping` rules and the
:class:`graphflow_core.manifests.OntologySpec` as the schema.
"""

from __future__ import annotations

from graphflow_core.mapping.fields import (
    FieldCoercionError,
    coerce_to_property_type,
    read_source_field,
)
from graphflow_core.mapping.issues import MappingIssue, MappingIssueSeverity
from graphflow_core.mapping.mapper import Mapper, MappingResult
from graphflow_core.mapping.nodes import map_record_to_node
from graphflow_core.mapping.relationships import map_record_to_relationship

__all__ = [
    "FieldCoercionError",
    "Mapper",
    "MappingIssue",
    "MappingIssueSeverity",
    "MappingResult",
    "coerce_to_property_type",
    "map_record_to_node",
    "map_record_to_relationship",
    "read_source_field",
]
