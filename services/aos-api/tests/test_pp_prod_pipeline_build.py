"""
W5 — 生产管道构建
Tests: ProdPipelineBuildEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_prod_pipeline_build import ProdPipelineBuild, ProdPipelineBuildEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ProdPipelineBuildEngine().reset()
    yield
    ProdPipelineBuildEngine().reset()


class TestProdPipelineBuildEngine:
    def test_register(self):
        item = ProdPipelineBuild(name="test-item")
        result = ProdPipelineBuildEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ProdPipelineBuild(name="get-test")
        ProdPipelineBuildEngine().register(item)
        found = ProdPipelineBuildEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ProdPipelineBuildEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ProdPipelineBuildEngine().register(ProdPipelineBuild(name=f"list-{i}"))
        items = ProdPipelineBuildEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ProdPipelineBuild(name="original")
        ProdPipelineBuildEngine().register(item)
        updated = ProdPipelineBuildEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ProdPipelineBuildEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ProdPipelineBuild(name="delete-me")
        ProdPipelineBuildEngine().register(item)
        assert ProdPipelineBuildEngine().delete(item.id) is True
        assert ProdPipelineBuildEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ProdPipelineBuildEngine().register(ProdPipelineBuild(name=f"cap-{i}"))
        assert len(ProdPipelineBuildEngine().list()) == 100

    def test_singleton(self):
        e1 = ProdPipelineBuildEngine()
        e2 = ProdPipelineBuildEngine()
        assert e1 is e2
