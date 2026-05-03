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

from graphflow_core.manifests.ontology import OntologySpec

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
