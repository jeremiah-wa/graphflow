"""Map a single :class:`ParsedRecord` into one :class:`GraphRelationship`.

The relationship's endpoints are identified by their ontology label
plus a key value extracted from a named source field. The endpoint key
property is taken from the ontology so that it stays in sync with how
nodes are keyed.

Relationship property handling mirrors :func:`map_record_to_node`:

- Missing or empty endpoint key fields are errors; the relationship is
  dropped.
- Required ontology relationship properties must be present and coerce
  to the declared type.
- Optional properties that fail coercion produce a warning.
- Mapped properties that are not declared in the ontology relationship
  produce a warning and are skipped.
"""

from __future__ import annotations

from graphflow_core.graph.objects import GraphRelationship, RecordProvenance
from graphflow_core.manifests.ontology import OntologySpec, RelationshipSpec
from graphflow_core.manifests.pipeline import RelationshipMapping
from graphflow_core.mapping.fields import (
    FieldCoercionError,
    coerce_to_property_type,
    read_source_field,
)
from graphflow_core.mapping.issues import MappingIssue, MappingIssueSeverity
from graphflow_core.sources.base import ParsedRecord


def map_record_to_relationship(
    record: ParsedRecord,
    mapping: RelationshipMapping,
    ontology_relationship: RelationshipSpec,
    ontology: OntologySpec,
) -> tuple[GraphRelationship | None, list[MappingIssue]]:
    """Build a :class:`GraphRelationship` from one ``record``."""
    issues: list[MappingIssue] = []
    rel_type = ontology_relationship.type
    target_prefix = f"{rel_type}({ontology_relationship.from_label}->{ontology_relationship.to})"

    # Endpoint label sanity (already cross-validated in load_connector,
    # but called out here for direct callers).
    endpoint_node_by_label = {n.label: n for n in ontology.nodes}
    from_node = endpoint_node_by_label.get(ontology_relationship.from_label)
    to_node = endpoint_node_by_label.get(ontology_relationship.to)
    if from_node is None or to_node is None:
        issues.append(
            MappingIssue(
                severity="error",
                message=(
                    f"relationship '{rel_type}' references an unknown endpoint "
                    f"label; ontology has {sorted(endpoint_node_by_label)}"
                ),
                source_name=record.source_name,
                location=record.location,
                target=target_prefix,
            )
        )
        return None, issues

    from_key_value = _read_endpoint_key(
        record, mapping.from_node.from_field, "from", target_prefix, issues
    )
    to_key_value = _read_endpoint_key(
        record, mapping.to_node.from_field, "to", target_prefix, issues
    )
    if from_key_value is None or to_key_value is None:
        return None, issues

    properties: dict[str, object] = {}
    for target_property, source_field in mapping.properties.items():
        ontology_property = ontology_relationship.properties.get(target_property)
        if ontology_property is None:
            issues.append(
                MappingIssue(
                    severity="warning",
                    message=(
                        f"relationship property '{target_property}' is not declared "
                        f"in ontology relationship '{rel_type}'; skipping"
                    ),
                    source_name=record.source_name,
                    location=record.location,
                    target=f"{target_prefix}.{target_property}",
                )
            )
            continue
        try:
            raw = read_source_field(record.data, source_field)
        except KeyError:
            if ontology_property.required:
                issues.append(
                    MappingIssue(
                        severity="error",
                        message=(
                            f"required relationship property '{target_property}' "
                            f"is missing or empty (source field '{source_field}')"
                        ),
                        source_name=record.source_name,
                        location=record.location,
                        target=f"{target_prefix}.{target_property}",
                    )
                )
            continue
        try:
            value = coerce_to_property_type(raw, ontology_property.type)
        except FieldCoercionError as exc:
            severity: MappingIssueSeverity = "error" if ontology_property.required else "warning"
            issues.append(
                MappingIssue(
                    severity=severity,
                    message=(
                        f"relationship property '{target_property}' could not be "
                        f"coerced to {ontology_property.type}: {exc}"
                    ),
                    source_name=record.source_name,
                    location=record.location,
                    target=f"{target_prefix}.{target_property}",
                )
            )
            continue
        properties[target_property] = value

    for prop_name, prop_spec in ontology_relationship.properties.items():
        if prop_spec.required and prop_name not in properties:
            issues.append(
                MappingIssue(
                    severity="error",
                    message=(
                        f"required ontology relationship property '{prop_name}' is not mapped"
                    ),
                    source_name=record.source_name,
                    location=record.location,
                    target=f"{target_prefix}.{prop_name}",
                )
            )

    if any(i.severity == "error" for i in issues):
        return None, issues

    rel = GraphRelationship(
        type=rel_type,
        from_label=ontology_relationship.from_label,
        from_key_property=from_node.key.property,
        from_key_value=from_key_value,
        to_label=ontology_relationship.to,
        to_key_property=to_node.key.property,
        to_key_value=to_key_value,
        properties=properties,
        provenance=RecordProvenance(
            source_name=record.source_name,
            source_path=record.source_path,
            location=record.location,
        ),
    )
    return rel, issues


def _read_endpoint_key(
    record: ParsedRecord,
    field: str,
    side: str,
    target_prefix: str,
    issues: list[MappingIssue],
) -> str | None:
    try:
        raw = read_source_field(record.data, field)
    except KeyError:
        issues.append(
            MappingIssue(
                severity="error",
                message=f"{side} endpoint field '{field}' is missing or empty",
                source_name=record.source_name,
                location=record.location,
                target=target_prefix,
            )
        )
        return None
    value = str(raw).strip()
    if value == "":
        issues.append(
            MappingIssue(
                severity="error",
                message=f"{side} endpoint field '{field}' resolved to an empty value",
                source_name=record.source_name,
                location=record.location,
                target=target_prefix,
            )
        )
        return None
    return value
