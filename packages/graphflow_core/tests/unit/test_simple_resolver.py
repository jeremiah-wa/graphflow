"""Unit tests for :class:`SimpleResolver`."""

from __future__ import annotations

import pytest

from graphflow_core.extraction import CandidateEntity
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologySpec,
    PropertySpec,
)
from graphflow_core.resolution import (
    ResolutionError,
    ResolutionResult,
    Resolver,
    SimpleResolver,
)
from graphflow_core.resolution.simple import (
    DEFAULT_AUTO_LINK_THRESHOLD,
    DEFAULT_REVIEW_THRESHOLD,
)

# ----------------------------- helpers --------------------------------------


def _ontology(*labels: str) -> OntologySpec:
    if not labels:
        labels = ("Company",)
    return OntologySpec(
        name="test_ontology",
        nodes=[
            NodeSpec(
                label=label,
                key=NodeKey(property="name"),
                properties={"name": PropertySpec(type="string", required=True)},
            )
            for label in labels
        ],
    )


def _candidate(
    surface: str,
    *,
    label: str = "Company",
    chunk_id: str = "c-0",
    chunk_index: int = 0,
    confidence: float = 1.0,
    properties: dict[str, str] | None = None,
) -> CandidateEntity:
    return CandidateEntity(
        label=label,
        surface_text=surface,
        confidence=confidence,
        properties=properties or {},
        source_chunk_id=chunk_id,
        source_name="docs",
        source_path="docs/x.txt",
        chunk_index=chunk_index,
        extractor="fast",
    )


# ----------------------------- protocol -------------------------------------


def test_simple_resolver_satisfies_resolver_protocol() -> None:
    assert isinstance(SimpleResolver(), Resolver)


# ----------------------------- thresholds -----------------------------------


def test_default_thresholds_are_exposed_as_constants() -> None:
    # Two callers should be able to assert against the defaults without
    # constructing a resolver, so the constants are part of the public
    # surface.
    assert DEFAULT_AUTO_LINK_THRESHOLD == 1.0
    assert DEFAULT_REVIEW_THRESHOLD == 0.85


def test_review_threshold_above_auto_link_is_rejected() -> None:
    with pytest.raises(ResolutionError) as excinfo:
        SimpleResolver(auto_link_threshold=0.8, review_threshold=0.9)
    assert "thresholds" in str(excinfo.value)


def test_negative_threshold_is_rejected() -> None:
    with pytest.raises(ResolutionError):
        SimpleResolver(review_threshold=-0.1)


def test_threshold_above_one_is_rejected() -> None:
    with pytest.raises(ResolutionError):
        SimpleResolver(auto_link_threshold=1.1)


# ------------------------------ empty input ---------------------------------


def test_empty_candidates_returns_empty_result() -> None:
    result = SimpleResolver().resolve([], ontology=_ontology())
    assert isinstance(result, ResolutionResult)
    assert result.entities == []
    assert result.decisions == []


# ------------------------------ no_match ------------------------------------


def test_single_candidate_becomes_one_no_match_entity() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme Ltd")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision.status == "no_match"
    assert decision.score == 0.0
    assert decision.alternatives == []
    entity = result.entities[0]
    assert entity.candidate_count == 1
    assert entity.needs_review is False
    assert entity.canonical_surface == "Acme Ltd"
    assert entity.entity_id == decision.entity_id


def test_dissimilar_candidates_each_become_their_own_entity() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme Ltd"), _candidate("Globex Industries")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 2
    assert {d.status for d in result.decisions} == {"no_match"}


# ----------------------------- exact match ----------------------------------


def test_identical_surfaces_auto_link_with_score_one() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme Ltd"), _candidate("Acme Ltd", chunk_id="c-1")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert result.entities[0].candidate_count == 2
    statuses = [d.status for d in result.decisions]
    assert statuses == ["no_match", "auto_link"]
    assert result.decisions[1].score == 1.0
    assert result.decisions[1].alternatives == []


def test_case_insensitive_match_auto_links() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme Ltd"), _candidate("ACME LTD")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert result.decisions[1].status == "auto_link"


def test_punctuation_difference_auto_links() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme, Ltd."), _candidate("Acme Ltd")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert result.decisions[1].status == "auto_link"


def test_whitespace_difference_auto_links() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme  Ltd"), _candidate("Acme Ltd")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert result.decisions[1].status == "auto_link"


def test_unicode_compatibility_auto_links() -> None:
    # Full-width "Ｓ" -> NFKC -> "S" so half-width and full-width
    # spellings of the same name should resolve to a single entity.
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("ＳAP"), _candidate("SAP")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert result.decisions[1].status == "auto_link"


# ----------------------------- review band ----------------------------------


def test_similar_surfaces_above_review_threshold_flagged_for_review() -> None:
    # "Acme Limited" vs "Acme Limmited" (typo): SequenceMatcher.ratio
    # is well above 0.85 so the second candidate sits in the review
    # range without auto-linking.
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme Limited"), _candidate("Acme Limmited")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 2, [e.entity_id for e in result.entities]
    statuses = [d.status for d in result.decisions]
    assert statuses == ["no_match", "review"]
    review_decision = result.decisions[1]
    review_entity_id = result.decisions[0].entity_id
    assert review_decision.alternatives == [review_entity_id]
    # New entity should be flagged for review.
    new_entity = next(
        e for e in result.entities if e.entity_id == review_decision.entity_id
    )
    assert new_entity.needs_review is True


def test_similar_surfaces_below_review_threshold_become_separate_entities() -> None:
    # "Acme" vs "Globex": no overlap, well below review threshold.
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme"), _candidate("Globex")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 2
    assert all(d.status == "no_match" for d in result.decisions)


def test_lowering_review_threshold_promotes_no_match_to_review() -> None:
    # "Acme" vs "Acme Ltd": SequenceMatcher.ratio is around 0.66 so
    # the default review threshold of 0.85 leaves them as no_match.
    # Lowering review_threshold to 0.5 promotes the second candidate
    # into the review range.
    default_resolver = SimpleResolver()
    default_result = default_resolver.resolve(
        [_candidate("Acme"), _candidate("Acme Ltd")],
        ontology=_ontology(),
    )
    assert [d.status for d in default_result.decisions] == ["no_match", "no_match"]

    permissive_resolver = SimpleResolver(review_threshold=0.5)
    permissive_result = permissive_resolver.resolve(
        [_candidate("Acme"), _candidate("Acme Ltd")],
        ontology=_ontology(),
    )
    assert [d.status for d in permissive_result.decisions] == ["no_match", "review"]


def test_raising_auto_link_below_one_promotes_review_to_auto_link() -> None:
    # With auto_link_threshold lowered to 0.85 (matching review), the
    # "Acme Limited" / "Acme Limmited" pair from the review test above
    # crosses into auto_link territory.
    resolver = SimpleResolver(auto_link_threshold=0.85, review_threshold=0.85)
    result = resolver.resolve(
        [_candidate("Acme Limited"), _candidate("Acme Limmited")],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert result.decisions[1].status == "auto_link"


# ------------------------- ambiguity / tie at top ---------------------------


def test_tied_top_score_is_treated_as_review_not_auto_link() -> None:
    # Two existing entities equally similar to the candidate: even
    # with auto_link_threshold lowered, a tie is genuinely ambiguous
    # so we never auto-link.
    resolver = SimpleResolver(auto_link_threshold=0.5, review_threshold=0.5)
    result = resolver.resolve(
        [_candidate("aaaa"), _candidate("bbbb"), _candidate("aabb")],
        ontology=_ontology(),
    )
    statuses = [d.status for d in result.decisions]
    # First two are independent no_matches; third is similar to both
    # equally and should be flagged for review.
    assert statuses[:2] == ["no_match", "no_match"]
    assert statuses[2] == "review"
    assert len(result.decisions[2].alternatives) >= 2


# ------------------------------ labels --------------------------------------


def test_same_surface_different_labels_become_separate_entities() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [
            _candidate("Acme", label="Company"),
            _candidate("Acme", label="Person"),
        ],
        ontology=_ontology("Company", "Person"),
    )
    assert len(result.entities) == 2
    assert {e.label for e in result.entities} == {"Company", "Person"}
    assert all(d.status == "no_match" for d in result.decisions)


def test_unknown_label_raises_resolution_error() -> None:
    resolver = SimpleResolver()
    with pytest.raises(ResolutionError) as excinfo:
        resolver.resolve(
            [_candidate("Acme", label="Vehicle")],
            ontology=_ontology("Company"),
        )
    assert "Vehicle" in str(excinfo.value)


# ----------------------- properties + provenance ----------------------------


def test_properties_merge_first_write_wins() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [
            _candidate("Acme Ltd", properties={"name": "Acme Ltd", "city": "Boston"}),
            _candidate("Acme Ltd", properties={"name": "Acme Limited", "country": "US"}),
        ],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    entity = result.entities[0]
    # First-write-wins: name stays "Acme Ltd"; new keys are added.
    assert entity.properties == {
        "name": "Acme Ltd",
        "city": "Boston",
        "country": "US",
    }


def test_canonical_surface_picks_longest_then_alphabetical() -> None:
    # All three surfaces normalise to "acme ltd" so they auto-link
    # into one entity. The canonical surface should be the longest;
    # all have length 8 so the alphabetical tiebreaker picks the
    # smallest: "ACME LTD" < "Acme Ltd" < "acme ltd".
    resolver = SimpleResolver()
    result = resolver.resolve(
        [
            _candidate("acme ltd"),
            _candidate("ACME LTD"),
            _candidate("Acme Ltd"),
        ],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert result.entities[0].canonical_surface == "ACME LTD"


def test_canonical_surface_prefers_longer_form_when_lengths_differ() -> None:
    # Auto-link only collapses identical-after-normalisation surfaces,
    # so test the merge path with three identical normalisations of
    # different lengths via punctuation: "Acme" / "Acme." / "Acme  ".
    # All normalise to "acme"; canonical should be the longest input.
    resolver = SimpleResolver()
    result = resolver.resolve(
        [
            _candidate("Acme"),
            _candidate("Acme."),
            _candidate("Acme  "),
        ],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    assert result.entities[0].canonical_surface == "Acme  "


def test_provenance_carried_from_first_contributing_candidate() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [
            _candidate("Acme Ltd", chunk_id="c-7", chunk_index=7),
            _candidate("Acme Ltd", chunk_id="c-99", chunk_index=99),
        ],
        ontology=_ontology(),
    )
    assert len(result.entities) == 1
    entity = result.entities[0]
    assert entity.source_chunk_id == "c-7"
    assert entity.chunk_index == 7


# --------------------------- determinism ------------------------------------


def test_resolution_output_is_deterministic_across_calls() -> None:
    resolver = SimpleResolver(review_threshold=0.7)
    candidates = [
        _candidate("Acme Ltd"),
        _candidate("ACME LTD"),
        _candidate("Acme Limmited"),
        _candidate("Globex"),
    ]
    first = resolver.resolve(candidates, ontology=_ontology())
    second = resolver.resolve(candidates, ontology=_ontology())
    assert first == second


def test_entities_sorted_by_label_then_entity_id() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [
            _candidate("Zebra Co", label="Company"),
            _candidate("Alice", label="Person"),
            _candidate("Acme", label="Company"),
            _candidate("Bob", label="Person"),
        ],
        ontology=_ontology("Company", "Person"),
    )
    keys = [(e.label, e.entity_id) for e in result.entities]
    assert keys == sorted(keys)


def test_decisions_preserve_input_order() -> None:
    resolver = SimpleResolver()
    candidates = [
        _candidate("Acme Ltd", chunk_id="c-0", chunk_index=0),
        _candidate("Globex", chunk_id="c-1", chunk_index=1),
        _candidate("Initech", chunk_id="c-2", chunk_index=2),
    ]
    result = resolver.resolve(candidates, ontology=_ontology())
    assert [d.candidate.source_chunk_id for d in result.decisions] == [
        "c-0",
        "c-1",
        "c-2",
    ]


def test_decision_entity_id_always_resolves_to_an_entity() -> None:
    # Every decision must point at an entity that actually exists in
    # the result, including review and no_match decisions.
    resolver = SimpleResolver(review_threshold=0.5)
    result = resolver.resolve(
        [
            _candidate("Acme Limited"),
            _candidate("Acme Limmited"),
            _candidate("Globex Industries"),
        ],
        ontology=_ontology(),
    )
    entity_ids = {e.entity_id for e in result.entities}
    for decision in result.decisions:
        assert decision.entity_id in entity_ids


# ---------------------------- entity ids ------------------------------------


def test_entity_id_is_stable_across_runs() -> None:
    resolver = SimpleResolver()
    first = resolver.resolve([_candidate("Acme Ltd")], ontology=_ontology())
    second = resolver.resolve([_candidate("Acme Ltd")], ontology=_ontology())
    assert first.entities[0].entity_id == second.entities[0].entity_id


def test_entity_id_uses_label_and_normalized_surface() -> None:
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("Acme, Ltd.")], ontology=_ontology()
    )
    assert result.entities[0].entity_id == "Company:acme_ltd"


def test_entity_id_collisions_get_unique_suffix() -> None:
    # "acme ltd" slugs to "acme_ltd"; an explicit "acme_ltd" surface
    # also slugs to "acme_ltd". They are different normalised forms
    # so they must end up as two entities, but they would collide on
    # the natural id, so the resolver appends a suffix to the second.
    resolver = SimpleResolver()
    result = resolver.resolve(
        [_candidate("acme ltd"), _candidate("acme_ltd")],
        ontology=_ontology(),
    )
    ids = sorted(e.entity_id for e in result.entities)
    assert ids[0] == "Company:acme_ltd"
    assert ids[1].startswith("Company:acme_ltd__")
