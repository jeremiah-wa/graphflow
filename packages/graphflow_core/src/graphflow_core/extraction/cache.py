"""Caching for LLM-based extraction.

The accurate extractor caches per-chunk results by a content-derived
key so a re-run with the same chunks, ontology, and extractor config
makes zero provider calls. The cache abstraction is small on purpose:
implementations only need ``get`` and ``set``. An in-memory default
ships here; persistent caches (filesystem, Redis, ...) plug in via the
same protocol.

Cache keys are SHA-256 hex digests over a stable JSON serialisation of:

- ``chunk.chunk_id`` and ``chunk.text`` (so editing the text invalidates),
- ``ontology.model_dump()`` (so editing the ontology invalidates),
- the extractor's config fingerprint (model, prompt version, ...).

Anything that changes the candidate set must contribute to the key.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from graphflow_core.extraction.base import CandidateEntity, TextChunk
from graphflow_core.manifests.ontology import OntologySpec


@runtime_checkable
class ExtractionCache(Protocol):
    """Structural protocol for an extraction-result cache.

    Implementations must be safe to call with the same key repeatedly
    and must return ``None`` for unknown keys (rather than raising) so
    the extractor can treat lookups as "may or may not be there".
    """

    def get(self, key: str) -> list[CandidateEntity] | None:
        """Return cached candidates for ``key`` or ``None`` if absent."""
        ...

    def set(self, key: str, candidates: list[CandidateEntity]) -> None:
        """Store ``candidates`` under ``key``."""
        ...


class InMemoryExtractionCache:
    """Process-local cache. Useful for tests and single-run pipelines."""

    def __init__(self) -> None:
        self._store: dict[str, list[CandidateEntity]] = {}

    def get(self, key: str) -> list[CandidateEntity] | None:
        cached = self._store.get(key)
        if cached is None:
            return None
        # Return a fresh list so callers cannot mutate the cache by
        # extending the returned list.
        return list(cached)

    def set(self, key: str, candidates: list[CandidateEntity]) -> None:
        self._store[key] = list(candidates)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._store)


def make_cache_key(
    *,
    chunk: TextChunk,
    ontology: OntologySpec,
    config_fingerprint: Mapping[str, object],
) -> str:
    """Return a deterministic hex digest for a (chunk, ontology, config) triple.

    The digest is stable across processes: it depends only on field
    values, not on object identity or insertion order. ``sort_keys=True``
    makes the JSON canonical so two semantically identical inputs
    always produce the same digest.

    Args:
        chunk: The chunk being extracted from.
        ontology: The active ontology. The full ``model_dump()`` is
            included so any change to labels, properties, keys, or
            relationships invalidates the cache.
        config_fingerprint: Anything else that changes the output:
            model name, prompt version, temperature, etc. The accurate
            extractor builds this dict from its own configuration.
    """
    payload = {
        "chunk_id": chunk.chunk_id,
        "chunk_text": chunk.text,
        "ontology": ontology.model_dump(mode="json"),
        "config": dict(config_fingerprint),
    }
    serialised = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()
