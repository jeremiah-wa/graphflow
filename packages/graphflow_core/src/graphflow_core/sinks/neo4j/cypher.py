"""Cypher rendering helpers for the Neo4j sink.

These helpers produce the Cypher statements the Neo4j driver runs.
Keeping them as pure functions makes them straightforward to unit-test
without any database connection. They use ``$``-prefixed parameter
placeholders exclusively; user-supplied values must never be
interpolated into the statement string.

Identifier safety:

- Node labels and relationship types come from the ontology, which has
  already validated them as PascalCase / SCREAMING_SNAKE_CASE
  identifiers.
- Property names (including key properties) are validated as
  snake_case in the ontology and mapping models.

The rendering helpers therefore accept these identifiers as-is but
double-check against a strict regex to defend against any model that
slips through with an unexpected value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from graphflow_core.graph.objects import GraphNode, GraphRelationship
from graphflow_core.manifests.ontology import OntologySpec, RelationshipSpec

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(value: str, *, kind: str) -> str:
    """Reject identifiers that do not match ``[A-Za-z_][A-Za-z0-9_]*``."""
    if not _IDENT_RE.fullmatch(value):
        raise ValueError(f"unsafe Cypher identifier for {kind}: {value!r}")
    return value


@dataclass(frozen=True)
class CypherStatement:
    """A Cypher statement plus its parameter dictionary."""

    cypher: str
    parameters: dict[str, Any]


def render_node_upsert_statements(nodes: list[GraphNode]) -> list[CypherStatement]:
    """Return one MERGE statement per ``(label, key_property)`` group.

    Nodes are grouped by their identity shape so each call uses
    ``UNWIND $rows AS row`` over a parameter list, keeping both the
    Cypher text and the parameter footprint small even for large
    batches. The MERGE matches on the key property and assigns the
    full property dictionary on each upsert so re-runs are idempotent.
    """
    if not nodes:
        return []

    groups: dict[tuple[str, str], list[GraphNode]] = {}
    for node in nodes:
        groups.setdefault((node.label, node.key_property), []).append(node)

    statements: list[CypherStatement] = []
    for (label, key_property), group_nodes in groups.items():
        safe_label = _safe_identifier(label, kind="node label")
        safe_key = _safe_identifier(key_property, kind="key property")
        rows = [{"key": node.key_value, "props": dict(node.properties)} for node in group_nodes]
        cypher = (
            f"UNWIND $rows AS row MERGE (n:{safe_label} {{{safe_key}: row.key}}) SET n += row.props"
        )
        statements.append(CypherStatement(cypher=cypher, parameters={"rows": rows}))
    return statements


def render_relationship_upsert_statements(
    relationships: list[GraphRelationship],
    ontology: OntologySpec,
) -> list[CypherStatement]:
    """Return one MERGE statement per relationship type.

    The MERGE clause depends on the ontology's
    :class:`RelationshipKey.strategy`:

    - ``endpoints_and_type``: ``MERGE (a)-[r:TYPE]->(b)``. Re-running
      with the same endpoints does not duplicate the edge.
    - ``explicit_property``: ``MERGE (a)-[r:TYPE {<key>: row.rel_key}]->(b)``.
      The mapping must supply the keying property in
      ``relationship.properties``.

    All other properties are SET via ``r += row.props`` so re-runs stay
    idempotent on property changes.
    """
    if not relationships:
        return []

    rels_by_type: dict[str, list[GraphRelationship]] = {}
    for rel in relationships:
        rels_by_type.setdefault(rel.type, []).append(rel)

    ontology_rels: dict[str, RelationshipSpec] = {
        spec.type: spec for spec in ontology.relationships
    }

    statements: list[CypherStatement] = []
    for rel_type, group_rels in rels_by_type.items():
        ontology_rel = ontology_rels.get(rel_type)
        if ontology_rel is None:
            raise ValueError(f"relationship type '{rel_type}' is not declared in the ontology")
        statements.append(_render_relationship_group(rel_type, group_rels, ontology_rel))
    return statements


def _render_relationship_group(
    rel_type: str,
    group_rels: list[GraphRelationship],
    ontology_rel: RelationshipSpec,
) -> CypherStatement:
    safe_type = _safe_identifier(rel_type, kind="relationship type")
    # Endpoint identifiers are uniform across the group (cross-validated
    # in load_connector and again on the GraphRelationship model), so we
    # take them from the first relationship.
    head = group_rels[0]
    safe_from_label = _safe_identifier(head.from_label, kind="from label")
    safe_to_label = _safe_identifier(head.to_label, kind="to label")
    safe_from_key = _safe_identifier(head.from_key_property, kind="from key property")
    safe_to_key = _safe_identifier(head.to_key_property, kind="to key property")

    if ontology_rel.key.strategy == "explicit_property":
        if ontology_rel.key.property is None:  # pragma: no cover - manifest validator
            raise ValueError(
                f"relationship '{rel_type}' uses 'explicit_property' strategy "
                "but does not declare a key property"
            )
        safe_key_prop = _safe_identifier(
            ontology_rel.key.property, kind="relationship key property"
        )
        merge_clause = f"MERGE (a)-[r:{safe_type} {{{safe_key_prop}: row.rel_key}}]->(b)"
        rows = [
            {
                "from_key": rel.from_key_value,
                "to_key": rel.to_key_value,
                "rel_key": rel.properties.get(ontology_rel.key.property),
                "props": {
                    k: v for k, v in rel.properties.items() if k != ontology_rel.key.property
                },
            }
            for rel in group_rels
        ]
    else:  # endpoints_and_type
        merge_clause = f"MERGE (a)-[r:{safe_type}]->(b)"
        rows = [
            {
                "from_key": rel.from_key_value,
                "to_key": rel.to_key_value,
                "props": dict(rel.properties),
            }
            for rel in group_rels
        ]

    cypher = (
        "UNWIND $rows AS row "
        f"MATCH (a:{safe_from_label} {{{safe_from_key}: row.from_key}}) "
        f"MATCH (b:{safe_to_label} {{{safe_to_key}: row.to_key}}) "
        f"{merge_clause} "
        "SET r += row.props"
    )
    return CypherStatement(cypher=cypher, parameters={"rows": rows})


def render_constraint_statements(ontology: OntologySpec) -> list[CypherStatement]:
    """Return one ``CREATE CONSTRAINT ... IF NOT EXISTS`` per node label.

    The constraint enforces uniqueness of the ontology's declared key
    property for each node label. ``IF NOT EXISTS`` makes the call
    idempotent so :class:`GraphSink.create_constraints` is safe to run
    on every pipeline start.
    """
    statements: list[CypherStatement] = []
    for node in ontology.nodes:
        label = _safe_identifier(node.label, kind="node label")
        prop = _safe_identifier(node.key.property, kind="key property")
        constraint_name = f"graphflow_unique_{label}_{prop}"
        cypher = (
            f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        )
        statements.append(CypherStatement(cypher=cypher, parameters={}))
    return statements
