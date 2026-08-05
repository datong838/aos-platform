"""D1-W2: G4 DatasetSink 单元测试 (FR-D1-1)。

验证 sink_to_dataset:
  - 调用 data_os_store.persist_dataset 落地 meta_dataset
  - 调用 data_os_store.persist_dataset_history 落地历史
  - 调用 eng.add_build 记录 DatasetBuild
  - 返回的 ds.id 可构造 dataset://catalog/<rid> 合法 output_ref
  - scope 被传递到 persist_dataset（守门 org_id/project_id）
  - rows_written 为非负整数
  - 骨架行为（eng.create_dataset）仍工作（向后兼容）
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from aos_api import data_os_store
from aos_api.ec_dataset_sink import sink_to_dataset
from aos_api.phase5_pipeline_engine import Pipeline, get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")


@pytest.fixture(autouse=True)
def reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


def _make_pipeline() -> Pipeline:
    eng = get_engine()
    return eng.create_pipeline(TEST_SCOPE, name="p")


def test_sink_calls_persist_dataset_with_scope():
    """FR-D1-1 #1/#4: persist_dataset 被调用，且 scope 完整传递（守门 org_id/project_id）。"""
    eng = get_engine()
    pl = _make_pipeline()
    captured = {}

    def fake_persist_dataset(scope, item):
        captured["scope"] = scope
        captured["item"] = item

    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", fake_persist_dataset)
    monkey.setattr(
        data_os_store, "persist_dataset_history", lambda *a, **kw: None
    )
    try:
        sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    finally:
        monkey.undo()

    assert captured.get("scope") is TEST_SCOPE
    item = captured.get("item", {})
    assert item.get("rid", "").startswith("ri.dataset.")
    assert item.get("pipelineId") == pl.id
    assert item.get("status") == "READY"


def test_sink_calls_persist_dataset_history():
    """FR-D1-1 #1: persist_dataset_history 被调用，且以 rid 为键。"""
    eng = get_engine()
    pl = _make_pipeline()
    captured = {}

    def fake_history(scope, dataset_rid, entries):
        captured["rid"] = dataset_rid
        captured["entries"] = entries

    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkey.setattr(data_os_store, "persist_dataset_history", fake_history)
    try:
        ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    finally:
        monkey.undo()

    assert captured.get("rid") == ds.id
    assert isinstance(captured.get("entries"), list)
    assert len(captured["entries"]) == 1


def test_sink_adds_build_with_nonneg_rows_written():
    """FR-D1-1 #1/#3: eng.add_build 被调用，rows_written 为非负整数。"""
    eng = get_engine()
    pl = _make_pipeline()
    rows = [{"a": 1}, {"b": 2}, {"c": 3}]

    ds = sink_to_dataset(eng, TEST_SCOPE, pl, rows)

    builds = eng.list_builds(TEST_SCOPE, ds.id)
    assert len(builds) == 1
    build = builds[0]
    assert build.dataset_id == ds.id
    assert build.status == "success"
    assert isinstance(build.rows_written, int)
    assert build.rows_written == len(rows)
    assert build.rows_written >= 0


def test_sink_empty_rows_still_nonneg():
    """FR-D1-1 #3: 空输出列表 rows_written == 0（非负）。"""
    eng = get_engine()
    pl = _make_pipeline()

    ds = sink_to_dataset(eng, TEST_SCOPE, pl, [])

    builds = eng.list_builds(TEST_SCOPE, ds.id)
    assert len(builds) == 1
    assert builds[0].rows_written == 0


def test_sink_returns_dataset_with_rid_id():
    """FR-D1-1 #2: 返回的 ds.id 是 rid，可构造 dataset://catalog/<rid> 合法 output_ref。

    合法约束：scheme=dataset, netloc 非空, 无 query/fragment, ≤512 字符。
    """
    eng = get_engine()
    pl = _make_pipeline()

    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkey.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)
    try:
        ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    finally:
        monkey.undo()

    # ds.id 应该是 ri.dataset.<...> 格式
    assert ds.id.startswith("ri.dataset.")

    output_ref = f"dataset://catalog/{ds.id}"
    assert len(output_ref) <= 512
    parsed = urlsplit(output_ref)
    assert parsed.scheme == "dataset"
    assert bool(parsed.netloc)  # 必须有 netloc (catalog)
    assert not parsed.query
    assert not parsed.fragment


def test_sink_backward_compat_dataset_resolver_sees_dataset():
    """FR-D1-1 向后兼容: 骨架行为仍工作 — ds 在 eng._datasets 中，dataset_resolver 能找到。"""
    eng = get_engine()
    pl = _make_pipeline()

    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkey.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)
    try:
        ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    finally:
        monkey.undo()

    # ds 仍在 engine 的内存 store 中（骨架行为）
    assert eng.get_dataset(TEST_SCOPE, ds.id) is ds

    # dataset_resolver 能找到（与 ec_live_executor 集成）
    from aos_api.ec_pipeline_resolvers import dataset_resolver

    output_ref = f"dataset://catalog/{ds.id}"
    assert dataset_resolver(output_ref) is True


def test_sink_rid_unique_per_call():
    """rid 每次调用唯一（避免 sink 多次冲突）。"""
    eng = get_engine()
    pl = _make_pipeline()

    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkey.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)
    try:
        ds1 = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
        ds2 = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 2}])
    finally:
        monkey.undo()

    assert ds1.id != ds2.id
