"""GraphFlow CLI entry point."""

from __future__ import annotations

import typer

import graphflow_core

from graphflow_cli import __version__ as cli_version

app = typer.Typer(
    name="graphflow",
    help="GraphFlow: turn files, APIs, and documents into knowledge graphs.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed GraphFlow CLI and core versions."""
    typer.echo(f"graphflow-cli {cli_version}")
    typer.echo(f"graphflow-core {graphflow_core.__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
