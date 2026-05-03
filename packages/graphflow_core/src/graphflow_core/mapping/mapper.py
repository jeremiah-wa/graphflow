"""High-level mapping driver.

The :class:`Mapper` walks an iterable of :class:`ParsedRecord` instances
and applies every :class:`NodeMapping` and :class:`RelationshipMapping`
declared in the pipeline manifest. The result is a
:class:`MappingResult` that bundles the produced graph objects and any
mapping issues so callers can present them together.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from graphflow_core.graph.objects import GraphNode, GraphRelationship
from graphflow_core.manifests.loader import ConnectorManifest
from graphflow_core.mapping.issues import MappingIssue
from graphflow_core.mapping.nodes import map_record_to_node
from graphflow_core.mapping.relationships import map_record_to_relationship
from graphflow_core.sources.base import ParsedRecord


class MappingResult(BaseModel):
    """Bundle of graph objects and issues produced by one mapping run."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
    issues: list[MappingIssue] = Field(default_factory=list)

    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)


class Mapper:
    """Drive node and relationship mappings against a record stream."""

    def __init__(self, connector: ConnectorManifest) -> None:
        self._connector = connector
        ontology = connector.ontology.ontology
        self._ontology = ontology
        self._nodes_by_label = {node.label: node for node in ontology.nodes}
        self._rels_by_type = {rel.type: rel for rel in ontology.relationships}

    def map(self, records: Iterable[ParsedRecord]) -> MappingResult:
        """Apply the pipeline mapping to ``records`` and return a result."""
        result = MappingResult()
        pipeline_mapping = self._connector.pipeline.pipeline.mapping

        for record in records:
            for node_mapping in pipeline_mapping.nodes:
                ontology_node = self._nodes_by_label.get(node_mapping.label)
                if ontology_node is None:
                    # Cross-validation in load_connector should already
                    # have caught this, but Mapper is documented to work
                    # standalone too.
                    result.issues.append(
                        MappingIssue(
                            severity="error",
                            message=(
                                f"node mapping label '{node_mapping.label}' is "
                                "not declared in ontology"
                            ),
                            source_name=record.source_name,
                            location=record.location,
                            target=node_mapping.label,
                        )
                    )
                    continue
                node, issues = map_record_to_node(record, node_mapping, ontology_node)
                result.issues.extend(issues)
                if node is not None:
                    result.nodes.append(node)

            for rel_mapping in pipeline_mapping.relationships:
                ontology_rel = self._rels_by_type.get(rel_mapping.type)
                if ontology_rel is None:
                    result.issues.append(
                        MappingIssue(
                            severity="error",
                            message=(
                                f"relationship mapping type '{rel_mapping.type}' "
                                "is not declared in ontology"
                            ),
                            source_name=record.source_name,
                            location=record.location,
                            target=rel_mapping.type,
                        )
                    )
                    continue
                rel, issues = map_record_to_relationship(
                    record, rel_mapping, ontology_rel, self._ontology
                )
                result.issues.extend(issues)
                if rel is not None:
                    result.relationships.append(rel)

        return result
