"""Phase 4 · Ontology Actions — 单元测试 (≥3)."""
from __future__ import annotations

import pytest

from aos_api.ontology_action_engine import get_action_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_action_engine().reset()
    yield


def test_create_and_get_action() -> None:
    eng = get_action_engine()
    a = eng.create_action(name="cancel_order", display_name="Cancel")
    fetched = eng.get_action(a.id)
    assert fetched is not None
    assert fetched.name == "cancel_order"


def test_update_action() -> None:
    eng = get_action_engine()
    a = eng.create_action(name="a1")
    updated = eng.update_action(a.id, description="updated", status="deprecated")
    assert updated.description == "updated"
    assert updated.status == "deprecated"
    assert updated.version == 2


def test_list_actions_filter() -> None:
    eng = get_action_engine()
    eng.create_action(name="a1", category="writeback")
    eng.create_action(name="a2", category="notification")
    items = eng.list_actions(category="writeback")
    assert len(items) == 1
    assert items[0].name == "a1"


def test_delete_action() -> None:
    eng = get_action_engine()
    a = eng.create_action(name="to_del")
    assert eng.delete_action(a.id) is True
    assert eng.get_action(a.id) is None
