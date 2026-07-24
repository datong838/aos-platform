"""W2-#14/#15 · Action 规则可视化 + Action 函数规则。

规则引擎（create/modify/delete/link）+ condition DSL 求值（复用 function_engine）+
函数规则（引用 functions_runtime.RuntimeFunction）。

独立内存 store，不修改 meta_action_type DB 表（最小更改，避免 seed 覆盖）。

详见 docs/palantier/20_tech/220tech_w2-c-ontology-manager.md §2.3/§2.4。
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from .function_engine import FunctionError, evaluate, parse


RuleKind = Literal["create", "modify", "delete", "link"]
FunctionTrigger = Literal["before", "after", "instead"]


class ActionRule(BaseModel):
    id: str = Field(default_factory=lambda: "rule-" + uuid.uuid4().hex[:8])
    name: str
    action_type_id: str
    kind: RuleKind
    condition: str = ""
    target_otd_id: str = ""
    enabled: bool = True
    priority: int = 0


class FunctionRule(BaseModel):
    id: str = Field(default_factory=lambda: "frule-" + uuid.uuid4().hex[:8])
    name: str
    action_type_id: str
    function_id: str
    trigger: FunctionTrigger = "before"
    condition: str = ""
    enabled: bool = True


class ActionRuleError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _eval_condition(condition: str, context: dict[str, Any]) -> bool:
    if not condition:
        return True
    try:
        return bool(evaluate(parse(condition), context))
    except FunctionError as exc:
        raise ActionRuleError("CONDITION_ERROR", f"规则条件表达式错误：{exc.message}") from exc


class ActionRuleStore:
    """Action 规则注册表：CRUD + condition 求值 + 按 Action 查询。"""

    def __init__(self) -> None:
        self._rules: dict[str, ActionRule] = {}

    def create(self, rule: ActionRule) -> ActionRule:
        if not rule.name:
            raise ActionRuleError("MISSING_NAME", "规则缺少 name")
        if not rule.action_type_id:
            raise ActionRuleError("MISSING_ACTION", "规则缺少 action_type_id")
        self._rules[rule.id] = rule
        return rule

    def get(self, rule_id: str) -> ActionRule | None:
        return self._rules.get(rule_id)

    def list_by_action(self, action_type_id: str) -> list[ActionRule]:
        return sorted(
            [r for r in self._rules.values() if r.action_type_id == action_type_id],
            key=lambda r: r.priority,
        )

    def list_all(self) -> list[ActionRule]:
        return list(self._rules.values())

    def update(self, rule_id: str, **fields: Any) -> ActionRule:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise ActionRuleError("NOT_FOUND", f"规则 {rule_id!r} 不存在")
        updated = rule.model_copy(update=fields)
        self._rules[rule_id] = updated
        return updated

    def delete(self, rule_id: str) -> bool:
        existed = rule_id in self._rules
        self._rules.pop(rule_id, None)
        return existed

    def evaluate(self, rule_id: str, context: dict[str, Any]) -> bool:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise ActionRuleError("NOT_FOUND", f"规则 {rule_id!r} 不存在")
        if not rule.enabled:
            return False
        return _eval_condition(rule.condition, context)


class FunctionRuleStore:
    """Action 函数规则：引用 functions_runtime.Function + 触发执行。"""

    def __init__(self, runtime: Any | None = None) -> None:
        self._rules: dict[str, FunctionRule] = {}
        if runtime is None:
            from .functions_runtime import get_runtime
            runtime = get_runtime()
        self._runtime = runtime

    def create(self, rule: FunctionRule) -> FunctionRule:
        if not rule.name:
            raise ActionRuleError("MISSING_NAME", "函数规则缺少 name")
        if not rule.action_type_id:
            raise ActionRuleError("MISSING_ACTION", "函数规则缺少 action_type_id")
        if not rule.function_id:
            raise ActionRuleError("MISSING_FUNCTION", "函数规则缺少 function_id")
        self._rules[rule.id] = rule
        return rule

    def get(self, rule_id: str) -> FunctionRule | None:
        return self._rules.get(rule_id)

    def list_by_action(self, action_type_id: str) -> list[FunctionRule]:
        return [r for r in self._rules.values() if r.action_type_id == action_type_id]

    def list_all(self) -> list[FunctionRule]:
        return list(self._rules.values())

    def update(self, rule_id: str, **fields: Any) -> FunctionRule:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise ActionRuleError("NOT_FOUND", f"函数规则 {rule_id!r} 不存在")
        updated = rule.model_copy(update=fields)
        self._rules[rule_id] = updated
        return updated

    def delete(self, rule_id: str) -> bool:
        existed = rule_id in self._rules
        self._rules.pop(rule_id, None)
        return existed

    def resolve(self, function_rule_id: str) -> Any:
        rule = self._rules.get(function_rule_id)
        if rule is None:
            raise ActionRuleError("NOT_FOUND", f"函数规则 {function_rule_id!r} 不存在")
        fn = self._runtime.get(rule.function_id)
        if fn is None:
            raise ActionRuleError("FUNCTION_NOT_FOUND", f"引用的函数 {rule.function_id!r} 不存在")
        return fn

    def evaluate_condition(self, rule_id: str, context: dict[str, Any]) -> bool:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise ActionRuleError("NOT_FOUND", f"函数规则 {rule_id!r} 不存在")
        if not rule.enabled:
            return False
        return _eval_condition(rule.condition, context)

    def execute(self, function_rule_id: str, payload: Any) -> Any:
        rule = self._rules.get(function_rule_id)
        if rule is None:
            raise ActionRuleError("NOT_FOUND", f"函数规则 {function_rule_id!r} 不存在")
        if not rule.enabled:
            raise ActionRuleError("RULE_DISABLED", f"函数规则 {function_rule_id!r} 已禁用")
        return self._runtime.invoke(rule.function_id, payload)


_rule_store = ActionRuleStore()
_function_rule_store: FunctionRuleStore | None = None


def get_rule_store() -> ActionRuleStore:
    return _rule_store


def get_function_rule_store() -> FunctionRuleStore:
    global _function_rule_store
    if _function_rule_store is None:
        _function_rule_store = FunctionRuleStore()
    return _function_rule_store
