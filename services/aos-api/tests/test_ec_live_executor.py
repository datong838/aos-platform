"""G2: 生产 executor 骨架测试。

ec-live-v1 executor 注册后，execution_mode="live" 的 pipeline 不再被
preflight 以 PIPELINE_EXECUTOR_MISSING 拒绝，能真实执行并产出可被
dataset_resolver 验证的 evidence。
"""

from __future__ import annotations

import time

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

    eng.register_executor("ec-live-v1", ec_live_executor)
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

    from aos_api.ec_live_executor import ec_live_executor

    def _wrapping_executor(**kwargs):
        captured["scope"] = kwargs.get("scope")
        return ec_live_executor(**kwargs)

    from aos_api.ec_pipeline_resolvers import dataset_resolver

    eng.register_executor("ec-live-v1", _wrapping_executor)
    eng.register_evidence_resolver("dataset", dataset_resolver)

    pl = eng.create_pipeline(
        TEST_SCOPE, name="p", executor_id="ec-live-v1", execution_mode="live"
    )
    sc = eng.create_schedule(TEST_SCOPE, name="s", pipeline_id=pl.id)
    eng.run_schedule(TEST_SCOPE, sc.id)

    assert captured.get("scope") is not None
    assert captured["scope"].org_id == TEST_SCOPE.org_id


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
