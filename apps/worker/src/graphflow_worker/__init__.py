"""GraphFlow worker: a thin process runner over ``graphflow_core``.

In v0.1 this is a synchronous, in-process runner. Later versions may
back this with Redis/Celery/Dramatiq, Temporal, Dagster, or a cloud job
runner without changing the public ``run_pipeline`` interface.
"""

__all__ = ["__version__", "run_pipeline"]

__version__ = "0.0.1"


def run_pipeline(pipeline_path: str) -> dict[str, str]:
    """Placeholder pipeline runner.

    Returns a stub status dict. Actual pipeline execution will be wired up
    in a later issue (see ``docs/architecture.md`` core pipeline).
    """
    return {"status": "not_implemented", "pipeline": pipeline_path}
