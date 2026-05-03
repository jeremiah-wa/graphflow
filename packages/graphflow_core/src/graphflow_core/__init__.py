"""GraphFlow core package.

This package owns the product/domain logic for GraphFlow: manifest models,
source and parser abstractions, the mapping engine, graph sink interfaces,
and the pipeline runner. Interface layers (CLI, API, worker, web) should be
thin wrappers around this package.
"""

__all__ = ["__version__"]

__version__ = "0.0.1"
