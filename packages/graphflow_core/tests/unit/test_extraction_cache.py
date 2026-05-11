"""Unit tests for the extraction cache and cache-key helper."""

from __future__ import annotations

from graphflow_core.extraction import (
    CandidateEntity,
    ExtractionCache,
    InMemoryExtractionCache,
    TextChunk,
    make_cache_key,
)
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)


def _ontology(label: str = "Company") -> OntologySpec:
    return OntologySpec(
        name="ontology",
        nodes=[
            NodeSpec(
                label=label,
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            )
        ],
    )


def _chunk(chunk_id: str = "c-0", text: str = "Acme Ltd is a company.") -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        text=text,
        source_name="src",
        source_path="docs/x.txt",
        chunk_index=0,
        location="chunk 0",
    )


def _candidate(label: str = "Company") -> CandidateEntity:
    return CandidateEntity(
        label=label,
        surface_text="Acme Ltd",
        confidence=0.9,
        source_chunk_id="c-0",
        source_name="src",
        source_path="docs/x.txt",
        chunk_index=0,
        extractor="accurate",
    )


def test_in_memory_cache_satisfies_protocol() -> None:
    assert isinstance(InMemoryExtractionCache(), ExtractionCache)


def test_get_missing_returns_none() -> None:
    cache = InMemoryExtractionCache()
    assert cache.get("missing") is None


def test_set_then_get_returns_stored_candidates() -> None:
    cache = InMemoryExtractionCache()
    cache.set("k", [_candidate()])
    got = cache.get("k")
    assert got is not None
    assert len(got) == 1
    assert got[0].label == "Company"


def test_get_returns_a_fresh_list_so_callers_cant_mutate_cache() -> None:
    cache = InMemoryExtractionCache()
    cache.set("k", [_candidate()])
    got = cache.get("k")
    assert got is not None
    got.append(_candidate(label="Other"))
    refetched = cache.get("k")
    assert refetched is not None
    assert len(refetched) == 1


def test_cache_key_is_deterministic_for_identical_inputs() -> None:
    chunk = _chunk()
    ontology = _ontology()
    fp = {"model": "m", "prompt_version": "1"}
    a = make_cache_key(chunk=chunk, ontology=ontology, config_fingerprint=fp)
    b = make_cache_key(chunk=chunk, ontology=ontology, config_fingerprint=fp)
    assert a == b


def test_cache_key_changes_with_chunk_text() -> None:
    ontology = _ontology()
    fp = {"model": "m"}
    a = make_cache_key(chunk=_chunk(text="foo"), ontology=ontology, config_fingerprint=fp)
    b = make_cache_key(chunk=_chunk(text="bar"), ontology=ontology, config_fingerprint=fp)
    assert a != b


def test_cache_key_changes_with_chunk_id() -> None:
    ontology = _ontology()
    fp = {"model": "m"}
    a = make_cache_key(chunk=_chunk(chunk_id="a"), ontology=ontology, config_fingerprint=fp)
    b = make_cache_key(chunk=_chunk(chunk_id="b"), ontology=ontology, config_fingerprint=fp)
    assert a != b


def test_cache_key_changes_with_ontology() -> None:
    chunk = _chunk()
    fp = {"model": "m"}
    a = make_cache_key(chunk=chunk, ontology=_ontology("Company"), config_fingerprint=fp)
    b = make_cache_key(chunk=chunk, ontology=_ontology("Person"), config_fingerprint=fp)
    assert a != b


def test_cache_key_changes_with_config_fingerprint() -> None:
    chunk = _chunk()
    ontology = _ontology()
    a = make_cache_key(chunk=chunk, ontology=ontology, config_fingerprint={"model": "m1"})
    b = make_cache_key(chunk=chunk, ontology=ontology, config_fingerprint={"model": "m2"})
    assert a != b


def test_cache_key_is_insensitive_to_fingerprint_dict_order() -> None:
    chunk = _chunk()
    ontology = _ontology()
    a = make_cache_key(
        chunk=chunk,
        ontology=ontology,
        config_fingerprint={"model": "m", "prompt": "p"},
    )
    b = make_cache_key(
        chunk=chunk,
        ontology=ontology,
        config_fingerprint={"prompt": "p", "model": "m"},
    )
    assert a == b
