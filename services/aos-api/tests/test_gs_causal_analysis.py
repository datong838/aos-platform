"""
W6 — 因果分析
Tests: CausalAnalysisEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_causal_analysis import CausalAnalysis, CausalAnalysisEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CausalAnalysisEngine().reset()
    yield
    CausalAnalysisEngine().reset()


class TestCausalAnalysisEngine:
    def test_register(self):
        item = CausalAnalysis(name="test-item")
        result = CausalAnalysisEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CausalAnalysis(name="get-test")
        CausalAnalysisEngine().register(item)
        found = CausalAnalysisEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CausalAnalysisEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CausalAnalysisEngine().register(CausalAnalysis(name=f"list-{i}"))
        items = CausalAnalysisEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CausalAnalysis(name="original")
        CausalAnalysisEngine().register(item)
        updated = CausalAnalysisEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CausalAnalysisEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CausalAnalysis(name="delete-me")
        CausalAnalysisEngine().register(item)
        assert CausalAnalysisEngine().delete(item.id) is True
        assert CausalAnalysisEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CausalAnalysisEngine().register(CausalAnalysis(name=f"cap-{i}"))
        assert len(CausalAnalysisEngine().list()) == 100

    def test_singleton(self):
        e1 = CausalAnalysisEngine()
        e2 = CausalAnalysisEngine()
        assert e1 is e2
