"""D1-W2: G4 DatasetSink 端到端集成测试 (FR-D1-1).

验证 sink_to_dataset 与 ec_live_executor 的端到端行为：
- output_ref 格式为 dataset://catalog/<rid>
- rows_read / rows_written 为非负整数
- scope 守门：落 meta_dataset 时带 (org_id, project_id)
- 跨 scope 写入失败关闭（persist_dataset 抛异常时降级为 warning 不阻塞）
- persist_dataset / persist_dataset_history 失败降级为 warning 不阻塞 sink 流程
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from aos_api import data_os_store
from aos_api.ec_dataset_sink import sink_to_dataset
from aos_api.errors import ApiError
from aos_api.phase5_pipeline_engine import Pipeline, get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("other-org", "other-project")


@pytest.fixture(autouse=True)
def reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


def _make_pipeline() -> Pipeline:
    eng = get_engine()
    return eng.create_pipeline(TEST_SCOPE, name="p")


def _stub_persist(monkeypatch: pytest.MonkeyPatch) -> dict:
    """把 data_os_store.persist_dataset / persist_dataset_history 替换为 noop，
    返回捕获字典。"""
    captured: dict = {}

    def fake_persist_dataset(scope, item):
        captured["scope"] = scope
        captured["item"] = item

    def fake_persist_history(scope, dataset_rid, entries):
        captured["history_rid"] = dataset_rid
        captured["history_entries"] = entries

    monkeypatch.setattr(data_os_store, "persist_dataset", fake_persist_dataset)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", fake_persist_history)
    return captured


# ── 1. output_ref 格式 ──


def test_output_ref_format_via_live_executor(monkeypatch):
    """ec_live_executor 返回的 output_ref 格式为 dataset://catalog/<rid>。

    合法约束：scheme=dataset, netloc=catalog, path=/<rid>, rid 以 ri.dataset. 开头。
    """
    from aos_api import ec_live_executor as mod

    # mock source/transform/sink_ot，只验证 sink_dataset 行为
    sample_rows = [{"a": 1}, {"b": 2}]
    monkeypatch.setattr(mod, "fetch_source_rows", lambda **kw: sample_rows)
    monkeypatch.setattr(mod, "apply_derived_metrics", lambda rows, p: rows)
    monkeypatch.setattr(mod, "build_link_rows", lambda rows, p: rows)
    monkeypatch.setattr(mod, "sink_to_ot", lambda *a, **kw: {"objects_written": 0, "links_written": 0})
    _stub_persist(monkeypatch)

    result = mod.ec_live_executor(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input={},
        execution_kind="schedule",
        cancel_event=None,
        deadline=0,
        scope=TEST_SCOPE,
    )

    output_ref = result["output_ref"]
    assert output_ref.startswith("dataset://catalog/ri.dataset.")
    parsed = urlsplit(output_ref)
    assert parsed.scheme == "dataset"
    assert parsed.netloc == "catalog"
    assert parsed.path.startswith("/ri.dataset.")
    assert not parsed.query
    assert not parsed.fragment
    assert len(output_ref) <= 512


def test_output_ref_rid_matches_returned_dataset(monkeypatch):
    """ec_live_executor 返回的 output_ref 中的 rid 与 sink_to_dataset 返回的 ds.id 一致。"""
    from aos_api import ec_live_executor as mod

    monkeypatch.setattr(mod, "fetch_source_rows", lambda **kw: [{"a": 1}])
    monkeypatch.setattr(mod, "apply_derived_metrics", lambda rows, p: rows)
    monkeypatch.setattr(mod, "build_link_rows", lambda rows, p: rows)
    monkeypatch.setattr(mod, "sink_to_ot", lambda *a, **kw: {"objects_written": 0, "links_written": 0})
    _stub_persist(monkeypatch)

    result = mod.ec_live_executor(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input={},
        execution_kind="schedule",
        cancel_event=None,
        deadline=0,
        scope=TEST_SCOPE,
    )

    # output_ref 中的 rid 应该是合法的 ri.dataset.<hex8>
    rid = result["output_ref"].split("/")[-1]
    assert rid.startswith("ri.dataset.")
    # rid 在 engine 中能找到对应 dataset
    eng = get_engine()
    assert eng.get_dataset(TEST_SCOPE, rid) is not None


# ── 2. rows_read / rows_written 非负整数 ──


def test_rows_read_written_nonneg_int(monkeypatch):
    """ec_live_executor 返回的 rows_read / rows_written 为非负整数。"""
    from aos_api import ec_live_executor as mod

    sample_rows = [{"a": 1}, {"b": 2}, {"c": 3}]
    monkeypatch.setattr(mod, "fetch_source_rows", lambda **kw: sample_rows)
    monkeypatch.setattr(mod, "apply_derived_metrics", lambda rows, p: rows)
    monkeypatch.setattr(mod, "build_link_rows", lambda rows, p: rows)
    monkeypatch.setattr(mod, "sink_to_ot", lambda *a, **kw: {"objects_written": 0, "links_written": 0})
    _stub_persist(monkeypatch)

    result = mod.ec_live_executor(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input={},
        execution_kind="schedule",
        cancel_event=None,
        deadline=0,
        scope=TEST_SCOPE,
    )

    assert isinstance(result["rows_read"], int)
    assert isinstance(result["rows_written"], int)
    assert result["rows_read"] >= 0
    assert result["rows_written"] >= 0
    assert result["rows_read"] == 3
    assert result["rows_written"] == 3


def test_rows_read_written_zero_on_empty_input(monkeypatch):
    """空输入时 rows_read / rows_written == 0（非负边界）。"""
    from aos_api import ec_live_executor as mod

    monkeypatch.setattr(mod, "fetch_source_rows", lambda **kw: [])
    monkeypatch.setattr(mod, "apply_derived_metrics", lambda rows, p: rows)
    monkeypatch.setattr(mod, "build_link_rows", lambda rows, p: rows)
    monkeypatch.setattr(mod, "sink_to_ot", lambda *a, **kw: {"objects_written": 0, "links_written": 0})
    _stub_persist(monkeypatch)

    result = mod.ec_live_executor(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input={},
        execution_kind="schedule",
        cancel_event=None,
        deadline=0,
        scope=TEST_SCOPE,
    )

    assert result["rows_read"] == 0
    assert result["rows_written"] == 0


# ── 3. scope 守门 ──


def test_scope_passed_to_persist_dataset(monkeypatch):
    """落 meta_dataset 时带 (org_id, project_id)：scope 完整传递给 persist_dataset。"""
    eng = get_engine()
    pl = _make_pipeline()
    captured = _stub_persist(monkeypatch)

    sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])

    assert captured["scope"] is TEST_SCOPE
    item = captured["item"]
    assert item["rid"].startswith("ri.dataset.")
    assert item["pipelineId"] == pl.id


def test_scope_passed_to_persist_dataset_history(monkeypatch):
    """落 meta_dataset_history 时 scope 完整传递，且以 rid 为键。"""
    eng = get_engine()
    pl = _make_pipeline()
    captured = _stub_persist(monkeypatch)

    ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])

    assert captured["history_rid"] == ds.id
    assert captured["scope"] is TEST_SCOPE
    entries = captured["history_entries"]
    assert isinstance(entries, list)
    assert len(entries) == 1
    assert entries[0]["rowsWritten"] == 1


def test_different_scope_isolated(monkeypatch):
    """不同 scope 的 sink 互不干扰：TEST_SCOPE 与 OTHER_SCOPE 的 dataset 隔离。"""
    eng = get_engine()
    pl_a = eng.create_pipeline(TEST_SCOPE, name="pa")
    pl_b = eng.create_pipeline(OTHER_SCOPE, name="pb")
    _stub_persist(monkeypatch)

    ds_a = sink_to_dataset(eng, TEST_SCOPE, pl_a, [{"a": 1}])
    ds_b = sink_to_dataset(eng, OTHER_SCOPE, pl_b, [{"b": 2}])

    # 两个 dataset 在各自的 scope 下可见，跨 scope 不可见
    assert eng.get_dataset(TEST_SCOPE, ds_a.id) is ds_a
    assert eng.get_dataset(OTHER_SCOPE, ds_a.id) is None
    assert eng.get_dataset(OTHER_SCOPE, ds_b.id) is ds_b
    assert eng.get_dataset(TEST_SCOPE, ds_b.id) is None


# ── 4. 跨 scope 写入失败关闭 ──


def test_persist_dataset_tenant_scope_conflict_degraded(monkeypatch):
    """persist_dataset 抛 TENANT_SCOPE_CONFLICT 时降级为 warning，sink 不阻塞。

    场景：meta_dataset 的 ON CONFLICT WHERE 子句拒绝跨 scope 写入，
    _assert_scoped_upsert 抛 ApiError("TENANT_SCOPE_CONFLICT")。
    sink_to_dataset 捕获后降级为 warning，仍返回 ds（骨架行为）。
    """
    eng = get_engine()
    pl = _make_pipeline()

    def raise_scope_conflict(scope, item):
        raise ApiError(
            code="TENANT_SCOPE_CONFLICT",
            message="dataset id belongs to another or unresolved tenant",
            status_code=409,
        )

    monkeypatch.setattr(data_os_store, "persist_dataset", raise_scope_conflict)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)

    # sink_to_dataset 不抛异常（降级为 warning）
    ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    assert ds is not None
    assert ds.id.startswith("ri.dataset.")


def test_persist_dataset_required_scope_violation(monkeypatch):
    """persist_dataset 抛 TENANT_SCOPE_REQUIRED 时降级为 warning，sink 不阻塞。"""
    eng = get_engine()
    pl = _make_pipeline()

    def raise_required(scope, item):
        raise ApiError(
            code="TENANT_SCOPE_REQUIRED",
            message="Data OS mutation requires TenantScope",
            status_code=400,
        )

    monkeypatch.setattr(data_os_store, "persist_dataset", raise_required)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)

    ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    assert ds is not None


# ── 5. persist 失败降级 ──


def test_persist_dataset_failure_degraded_to_warning(monkeypatch):
    """persist_dataset 抛通用 Exception 时降级为 warning，sink 不阻塞。"""
    eng = get_engine()
    pl = _make_pipeline()

    def boom(scope, item):
        raise RuntimeError("db connection lost")

    monkeypatch.setattr(data_os_store, "persist_dataset", boom)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)

    ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    assert ds is not None
    # Dataset 仍在 engine 中（骨架行为）
    assert eng.get_dataset(TEST_SCOPE, ds.id) is ds


def test_persist_dataset_history_failure_degraded(monkeypatch):
    """persist_dataset_history 抛异常时降级为 warning，sink 不阻塞。"""
    eng = get_engine()
    pl = _make_pipeline()

    monkeypatch.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)

    def boom_history(scope, rid, entries):
        raise RuntimeError("history table locked")

    monkeypatch.setattr(data_os_store, "persist_dataset_history", boom_history)

    ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    assert ds is not None


def test_add_build_failure_degraded(monkeypatch):
    """eng.add_build 抛异常时降级为 warning，sink 不阻塞。

    场景：Dataset 因并发被删除，add_build 找不到 dataset 抛 KeyError。
    """
    eng = get_engine()
    pl = _make_pipeline()
    _stub_persist(monkeypatch)

    # 预先删除 dataset 让 add_build 失败
    original_add_build = eng.add_build

    def boom_add_build(scope, dataset_id, **kwargs):
        raise KeyError(f"Dataset {dataset_id} not found")

    monkeypatch.setattr(eng, "add_build", boom_add_build)

    ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    assert ds is not None


def test_all_persist_fail_sink_still_returns_dataset(monkeypatch):
    """所有 persist 都失败时，sink 仍返回 dataset（骨架行为，向后兼容）。"""
    eng = get_engine()
    pl = _make_pipeline()

    def boom(scope, *args, **kwargs):
        raise RuntimeError("persist failed")

    monkeypatch.setattr(data_os_store, "persist_dataset", boom)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", boom)
    monkeypatch.setattr(eng, "add_build", boom)

    ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}])
    assert ds is not None
    assert ds.id.startswith("ri.dataset.")


# ── 6. 端到端集成：sink_to_dataset + ec_live_executor ──


def test_live_executor_sink_integration_rows_consistent(monkeypatch):
    """ec_live_executor 端到端：rows_read == len(input_rows), rows_written == len(output_rows)。"""
    from aos_api import ec_live_executor as mod

    sample_rows = [{"a": 1}, {"b": 2}]
    monkeypatch.setattr(mod, "fetch_source_rows", lambda **kw: sample_rows)
    monkeypatch.setattr(mod, "apply_derived_metrics", lambda rows, p: rows)
    monkeypatch.setattr(mod, "build_link_rows", lambda rows, p: rows)
    monkeypatch.setattr(mod, "sink_to_ot", lambda *a, **kw: {"objects_written": 0, "links_written": 0})
    _stub_persist(monkeypatch)

    result = mod.ec_live_executor(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input={},
        execution_kind="schedule",
        cancel_event=None,
        deadline=0,
        scope=TEST_SCOPE,
    )

    assert result["rows_read"] == len(sample_rows)
    assert result["rows_written"] == len(sample_rows)
    assert result["output_ref"].startswith("dataset://catalog/ri.dataset.")


def test_live_executor_sink_dataset_resolver_sees_dataset(monkeypatch):
    """ec_live_executor 产出的 dataset 能被 dataset_resolver 找到（向后兼容）。"""
    from aos_api import ec_live_executor as mod
    from aos_api.ec_pipeline_resolvers import dataset_resolver

    monkeypatch.setattr(mod, "fetch_source_rows", lambda **kw: [{"a": 1}])
    monkeypatch.setattr(mod, "apply_derived_metrics", lambda rows, p: rows)
    monkeypatch.setattr(mod, "build_link_rows", lambda rows, p: rows)
    monkeypatch.setattr(mod, "sink_to_ot", lambda *a, **kw: {"objects_written": 0, "links_written": 0})
    _stub_persist(monkeypatch)

    result = mod.ec_live_executor(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input={},
        execution_kind="schedule",
        cancel_event=None,
        deadline=0,
        scope=TEST_SCOPE,
    )

    assert dataset_resolver(result["output_ref"]) is True
