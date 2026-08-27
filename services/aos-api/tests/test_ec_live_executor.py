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


@pytest.mark.parametrize(
    ("pipeline_id", "target_ot", "raw_row"),
    [
        ("P01-shop-qyh", "Shop", {"site_id": 1}),
        ("P02-product-qyh", "Product", {"goods_id": 1}),
        ("P03-sku-qyh", "ProductSku", {"sku_id": 1}),
        ("P05-order-qyh", "Order", {"order_id": 1}),
        ("P08-customer-qyh", "CustomerLite", {"member_id": 1}),
        ("P09-weapp-qyh", "Weapp", {"weapp_id": 1}),
        ("P10-config-qyh", "SystemConfig", {"id": 1}),
        ("P11-review-qyh", "ProductReview", {"evaluate_id": 1}),
    ],
)
def test_snapshot_observation_allowlist_is_scoped_and_stable(
    pipeline_id, target_ot, raw_row
):
    from types import SimpleNamespace
    from aos_api.ec_live_executor import _stamp_snapshot_observation

    rows = [dict(raw_row), dict(raw_row)]
    pipeline = SimpleNamespace(
        id=pipeline_id,
        write_mode="SNAPSHOT",
        config={"target_ot": target_ot},
    )
    _stamp_snapshot_observation(
        pipeline=pipeline,
        rows=rows,
        run_started_at=1700005000.25,
    )
    assert [row["_aos_observed_at"] for row in rows] == [1700005000.25, 1700005000.25]


def test_snapshot_observation_preserves_p02_upsert_compatibility():
    from types import SimpleNamespace
    from aos_api.ec_live_executor import _stamp_snapshot_observation

    rows = [{"goods_id": 3}]
    _stamp_snapshot_observation(
        pipeline=SimpleNamespace(
            id="P02-product-qyh",
            write_mode="UPSERT",
            config={"target_ot": "Product"},
        ),
        rows=rows,
        run_started_at=1700005000.25,
    )
    assert rows[0]["_aos_observed_at"] == 1700005000.25


def test_snapshot_observation_advances_batch_version_without_rewriting_business_time():
    from types import SimpleNamespace

    from aos_api.ec_live_executor import _stamp_snapshot_observation
    from aos_api.ec_normalizer import normalize_rows

    pipeline = SimpleNamespace(
        id="P05-order-qyh",
        write_mode="SNAPSHOT",
        config={"target_ot": "Order"},
    )
    raw = {
        "order_id": 1,
        "create_time": 1700000000,
        "modify_time": 1700001000,
    }
    versions = []
    for observed_at in (1700005000.0, 1700006000.0):
        rows = [dict(raw)]
        _stamp_snapshot_observation(
            pipeline=pipeline,
            rows=rows,
            run_started_at=observed_at,
        )
        versions.append(normalize_rows(rows, pipeline)[0])

    assert versions[0]["source_updated_at"] != versions[1]["source_updated_at"]
    assert versions[0]["properties"] == versions[1]["properties"]
    assert versions[0]["properties"]["updatedAt"] == "2023-11-14T22:30:00Z"


@pytest.mark.parametrize(
    ("pipeline", "row"),
    [
        (
            {
                "id": "P04-category-qyh",
                "write_mode": "SNAPSHOT",
                "config": {"target_ot": "Category"},
            },
            {"category_id": 1},
        ),
        (
            {"id": "P06-line-qyh", "write_mode": "SNAPSHOT", "config": {"target_ot": "OrderLine"}},
            {"order_goods_id": 1},
        ),
        (
            {
                "id": "P07-shipment-qyh",
                "write_mode": "SNAPSHOT",
                "config": {"target_ot": "Shipment"},
            },
            {"id": 1},
        ),
        (
            {"id": "P12-payment-qyh", "write_mode": "SNAPSHOT", "config": {"target_ot": "Payment"}},
            {"id": 1},
        ),
        (
            {"id": "P05-order-qyh", "write_mode": "APPEND", "config": {"target_ot": "Order"}},
            {"order_id": 1},
        ),
        (
            {"id": "P05-order-qyh", "write_mode": "SNAPSHOT", "config": {"target_ot": "Product"}},
            {"order_id": 1},
        ),
    ],
)
def test_snapshot_observation_ignores_non_allowlisted_or_mismatched_pipelines(
    pipeline, row
):
    from types import SimpleNamespace
    from aos_api.ec_live_executor import _stamp_snapshot_observation

    rows = [dict(row)]
    _stamp_snapshot_observation(
        pipeline=SimpleNamespace(**pipeline),
        rows=rows,
        run_started_at=1700005000.25,
    )
    assert "_aos_observed_at" not in rows[0]


def test_snapshot_observation_does_not_rewrite_normalized_rows():
    from types import SimpleNamespace
    from aos_api.ec_live_executor import _stamp_snapshot_observation

    rows = [{"ot": "Order", "source_pk": "1"}]
    _stamp_snapshot_observation(
        pipeline=SimpleNamespace(
            id="P05-order-qyh",
            write_mode="SNAPSHOT",
            config={"target_ot": "Order"},
        ),
        rows=rows,
        run_started_at=1700005000.25,
    )
    assert "_aos_observed_at" not in rows[0]


def test_snapshot_observation_fails_closed_without_stable_run_time():
    from types import SimpleNamespace
    from aos_api.ec_live_executor import _stamp_snapshot_observation

    with pytest.raises(RuntimeError, match="stable run_started_at"):
        _stamp_snapshot_observation(
            pipeline=SimpleNamespace(
                id="P05-order-qyh",
                write_mode="SNAPSHOT",
                config={"target_ot": "Order"},
            ),
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
