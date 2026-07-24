"""
W5 — 审核编辑对话框
Tests: AuditEditDialogEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oc_audit_edit_dialog import AuditEditDialog, AuditEditDialogEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AuditEditDialogEngine().reset()
    yield
    AuditEditDialogEngine().reset()


class TestAuditEditDialogEngine:
    def test_register(self):
        item = AuditEditDialog(name="test-item")
        result = AuditEditDialogEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AuditEditDialog(name="get-test")
        AuditEditDialogEngine().register(item)
        found = AuditEditDialogEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AuditEditDialogEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AuditEditDialogEngine().register(AuditEditDialog(name=f"list-{i}"))
        items = AuditEditDialogEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AuditEditDialog(name="original")
        AuditEditDialogEngine().register(item)
        updated = AuditEditDialogEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AuditEditDialogEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AuditEditDialog(name="delete-me")
        AuditEditDialogEngine().register(item)
        assert AuditEditDialogEngine().delete(item.id) is True
        assert AuditEditDialogEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AuditEditDialogEngine().register(AuditEditDialog(name=f"cap-{i}"))
        assert len(AuditEditDialogEngine().list()) == 100

    def test_singleton(self):
        e1 = AuditEditDialogEngine()
        e2 = AuditEditDialogEngine()
        assert e1 is e2
