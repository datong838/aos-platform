"""G2: 生产 executor 骨架测试。

ec-live-v1 executor 注册后，execution_mode="live" 的 pipeline 不再被
preflight 以 PIPELINE_EXECUTOR_MISSING 拒绝，能真实执行并产出可被
dataset_resolver 验证的 evidence。
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")


@pytest.fixture(autouse=True)
def reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield


def _register_live_stack(eng):
    from aos_api.ec_live_executor import ec_live_executor
    from aos_api.ec_pipeline_resolvers import dataset_resolver

    def _contract_executor(**kwargs):
        # 本文件验证 Phase5 执行与 evidence/resolver 合同，不读外部数据源。
        # 真实 Source 节点与 JdbcConnectorRuntime 由专项测试覆盖。
        with (
            patch("aos_api.ec_live_executor.fetch_source_rows", return_value=[]),
            patch("aos_api.ec_live_executor.ensure_store_assembled", return_value=None),
            patch("aos_api.data_os_store.persist_dataset", return_value=None),
            patch("aos_api.data_os_store.persist_dataset_history", return_value=None),
        ):
            return ec_live_executor(**kwargs)

    eng.register_executor("ec-live-v1", _contract_executor)
    eng.register_evidence_resolver("dataset", dataset_resolver)


def test_live_pipeline_succeeds_with_ec_live_executor():
    eng = get_engine()
    _register_live_stack(eng)

    pl = eng.create_pipeline(
        TEST_SCOPE, name="p", executor_id="ec-live-v1", execution_mode="live"
    )
    sc = eng.create_schedule(TEST_SCOPE, name="s", pipeline_id=pl.id)

    run = eng.run_schedule(TEST_SCOPE, sc.id)

    assert run.status == "succeeded", f"expected succeeded, got {run.status} ({run.error_code})"
    assert run.error_code == ""
    assert run.output_ref.startswith("dataset://catalog/")
    assert run.mode == "live"


def test_live_executor_receives_scope():
    eng = get_engine()
    captured = {}

    def _wrapping_executor(**kwargs):
        captured["scope"] = kwargs.get("scope")
        return {"output_ref": "dataset://catalog/scope-check", "rows_read": 0, "rows_written": 0}

    eng.register_executor("ec-live-v1", _wrapping_executor)
    from aos_api.ec_pipeline_resolvers import dataset_resolver

    eng.register_evidence_resolver("dataset", dataset_resolver)

    pl = eng.create_pipeline(
        TEST_SCOPE, name="p", executor_id="ec-live-v1", execution_mode="live"
    )
    sc = eng.create_schedule(TEST_SCOPE, name="s", pipeline_id=pl.id)
    eng.run_schedule(TEST_SCOPE, sc.id)

    assert captured.get("scope") is not None
    assert captured["scope"].org_id == TEST_SCOPE.org_id


def test_live_executor_receives_stable_run_started_at():
    eng = get_engine()
    captured = {}

    def _wrapping_executor(**kwargs):
        captured["run_started_at"] = kwargs.get("run_started_at")
        return {"output_ref": "dataset://catalog/run-start-check", "rows_read": 0, "rows_written": 0}

    eng.register_executor("ec-live-v1", _wrapping_executor)
    eng.register_evidence_resolver("dataset", lambda _ref: True)
    pl = eng.create_pipeline(
        TEST_SCOPE, name="p", executor_id="ec-live-v1", execution_mode="live"
    )
    sc = eng.create_schedule(TEST_SCOPE, name="s", pipeline_id=pl.id)
    before = time.time()
    run = eng.run_schedule(TEST_SCOPE, sc.id)
    after = time.time()

    assert run.status == "succeeded"
    assert before <= captured["run_started_at"] <= after


def test_p02_snapshot_observation_is_scoped_and_stable():
    from types import SimpleNamespace
    from aos_api.ec_live_executor import _stamp_snapshot_observation

    rows = [{"goods_id": 1}, {"goods_id": 2}]
    pipeline = SimpleNamespace(id="P02-product-qyh", write_mode="UPSERT")
    _stamp_snapshot_observation(
        pipeline=pipeline,
        rows=rows,
        run_started_at=1700005000.25,
    )
    assert [row["_aos_observed_at"] for row in rows] == [1700005000.25, 1700005000.25]

    snapshot_rows = [{"goods_id": 3}]
    _stamp_snapshot_observation(
        pipeline=SimpleNamespace(id="P02-product-qyh", write_mode="SNAPSHOT"),
        rows=snapshot_rows,
        run_started_at=1700005000.25,
    )
    assert snapshot_rows[0]["_aos_observed_at"] == 1700005000.25

    other = [{"order_id": 1}]
    _stamp_snapshot_observation(
        pipeline=SimpleNamespace(id="P05-order-qyh", write_mode="SNAPSHOT"),
        rows=other,
        run_started_at=1700005000.25,
    )
    assert "_aos_observed_at" not in other[0]


def test_p02_snapshot_observation_fails_closed_without_stable_run_time():
    from types import SimpleNamespace
    from aos_api.ec_live_executor import _stamp_snapshot_observation

    with pytest.raises(RuntimeError, match="stable run_started_at"):
        _stamp_snapshot_observation(
            pipeline=SimpleNamespace(id="P02-product-qyh", write_mode="SNAPSHOT"),
            rows=[{"goods_id": 1}],
            run_started_at=None,
        )


def test_live_executor_output_ref_verifiable_by_resolver():
    eng = get_engine()
    _register_live_stack(eng)

    pl = eng.create_pipeline(
        TEST_SCOPE, name="p", executor_id="ec-live-v1", execution_mode="live"
    )
    sc = eng.create_schedule(TEST_SCOPE, name="s", pipeline_id=pl.id)
    run = eng.run_schedule(TEST_SCOPE, sc.id)

    assert run.status == "succeeded"
    from aos_api.ec_pipeline_resolvers import dataset_resolver

    assert dataset_resolver(run.output_ref) is True


def test_live_executor_evidence_has_row_counts():
    eng = get_engine()
    _register_live_stack(eng)

    pl = eng.create_pipeline(
        TEST_SCOPE, name="p", executor_id="ec-live-v1", execution_mode="live"
    )
    sc = eng.create_schedule(TEST_SCOPE, name="s", pipeline_id=pl.id)
    run = eng.run_schedule(TEST_SCOPE, sc.id)

    assert run.status == "succeeded"
    assert isinstance(run.rows_read, int)
    assert isinstance(run.rows_written, int)
    assert run.rows_read >= 0
    assert run.rows_written >= 0
