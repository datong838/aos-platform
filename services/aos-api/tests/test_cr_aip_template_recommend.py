"""
W5 — AIP 代码模板推荐
Tests: AipTemplateRecommendEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_aip_template_recommend import AipTemplateRecommend, AipTemplateRecommendEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AipTemplateRecommendEngine().reset()
    yield
    AipTemplateRecommendEngine().reset()


class TestAipTemplateRecommendEngine:
    def test_register(self):
        item = AipTemplateRecommend(name="test-item")
        result = AipTemplateRecommendEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AipTemplateRecommend(name="get-test")
        AipTemplateRecommendEngine().register(item)
        found = AipTemplateRecommendEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AipTemplateRecommendEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AipTemplateRecommendEngine().register(AipTemplateRecommend(name=f"list-{i}"))
        items = AipTemplateRecommendEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AipTemplateRecommend(name="original")
        AipTemplateRecommendEngine().register(item)
        updated = AipTemplateRecommendEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AipTemplateRecommendEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AipTemplateRecommend(name="delete-me")
        AipTemplateRecommendEngine().register(item)
        assert AipTemplateRecommendEngine().delete(item.id) is True
        assert AipTemplateRecommendEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AipTemplateRecommendEngine().register(AipTemplateRecommend(name=f"cap-{i}"))
        assert len(AipTemplateRecommendEngine().list()) == 100

    def test_singleton(self):
        e1 = AipTemplateRecommendEngine()
        e2 = AipTemplateRecommendEngine()
        assert e1 is e2
