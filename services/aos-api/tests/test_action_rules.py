"""W2-#14/#15 · Action 规则 + 函数规则测试。"""
from __future__ import annotations

import pytest

from aos_api.action_rules import (
    ActionRule,
    ActionRuleError,
    ActionRuleStore,
    FunctionRule,
    FunctionRuleStore,
)


# ---------- Action 规则 (#14) ----------


@pytest.fixture
def store() -> ActionRuleStore:
    return ActionRuleStore()


def test_create_rule(store: ActionRuleStore):
    rule = ActionRule(name="金额校验", action_type_id="act-1", kind="modify", condition="amount > 0")
    created = store.create(rule)
    assert created.id in {r.id for r in store.list_all()}


def test_create_missing_name_raises(store: ActionRuleStore):
    with pytest.raises(ActionRuleError) as exc:
        store.create(ActionRule(name="", action_type_id="act-1", kind="create"))
    assert exc.value.code == "MISSING_NAME"


def test_create_missing_action_raises(store: ActionRuleStore):
    with pytest.raises(ActionRuleError) as exc:
        store.create(ActionRule(name="r", action_type_id="", kind="create"))
    assert exc.value.code == "MISSING_ACTION"


def test_evaluate_condition_true(store: ActionRuleStore):
    rule = store.create(ActionRule(name="r", action_type_id="act-1", kind="modify", condition="amount > 100"))
    assert store.evaluate(rule.id, {"amount": 200}) is True


def test_evaluate_condition_false(store: ActionRuleStore):
    rule = store.create(ActionRule(name="r", action_type_id="act-1", kind="modify", condition="amount > 100"))
    assert store.evaluate(rule.id, {"amount": 50}) is False


def test_evaluate_empty_condition_defaults_true(store: ActionRuleStore):
    rule = store.create(ActionRule(name="r", action_type_id="act-1", kind="create"))
    assert store.evaluate(rule.id, {}) is True


def test_evaluate_disabled_rule_returns_false(store: ActionRuleStore):
    rule = store.create(ActionRule(name="r", action_type_id="act-1", kind="create", enabled=False))
    assert store.evaluate(rule.id, {}) is False


def test_list_by_action_sorted_by_priority(store: ActionRuleStore):
    store.create(ActionRule(name="low", action_type_id="act-1", kind="create", priority=10))
    store.create(ActionRule(name="high", action_type_id="act-1", kind="create", priority=1))
    rules = store.list_by_action("act-1")
    assert rules[0].name == "high"
    assert rules[1].name == "low"


def test_update_and_delete_rule(store: ActionRuleStore):
    rule = store.create(ActionRule(name="r", action_type_id="act-1", kind="create"))
    updated = store.update(rule.id, enabled=False, priority=5)
    assert updated.enabled is False and updated.priority == 5
    assert store.delete(rule.id) is True
    assert store.get(rule.id) is None


def test_four_rule_kinds_supported(store: ActionRuleStore):
    for kind in ["create", "modify", "delete", "link"]:
        store.create(ActionRule(name=f"r-{kind}", action_type_id="act-1", kind=kind))  # type: ignore[arg-type]
    assert len(store.list_by_action("act-1")) == 4


def test_evaluate_condition_error_wrapped(store: ActionRuleStore):
    rule = store.create(ActionRule(name="r", action_type_id="act-1", kind="create", condition="@@@"))
    with pytest.raises(ActionRuleError) as exc:
        store.evaluate(rule.id, {})
    assert exc.value.code == "CONDITION_ERROR"


def test_evaluate_unknown_rule_raises(store: ActionRuleStore):
    with pytest.raises(ActionRuleError) as exc:
        store.evaluate("ghost", {})
    assert exc.value.code == "NOT_FOUND"


# ---------- 函数规则 (#15) ----------


class _FakeRuntime:
    def __init__(self) -> None:
        self._fns = {"fn-1": object()}

    def get(self, fn_id: str):
        return self._fns.get(fn_id)

    def invoke(self, fn_id: str, payload):
        return {"invoked": fn_id, "payload": payload}


@pytest.fixture
def frule_store() -> FunctionRuleStore:
    return FunctionRuleStore(runtime=_FakeRuntime())


def test_create_function_rule(frule_store: FunctionRuleStore):
    rule = FunctionRule(name="fr", action_type_id="act-1", function_id="fn-1")
    created = frule_store.create(rule)
    assert created.id in {r.id for r in frule_store.list_all()}


def test_create_function_rule_missing_function_raises(frule_store: FunctionRuleStore):
    with pytest.raises(ActionRuleError) as exc:
        frule_store.create(FunctionRule(name="fr", action_type_id="act-1", function_id=""))
    assert exc.value.code == "MISSING_FUNCTION"


def test_resolve_function_rule(frule_store: FunctionRuleStore):
    rule = frule_store.create(FunctionRule(name="fr", action_type_id="act-1", function_id="fn-1"))
    fn = frule_store.resolve(rule.id)
    assert fn is not None


def test_resolve_unknown_function_raises(frule_store: FunctionRuleStore):
    rule = frule_store.create(FunctionRule(name="fr", action_type_id="act-1", function_id="ghost"))
    with pytest.raises(ActionRuleError) as exc:
        frule_store.resolve(rule.id)
    assert exc.value.code == "FUNCTION_NOT_FOUND"


def test_execute_function_rule(frule_store: FunctionRuleStore):
    rule = frule_store.create(FunctionRule(name="fr", action_type_id="act-1", function_id="fn-1", trigger="before"))
    result = frule_store.execute(rule.id, {"x": 1})
    assert result["invoked"] == "fn-1"
    assert result["payload"] == {"x": 1}


def test_execute_disabled_function_rule_raises(frule_store: FunctionRuleStore):
    rule = frule_store.create(FunctionRule(name="fr", action_type_id="act-1", function_id="fn-1", enabled=False))
    with pytest.raises(ActionRuleError) as exc:
        frule_store.execute(rule.id, None)
    assert exc.value.code == "RULE_DISABLED"


def test_function_rule_triggers(frule_store: FunctionRuleStore):
    for trigger in ["before", "after", "instead"]:
        frule_store.create(FunctionRule(name=f"fr-{trigger}", action_type_id="act-1", function_id="fn-1", trigger=trigger))  # type: ignore[arg-type]
    assert len(frule_store.list_by_action("act-1")) == 3
