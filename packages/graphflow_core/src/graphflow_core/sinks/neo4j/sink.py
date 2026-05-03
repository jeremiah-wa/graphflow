"""Neo4j-backed :class:`GraphSink` implementation.

The sink is a thin adapter: it constructs Cypher via the rendering
helpers in :mod:`graphflow_core.sinks.neo4j.cypher` and dispatches the
statements through a Neo4j driver session. It does not own any other
business logic.

Connection details come from a validated
:class:`graphflow_core.manifests.connections.ConnectionSpec` (with
``type='neo4j'``) plus the password resolved from the named
environment variable. The sink never logs the password or includes it
in error messages.
"""

from __future__ import annotations

import os
from types import TracebackType
from typing import Any, Protocol, cast

from graphflow_core.graph.objects import GraphNode, GraphRelationship
from graphflow_core.manifests.connections import ConnectionSpec
from graphflow_core.manifests.ontology import OntologySpec
from graphflow_core.sinks.base import GraphSinkError, GraphWriteResult
from graphflow_core.sinks.neo4j.cypher import (
    CypherStatement,
    render_constraint_statements,
    render_node_upsert_statements,
    render_relationship_upsert_statements,
)


class _DriverLike(Protocol):
    """Subset of the neo4j.Driver API the sink relies on.

    Declared as a Protocol so unit tests can pass a stub driver without
    importing the real one.
    """

    def session(self, **kwargs: Any) -> Any: ...

    def close(self) -> None: ...


class Neo4jGraphSink:
    """Idempotent Neo4j graph sink.

    Construct directly for testing with a stub driver, or use
    :meth:`from_connection` for the production path that resolves the
    URI, username, and password-from-env from a manifest.
    """

    def __init__(
        self,
        driver: _DriverLike,
        *,
        database: str | None = None,
    ) -> None:
        self._driver = driver
        self._database = database
        self._closed = False

    @classmethod
    def from_connection(
        cls,
        connection: ConnectionSpec,
        *,
        database: str | None = None,
        env: dict[str, str] | None = None,
    ) -> Neo4jGraphSink:
        """Construct a sink from a validated neo4j ``ConnectionSpec``.

        ``env`` defaults to ``os.environ``; tests may inject a custom
        mapping. The password is read from the environment variable
        named in ``connection.password_from_env`` and is not stored on
        the instance.
        """
        if connection.type != "neo4j":
            raise GraphSinkError(
                f"Neo4jGraphSink requires a connection of type 'neo4j', got '{connection.type}'"
            )
        if (
            connection.uri is None
            or connection.username is None
            or connection.password_from_env is None
        ):
            raise GraphSinkError(
                "neo4j connection is missing one of: uri, username, password_from_env"
            )

        env_map = env if env is not None else os.environ
        password = env_map.get(connection.password_from_env)
        if not password:
            raise GraphSinkError(
                f"environment variable '{connection.password_from_env}' is not set"
            )

        # Imported lazily so the unit tests above don't need a real Neo4j
        # driver in their import path.
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(connection.uri, auth=(connection.username, password))
        return cls(cast(_DriverLike, driver), database=database)

    # GraphSink protocol -----------------------------------------------

    def create_constraints(self, ontology: OntologySpec) -> GraphWriteResult:
        statements = render_constraint_statements(ontology)
        self._run_statements(statements)
        return GraphWriteResult(constraints_created=len(statements))

    def upsert_nodes(self, nodes: list[GraphNode]) -> GraphWriteResult:
        statements = render_node_upsert_statements(nodes)
        self._run_statements(statements)
        return GraphWriteResult(nodes_written=len(nodes))

    def upsert_relationships(self, relationships: list[GraphRelationship]) -> GraphWriteResult:
        # The renderer needs the ontology to know each relationship
        # type's MERGE strategy. The connection-level sink does not own
        # the ontology, so callers (Mapper or pipeline runner) must set
        # it explicitly via :meth:`set_ontology` before upserting
        # relationships. This avoids passing the ontology on every call
        # while keeping the protocol surface minimal.
        if self._ontology is None:
            raise GraphSinkError(
                "ontology must be configured via set_ontology() or "
                "create_constraints() before upserting relationships"
            )
        statements = render_relationship_upsert_statements(relationships, self._ontology)
        self._run_statements(statements)
        return GraphWriteResult(relationships_written=len(relationships))

    def close(self) -> None:
        if not self._closed:
            self._driver.close()
            self._closed = True

    # Helpers -----------------------------------------------------------

    _ontology: OntologySpec | None = None

    def set_ontology(self, ontology: OntologySpec) -> None:
        """Cache the ontology for subsequent relationship upserts."""
        self._ontology = ontology

    def _run_statements(self, statements: list[CypherStatement]) -> None:
        if not statements:
            return
        kwargs: dict[str, Any] = {}
        if self._database is not None:
            kwargs["database"] = self._database
        with self._driver.session(**kwargs) as session:
            for statement in statements:
                session.run(statement.cypher, **statement.parameters)

    # Context manager support so callers can use ``with Neo4jGraphSink(...) as sink:``
    def __enter__(self) -> Neo4jGraphSink:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
