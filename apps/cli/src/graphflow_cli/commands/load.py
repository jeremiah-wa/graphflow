"""``graphflow load`` subcommand.

Runs the full v0.1 pipeline against a connector folder:

```
parse source -> Mapper -> Neo4jGraphSink (constraints + nodes + relationships)
```

Errors at any stage cause a non-zero exit. By default the command
refuses to write to Neo4j when mapping reports any error-severity
issues; pass ``--force`` to write whatever was successfully mapped.
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
from graphflow_core.mapping import Mapper
from graphflow_core.sinks import GraphSinkError, Neo4jGraphSink
from graphflow_core.sources import SourceReadError, open_source


def load_command(
    folder: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Path to a connector folder to load into Neo4j.",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force/--no-force",
            help=(
                "Write to Neo4j even if mapping reports errors. By default the "
                "command aborts before writing when error-severity issues are "
                "present."
            ),
        ),
    ] = False,
) -> None:
    """Parse, map, and load a connector folder into Neo4j."""
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
            f"Destination type '{destination.type}' is not supported by load; "
            "v0.1 supports 'neo4j'.",
            err=True,
        )
        raise typer.Exit(code=1) from None

    try:
        reader = open_source(connector.source.source, base_dir=folder)
        records = list(reader.read())
    except SourceReadError as exc:
        typer.echo(f"Could not read source: {exc}", err=True)
        raise typer.Exit(code=1) from None

    mapping_result = Mapper(connector).map(records)
    typer.echo(f"Records read: {len(records)}")
    typer.echo(f"Nodes mapped: {len(mapping_result.nodes)}")
    typer.echo(f"Relationships mapped: {len(mapping_result.relationships)}")
    error_count = sum(1 for i in mapping_result.issues if i.severity == "error")
    warning_count = sum(1 for i in mapping_result.issues if i.severity == "warning")
    typer.echo(f"Mapping issues: {error_count} error(s), {warning_count} warning(s)")

    if mapping_result.has_errors() and not force:
        typer.echo(
            "Refusing to write to Neo4j because mapping reported errors. Pass --force to override.",
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
        with sink:
            sink.set_ontology(connector.ontology.ontology)
            constraints = sink.create_constraints(connector.ontology.ontology)
            nodes = sink.upsert_nodes(mapping_result.nodes)
            rels = sink.upsert_relationships(mapping_result.relationships)
    except Exception as exc:  # noqa: BLE001 - report any driver error verbatim
        typer.echo(f"Neo4j load failed: {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(
        "Loaded into Neo4j: "
        f"{constraints.constraints_created} constraint(s), "
        f"{nodes.nodes_written} node(s), "
        f"{rels.relationships_written} relationship(s)"
    )
