"""W2-N · Object 编辑增强测试：#42 冲突解决 + #44 模式迁移 + #45 编辑历史追踪."""
from __future__ import annotations

import pytest

from aos_api.object_editing import (
    ChangeLogEngine,
    ConflictEngine,
    ConflictError,
    EditConflict,
    MigrationBatch,
    MigrationEngine,
    MigrationError,
    ObjectChangeLog,
)


# ── #42 冲突解决 ──

def test_conflict_detect_and_get():
    eng = ConflictEngine()
    c = eng.detect("Employee", "emp-1", "name",
                   edit_a={"user": "alice", "value": "Alice", "timestamp": "2026-01-01T10:00:00Z"},
                   edit_b={"user": "bob", "value": "Bob", "timestamp": "2026-01-01T10:00:01Z"})
    fetched = eng.get(c.id)
    assert fetched.field == "name"
    assert fetched.edit_a["user"] == "alice"


def test_conflict_get_not_found():
    eng = ConflictEngine()
    with pytest.raises(ConflictError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_conflict_resolve_timestamp_priority():
    eng = ConflictEngine()
    c = eng.detect("OT", "obj-1", "field",
                   edit_a={"user": "a", "value": "old", "timestamp": "2026-01-01T10:00:00Z"},
                   edit_b={"user": "b", "value": "new", "timestamp": "2026-01-01T10:00:01Z"})
    resolved = eng.resolve(c.id, "timestamp_priority")
    assert resolved.resolution["winner"] == "b"
    assert resolved.resolution["resolved_value"] == "new"


def test_conflict_resolve_user_priority():
    eng = ConflictEngine()
    eng.set_user_priority("alice", 10)
    eng.set_user_priority("bob", 5)
    c = eng.detect("OT", "obj-1", "field",
                   edit_a={"user": "alice", "value": "A", "timestamp": "2026-01-01T10:00:00Z"},
                   edit_b={"user": "bob", "value": "B", "timestamp": "2026-01-01T10:00:01Z"})
    resolved = eng.resolve(c.id, "user_priority")
    assert resolved.resolution["winner"] == "a"
    assert resolved.resolution["resolved_value"] == "A"


def test_conflict_resolve_already_resolved():
    eng = ConflictEngine()
    c = eng.detect("OT", "obj-1", "f",
                   edit_a={"user": "a", "value": "A", "timestamp": "t1"},
                   edit_b={"user": "b", "value": "B", "timestamp": "t2"})
    eng.resolve(c.id, "timestamp_priority")
    with pytest.raises(ConflictError) as exc:
        eng.resolve(c.id, "timestamp_priority")
    assert exc.value.code == "ALREADY_RESOLVED"


def test_conflict_resolve_invalid_strategy():
    eng = ConflictEngine()
    c = eng.detect("OT", "obj-1", "f",
                   edit_a={"user": "a", "value": "A", "timestamp": "t1"},
                   edit_b={"user": "b", "value": "B", "timestamp": "t2"})
    with pytest.raises(ConflictError) as exc:
        eng.resolve(c.id, "invalid_strategy")
    assert exc.value.code == "INVALID_STRATEGY"


def test_conflict_list_filter():
    eng = ConflictEngine()
    eng.detect("OT1", "obj-1", "f1", {"user": "a", "value": 1, "timestamp": "t1"}, {"user": "b", "value": 2, "timestamp": "t2"})
    eng.detect("OT2", "obj-2", "f2", {"user": "a", "value": 3, "timestamp": "t3"}, {"user": "b", "value": 4, "timestamp": "t4"})
    assert len(eng.list()) == 2
    assert len(eng.list(object_type="OT1")) == 1


def test_conflict_list_filter_resolved():
    eng = ConflictEngine()
    c = eng.detect("OT", "obj", "f", {"user": "a", "value": 1, "timestamp": "t1"}, {"user": "b", "value": 2, "timestamp": "t2"})
    eng.resolve(c.id, "timestamp_priority")
    assert len(eng.list(resolved=True)) == 1
    assert len(eng.list(resolved=False)) == 0


# ── #44 模式迁移 ──

def test_migration_register_and_get_schema():
    eng = MigrationEngine()
    eng.register_schema("Employee", [{"name": "id", "data_type": "int", "nullable": False}])
    schema = eng.get_schema("Employee")
    assert len(schema) == 1
    assert schema[0]["name"] == "id"


def test_migration_create_batch():
    eng = MigrationEngine()
    batch = eng.create_batch("Employee", [
        {"instruction": "ADD_PROPERTY", "field": "email", "params": {"data_type": "string"}},
    ])
    assert batch.total == 1
    assert batch.status == "PENDING"


def test_migration_invalid_instruction():
    eng = MigrationEngine()
    with pytest.raises(MigrationError) as exc:
        eng.create_batch("OT", [{"instruction": "INVALID", "field": "f"}])
    assert exc.value.code == "INVALID_INSTRUCTION"


def test_migration_batch_too_large():
    eng = MigrationEngine()
    commands = [{"instruction": "ADD_PROPERTY", "field": f"f{i}"} for i in range(501)]
    with pytest.raises(MigrationError) as exc:
        eng.create_batch("OT", commands)
    assert exc.value.code == "BATCH_TOO_LARGE"


def test_migration_execute_add_property():
    eng = MigrationEngine()
    eng.register_schema("OT", [])
    batch = eng.create_batch("OT", [
        {"instruction": "ADD_PROPERTY", "field": "name", "params": {"data_type": "string"}},
    ])
    result = eng.execute_batch(batch.id)
    assert result.status == "COMPLETED"
    assert result.processed == 1
    schema = eng.get_schema("OT")
    assert any(p["name"] == "name" for p in schema)


def test_migration_execute_remove_property():
    eng = MigrationEngine()
    eng.register_schema("OT", [{"name": "a"}, {"name": "b"}])
    batch = eng.create_batch("OT", [
        {"instruction": "REMOVE_PROPERTY", "field": "a"},
    ])
    result = eng.execute_batch(batch.id)
    assert result.status == "COMPLETED"
    schema = eng.get_schema("OT")
    assert len(schema) == 1
    assert schema[0]["name"] == "b"


def test_migration_execute_rename_property():
    eng = MigrationEngine()
    eng.register_schema("OT", [{"name": "old_name", "data_type": "string"}])
    batch = eng.create_batch("OT", [
        {"instruction": "RENAME_PROPERTY", "field": "old_name", "params": {"new_name": "new_name"}},
    ])
    eng.execute_batch(batch.id)
    schema = eng.get_schema("OT")
    assert schema[0]["name"] == "new_name"


def test_migration_execute_change_type():
    eng = MigrationEngine()
    eng.register_schema("OT", [{"name": "age", "data_type": "string"}])
    batch = eng.create_batch("OT", [
        {"instruction": "CHANGE_TYPE", "field": "age", "params": {"data_type": "int"}},
    ])
    eng.execute_batch(batch.id)
    schema = eng.get_schema("OT")
    assert schema[0]["data_type"] == "int"


def test_migration_dry_run_does_not_modify():
    eng = MigrationEngine()
    eng.register_schema("OT", [])
    batch = eng.create_batch("OT", [
        {"instruction": "ADD_PROPERTY", "field": "name"},
    ], dry_run=True)
    eng.execute_batch(batch.id)
    # dry_run 不应修改 schema
    assert eng.get_schema("OT") == []


def test_migration_list_batches():
    eng = MigrationEngine()
    eng.create_batch("A", [])
    eng.create_batch("B", [])
    assert len(eng.list_batches()) == 2
    assert len(eng.list_batches(object_type="A")) == 1


def test_migration_get_not_found():
    eng = MigrationEngine()
    with pytest.raises(MigrationError) as exc:
        eng.get_batch("nonexistent")
    assert exc.value.code == "NOT_FOUND"


# ── #45 编辑历史追踪 ──

def test_changelog_enable_disable():
    eng = ChangeLogEngine()
    assert not eng.is_enabled("Employee")
    eng.enable("Employee")
    assert eng.is_enabled("Employee")
    eng.disable("Employee")
    assert not eng.is_enabled("Employee")


def test_changelog_record_when_enabled():
    eng = ChangeLogEngine()
    eng.enable("Employee")
    log = ObjectChangeLog(object_type="Employee", object_id="1", field="name",
                          old_value="Alice", new_value="Alicia", author="admin")
    result = eng.record(log)
    assert result is not None
    assert len(eng.query()) == 1


def test_changelog_record_when_disabled():
    eng = ChangeLogEngine()
    # 默认未启用
    log = ObjectChangeLog(object_type="Employee", object_id="1", field="name",
                          old_value="Alice", new_value="Alicia", author="admin")
    result = eng.record(log)
    assert result is None
    assert eng.query() == []


def test_changelog_record_force():
    eng = ChangeLogEngine()
    log = ObjectChangeLog(object_type="Employee", object_id="1", field="name",
                          old_value="Alice", new_value="Alicia", author="admin")
    result = eng.record_force(log)
    assert result is not None
    assert len(eng.query()) == 1


def test_changelog_query_filters():
    eng = ChangeLogEngine()
    eng.enable("OT")
    eng.record(ObjectChangeLog(object_type="OT", object_id="1", field="name", author="alice", operation="update"))
    eng.record(ObjectChangeLog(object_type="OT", object_id="1", field="age", author="bob", operation="update"))
    eng.record(ObjectChangeLog(object_type="OT", object_id="2", field="name", author="alice", operation="create"))
    assert len(eng.query(object_type="OT")) == 3
    assert len(eng.query(object_id="1")) == 2
    assert len(eng.query(field="name")) == 2
    assert len(eng.query(author="alice")) == 2
    assert len(eng.query(operation="create")) == 1


def test_changelog_timeline():
    eng = ChangeLogEngine()
    eng.enable("Employee")
    eng.record(ObjectChangeLog(object_type="Employee", object_id="1", field="name", old_value="A", new_value="B", author="u1"))
    eng.record(ObjectChangeLog(object_type="Employee", object_id="1", field="age", old_value=30, new_value=31, author="u1"))
    timeline = eng.get_timeline("Employee", "1")
    assert len(timeline) == 2


def test_changelog_query_time_range():
    eng = ChangeLogEngine()
    eng.enable("OT")
    eng.record(ObjectChangeLog(object_type="OT", object_id="1", field="f", author="a", timestamp="2026-01-01T00:00:00Z"))
    eng.record(ObjectChangeLog(object_type="OT", object_id="1", field="f", author="a", timestamp="2026-06-01T00:00:00Z"))
    eng.record(ObjectChangeLog(object_type="OT", object_id="1", field="f", author="a", timestamp="2026-12-01T00:00:00Z"))
    result = eng.query(since="2026-03-01T00:00:00Z", until="2026-09-01T00:00:00Z")
    assert len(result) == 1
