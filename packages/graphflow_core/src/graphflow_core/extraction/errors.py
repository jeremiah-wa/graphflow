"""Errors raised by text-to-graph extractors."""

from __future__ import annotations


class ExtractionError(Exception):
    """Raised when an extractor cannot complete an extraction request.

    Concrete extractor implementations should raise this for failures
    that are specific to extraction (e.g. malformed chunk, unsupported
    ontology label, provider error in an LLM extractor) so callers can
    distinguish extraction problems from upstream source-read or
    downstream mapping problems.
    """
