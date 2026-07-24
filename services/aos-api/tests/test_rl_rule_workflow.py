"""
W5 — 规则工作流
Tests: RuleWorkflowEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.rl_rule_workflow import RuleWorkflow, RuleWorkflowEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    RuleWorkflowEngine().reset()
    yield
    RuleWorkflowEngine().reset()


class TestRuleWorkflowEngine:
    def test_register(self):
        item = RuleWorkflow(name="test-item")
        result = RuleWorkflowEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = RuleWorkflow(name="get-test")
        RuleWorkflowEngine().register(item)
        found = RuleWorkflowEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert RuleWorkflowEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            RuleWorkflowEngine().register(RuleWorkflow(name=f"list-{i}"))
        items = RuleWorkflowEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = RuleWorkflow(name="original")
        RuleWorkflowEngine().register(item)
        updated = RuleWorkflowEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert RuleWorkflowEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = RuleWorkflow(name="delete-me")
        RuleWorkflowEngine().register(item)
        assert RuleWorkflowEngine().delete(item.id) is True
        assert RuleWorkflowEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            RuleWorkflowEngine().register(RuleWorkflow(name=f"cap-{i}"))
        assert len(RuleWorkflowEngine().list()) == 100

    def test_singleton(self):
        e1 = RuleWorkflowEngine()
        e2 = RuleWorkflowEngine()
        assert e1 is e2
