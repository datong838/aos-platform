"""W2-K · Ontology 管理增强测试：#36 Edit History + #37 Cleanup + #32 Interface."""
from __future__ import annotations

import pytest

from aos_api.ontology_management import (
    CleanupEngine,
    CleanupItem,
    EditEvent,
    EditHistoryEngine,
    InterfaceEngine,
    InterfaceError,
    OntologyInterface,
)


# ── #36 Edit History ──
def test_edit_record_and_list():
    eng = EditHistoryEngine()
    e1 = eng.record(EditEvent(target_type="object_type", target_id="Employee", action="create", author="alice"))
    e2 = eng.record(EditEvent(target_type="property", target_id="prop-1", action="update", author="bob"))
    assert len(eng.list()) == 2
    assert len(eng.list(author="alice")) == 1
    assert len(eng.list(target_type="property")) == 1


def test_edit_get():
    eng = EditHistoryEngine()
    e = eng.record(EditEvent(target_type="object_type", target_id="X", action="create", author="alice"))
    assert eng.get(e.id).target_id == "X"
    with pytest.raises(KeyError):
        eng.get("nonexistent")


def test_edit_rollback_single():
    eng = EditHistoryEngine()
    e = eng.record(EditEvent(target_type="object_type", target_id="X", action="update", author="alice"))
    rolled = eng.rollback(e.id)
    assert rolled.rolled_back is True


def test_edit_rollback_by_author():
    eng = EditHistoryEngine()
    eng.record(EditEvent(target_type="ot", target_id="a", action="create", author="alice"))
    eng.record(EditEvent(target_type="ot", target_id="b", action="update", author="alice"))
    eng.record(EditEvent(target_type="ot", target_id="c", action="create", author="bob"))
    rolled = eng.rollback_by_author("alice")
    assert len(rolled) == 2
    assert all(e.rolled_back for e in rolled)
    # bob 的事件不受影响
    bob_events = eng.list(author="bob")
    assert all(not e.rolled_back for e in bob_events)


def test_edit_timeline_merged():
    eng = EditHistoryEngine()
    eng.record(EditEvent(target_type="ot", target_id="a", action="create", author="alice"))
    eng.record(EditEvent(target_type="ot", target_id="b", action="update", author="alice"))
    eng.record(EditEvent(target_type="ot", target_id="c", action="create", author="bob"))
    timeline = eng.timeline_merged_by_author()
    assert len(timeline) == 2
    alice_entry = next(t for t in timeline if t["author"] == "alice")
    assert alice_entry["eventCount"] == 2
    assert "a" in alice_entry["targets"]
    assert "b" in alice_entry["targets"]


# ── #37 Cleanup ──
def test_cleanup_scan_all_tags():
    eng = CleanupEngine()
    eng.register(CleanupItem(
        resource_type="object_type", resource_id="test_ot",
        name="test_deprecated_ot", description="", is_indexed=False,
    ))
    items = eng.scan()
    assert len(items) == 1
    tags = items[0].tags
    assert "missing_description" in tags
    assert "name_matches_regex" in tags
    assert "unindexed" in tags


def test_cleanup_deprecated_date_passed():
    eng = CleanupEngine()
    eng.register(CleanupItem(
        resource_type="object_type", resource_id="old_ot",
        name="Employee", description="has desc",
        deprecated_date="2020-01-01T00:00:00+00:00",
    ))
    items = eng.scan()
    assert "deprecated_date_passed" in items[0].tags


def test_cleanup_long_no_update():
    eng = CleanupEngine()
    eng.register(CleanupItem(
        resource_type="link_type", resource_id="old_link",
        name="LinkType", description="desc",
        updated_at="2020-01-01T00:00:00+00:00",
    ))
    items = eng.scan()
    assert "long_no_update" in items[0].tags


def test_cleanup_recycle_bin():
    eng = CleanupEngine()
    eng.register(CleanupItem(
        resource_type="object_type", resource_id="rb",
        name="Normal", description="desc", is_recycle_bin=True,
    ))
    items = eng.scan()
    assert "recycle_bin_source" in items[0].tags


def test_cleanup_apply_delay():
    eng = CleanupEngine()
    eng.register(CleanupItem(
        resource_type="object_type", resource_id="emp",
        name="Employee", description="desc",
    ))
    item = eng.apply("object_type", "emp", "delay")
    assert item.action == "delay"


def test_cleanup_apply_deprecate():
    eng = CleanupEngine()
    eng.register(CleanupItem(
        resource_type="object_type", resource_id="emp",
        name="Employee", description="desc",
    ))
    item = eng.apply("object_type", "emp", "deprecate")
    assert item.action == "deprecate"


def test_cleanup_apply_delete():
    eng = CleanupEngine()
    eng.register(CleanupItem(
        resource_type="object_type", resource_id="emp",
        name="Employee", description="desc",
    ))
    item = eng.apply("object_type", "emp", "delete")
    # 删除后资源不再可扫描
    assert eng.scan() == []


def test_cleanup_batch():
    eng = CleanupEngine()
    eng.register(CleanupItem(resource_type="ot", resource_id="a", name="test_a", description=""))
    eng.register(CleanupItem(resource_type="ot", resource_id="b", name="normal", description="has desc"))
    results = eng.batch_apply(tag="missing_description", action="delay")
    assert len(results) == 1
    assert results[0].resource_id == "a"


def test_cleanup_invalid_action():
    eng = CleanupEngine()
    eng.register(CleanupItem(resource_type="ot", resource_id="x", name="X", description="d"))
    with pytest.raises(ValueError):
        eng.apply("ot", "x", "invalid")


# ── #32 Interface ──
def test_interface_create():
    eng = InterfaceEngine()
    iface = eng.create(OntologyInterface(name="INameable", description="has a name"))
    assert iface.id.startswith("iface-")
    assert iface.name == "INameable"


def test_interface_create_with_extends():
    eng = InterfaceEngine()
    parent = eng.create(OntologyInterface(name="IBase", properties=[{"name": "id", "type": "string"}]))
    child = eng.create(OntologyInterface(
        name="IDerived", extends=[parent.id], properties=[{"name": "label", "type": "string"}],
    ))
    assert child.extends == [parent.id]


def test_interface_extends_not_found():
    eng = InterfaceEngine()
    with pytest.raises(InterfaceError) as exc:
        eng.create(OntologyInterface(name="X", extends=["nonexistent"]))
    assert exc.value.code == "PARENT_NOT_FOUND"


def test_interface_update():
    eng = InterfaceEngine()
    iface = eng.create(OntologyInterface(name="INameable"))
    updated = eng.update(iface.id, {"description": "updated desc", "version": 2})
    assert updated.description == "updated desc"
    assert updated.version == 2


def test_interface_implement():
    eng = InterfaceEngine()
    iface = eng.create(OntologyInterface(name="INameable"))
    result = eng.implement(iface.id, "Employee")
    assert "Employee" in result.implemented_by
    # 重复实现不报错
    result = eng.implement(iface.id, "Employee")
    assert result.implemented_by.count("Employee") == 1


def test_interface_effective_properties():
    eng = InterfaceEngine()
    parent = eng.create(OntologyInterface(name="IBase", properties=[{"name": "id", "type": "string"}]))
    child = eng.create(OntologyInterface(
        name="IDerived", extends=[parent.id], properties=[{"name": "label", "type": "string"}],
    ))
    effective = eng.get_effective_properties(child.id)
    assert len(effective) == 2
    names = {p["name"] for p in effective}
    assert "id" in names
    assert "label" in names


def test_interface_delete_blocked_by_extend():
    eng = InterfaceEngine()
    parent = eng.create(OntologyInterface(name="IBase"))
    eng.create(OntologyInterface(name="IChild", extends=[parent.id]))
    with pytest.raises(InterfaceError) as exc:
        eng.delete(parent.id)
    assert exc.value.code == "STILL_EXTENDED"


def test_interface_delete_blocked_by_implement():
    eng = InterfaceEngine()
    iface = eng.create(OntologyInterface(name="INameable"))
    eng.implement(iface.id, "Employee")
    with pytest.raises(InterfaceError) as exc:
        eng.delete(iface.id)
    assert exc.value.code == "STILL_IMPLEMENTED"


def test_interface_delete_success():
    eng = InterfaceEngine()
    iface = eng.create(OntologyInterface(name="ITemp"))
    assert eng.delete(iface.id) is True
    with pytest.raises(InterfaceError):
        eng.get(iface.id)


def test_interface_list():
    eng = InterfaceEngine()
    eng.create(OntologyInterface(name="A"))
    eng.create(OntologyInterface(name="B"))
    assert len(eng.list()) == 2
