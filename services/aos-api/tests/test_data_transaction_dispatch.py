"""W2-#24 · Data Connection 事务类型补强测试。

data_transaction.apply_write_mode 是公共函数库，verify 其边界稳定性。
dispatch 集成已重构移除，本批不强行重新接入（避免破坏现状）。
"""
from __future__ import annotations

import pytest

from aos_api.data_transaction import (
    ALL_WRITE_MODES,
    WRITE_MODE_APPEND,
    WRITE_MODE_SNAPSHOT,
    WRITE_MODE_UPDATE,
    apply_write_mode,
    describe_write_modes,
    resolve_write_mode,
)


def test_all_write_modes_set_complete():
    assert ALL_WRITE_MODES == {"default", "append", "snapshot", "update"}


def test_resolve_defaults_to_default():
    assert resolve_write_mode(None) == "default"


def test_resolve_case_insensitive():
    assert resolve_write_mode("APPEND") == "append"
    assert resolve_write_mode("Snapshot") == "snapshot"
    assert resolve_write_mode("UPDATE") == "update"


def test_resolve_invalid_raises():
    with pytest.raises(Exception):
        resolve_write_mode("bogus")


def test_append_deduplicates_by_pk():
    existing = [{"id": 1, "v": "old"}]
    new = [{"id": 1, "v": "new"}, {"id": 2, "v": "b"}]
    result = apply_write_mode(existing, new, WRITE_MODE_APPEND)
    ids = {r["id"] for r in result}
    assert ids == {1, 2}


def test_snapshot_replaces_all():
    existing = [{"id": 1}, {"id": 2}, {"id": 3}]
    new = [{"id": 10}]
    result = apply_write_mode(existing, new, WRITE_MODE_SNAPSHOT)
    assert result == [{"id": 10}]


def test_update_merges_fields():
    existing = [{"id": 1, "a": 1, "b": 2}]
    new = [{"id": 1, "b": 20, "c": 3}]
    result = apply_write_mode(existing, new, WRITE_MODE_UPDATE)
    assert result[0] == {"id": 1, "a": 1, "b": 20, "c": 3}


def test_update_inserts_new_rows():
    existing = [{"id": 1}]
    new = [{"id": 2}]
    result = apply_write_mode(existing, new, WRITE_MODE_UPDATE)
    assert {r["id"] for r in result} == {1, 2}


def test_describe_write_modes_returns_four():
    modes = describe_write_modes()
    assert len(modes) == 4
    names = {m.get("mode") or m.get("name") for m in modes}
    assert names == {"default", "append", "snapshot", "update"}
