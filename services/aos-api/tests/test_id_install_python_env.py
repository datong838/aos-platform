"""
W5 — Install Python Environment
Tests: InstallPythonEnvEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_install_python_env import InstallPythonEnv, InstallPythonEnvEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    InstallPythonEnvEngine().reset()
    yield
    InstallPythonEnvEngine().reset()


class TestInstallPythonEnvEngine:
    def test_register(self):
        item = InstallPythonEnv(name="test-item")
        result = InstallPythonEnvEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = InstallPythonEnv(name="get-test")
        InstallPythonEnvEngine().register(item)
        found = InstallPythonEnvEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert InstallPythonEnvEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            InstallPythonEnvEngine().register(InstallPythonEnv(name=f"list-{i}"))
        items = InstallPythonEnvEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = InstallPythonEnv(name="original")
        InstallPythonEnvEngine().register(item)
        updated = InstallPythonEnvEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert InstallPythonEnvEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = InstallPythonEnv(name="delete-me")
        InstallPythonEnvEngine().register(item)
        assert InstallPythonEnvEngine().delete(item.id) is True
        assert InstallPythonEnvEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            InstallPythonEnvEngine().register(InstallPythonEnv(name=f"cap-{i}"))
        assert len(InstallPythonEnvEngine().list()) == 100

    def test_singleton(self):
        e1 = InstallPythonEnvEngine()
        e2 = InstallPythonEnvEngine()
        assert e1 is e2
