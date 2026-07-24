"""
W5 — 变换管道规则
Tests: TransformPipelineRuleEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.rl_transform_pipeline_rule import TransformPipelineRule, TransformPipelineRuleEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TransformPipelineRuleEngine().reset()
    yield
    TransformPipelineRuleEngine().reset()


class TestTransformPipelineRuleEngine:
    def test_register(self):
        item = TransformPipelineRule(name="test-item")
        result = TransformPipelineRuleEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TransformPipelineRule(name="get-test")
        TransformPipelineRuleEngine().register(item)
        found = TransformPipelineRuleEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TransformPipelineRuleEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TransformPipelineRuleEngine().register(TransformPipelineRule(name=f"list-{i}"))
        items = TransformPipelineRuleEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TransformPipelineRule(name="original")
        TransformPipelineRuleEngine().register(item)
        updated = TransformPipelineRuleEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TransformPipelineRuleEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TransformPipelineRule(name="delete-me")
        TransformPipelineRuleEngine().register(item)
        assert TransformPipelineRuleEngine().delete(item.id) is True
        assert TransformPipelineRuleEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TransformPipelineRuleEngine().register(TransformPipelineRule(name=f"cap-{i}"))
        assert len(TransformPipelineRuleEngine().list()) == 100

    def test_singleton(self):
        e1 = TransformPipelineRuleEngine()
        e2 = TransformPipelineRuleEngine()
        assert e1 is e2
