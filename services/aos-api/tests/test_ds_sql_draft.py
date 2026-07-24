"""
W5 — SQL 草稿
Tests: SqlDraftEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_sql_draft import SqlDraft, SqlDraftEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SqlDraftEngine().reset()
    yield
    SqlDraftEngine().reset()


class TestSqlDraftEngine:
    def test_register(self):
        item = SqlDraft(name="test-item")
        result = SqlDraftEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SqlDraft(name="get-test")
        SqlDraftEngine().register(item)
        found = SqlDraftEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SqlDraftEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SqlDraftEngine().register(SqlDraft(name=f"list-{i}"))
        items = SqlDraftEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SqlDraft(name="original")
        SqlDraftEngine().register(item)
        updated = SqlDraftEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SqlDraftEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SqlDraft(name="delete-me")
        SqlDraftEngine().register(item)
        assert SqlDraftEngine().delete(item.id) is True
        assert SqlDraftEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SqlDraftEngine().register(SqlDraft(name=f"cap-{i}"))
        assert len(SqlDraftEngine().list()) == 100

    def test_singleton(self):
        e1 = SqlDraftEngine()
        e2 = SqlDraftEngine()
        assert e1 is e2
