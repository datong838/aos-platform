"""
W5 — 函数操作入门向导
Tests: FuncOnboardingEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_func_onboarding import FuncOnboarding, FuncOnboardingEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    FuncOnboardingEngine().reset()
    yield
    FuncOnboardingEngine().reset()


class TestFuncOnboardingEngine:
    def test_register(self):
        item = FuncOnboarding(name="test-item")
        result = FuncOnboardingEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = FuncOnboarding(name="get-test")
        FuncOnboardingEngine().register(item)
        found = FuncOnboardingEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert FuncOnboardingEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            FuncOnboardingEngine().register(FuncOnboarding(name=f"list-{i}"))
        items = FuncOnboardingEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = FuncOnboarding(name="original")
        FuncOnboardingEngine().register(item)
        updated = FuncOnboardingEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert FuncOnboardingEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = FuncOnboarding(name="delete-me")
        FuncOnboardingEngine().register(item)
        assert FuncOnboardingEngine().delete(item.id) is True
        assert FuncOnboardingEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            FuncOnboardingEngine().register(FuncOnboarding(name=f"cap-{i}"))
        assert len(FuncOnboardingEngine().list()) == 100

    def test_singleton(self):
        e1 = FuncOnboardingEngine()
        e2 = FuncOnboardingEngine()
        assert e1 is e2
