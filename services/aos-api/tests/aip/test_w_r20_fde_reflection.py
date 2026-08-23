from __future__ import annotations

from aos_api.aip_fde_reflection import (
    REFLECTION_RULES,
    RULE_SET_HASH,
    ReflectionKind,
    evaluate_reflection,
)


def test_reflection_registry_has_exact_versioned_26_rule_distribution() -> None:
    assert len(REFLECTION_RULES) == 26
    assert len({rule.rule_key for rule in REFLECTION_RULES}) == 26
    assert sum(rule.kind is ReflectionKind.HARD for rule in REFLECTION_RULES) == 21
    assert sum(rule.kind is ReflectionKind.SOFT for rule in REFLECTION_RULES) == 5
    assert len(RULE_SET_HASH) == 64
    assert any(rule.rule_key == "s4.required_target_fields_check" for rule in REFLECTION_RULES)


def test_hard_rules_fail_closed_and_soft_rules_require_exact_approval() -> None:
    missing = evaluate_reflection("fde.s4.mapping-proposal", {})
    approved = evaluate_reflection(
        "fde.s4.mapping-proposal",
        {
            "coverage": 1.0,
            "requiredTargetsPresent": True,
            "mappingConflicts": [],
            "unsupportedTypes": [],
            "expressionExecution": False,
            "softApprovals": {
                "s4.confidence_review": True,
                "s4.episodic_difference_review": True,
            },
        },
    )

    assert {row["status"] for row in missing if row["kind"] == "hard"} == {"failed"}
    assert {row["status"] for row in missing if row["kind"] == "soft"} == {"external_required"}
    assert {row["status"] for row in approved} == {"passed"}


def test_registry_uses_only_declared_predicates_without_executable_conditions() -> None:
    for rule in REFLECTION_RULES:
        assert "(" not in rule.predicate
        assert ")" not in rule.predicate
        assert " " not in rule.predicate
