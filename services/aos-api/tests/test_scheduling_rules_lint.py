"""Scheduling Rules & Lint Engine 单元测试。

覆盖三个引擎：SchedulingSmartFunctionsEngine、SchedulingValidationEngine、OkfLintEngine。
"""
from __future__ import annotations

import pytest

from aos_api.scheduling_rules_lint import (
    OkfLintEngine,
    SchedulingRulesLintError,
    SchedulingSmartFunctionsEngine,
    SchedulingValidationEngine,
    _MAX_ENTRIES,
)


# --------------------------------------------------------------------------- #
# SchedulingSmartFunctionsEngine 测试
# --------------------------------------------------------------------------- #
class TestSchedulingSmartFunctionsEngine:
    def setup_method(self) -> None:
        self.engine = SchedulingSmartFunctionsEngine()

    def test_singleton_instance(self) -> None:
        from aos_api.scheduling_rules_lint import get_smart_func_engine

        eng1 = get_smart_func_engine()
        eng2 = get_smart_func_engine()
        assert eng1 is eng2

    def test_create_function_success(self) -> None:
        func = self.engine.create_function(
            name="test-suggest",
            function_type="suggestion",
            description="test description",
        )
        assert func.function_id.startswith("sf-")
        assert func.name == "test-suggest"
        assert func.function_type == "suggestion"
        assert func.description == "test description"
        assert func.enabled is True

    def test_create_function_missing_name(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.create_function(name="", function_type="suggestion")
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_function_invalid_type(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.create_function(name="test", function_type="invalid_type")
        assert exc_info.value.code == "INVALID_FUNCTION_TYPE"

    def test_get_function_success(self) -> None:
        func = self.engine.create_function(name="test", function_type="search")
        retrieved = self.engine.get_function(func.function_id)
        assert retrieved.function_id == func.function_id
        assert retrieved.name == "test"

    def test_get_function_not_found(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.get_function("sf-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_functions(self) -> None:
        self.engine.create_function(name="f1", function_type="suggestion")
        self.engine.create_function(name="f2", function_type="search")
        self.engine.create_function(name="f3", function_type="filter")
        assert len(self.engine.list_functions()) == 3

    def test_list_functions_by_type(self) -> None:
        self.engine.create_function(name="f1", function_type="suggestion")
        self.engine.create_function(name="f2", function_type="search")
        self.engine.create_function(name="f3", function_type="suggestion")
        suggestions = self.engine.list_functions(function_type="suggestion")
        assert len(suggestions) == 2
        assert all(f.function_type == "suggestion" for f in suggestions)

    def test_list_functions_by_enabled(self) -> None:
        self.engine.create_function(name="f1", function_type="suggestion", enabled=True)
        self.engine.create_function(name="f2", function_type="search", enabled=False)
        self.engine.create_function(name="f3", function_type="filter", enabled=True)
        enabled = self.engine.list_functions(enabled=True)
        assert len(enabled) == 2
        assert all(f.enabled is True for f in enabled)
        disabled = self.engine.list_functions(enabled=False)
        assert len(disabled) == 1
        assert all(f.enabled is False for f in disabled)

    def test_update_function_success(self) -> None:
        func = self.engine.create_function(name="original", function_type="suggestion")
        updated = self.engine.update_function(
            func.function_id,
            name="updated",
            description="new desc",
            enabled=False,
        )
        assert updated.name == "updated"
        assert updated.description == "new desc"
        assert updated.enabled is False

    def test_update_function_not_found(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.update_function("sf-nonexistent", name="updated")
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_function_success(self) -> None:
        func = self.engine.create_function(name="to-delete", function_type="search")
        assert self.engine.delete_function(func.function_id) is True
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.get_function(func.function_id)
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_function_not_found(self) -> None:
        assert self.engine.delete_function("sf-nonexistent") is False

    def test_suggest(self) -> None:
        func = self.engine.create_function(name="suggest-func", function_type="suggestion")
        result = self.engine.suggest(entity_id="entity-1", function_id=func.function_id)
        assert result.function_id == func.function_id
        assert result.entity_id == "entity-1"
        assert isinstance(result.score, float)
        assert -1.0 <= result.score <= 1.0

    def test_search(self) -> None:
        self.engine.create_function(name="Order Search", function_type="search")
        self.engine.create_function(name="User Filter", function_type="filter")
        self.engine.create_function(name="Search Orders", function_type="search", enabled=False)
        results = self.engine.search(entity_id="entity-1", query="search")
        assert len(results) == 1
        assert results[0].score == 0.8

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_ENTRIES + 5):
            self.engine.create_function(name=f"func-{i}", function_type="suggestion")
        assert len(self.engine.list_functions()) == _MAX_ENTRIES


# --------------------------------------------------------------------------- #
# SchedulingValidationEngine 测试
# --------------------------------------------------------------------------- #
class TestSchedulingValidationEngine:
    def setup_method(self) -> None:
        self.engine = SchedulingValidationEngine()

    def test_singleton_instance(self) -> None:
        from aos_api.scheduling_rules_lint import get_validation_engine

        eng1 = get_validation_engine()
        eng2 = get_validation_engine()
        assert eng1 is eng2

    def test_create_rule_success(self) -> None:
        rule = self.engine.create_rule(
            name="test-rule",
            rule_type="hard",
            constraint_expression="x > 0",
            description="test rule",
            severity="critical",
        )
        assert rule.rule_id.startswith("vr-")
        assert rule.name == "test-rule"
        assert rule.rule_type == "hard"
        assert rule.constraint_expression == "x > 0"
        assert rule.severity == "critical"

    def test_create_rule_missing_name(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.create_rule(
                name="",
                rule_type="hard",
                constraint_expression="x > 0",
            )
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_rule_invalid_type(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.create_rule(
                name="test",
                rule_type="invalid",
                constraint_expression="x > 0",
            )
        assert exc_info.value.code == "INVALID_RULE_TYPE"

    def test_create_rule_invalid_severity(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.create_rule(
                name="test",
                rule_type="hard",
                constraint_expression="x > 0",
                severity="invalid",
            )
        assert exc_info.value.code == "INVALID_SEVERITY"

    def test_get_rule_success(self) -> None:
        rule = self.engine.create_rule(
            name="test",
            rule_type="soft",
            constraint_expression="x > 0",
        )
        retrieved = self.engine.get_rule(rule.rule_id)
        assert retrieved.rule_id == rule.rule_id
        assert retrieved.name == "test"

    def test_get_rule_not_found(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.get_rule("vr-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_rules(self) -> None:
        self.engine.create_rule(name="r1", rule_type="hard", constraint_expression="x > 0")
        self.engine.create_rule(name="r2", rule_type="soft", constraint_expression="y > 0")
        self.engine.create_rule(name="r3", rule_type="hard", constraint_expression="z > 0")
        assert len(self.engine.list_rules()) == 3

    def test_list_rules_by_type(self) -> None:
        self.engine.create_rule(name="r1", rule_type="hard", constraint_expression="x > 0")
        self.engine.create_rule(name="r2", rule_type="soft", constraint_expression="y > 0")
        self.engine.create_rule(name="r3", rule_type="hard", constraint_expression="z > 0")
        hard_rules = self.engine.list_rules(rule_type="hard")
        assert len(hard_rules) == 2
        assert all(r.rule_type == "hard" for r in hard_rules)

    def test_list_rules_by_severity(self) -> None:
        self.engine.create_rule(
            name="r1",
            rule_type="hard",
            constraint_expression="x > 0",
            severity="critical",
        )
        self.engine.create_rule(
            name="r2",
            rule_type="soft",
            constraint_expression="y > 0",
            severity="warning",
        )
        self.engine.create_rule(
            name="r3",
            rule_type="hard",
            constraint_expression="z > 0",
            severity="critical",
        )
        critical = self.engine.list_rules(severity="critical")
        assert len(critical) == 2
        assert all(r.severity == "critical" for r in critical)

    def test_update_rule_success(self) -> None:
        rule = self.engine.create_rule(
            name="original",
            rule_type="hard",
            constraint_expression="x > 0",
        )
        updated = self.engine.update_rule(
            rule.rule_id,
            name="updated",
            description="new desc",
            severity="info",
            enabled=False,
        )
        assert updated.name == "updated"
        assert updated.description == "new desc"
        assert updated.severity == "info"
        assert updated.enabled is False

    def test_update_rule_not_found(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.update_rule("vr-nonexistent", name="updated")
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_rule_success(self) -> None:
        rule = self.engine.create_rule(
            name="to-delete",
            rule_type="soft",
            constraint_expression="x > 0",
        )
        assert self.engine.delete_rule(rule.rule_id) is True
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.get_rule(rule.rule_id)
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_rule_not_found(self) -> None:
        assert self.engine.delete_rule("vr-nonexistent") is False

    def test_validate(self) -> None:
        rule = self.engine.create_rule(
            name="test-validate",
            rule_type="hard",
            constraint_expression="x > 0",
            severity="critical",
        )
        result = self.engine.validate(entity_id="entity-1", rule_id=rule.rule_id)
        assert result.rule_id == rule.rule_id
        assert result.entity_id == "entity-1"
        assert result.severity == "critical"
        assert isinstance(result.passed, bool)

    def test_validate_not_found(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.validate(entity_id="entity-1", rule_id="vr-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_validate_all(self) -> None:
        self.engine.create_rule(
            name="r1",
            rule_type="hard",
            constraint_expression="x > 0",
            enabled=True,
        )
        self.engine.create_rule(
            name="r2",
            rule_type="soft",
            constraint_expression="y > 0",
            enabled=True,
        )
        self.engine.create_rule(
            name="r3",
            rule_type="hard",
            constraint_expression="z > 0",
            enabled=False,
        )
        results = self.engine.validate_all(entity_id="entity-1")
        assert len(results) == 2

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_ENTRIES + 5):
            self.engine.create_rule(
                name=f"rule-{i}",
                rule_type="hard",
                constraint_expression="x > 0",
            )
        assert len(self.engine.list_rules()) == _MAX_ENTRIES


# --------------------------------------------------------------------------- #
# OkfLintEngine 测试
# --------------------------------------------------------------------------- #
class TestOkfLintEngine:
    def setup_method(self) -> None:
        self.engine = OkfLintEngine()

    def test_singleton_instance(self) -> None:
        from aos_api.scheduling_rules_lint import get_okf_lint_engine

        eng1 = get_okf_lint_engine()
        eng2 = get_okf_lint_engine()
        assert eng1 is eng2

    def test_create_rule_success(self) -> None:
        rule = self.engine.create_rule(
            name="test-lint",
            rule_type="column_drift",
            severity="warning",
        )
        assert rule.rule_id.startswith("ol-")
        assert rule.name == "test-lint"
        assert rule.rule_type == "column_drift"
        assert rule.severity == "warning"

    def test_create_rule_missing_name(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.create_rule(name="", rule_type="column_drift")
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_rule_invalid_type(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.create_rule(name="test", rule_type="invalid_type")
        assert exc_info.value.code == "INVALID_RULE_TYPE"

    def test_create_rule_invalid_severity(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.create_rule(
                name="test",
                rule_type="column_drift",
                severity="invalid",
            )
        assert exc_info.value.code == "INVALID_SEVERITY"

    def test_get_rule_success(self) -> None:
        rule = self.engine.create_rule(name="test", rule_type="data_quality")
        retrieved = self.engine.get_rule(rule.rule_id)
        assert retrieved.rule_id == rule.rule_id
        assert retrieved.name == "test"

    def test_get_rule_not_found(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.get_rule("ol-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_rules(self) -> None:
        self.engine.create_rule(name="r1", rule_type="column_drift")
        self.engine.create_rule(name="r2", rule_type="data_quality")
        self.engine.create_rule(name="r3", rule_type="contract_violation")
        assert len(self.engine.list_rules()) == 3

    def test_list_rules_by_type(self) -> None:
        self.engine.create_rule(name="r1", rule_type="column_drift")
        self.engine.create_rule(name="r2", rule_type="data_quality")
        self.engine.create_rule(name="r3", rule_type="column_drift")
        drift_rules = self.engine.list_rules(rule_type="column_drift")
        assert len(drift_rules) == 2
        assert all(r.rule_type == "column_drift" for r in drift_rules)

    def test_list_rules_by_severity(self) -> None:
        self.engine.create_rule(
            name="r1",
            rule_type="column_drift",
            severity="critical",
        )
        self.engine.create_rule(
            name="r2",
            rule_type="data_quality",
            severity="warning",
        )
        self.engine.create_rule(
            name="r3",
            rule_type="contract_violation",
            severity="critical",
        )
        critical = self.engine.list_rules(severity="critical")
        assert len(critical) == 2
        assert all(r.severity == "critical" for r in critical)

    def test_update_rule_success(self) -> None:
        rule = self.engine.create_rule(name="original", rule_type="column_drift")
        updated = self.engine.update_rule(
            rule.rule_id,
            name="updated",
            severity="info",
            enabled=False,
        )
        assert updated.name == "updated"
        assert updated.severity == "info"
        assert updated.enabled is False

    def test_update_rule_not_found(self) -> None:
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.update_rule("ol-nonexistent", name="updated")
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_rule_success(self) -> None:
        rule = self.engine.create_rule(name="to-delete", rule_type="data_quality")
        assert self.engine.delete_rule(rule.rule_id) is True
        with pytest.raises(SchedulingRulesLintError) as exc_info:
            self.engine.get_rule(rule.rule_id)
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_rule_not_found(self) -> None:
        assert self.engine.delete_rule("ol-nonexistent") is False

    def test_lint(self) -> None:
        self.engine.create_rule(name="r1", rule_type="column_drift", enabled=True)
        self.engine.create_rule(name="r2", rule_type="data_quality", enabled=True)
        self.engine.create_rule(name="r3", rule_type="schema_change", enabled=False)
        results = self.engine.lint(dataset_rid="ds-1")
        assert len(results) == 2
        for r in results:
            assert r.dataset_rid == "ds-1"
            assert isinstance(r.passed, bool)

    def test_lint_not_found(self) -> None:
        results = self.engine.lint(dataset_rid="ds-nonexistent")
        assert len(results) == 0

    def test_get_drift_report(self) -> None:
        self.engine.create_rule(name="drift1", rule_type="column_drift", enabled=True)
        self.engine.create_rule(name="drift2", rule_type="column_drift", enabled=True)
        self.engine.create_rule(name="quality", rule_type="data_quality", enabled=True)
        report = self.engine.get_drift_report(dataset_rid="ds-1")
        assert report["dataset_rid"] == "ds-1"
        assert report["total_drift_rules"] == 2
        assert "overall_drift_score" in report
        assert "generated_at" in report

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_ENTRIES + 5):
            self.engine.create_rule(name=f"rule-{i}", rule_type="column_drift")
        assert len(self.engine.list_rules()) == _MAX_ENTRIES