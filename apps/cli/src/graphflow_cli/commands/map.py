"""``graphflow map`` subcommand.

Loads a connector folder, parses the source, runs the mapping engine,
and prints a summary of produced graph objects plus any issues. Like
``graphflow ingest``, this command is a thin wrapper over
``graphflow_core``.
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
from graphflow_core.sources import SourceReadError, open_source


def map_command(
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
    show_issues: Annotated[
        bool,
        typer.Option(
            "--show-issues/--no-show-issues",
            help="Print each mapping issue, not just the totals.",
        ),
    ] = True,
) -> None:
    """Run the structured mapping engine and print a summary."""
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

    mapper = Mapper(connector)
    result = mapper.map(records)

    typer.echo(f"Source: {connector.source.source.name}")
    typer.echo(f"Records read: {len(records)}")
    typer.echo(f"Nodes produced: {len(result.nodes)}")
    typer.echo(f"Relationships produced: {len(result.relationships)}")

    error_count = sum(1 for i in result.issues if i.severity == "error")
    warning_count = sum(1 for i in result.issues if i.severity == "warning")
    typer.echo(f"Issues: {error_count} error(s), {warning_count} warning(s)")

    if show_issues and result.issues:
        for mapping_issue in result.issues:
            typer.echo(
                f"  [{mapping_issue.severity}] {mapping_issue.target} "
                f"@ {mapping_issue.location}: {mapping_issue.message}"
            )

    if result.has_errors():
        raise typer.Exit(code=1)
