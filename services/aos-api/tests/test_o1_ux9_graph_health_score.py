from __future__ import annotations

from aos_api.routers.ontology import _classify_graph_properties, _graph_health_score_breakdown


def test_score_is_exactly_recomputable_from_versioned_breakdown() -> None:
    score, breakdown = _graph_health_score_breakdown(
        dangling_affected=1,
        dangling_denominator=100,
        conflict_affected=5,
        conflict_denominator=100,
        orphan_affected=2,
        orphan_denominator=100,
        rule_affected=0,
        rule_denominator=100,
    )
    assert [item["deduction"] for item in breakdown] == [40.0, 12.5, 5.0, 0.0]
    assert score == 42
    assert score == round(100 - sum(item["deduction"] for item in breakdown))


def test_canonical_optional_system_and_alias_properties_are_not_actual_conflicts() -> None:
    classified = _classify_graph_properties(
        {
            "object_type": "Order",
            "properties": [{"name": "createdAt"}],
            "props": {
                "createdAt": "2026-01-01T00:00:00Z",
                "orderNo": "O-1",
                "risk_score": 0.1,
                "createdAtSourceTimezone": "Z",
                "legacy_field": "compat",
                "unregisteredCamel": "bad",
            },
        }
    )
    assert classified["canonical"] == ["createdAt", "orderNo", "risk_score"]
    assert classified["system"] == ["createdAtSourceTimezone"]
    assert classified["compatibilityAlias"] == ["legacy_field"]
    assert classified["actualConflict"] == ["unregisteredCamel"]
