"""D1-W1: P07 Shipment 端到端测试（FR-D1-6 四段实施 + FR-D1-7 overdue_hours）。

P07 Shipment 规格（frozen/02）：
- 源表/主键: ns_express_delivery_package / id
- 源过滤: site_id=1
- 增量策略: 每日快照
- 目标 OT: Shipment
- 唯一键: niushop:1:{id}
- 关键映射: 指向 Order；delivery_no 物流号按敏感级别遮罩
- Link: ships: Shipment → Order (order_id)（由 W3 ec_link_builder 构造）
- 派生指标: overdue_hours（SLA_HOURS=48；delivery_time=0 AND Order.pay_time>0 时
  = max(0, (now - Order.pay_time - 48h) / 3600)；否则 null）
- 数据现状: count=19

测试覆盖 6 项（FR-D1-6 四段实施）：
1. 初装：首次全量读取 → 落地 OT + Dataset + overdue_hours 写入 properties
2. 增量：基于复合游标增量读取 → 幂等 upsert
3. 重跑：重复执行同一批次 → 验证幂等
4. 断点：模拟中断后恢复 → 验证 checkpoint CAS 不前移
5. 重复：相同版本+不同 hash → 验证冲突检测
6. 越租户：跨 org/workspace 写入 → 验证拒绝（fail-closed）

mock 策略：
- fetch_source_rows: mock 返回 normalized shipment rows（绕过 MySQL 依赖）
- build_link_rows: mock 透传（ships Link 由 W3 构造，本测试只验证 overdue_hours）
- data_os_store: mock no-op（避免 DB 副作用）
- _now_utc: patch 固定时间（让 overdue_hours 断言确定）
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aos_api import data_os_store
from aos_api.ecom_core_models import (
    BatchCommand,
    BatchResult,
    EcomConsistencyError,
    SyncScope,
)
from aos_api.ec_live_executor import ec_live_executor
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")
FIXED_NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════
# FakeStore（与 P01 测试一致，模拟一致性内核）
# ═══════════════════════════════════════════════


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，模拟一致性内核行为。

    内容指纹排除 expected_checkpoint_version（CAS 守卫不属于批次内容）。
    """

    def __init__(self) -> None:
        self.calls: list[BatchCommand] = []
        self.derived_calls: list[object] = []
        self._checkpoints: dict[tuple, int] = {}
        self._idempotency: dict[tuple, tuple] = {}

    @staticmethod
    def _content_fingerprint(command: BatchCommand) -> tuple:
        return (
            command.scope.key(),
            command.next_checkpoint.source_updated_at_utc,
            command.next_checkpoint.external_id,
            tuple(obj.model_dump(mode="python") for obj in command.ordered_objects()),
            tuple(link.model_dump(mode="python") for link in command.ordered_links()),
        )

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        self.calls.append(command)
        scope_key = command.scope.key()
        idem_key = (scope_key, command.idempotency_key)
        content = self._content_fingerprint(command)

        if idem_key in self._idempotency:
            if self._idempotency[idem_key] != content:
                raise EcomConsistencyError(
                    "IDEMPOTENCY_CONFLICT",
                    "idempotency key was already used with a different request",
                )
            return BatchResult(
                objects_written=len(command.objects),
                links_written=len(command.links),
                checkpoint_version=self._checkpoints.get(scope_key, 0),
                checkpoint=command.next_checkpoint,
                replayed=True,
            )

        self._idempotency[idem_key] = content
        if scope_key not in self._checkpoints:
            self._checkpoints[scope_key] = 0
        self._checkpoints[scope_key] += 1
        return BatchResult(
            objects_written=len(command.objects),
            links_written=len(command.links),
            checkpoint_version=self._checkpoints[scope_key],
            checkpoint=command.next_checkpoint,
        )

    def get_checkpoint(self, command: BatchCommand) -> dict | None:
        scope_key = command.scope.key()
        version = self._checkpoints.get(scope_key)
        if version is None:
            return None
        return {"version": version}

    def get_latest_authoritative_revision(self, _identity) -> int:
        return max(1, len(self.calls))

    def get_derived_revision(self, _identity, _object_type: str) -> int:
        return len(self.derived_calls)

    def update_derived_metrics(self, command):
        self.derived_calls.append(command)
        return SimpleNamespace(updated=True, replayed=False)


class TenantGuardStore(FakeStore):
    """只接受指定 scope 的 store，跨租户写入抛 TENANT_MISMATCH。"""

    def __init__(self, allowed_scope_key: tuple) -> None:
        super().__init__()
        self._allowed = allowed_scope_key

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        scope_key = command.scope.key()
        if scope_key != self._allowed:
            raise EcomConsistencyError(
                "TENANT_MISMATCH",
                f"scope {scope_key} does not match allowed {self._allowed}",
            )
        return super().apply_batch(command)


# ═══════════════════════════════════════════════
# fixtures
# ═══════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


@pytest.fixture(autouse=True)
def _mock_data_os_store():
    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkey.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)
    yield
    monkey.undo()


@pytest.fixture(autouse=True)
def _mock_build_links():
    """P07 的 ships Link 由 W3 构造，本测试 mock 透传，只验证 overdue_hours。"""
    with patch(
        "aos_api.ec_live_executor.build_link_rows",
        side_effect=lambda rows, pipeline: rows,
    ):
        yield


@pytest.fixture(autouse=True)
def _fixed_now():
    """patch _now_utc 返回固定时间，让 overdue_hours 断言确定。"""
    with patch("aos_api.ec_derived_metrics._now_utc", return_value=FIXED_NOW):
        yield


@pytest.fixture
def mock_fetch():
    with patch("aos_api.ec_live_executor.fetch_source_rows") as m:
        yield m


# ═══════════════════════════════════════════════
# row 工厂
# ═══════════════════════════════════════════════


def shipment_row(
    *,
    pkg_id: str = "1",
    order_id: str = "ord-1",
    delivery_time: int | None = 0,
    pay_time: float | None = None,
    when: datetime = FIXED_NOW,
) -> dict:
    """P07 Shipment 行（normalized executor 格式）。

    properties 包含 REQUIRED_PROPERTIES['Shipment'] 要求的字段。
    delivery_time / pay_time 是源字段（用于 overdue_hours 计算），
    放在 row 顶层（denormalized from Order）。

    默认 pay_time=72h前 → overdue_hours = (72-48)/1 = 24.0
    """
    if pay_time is None:
        pay_time = (FIXED_NOW - timedelta(hours=72)).timestamp()
    return {
        "ot": "Shipment",
        "source_pk": pkg_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "orderId": order_id,
            "status": "pending",
            "carrier": "SF",
            "trackingNo": f"SF{pkg_id}1234567890",
            "shippedAt": "2026-08-05T10:00:00+00:00",
            "updatedAt": "2026-08-05T10:00:00+00:00",
        },
        # 源字段（denormalized from Order，用于 overdue_hours 计算）
        "delivery_time": delivery_time,
        "pay_time": pay_time,
    }


def _make_pipeline(pid: str = "p07-shipment") -> SimpleNamespace:
    return SimpleNamespace(id=pid, config={})


def _run_executor(*, pipeline=None, scope=TEST_SCOPE):
    return ec_live_executor(
        pipeline=pipeline or _make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input=None,
        execution_kind="initial",
        cancel_event=None,
        deadline=time.time() + 30,
        scope=scope,
    )


def _inject_store(store: FakeStore) -> None:
    eng = get_engine()
    eng.ecom_consistency_store = store


# ═══════════════════════════════════════════════
# 1. 初装：首次全量读取 → 落地 OT + Dataset + overdue_hours
# ═══════════════════════════════════════════════


def test_p07_initial_load_lands_ot_dataset_and_overdue_hours(mock_fetch):
    """初装：首次全量读取 → 落地 OT + Dataset + overdue_hours 写入 properties。

    pay_time 在 FIXED_NOW 前 72h，SLA=48h → overdue_hours = (72-48)/1 = 24.0
    """
    mock_fetch.return_value = [shipment_row()]
    store = FakeStore()
    _inject_store(store)

    result = _run_executor()

    # OT 落地验证
    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    obj = command.objects[0]
    assert obj.object_type == "Shipment"
    assert obj.identity.external_id == "niushop:1:1"
    assert obj.identity.platform == "niushop"
    # overdue_hours 通过独立 CAS 命令写入，基础 properties 不再混入派生键。
    assert "overdue_hours" not in obj.properties
    assert store.derived_calls[0].derived_props["overdue_hours"] == 24.0

    # Dataset 落地验证
    assert result["output_ref"].startswith("dataset://catalog/")
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1


# ═══════════════════════════════════════════════
# 2. 增量：基于复合游标增量读取 → 幂等 upsert
# ═══════════════════════════════════════════════


def test_p07_incremental_snapshot_mode_idempotent_upsert(mock_fetch):
    """增量：P07 是快照模式，增量等价于重跑 → 幂等 upsert。

    第二次 expected_checkpoint_version=1（不退回 0）。
    """
    mock_fetch.return_value = [shipment_row()]
    store = FakeStore()
    _inject_store(store)

    _run_executor()
    _run_executor()

    assert len(store.calls) == 2
    assert store.calls[0].expected_checkpoint_version == 0
    assert store.calls[1].expected_checkpoint_version == 1


# ═══════════════════════════════════════════════
# 3. 重跑：重复执行同一批次 → 验证幂等
# ═══════════════════════════════════════════════


def test_p07_rerun_same_batch_idempotent_no_double_count(mock_fetch):
    """重跑：相同 key+相同 hash → 计数不翻倍。"""
    mock_fetch.return_value = [shipment_row()]
    store = FakeStore()
    _inject_store(store)

    first = _run_executor()
    second = _run_executor()

    assert first["rows_written"] == 1
    assert second["rows_written"] == 1
    assert len(store.calls) == 2
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


# ═══════════════════════════════════════════════
# 4. 断点：模拟中断后恢复 → 验证 checkpoint CAS 不前移
# ═══════════════════════════════════════════════


def test_p07_checkpoint_recovery_cas_not_moved_backward(mock_fetch):
    """断点恢复：首装后中断，重跑时 expected_checkpoint_version 不退回 0。"""
    mock_fetch.return_value = [shipment_row()]
    store = FakeStore()
    _inject_store(store)

    _run_executor()
    assert store.calls[0].expected_checkpoint_version == 0

    _run_executor()
    assert store.calls[1].expected_checkpoint_version == 1
    assert store.calls[1].expected_checkpoint_version >= store.calls[0].expected_checkpoint_version


# ═══════════════════════════════════════════════
# 5. 重复：相同版本+不同 hash → 验证冲突检测
# ═══════════════════════════════════════════════


def test_p07_same_version_different_hash_conflict_detected(mock_fetch):
    """相同版本+不同 hash → IDEMPOTENCY_CONFLICT。

    场景：首装 carrier="SF"，重跑时 carrier="YTO"
    （相同 source_pk + source_updated_at，但 properties 不同）。
    """
    store = FakeStore()
    _inject_store(store)

    mock_fetch.return_value = [shipment_row()]
    _run_executor()

    # 重跑：相同 cursor 但不同 carrier → 冲突
    mock_fetch.return_value = [shipment_row()]
    # 修改 properties 中的 carrier（通过直接修改返回值）
    modified_row = shipment_row()
    modified_row["properties"]["carrier"] = "YTO"
    mock_fetch.return_value = [modified_row]

    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor()

    assert caught.value.code == "IDEMPOTENCY_CONFLICT"
    assert len(store.calls) == 2
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


# ═══════════════════════════════════════════════
# 6. 越租户：跨 org/workspace 写入 → 验证拒绝（fail-closed）
# ═══════════════════════════════════════════════


def test_p07_cross_tenant_write_rejected_fail_closed(mock_fetch):
    """跨 org/workspace 写入 → TENANT_MISMATCH。"""
    allowed_scope = SyncScope(
        org_id="dev-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        stream="p07-shipment",
    )
    store = TenantGuardStore(allowed_scope_key=allowed_scope.key())
    _inject_store(store)

    other_scope = TenantScope("other-org", "other-project")
    mock_fetch.return_value = [shipment_row()]
    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor(scope=other_scope)

    assert caught.value.code == "TENANT_MISMATCH"


# ═══════════════════════════════════════════════
# 附加：overdue_hours 边界（通过 executor 端到端验证）
# ═══════════════════════════════════════════════


def test_p07_overdue_hours_for_delivered_uses_actual_duration(mock_fetch):
    """delivery_time>0（已发货）→ 按实际履约时长计算。"""
    mock_fetch.return_value = [shipment_row(delivery_time=1000)]
    store = FakeStore()
    _inject_store(store)

    _run_executor()

    assert store.derived_calls[0].derived_props["overdue_hours"] == 0.0


def test_p07_overdue_hours_null_when_not_paid(mock_fetch):
    """pay_time=0（未支付）→ overdue_hours=null。"""
    mock_fetch.return_value = [shipment_row(pay_time=0)]
    store = FakeStore()
    _inject_store(store)

    _run_executor()

    assert store.derived_calls[0].derived_props["overdue_hours"] is None


def test_p07_overdue_hours_zero_within_sla(mock_fetch):
    """pay_time 距 now < 48h → overdue_hours=0.0（max(0, ...) 截断）。"""
    pay_time = (FIXED_NOW - timedelta(hours=24)).timestamp()
    mock_fetch.return_value = [shipment_row(pay_time=pay_time)]
    store = FakeStore()
    _inject_store(store)

    _run_executor()

    assert store.derived_calls[0].derived_props["overdue_hours"] == 0.0
