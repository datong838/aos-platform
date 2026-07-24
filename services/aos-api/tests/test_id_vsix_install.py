"""
W5 — VSIX 扩展安装
Tests: VsixInstallEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_vsix_install import VsixInstall, VsixInstallEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    VsixInstallEngine().reset()
    yield
    VsixInstallEngine().reset()


class TestVsixInstallEngine:
    def test_register(self):
        item = VsixInstall(name="test-item")
        result = VsixInstallEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = VsixInstall(name="get-test")
        VsixInstallEngine().register(item)
        found = VsixInstallEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert VsixInstallEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            VsixInstallEngine().register(VsixInstall(name=f"list-{i}"))
        items = VsixInstallEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = VsixInstall(name="original")
        VsixInstallEngine().register(item)
        updated = VsixInstallEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert VsixInstallEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = VsixInstall(name="delete-me")
        VsixInstallEngine().register(item)
        assert VsixInstallEngine().delete(item.id) is True
        assert VsixInstallEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            VsixInstallEngine().register(VsixInstall(name=f"cap-{i}"))
        assert len(VsixInstallEngine().list()) == 100

    def test_singleton(self):
        e1 = VsixInstallEngine()
        e2 = VsixInstallEngine()
        assert e1 is e2
