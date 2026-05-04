"""Errors raised by entity resolvers."""

from __future__ import annotations


class ResolutionError(Exception):
    """Raised when a resolver cannot complete a resolution request.

    Concrete resolver implementations should raise this for failures
    that are specific to resolution (e.g. a candidate carries a label
    that does not exist in the active ontology, configured thresholds
    are inconsistent) so callers can distinguish resolution problems
    from upstream extraction or downstream mapping problems.
    """
