"""Map a single :class:`ParsedRecord` into one :class:`GraphNode`.

Validation rules:

- The node's key property (declared in the ontology) must be mapped and
  must produce a non-empty value.
- Required ontology properties must be present, non-empty, and coerce
  to the declared :class:`PropertyType`.
- Optional ontology properties that are missing are simply omitted.
- Optional ontology properties that fail coercion produce a warning and
  are omitted (the node is still emitted).
- Mapping properties that reference an ontology property that does not
  exist produce a warning and are skipped.

A node mapping that cannot produce a key value yields ``None`` for the
node and at least one error in the issue list.
"""

from __future__ import annotations

from graphflow_core.graph.objects import GraphNode, RecordProvenance
from graphflow_core.manifests.ontology import NodeSpec
from graphflow_core.manifests.pipeline import NodeMapping
from graphflow_core.mapping.fields import (
    FieldCoercionError,
    coerce_to_property_type,
    read_source_field,
)
from graphflow_core.mapping.issues import MappingIssue, MappingIssueSeverity
from graphflow_core.sources.base import ParsedRecord


def map_record_to_node(
    record: ParsedRecord,
    mapping: NodeMapping,
    ontology_node: NodeSpec,
) -> tuple[GraphNode | None, list[MappingIssue]]:
    """Build a :class:`GraphNode` for ``ontology_node`` from one ``record``."""
    issues: list[MappingIssue] = []
    target_label = ontology_node.label
    key_property = ontology_node.key.property

    # 1. Key value must be available and non-empty.
    if mapping.key.from_field != key_property and key_property not in mapping.properties:
        # The mapping does not expose the ontology key at all. Cross-validation
        # in load_connector should already have caught this, but we still
        # report a clear error for direct callers.
        issues.append(
            MappingIssue(
                severity="error",
                message=(
                    f"node mapping for '{target_label}' does not produce the "
                    f"ontology key property '{key_property}'"
                ),
                source_name=record.source_name,
                location=record.location,
                target=f"{target_label}.{key_property}",
            )
        )
        return None, issues

    try:
        raw_key = read_source_field(record.data, mapping.key.from_field)
    except KeyError:
        issues.append(
            MappingIssue(
                severity="error",
                message=(f"key field '{mapping.key.from_field}' is missing or empty"),
                source_name=record.source_name,
                location=record.location,
                target=f"{target_label}.{key_property}",
            )
        )
        return None, issues

    key_value = str(raw_key).strip()
    if key_value == "":
        issues.append(
            MappingIssue(
                severity="error",
                message=f"key field '{mapping.key.from_field}' resolved to an empty value",
                source_name=record.source_name,
                location=record.location,
                target=f"{target_label}.{key_property}",
            )
        )
        return None, issues

    # 2. Walk every mapped property and coerce.
    properties: dict[str, object] = {}
    for target_property, source_field in mapping.properties.items():
        ontology_property = ontology_node.properties.get(target_property)
        if ontology_property is None:
            issues.append(
                MappingIssue(
                    severity="warning",
                    message=(
                        f"mapping property '{target_property}' is not declared "
                        f"in ontology node '{target_label}'; skipping"
                    ),
                    source_name=record.source_name,
                    location=record.location,
                    target=f"{target_label}.{target_property}",
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
                            f"required property '{target_property}' is missing "
                            f"or empty (source field '{source_field}')"
                        ),
                        source_name=record.source_name,
                        location=record.location,
                        target=f"{target_label}.{target_property}",
                    )
                )
            continue
        try:
            value = coerce_to_property_type(raw, ontology_property.type)
        except FieldCoercionError as exc:
            severity: MappingIssueSeverity = (
                "error" if ontology_property.required else "warning"
            )
            issues.append(
                MappingIssue(
                    severity=severity,
                    message=(
                        f"property '{target_property}' could not be coerced to "
                        f"{ontology_property.type}: {exc}"
                    ),
                    source_name=record.source_name,
                    location=record.location,
                    target=f"{target_label}.{target_property}",
                )
            )
            continue
        properties[target_property] = value

    # 3. Verify every required ontology property is satisfied.
    has_required_error = any(
        i.severity == "error" and i.target.startswith(f"{target_label}.") for i in issues
    )
    for prop_name, prop_spec in ontology_node.properties.items():
        if prop_spec.required and prop_name not in properties and prop_name != key_property:
            issues.append(
                MappingIssue(
                    severity="error",
                    message=(f"required ontology property '{prop_name}' is not mapped"),
                    source_name=record.source_name,
                    location=record.location,
                    target=f"{target_label}.{prop_name}",
                )
            )
            has_required_error = True

    if has_required_error:
        return None, issues

    # 4. Ensure the key property is included in the node's properties dict
    #    even when it was supplied via mapping.key alone.
    properties.setdefault(key_property, key_value)

    node = GraphNode(
        label=target_label,
        key_property=key_property,
        key_value=key_value,
        properties=properties,
        provenance=RecordProvenance(
            source_name=record.source_name,
            source_path=record.source_path,
            location=record.location,
        ),
    )
    return node, issues
