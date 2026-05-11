"""GraphFlow text-to-graph extraction.

This subpackage owns the contract between text inputs and graph
candidates: ``TextChunk`` is the input the pipeline feeds in, and
``CandidateEntity`` is the reviewable output an extractor produces
*before* graph mapping or graph loading happens. Every extractor must
implement the :class:`Extractor` protocol so the pipeline can stay
extractor-neutral (fast deterministic, accurate LLM, hybrid router,
...).

The output model intentionally records:

- The ontology ``label`` the candidate maps to (categories come from
  the ontology, not from the extractor).
- A ``confidence`` score in ``[0.0, 1.0]`` so downstream review and
  hybrid routing can act on it.
- The originating ``source_chunk_id`` plus the chunk's source name,
  path, and chunk index, so candidates can always be traced back to
  the exact text they came from.
"""

from __future__ import annotations

from graphflow_core.extraction.accurate import AccurateExtractor
from graphflow_core.extraction.base import (
    CandidateEntity,
    Extractor,
    TextChunk,
)
from graphflow_core.extraction.cache import (
    ExtractionCache,
    InMemoryExtractionCache,
    make_cache_key,
)
from graphflow_core.extraction.cost import (
    CostEntry,
    CostLimitExceeded,
    CostTracker,
)
from graphflow_core.extraction.errors import ExtractionError
from graphflow_core.extraction.fast import FastExtractor
from graphflow_core.extraction.provider import LLMError, LLMProvider, LLMResponse

__all__ = [
    "AccurateExtractor",
    "CandidateEntity",
    "CostEntry",
    "CostLimitExceeded",
    "CostTracker",
    "ExtractionCache",
    "ExtractionError",
    "Extractor",
    "FastExtractor",
    "InMemoryExtractionCache",
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "TextChunk",
    "make_cache_key",
]
