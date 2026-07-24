"""W2-#24 · Data Connection 事务类型 单元测试。"""
from __future__ import annotations

import pytest

from aos_api.data_transaction import (
    ALL_WRITE_MODES,
    TransactionError,
    apply_write_mode,
    describe_write_modes,
    resolve_write_mode,
)


@pytest.fixture
def existing_rows():
    return [
        {"id": "A", "name": "Alice", "score": 90},
        {"id": "B", "name": "Bob", "score": 85},
        {"id": "C", "name": "Carol", "score": 92},
    ]


@pytest.fixture
def new_rows():
    return [
        {"id": "B", "name": "Bob", "score": 95},  # 更新 B
        {"id": "D", "name": "Dave", "score": 88},  # 新增 D
    ]


# ── resolve_write_mode ──

def test_resolve_default():
    assert resolve_write_mode(None) == "default"


def test_resolve_valid():
    assert resolve_write_mode("snapshot") == "snapshot"
    assert resolve_write_mode("UPDATE") == "update"


def test_resolve_invalid():
    with pytest.raises(TransactionError) as exc:
        resolve_write_mode("bogus")
    assert "bogus" in str(exc.value)


# ── APPEND mode ──

def test_append_preserves_existing(existing_rows, new_rows):
    result = apply_write_mode(existing_rows, new_rows, "append")
    assert len(result) == 4  # 3 existing + 1 new (D) (B already exists)

    ids = {r["id"] for r in result}
    assert ids == {"A", "B", "C", "D"}

    # 验证 B 的数据没有被新数据覆盖
    b_row = next(r for r in result if r["id"] == "B")
    assert b_row["score"] == 85  # 保留旧的


# ── SNAPSHOT mode ──

def test_snapshot_replaces_all(existing_rows, new_rows):
    result = apply_write_mode(existing_rows, new_rows, "snapshot")
    assert len(result) == 2  # 只有 new_rows

    ids = {r["id"] for r in result}
    assert ids == {"B", "D"}
    assert "A" not in ids
    assert "C" not in ids


# ── UPDATE mode ──

def test_update_upserts(existing_rows, new_rows):
    result = apply_write_mode(existing_rows, new_rows, "update")
    assert len(result) == 4  # A, B(updated), C, D(new)

    ids = {r["id"] for r in result}
    assert ids == {"A", "B", "C", "D"}

    # B 被更新
    b_row = next(r for r in result if r["id"] == "B")
    assert b_row["score"] == 95  # 新值
    assert b_row["name"] == "Bob"

    # D 是新增
    d_row = next(r for r in result if r["id"] == "D")
    assert d_row["score"] == 88


def test_update_merges_fields(existing_rows):
    """Update 模式合并：新字段覆盖，旧字段保留"""
    updates = [{"id": "A", "score": 100}]  # 只更新 score，name 不传
    result = apply_write_mode(existing_rows, updates, "update")
    a_row = next(r for r in result if r["id"] == "A")
    assert a_row["score"] == 100  # 新值覆盖
    assert a_row["name"] == "Alice"  # 旧值保留


# ── Custom primary key ──

def test_custom_primary_key():
    existing = [{"uid": 1, "name": "X"}, {"uid": 2, "name": "Y"}]
    new = [{"uid": 2, "name": "Y-Updated"}, {"uid": 3, "name": "Z"}]
    result = apply_write_mode(existing, new, "update", primary_key="uid")
    assert len(result) == 3  # 1, 2(updated), 3(new)

    r2 = next(r for r in result if r["uid"] == 2)
    assert r2["name"] == "Y-Updated"


# ── describe_write_modes ──

def test_describe_write_modes():
    modes = describe_write_modes()
    assert len(modes) == 4
    mode_names = {m["mode"] for m in modes}
    assert mode_names == ALL_WRITE_MODES
    for m in modes:
        assert "label" in m
        assert "description" in m
        assert m["idempotent"] is True


# ── Edge cases ──

def test_empty_existing():
    result = apply_write_mode([], [{"id": 1, "val": "x"}], "append")
    assert len(result) == 1


def test_empty_new():
    existing = [{"id": 1, "val": "x"}]
    result = apply_write_mode(existing, [], "snapshot")
    assert len(result) == 0


def test_snapshot_preserves_order():
    new = [{"id": "Z"}, {"id": "A"}, {"id": "M"}]
    result = apply_write_mode([{"id": "X"}], new, "snapshot")
    assert [r["id"] for r in result] == ["Z", "A", "M"]


def test_update_null_pk_skipped():
    """没有主键的行不参与 upsert 匹配，被静默跳过"""
    existing = [{"id": 1, "val": "a"}]
    new = [{"val": "b"}]  # 无 id → 不会匹配也不会新增
    result = apply_write_mode(existing, new, "update")
    assert len(result) == 1  # 仅保留旧行，无主键的新行被跳过
