"""``graphflow graph`` subcommands.

These commands operate on the destination graph database declared in a
connector folder's ``connections.yaml``. They are thin wrappers over
``graphflow_core.sinks``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from graphflow_core.manifests import (
    ManifestError,
    ManifestValidationError,
    load_connector,
)
from graphflow_core.sinks import GraphSinkError, Neo4jGraphSink

graph_app = typer.Typer(
    name="graph",
    help="Inspect and connect to the destination graph database.",
    no_args_is_help=True,
)


@graph_app.command("ping")
def ping(
    folder: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Path to a connector folder with a Neo4j destination connection.",
        ),
    ],
) -> None:
    """Open a Neo4j connection using the connector's destination spec.

    Reports success when the driver can verify connectivity, or
    explains why it could not. The password is sourced from the env
    var named in ``connections.yaml`` and is never printed.
    """
    try:
        connector = load_connector(folder)
    except ManifestValidationError as exc:
        typer.echo(f"Invalid manifests in {folder}:", err=True)
        for issue in exc.issues:
            typer.echo(f"  - {issue}", err=True)
        raise typer.Exit(code=1) from None
    except ManifestError as exc:
        typer.echo(f"Could not load manifests: {exc}", err=True)
        raise typer.Exit(code=1) from None

    destination = connector.pipeline.pipeline.destination
    if destination.type != "neo4j":
        typer.echo(
            f"Destination type '{destination.type}' is not supported by ping; "
            "v0.1 supports 'neo4j'.",
            err=True,
        )
        raise typer.Exit(code=1) from None

    connection = connector.connections.connections[destination.connection_ref]
    try:
        sink = Neo4jGraphSink.from_connection(connection)
    except GraphSinkError as exc:
        typer.echo(f"Could not configure Neo4j sink: {exc}", err=True)
        raise typer.Exit(code=1) from None

    try:
        # The driver verifies connectivity lazily; force it by opening a
        # session and running a trivial query.
        with sink:
            sink.create_constraints(connector.ontology.ontology)
    except Exception as exc:  # noqa: BLE001 - report any driver error verbatim
        typer.echo(f"Neo4j ping failed: {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"OK: connected to {connection.uri} as {connection.username}")
