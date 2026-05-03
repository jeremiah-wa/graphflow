"""``graphflow ingest`` subcommand.

Reads the source defined by a connector folder and prints a small
summary of parsed records. This is intentionally a thin wrapper over
``graphflow_core.manifests.load_connector`` and
``graphflow_core.sources.open_source``.
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
from graphflow_core.sources import SourceReadError, open_source


def ingest(
    folder: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Path to a connector folder containing the four manifests.",
        ),
    ],
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            min=0,
            help="Maximum number of records to display (0 means show count only).",
        ),
    ] = 5,
) -> None:
    """Parse the source declared by a connector folder and print a summary."""
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

    try:
        reader = open_source(connector.source.source, base_dir=folder)
        records = list(reader.read())
    except SourceReadError as exc:
        typer.echo(f"Could not read source: {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Source: {connector.source.source.name}")
    typer.echo(f"Format: {connector.source.source.format}")
    typer.echo(f"Records: {len(records)}")
    for record in records[:limit]:
        typer.echo(f"  {record.location}: {record.data}")
