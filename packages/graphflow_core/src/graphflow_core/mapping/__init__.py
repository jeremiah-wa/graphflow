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

__all__ = [
    "FieldCoercionError",
    "MappingIssue",
    "MappingIssueSeverity",
    "coerce_to_property_type",
    "read_source_field",
]
