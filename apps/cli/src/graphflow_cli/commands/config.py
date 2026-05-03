"""``graphflow config`` subcommands.

These commands operate on connector folders containing the four
GraphFlow manifest files. The CLI must remain a thin wrapper over
``graphflow_core.manifests``.
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

config_app = typer.Typer(
    name="config",
    help="Inspect and validate GraphFlow manifest folders.",
    no_args_is_help=True,
)


@config_app.command("validate")
def validate(
    folder: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Path to a connector folder containing source.yaml, "
            "ontology.yaml, pipeline.yaml, and connections.yaml.",
        ),
    ],
) -> None:
    """Validate all manifests in a connector folder.

    Exits with status 0 if every manifest parses, validates, and is
    consistent across files. Exits with status 1 and a list of issues
    otherwise.
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

    typer.echo(f"OK: {folder}")
    typer.echo(f"  source     : {connector.source.source.name}")
    typer.echo(f"  ontology   : {connector.ontology.ontology.name}")
    typer.echo(f"  pipeline   : {connector.pipeline.pipeline.name}")
    typer.echo(f"  connections: {sorted(connector.connections.connections)}")
