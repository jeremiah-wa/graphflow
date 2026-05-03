"""Unit tests for duplicate-node-key and orphan-relationship detection."""

from __future__ import annotations

from typing import Any

from graphflow_core.graph.objects import GraphNode, GraphRelationship
from graphflow_core.mapping import (
    detect_duplicate_node_keys,
    detect_orphan_relationships,
)


def _node(**overrides: Any) -> GraphNode:
    base: dict[str, Any] = {
        "label": "Company",
        "key_property": "company_number",
        "key_value": "1",
        "properties": {"company_number": "1", "name": "Foo"},
    }
    base.update(overrides)
    return GraphNode.model_validate(base)


def _rel(**overrides: Any) -> GraphRelationship:
    base: dict[str, Any] = {
        "type": "OFFICER_OF",
        "from_label": "Person",
        "from_key_property": "person_id",
        "from_key_value": "P-1",
        "to_label": "Company",
        "to_key_property": "company_number",
        "to_key_value": "1",
        "properties": {},
    }
    base.update(overrides)
    return GraphRelationship.model_validate(base)


def test_dedup_keeps_first_when_properties_match() -> None:
    a = _node()
    b = _node()
    deduped, issues = detect_duplicate_node_keys([a, b])
    assert len(deduped) == 1
    assert deduped[0] is a
    assert issues == []


def test_dedup_reports_conflict_when_properties_differ() -> None:
    a = _node()
    b = _node(properties={"company_number": "1", "name": "Bar"})
    deduped, issues = detect_duplicate_node_keys([a, b])
    assert len(deduped) == 1
    assert deduped[0] is a
    assert any(i.severity == "error" and "duplicate" in i.message for i in issues)


def test_orphan_relationship_detected_when_endpoint_missing() -> None:
    nodes = [_node(label="Person", key_property="person_id", key_value="P-1")]
    rels = [_rel()]  # to-Company endpoint not in nodes
    issues = detect_orphan_relationships(nodes, rels)
    assert any("unknown to" in i.message for i in issues)


def test_no_orphan_when_both_endpoints_known() -> None:
    nodes = [
        _node(label="Person", key_property="person_id", key_value="P-1"),
        _node(label="Company", key_property="company_number", key_value="1"),
    ]
    issues = detect_orphan_relationships(nodes, [_rel()])
    assert issues == []
