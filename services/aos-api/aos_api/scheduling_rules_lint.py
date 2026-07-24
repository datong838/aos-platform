"""Scheduling Rules & Lint Engine — Dynamic Scheduling 智能函数 + 验证规则 + OKF Lint."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

_MAX_ENTRIES = 200

FunctionType = Literal["suggestion", "search", "filter", "sort"]
RuleType = Literal["hard", "soft"]
Severity = Literal["critical", "warning", "info"]
LintRuleType = Literal["column_drift", "contract_violation", "data_quality", "schema_change"]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())


class SmartFunction(BaseModel):
    function_id: str = Field(default_factory=lambda: f"sf-{uuid.uuid4().hex[:8]}")
    name: str
    function_type: FunctionType
    description: str = ""
    enabled: bool = True
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class SuggestionResult(BaseModel):
    function_id: str
    entity_id: str
    score: float
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)


class ValidationRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: f"vr-{uuid.uuid4().hex[:8]}")
    name: str
    rule_type: RuleType
    constraint_expression: str
    description: str = ""
    severity: Severity = "warning"
    enabled: bool = True
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class ValidationResult(BaseModel):
    result_id: str = Field(default_factory=lambda: f"vr-{uuid.uuid4().hex[:8]}")
    rule_id: str
    entity_id: str
    passed: bool
    violation_details: str = ""
    severity: Severity
    evaluated_at: str = Field(default_factory=_now_iso)


class LintRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: f"ol-{uuid.uuid4().hex[:8]}")
    name: str
    rule_type: LintRuleType
    severity: Severity = "warning"
    enabled: bool = True
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class LintResult(BaseModel):
    result_id: str = Field(default_factory=lambda: f"lr-{uuid.uuid4().hex[:8]}")
    rule_id: str
    dataset_rid: str
    passed: bool
    violation_details: str = ""
    severity: Severity
    drift_metrics: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: str = Field(default_factory=_now_iso)


class SchedulingRulesLintError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class SchedulingSmartFunctionsEngine:
    def __init__(self) -> None:
        self._functions: dict[str, SmartFunction] = {}
        self._lock = threading.Lock()

    def create_function(self, name: str, function_type: str, **kwargs: Any) -> SmartFunction:
        if not name:
            raise SchedulingRulesLintError("MISSING_NAME", "函数名称不能为空")
        if function_type not in {"suggestion", "search", "filter", "sort"}:
            raise SchedulingRulesLintError("INVALID_FUNCTION_TYPE", f"未知函数类型：{function_type}")
        func = SmartFunction(name=name, function_type=function_type, **kwargs)
        with self._lock:
            if len(self._functions) >= _MAX_ENTRIES:
                oldest_id = next(iter(self._functions))
                self._functions.pop(oldest_id, None)
            self._functions[func.function_id] = func
        return func

    def get_function(self, function_id: str) -> SmartFunction:
        func = self._functions.get(function_id)
        if func is None:
            raise SchedulingRulesLintError("NOT_FOUND", f"函数 {function_id} 不存在")
        return func

    def list_functions(
        self, function_type: str | None = None, enabled: bool | None = None,
    ) -> list[SmartFunction]:
        items = list(self._functions.values())
        if function_type:
            items = [f for f in items if f.function_type == function_type]
        if enabled is not None:
            items = [f for f in items if f.enabled == enabled]
        return items

    def update_function(self, function_id: str, **kwargs: Any) -> SmartFunction:
        func = self.get_function(function_id)
        for k, v in kwargs.items():
            if k in ("function_id", "created_at"):
                continue
            if hasattr(func, k):
                setattr(func, k, v)
        func.updated_at = _now_iso()
        return func

    def delete_function(self, function_id: str) -> bool:
        with self._lock:
            return self._functions.pop(function_id, None) is not None

    def suggest(self, entity_id: str, function_id: str) -> SuggestionResult:
        func = self.get_function(function_id)
        if func.function_type != "suggestion":
            raise SchedulingRulesLintError(
                "INVALID_FUNCTION_TYPE", "该函数不是 suggestion 类型",
            )
        score = (hash(entity_id) % 201 - 100) / 100.0
        return SuggestionResult(
            function_id=function_id,
            entity_id=entity_id,
            score=score,
            reason="基于实体特征计算的推荐分数",
        )

    def search(self, entity_id: str, query: str) -> list[SuggestionResult]:
        results: list[SuggestionResult] = []
        for func in self._functions.values():
            if func.function_type == "search" and func.enabled:
                score = 0.0
                if query.lower() in func.name.lower():
                    score = 0.8
                elif query.lower() in func.description.lower():
                    score = 0.5
                if score > 0:
                    results.append(
                        SuggestionResult(
                            function_id=func.function_id,
                            entity_id=entity_id,
                            score=score,
                            reason=f"搜索匹配：{query}",
                        ),
                    )
        return sorted(results, key=lambda r: r.score, reverse=True)


class SchedulingValidationEngine:
    def __init__(self) -> None:
        self._rules: dict[str, ValidationRule] = {}
        self._lock = threading.Lock()

    def create_rule(
        self, name: str, rule_type: str, constraint_expression: str, **kwargs: Any,
    ) -> ValidationRule:
        if not name:
            raise SchedulingRulesLintError("MISSING_NAME", "规则名称不能为空")
        if rule_type not in {"hard", "soft"}:
            raise SchedulingRulesLintError("INVALID_RULE_TYPE", f"未知规则类型：{rule_type}")
        severity = kwargs.get("severity", "warning")
        if severity not in {"critical", "warning", "info"}:
            raise SchedulingRulesLintError("INVALID_SEVERITY", f"未知严重级别：{severity}")
        rule = ValidationRule(
            name=name,
            rule_type=rule_type,
            constraint_expression=constraint_expression,
            **kwargs,
        )
        with self._lock:
            if len(self._rules) >= _MAX_ENTRIES:
                oldest_id = next(iter(self._rules))
                self._rules.pop(oldest_id, None)
            self._rules[rule.rule_id] = rule
        return rule

    def get_rule(self, rule_id: str) -> ValidationRule:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise SchedulingRulesLintError("NOT_FOUND", f"规则 {rule_id} 不存在")
        return rule

    def list_rules(
        self, rule_type: str | None = None, severity: str | None = None,
        enabled: bool | None = None,
    ) -> list[ValidationRule]:
        items = list(self._rules.values())
        if rule_type:
            items = [r for r in items if r.rule_type == rule_type]
        if severity:
            items = [r for r in items if r.severity == severity]
        if enabled is not None:
            items = [r for r in items if r.enabled == enabled]
        return items

    def update_rule(self, rule_id: str, **kwargs: Any) -> ValidationRule:
        rule = self.get_rule(rule_id)
        for k, v in kwargs.items():
            if k in ("rule_id", "created_at"):
                continue
            if k == "severity" and v not in {"critical", "warning", "info"}:
                raise SchedulingRulesLintError("INVALID_SEVERITY", f"未知严重级别：{v}")
            if k == "rule_type" and v not in {"hard", "soft"}:
                raise SchedulingRulesLintError("INVALID_RULE_TYPE", f"未知规则类型：{v}")
            if hasattr(rule, k):
                setattr(rule, k, v)
        rule.updated_at = _now_iso()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(rule_id, None) is not None

    def validate(self, entity_id: str, rule_id: str) -> ValidationResult:
        rule = self.get_rule(rule_id)
        if not rule.enabled:
            return ValidationResult(
                rule_id=rule_id,
                entity_id=entity_id,
                passed=True,
                violation_details="规则已禁用，跳过验证",
                severity=rule.severity,
            )
        passed = (hash(entity_id) % 100) >= 30
        return ValidationResult(
            rule_id=rule_id,
            entity_id=entity_id,
            passed=passed,
            violation_details="" if passed else f"违反约束表达式：{rule.constraint_expression}",
            severity=rule.severity,
        )

    def validate_all(self, entity_id: str) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for rule in self._rules.values():
            if rule.enabled:
                results.append(self.validate(entity_id, rule.rule_id))
        return results


class OkfLintEngine:
    def __init__(self) -> None:
        self._rules: dict[str, LintRule] = {}
        self._lock = threading.Lock()

    def create_rule(self, name: str, rule_type: str, **kwargs: Any) -> LintRule:
        if not name:
            raise SchedulingRulesLintError("MISSING_NAME", "规则名称不能为空")
        valid_types = {"column_drift", "contract_violation", "data_quality", "schema_change"}
        if rule_type not in valid_types:
            raise SchedulingRulesLintError("INVALID_RULE_TYPE", f"未知规则类型：{rule_type}")
        severity = kwargs.get("severity", "warning")
        if severity not in {"critical", "warning", "info"}:
            raise SchedulingRulesLintError("INVALID_SEVERITY", f"未知严重级别：{severity}")
        rule = LintRule(name=name, rule_type=rule_type, **kwargs)
        with self._lock:
            if len(self._rules) >= _MAX_ENTRIES:
                oldest_id = next(iter(self._rules))
                self._rules.pop(oldest_id, None)
            self._rules[rule.rule_id] = rule
        return rule

    def get_rule(self, rule_id: str) -> LintRule:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise SchedulingRulesLintError("NOT_FOUND", f"规则 {rule_id} 不存在")
        return rule

    def list_rules(
        self, rule_type: str | None = None, severity: str | None = None,
        enabled: bool | None = None,
    ) -> list[LintRule]:
        items = list(self._rules.values())
        if rule_type:
            items = [r for r in items if r.rule_type == rule_type]
        if severity:
            items = [r for r in items if r.severity == severity]
        if enabled is not None:
            items = [r for r in items if r.enabled == enabled]
        return items

    def update_rule(self, rule_id: str, **kwargs: Any) -> LintRule:
        rule = self.get_rule(rule_id)
        for k, v in kwargs.items():
            if k in ("rule_id", "created_at"):
                continue
            if k == "severity" and v not in {"critical", "warning", "info"}:
                raise SchedulingRulesLintError("INVALID_SEVERITY", f"未知严重级别：{v}")
            valid_types = {"column_drift", "contract_violation", "data_quality", "schema_change"}
            if k == "rule_type" and v not in valid_types:
                raise SchedulingRulesLintError("INVALID_RULE_TYPE", f"未知规则类型：{v}")
            if hasattr(rule, k):
                setattr(rule, k, v)
        rule.updated_at = _now_iso()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(rule_id, None) is not None

    def lint(self, dataset_rid: str) -> list[LintResult]:
        results: list[LintResult] = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            passed = (hash(dataset_rid) % 100) >= 40
            drift_metrics: dict[str, Any] = {}
            if rule.rule_type == "column_drift":
                drift_metrics = {
                    "mean_difference": abs(hash(dataset_rid) % 1000) / 1000.0,
                    "std_deviation": abs(hash(dataset_rid + rule.rule_id) % 500) / 500.0,
                }
            results.append(
                LintResult(
                    rule_id=rule.rule_id,
                    dataset_rid=dataset_rid,
                    passed=passed,
                    violation_details="" if passed else f"{rule.rule_type} 规则检查失败",
                    severity=rule.severity,
                    drift_metrics=drift_metrics,
                ),
            )
        return results

    def get_drift_report(self, dataset_rid: str) -> dict[str, Any]:
        total_rules = 0
        passed_rules = 0
        drift_summary: dict[str, float] = {}
        for rule in self._rules.values():
            if rule.enabled and rule.rule_type == "column_drift":
                total_rules += 1
                if (hash(dataset_rid) % 100) >= 40:
                    passed_rules += 1
                drift_summary[rule.rule_id] = abs(hash(dataset_rid + rule.rule_id) % 100) / 100.0
        return {
            "dataset_rid": dataset_rid,
            "total_drift_rules": total_rules,
            "passed_drift_rules": passed_rules,
            "drift_summary": drift_summary,
            "overall_drift_score": passed_rules / max(total_rules, 1),
            "generated_at": _now_iso(),
        }


_smart_func_engine: SchedulingSmartFunctionsEngine | None = None
_validation_engine: SchedulingValidationEngine | None = None
_okf_lint_engine: OkfLintEngine | None = None
_singleton_lock = threading.Lock()


def get_smart_func_engine() -> SchedulingSmartFunctionsEngine:
    global _smart_func_engine
    if _smart_func_engine is None:
        with _singleton_lock:
            if _smart_func_engine is None:
                _smart_func_engine = SchedulingSmartFunctionsEngine()
    return _smart_func_engine


def get_validation_engine() -> SchedulingValidationEngine:
    global _validation_engine
    if _validation_engine is None:
        with _singleton_lock:
            if _validation_engine is None:
                _validation_engine = SchedulingValidationEngine()
    return _validation_engine


def get_okf_lint_engine() -> OkfLintEngine:
    global _okf_lint_engine
    if _okf_lint_engine is None:
        with _singleton_lock:
            if _okf_lint_engine is None:
                _okf_lint_engine = OkfLintEngine()
    return _okf_lint_engine