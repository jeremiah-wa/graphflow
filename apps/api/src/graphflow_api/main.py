"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

import graphflow_core
from graphflow_api import __version__ as api_version

app = FastAPI(
    title="GraphFlow API",
    version=api_version,
    description="HTTP API for GraphFlow. Thin wrapper over graphflow_core.",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    """Report the installed API and core versions."""
    return {
        "api": api_version,
        "core": graphflow_core.__version__,
    }
