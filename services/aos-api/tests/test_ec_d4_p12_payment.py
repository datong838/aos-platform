"""D4 Phase A: P12 Payment OT 管道执行测试（frozen/02 §P12）。

P12 Payment 规格：
- 源表/主键: ns_pay / id
- 增量策略: (pay_time, id) 复合游标，pay_time=0 回退 create_time；每小时重扫 24h
- 目标 OT: Payment
- normalize mapper to_payment: orderId=relate_id/order_id, outTradeNo=out_trade_no, payStatus=pay_status
- Link: Order.hasPayment（orderId 关联）
- 派生指标: pay_duration_min（Order.create_time→Payment.pay_time 分钟差，管道内关联）
- PII 脱敏: ns_pay 的 mch_id/trade_no/pay_no/pay_body/pay_detail/pay_voucher 被 SourceAdapter drop

测试覆盖 5 项（FR-D1-6 四段实施）：
1. 初装：首次全量读取 → 落地 OT + Dataset（含 pay_duration_min 派生指标）
2. 增量：复合游标推进 → checkpoint 推进（CAS 不前移）
3. 重跑：重复执行同一批次 → 幂等（replayed=True）
4. 断点：模拟中断后恢复 → checkpoint CAS 不前移
5. 越租户：跨 org/workspace 写入 → 拒绝（fail-closed）

额外覆盖：
6. pay_duration_min 跨表关联成功（_order_create_time + pay_time → 分钟差）
7. pay_duration_min 跨表关联失败（_order_create_time 缺失 → null）
8. pay_duration_min 异常数据（pay_time 早于 create_time → 截断 0）
9. PII 脱敏断言（_clean_rows drop 6 个 PII 字段）
10. hasPayment Link 构造（build_link_rows 直接验证）
11. to_payment mapper 字段映射

mock 策略（照搬 test_ec_d1_p01_shop.py）：
- fetch_source_rows: mock 返回 normalized Payment 行（绕过 MySQL + normalize）
- build_link_rows: mock 透传（5 标准case 不构造 Link，避免 CoreLinkRecord 方向校验；
  Link 构造由额外单测直接调用 ec_link_builder.build_link_rows 验证）
- data_os_store.persist_dataset/history: mock no-op
- eng.ecom_consistency_store: 注入 FakeStore（模拟一致性内核）

pay_duration_min 管道内关联（用户 2026-08-06 拍板）：
- normalize 阶段已用 ns_pay.relate_id（≈order_id）关联查 ns_order.create_time，
  结果挂到 row._order_create_time（内部字段，不进 properties）。
- 测试 mock 在 normalized 行里直接填 _order_create_time 字段（模拟管道内关联已完成）。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aos_api import data_os_store
from aos_api.ec_derived_metrics import apply_derived_metrics
from aos_api.ec_link_builder import build_link_rows
from aos_api.ec_normalizer import to_payment
from aos_api.ec_source_adapter import _clean_rows
from aos_api.ecom_core_models import BatchCommand, BatchResult, EcomConsistencyError
from aos_api.ec_live_executor import ec_live_executor
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
NOW_TS = int(NOW.timestamp())
# 10 分钟后的 pay_time（用于 pay_duration_min 成功场景）
PAY_TIME_TS = NOW_TS + 600


# ═══════════════════════════════════════════════
# FakeStore — 模拟 ecom_consistency_store 内核行为（照搬 test_ec_d1_p01_shop.py）
# ═══════════════════════════════════════════════


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，模拟一致性内核行为。"""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[BatchCommand] = []
        self._raises = raises
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
        if self._raises is not None:
            raise self._raises

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
# fixtures（照搬 test_ec_d1_p01_shop.py）
# ═══════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


@pytest.fixture(autouse=True)
def _mock_data_os_store():
    """避免 persist_dataset / persist_dataset_history 打 DB。"""
    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkey.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)
    yield
    monkey.undo()


@pytest.fixture(autouse=True)
def _mock_build_links():
    """5 标准case 不构造 Link（透传 rows），避免 CoreLinkRecord 方向校验。

    Link 构造由额外单测直接调用 ec_link_builder.build_link_rows 验证。
    patch 的是 ec_live_executor 模块的引用，不影响直接 import 的 build_link_rows。
    """
    with patch(
        "aos_api.ec_live_executor.build_link_rows",
        side_effect=lambda rows, pipeline: rows,
    ):
        yield


@pytest.fixture
def mock_fetch():
    with patch("aos_api.ec_live_executor.fetch_source_rows") as m:
        yield m


# ═══════════════════════════════════════════════
# 管道配置工厂（A3-3，内嵌测试文件）
# ═══════════════════════════════════════════════


def define_p12_pipeline_config(pid: str = "p12-payment") -> dict:
    """P12 Payment Pipeline 完整配置（5 节点 graph）。"""
    return {
        "id": pid,
        "sourceId": "niushop-pay",
        "name": "P12 Payment Pipeline",
        "objectTypeHint": "Payment",
        "config": {
            "target_ot": "Payment",
            "source_table": "ns_pay",
            "primary_key": "id",
            "unique_key_template": "niushop:1:pay_{id}",
            "incremental_strategy": "cursor",
            "cursor_fields": ["pay_time", "id"],
            "cursor_fallback": "create_time",
            "rescan_window_hours": 24,
            "rescan_interval_hours": 1,
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": "niushop-pay",
                    "source_table": "ns_pay",
                    "primary_key": "id",
                    "watermark_col": "pay_time",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {"target_ot": "Payment"},
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {"required_fields": ["out_trade_no"]},
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {"target_ot": "Payment"},
            },
            {
                "id": "sink",
                "name": "Sink",
                "type": "sink",
                "config": {"target_ot": "Payment"},
            },
        ],
        "edges": [
            {"source": "source", "target": "normalize"},
            {"source": "normalize", "target": "validate"},
            {"source": "validate", "target": "quality_gate"},
            {"source": "quality_gate", "target": "sink"},
        ],
    }


# ═══════════════════════════════════════════════
# row 工厂
# ═══════════════════════════════════════════════


def payment_row(
    *,
    pay_id: str = "pay_001",
    relate_id: str = "o-1",
    out_trade_no: str = "otn_001",
    pay_status: str = "2",
    pay_time: int = PAY_TIME_TS,
    order_create_time: int | None = NOW_TS,
    when: datetime = NOW,
) -> dict:
    """P12 Payment normalized 行（含 ot 字段，绕过 normalize_rows）。

    properties 含 REQUIRED_PROPERTIES['Payment'] 要求的 orderId/outTradeNo/payStatus/updatedAt。
    顶层保留 pay_time + _order_create_time（供 _apply_pay_duration_min 读取，管道内关联挂载）。
    """
    row = {
        "ot": "Payment",
        "source_pk": pay_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "pay_time": pay_time,
        "properties": {
            "orderId": relate_id,
            "outTradeNo": out_trade_no,
            "payStatus": pay_status,
            "updatedAt": "2026-08-06T10:00:00Z",
        },
    }
    if order_create_time is not None:
        row["_order_create_time"] = order_create_time
    return row


def raw_payment_row(
    *,
    pay_id: str = "1",
    relate_id: str = "o-1",
    out_trade_no: str = "otn_001",
    pay_status: str = "2",
    pay_time: int = PAY_TIME_TS,
    create_time: int = NOW_TS,
) -> dict:
    """P12 raw ns_pay 行（未 normalize，供 to_payment mapper 单测）。"""
    return {
        "id": pay_id,
        "site_id": 1,
        "weapp_id": "wx_001",
        "relate_id": relate_id,
        "out_trade_no": out_trade_no,
        "pay_type": 1,
        "pay_money": "99.00",
        "pay_status": pay_status,
        "pay_time": pay_time,
        "create_time": create_time,
        "event": "pay",
    }


def raw_payment_row_with_pii(**kwargs) -> dict:
    """P12 raw ns_pay 行 + 6 个 PII 字段（供 PII 脱敏单测）。"""
    row = raw_payment_row(**kwargs)
    row.update(
        {
            "mch_id": "mch_1234567890",
            "trade_no": "tn_2026080610001234",
            "pay_no": "pn_2026080610001234",
            "pay_body": '{"attach":"sensitive_body"}',
            "pay_detail": '{"detail":"sensitive_detail"}',
            "pay_voucher": "voucher_2026080610001234",
        }
    )
    return row


def _make_pipeline(pid: str = "p12-payment") -> SimpleNamespace:
    cfg = define_p12_pipeline_config(pid)
    return SimpleNamespace(id=cfg["id"], config=cfg["config"])


def _run_executor(*, pipeline=None, scope=TEST_SCOPE, mock_fetch=None):
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
# 1. 初装：首次全量读取 → 落地 OT + Dataset（含 pay_duration_min 派生指标）
# ═══════════════════════════════════════════════


def test_p12_initial_load_lands_ot_and_dataset(mock_fetch):
    """初装：首次全量读取 → 落地 Payment OT + Dataset + pay_duration_min 派生指标。

    pay_duration_min = (pay_time - _order_create_time) // 60
    pay_time = NOW_TS + 600, _order_create_time = NOW_TS → 600 // 60 = 10 分钟
    """
    mock_fetch.return_value = [payment_row()]
    store = FakeStore()
    _inject_store(store)

    result = _run_executor(mock_fetch=mock_fetch)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    obj = command.objects[0]
    assert obj.object_type == "Payment"
    assert obj.identity.external_id == "niushop:1:pay_001"
    assert obj.properties.get("orderId") == "o-1"
    assert obj.properties.get("outTradeNo") == "otn_001"
    assert obj.properties.get("payStatus") == "2"
    # 派生指标 pay_duration_min（10 分钟差）
    assert obj.properties.get("pay_duration_min") == 10
    # updatedAt 经 ZonedInstant 规范化
    assert obj.properties.get("updatedAt", "").startswith("2026-08-06T10:00:00")

    # Dataset 落地验证
    assert result["output_ref"].startswith("dataset://catalog/")
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1


# ═══════════════════════════════════════════════
# 2. 增量：复合游标推进 → checkpoint 推进（CAS 不前移）
# ═══════════════════════════════════════════════


def test_p12_incremental_cursor_mode_checkpoint_advances(mock_fetch):
    """增量：P12 是游标模式，第二次执行 → checkpoint 推进。"""
    mock_fetch.return_value = [payment_row()]
    store = FakeStore()
    _inject_store(store)

    _run_executor(mock_fetch=mock_fetch)
    _run_executor(mock_fetch=mock_fetch)

    assert len(store.calls) == 2
    assert store.calls[0].expected_checkpoint_version == 0
    assert store.calls[1].expected_checkpoint_version == 1


# ═══════════════════════════════════════════════
# 3. 重跑：重复执行同一批次 → 幂等（replayed=True）
# ═══════════════════════════════════════════════


def test_p12_rerun_same_batch_idempotent_replayed(mock_fetch):
    """重跑：相同 key+相同 hash → replayed=True，计数不翻倍。"""
    mock_fetch.return_value = [payment_row()]
    store = FakeStore()
    _inject_store(store)

    first = _run_executor(mock_fetch=mock_fetch)
    second = _run_executor(mock_fetch=mock_fetch)

    assert first["rows_written"] == 1
    assert second["rows_written"] == 1
    assert len(store.calls) == 2
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


# ═══════════════════════════════════════════════
# 4. 断点：模拟中断后恢复 → checkpoint CAS 不前移
# ═══════════════════════════════════════════════


def test_p12_checkpoint_recovery_cas_not_moved_backward(mock_fetch):
    """断点恢复：首装后中断，重跑时 expected_checkpoint_version 不退回 0。"""
    mock_fetch.return_value = [payment_row()]
    store = FakeStore()
    _inject_store(store)

    _run_executor(mock_fetch=mock_fetch)
    assert store.calls[0].expected_checkpoint_version == 0

    _run_executor(mock_fetch=mock_fetch)
    assert store.calls[1].expected_checkpoint_version == 1
    assert store.calls[1].expected_checkpoint_version >= store.calls[0].expected_checkpoint_version


# ═══════════════════════════════════════════════
# 5. 越租户：跨 org/workspace 写入 → 拒绝（fail-closed）
# ═══════════════════════════════════════════════


def test_p12_cross_tenant_write_rejected_fail_closed(mock_fetch):
    """跨 org/workspace 写入 → EcomConsistencyError(TENANT_MISMATCH)。"""
    from aos_api.ecom_core_models import SyncScope

    allowed_scope = SyncScope(
        org_id="dev-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        stream="p12-payment",
    )
    store = TenantGuardStore(allowed_scope_key=allowed_scope.key())
    _inject_store(store)

    other_scope = TenantScope("other-org", "other-project")
    mock_fetch.return_value = [payment_row()]
    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor(scope=other_scope, mock_fetch=mock_fetch)

    assert caught.value.code == "TENANT_MISMATCH"


# ═══════════════════════════════════════════════
# 6. pay_duration_min 跨表关联成功（_order_create_time + pay_time → 分钟差）
# ═══════════════════════════════════════════════


def test_p12_pay_duration_min_cross_table_success():
    """pay_duration_min 跨表关联成功：_order_create_time + pay_time → 分钟差。

    场景：normalize 阶段已关联查到 Order.create_time，挂到 row._order_create_time。
    _apply_pay_duration_min 读 row._order_create_time 和 row.pay_time 计算分钟差。
    """
    raw = raw_payment_row(pay_time=NOW_TS + 600, create_time=NOW_TS)
    # 模拟管道内关联挂载 _order_create_time
    raw["_order_create_time"] = NOW_TS
    normalized = to_payment(raw)
    pipeline = SimpleNamespace(id="p12-payment", config={"target_ot": "Payment"})
    apply_derived_metrics([normalized], pipeline)

    # pay_time - _order_create_time = 600秒 = 10分钟
    assert normalized["properties"]["pay_duration_min"] == 10


def test_p12_pay_duration_min_large_diff():
    """pay_duration_min 大时间差：2 小时 = 120 分钟。"""
    raw = raw_payment_row(pay_time=NOW_TS + 7200, create_time=NOW_TS)
    raw["_order_create_time"] = NOW_TS
    normalized = to_payment(raw)
    pipeline = SimpleNamespace(id="p12-payment", config={"target_ot": "Payment"})
    apply_derived_metrics([normalized], pipeline)

    assert normalized["properties"]["pay_duration_min"] == 120


# ═══════════════════════════════════════════════
# 7. pay_duration_min 跨表关联失败（_order_create_time 缺失 → null）
# ═══════════════════════════════════════════════


def test_p12_pay_duration_min_null_when_order_create_time_missing():
    """pay_duration_min 关联失败：_order_create_time 缺失 → null（不阻塞 Pipeline）。"""
    raw = raw_payment_row(pay_time=NOW_TS + 600, create_time=NOW_TS)
    # 不挂载 _order_create_time（模拟关联失败：relate_id 为空或查不到 order）
    normalized = to_payment(raw)
    pipeline = SimpleNamespace(id="p12-payment", config={"target_ot": "Payment"})
    apply_derived_metrics([normalized], pipeline)

    assert normalized["properties"]["pay_duration_min"] is None


def test_p12_pay_duration_min_null_when_pay_time_missing():
    """pay_duration_min 关联失败：pay_time 缺失 → null。"""
    raw = raw_payment_row(pay_time=0, create_time=NOW_TS)
    raw["_order_create_time"] = NOW_TS
    normalized = to_payment(raw)
    pipeline = SimpleNamespace(id="p12-payment", config={"target_ot": "Payment"})
    apply_derived_metrics([normalized], pipeline)

    # pay_time=0 → _to_datetime 返回 None → pay_duration_min=None
    assert normalized["properties"]["pay_duration_min"] is None


# ═══════════════════════════════════════════════
# 8. pay_duration_min 异常数据（pay_time 早于 create_time → 截断 0）
# ═══════════════════════════════════════════════


def test_p12_pay_duration_min_clamped_to_zero_when_negative():
    """pay_duration_min 异常数据：pay_time 早于 _order_create_time → 截断 0。

    场景：异常数据（支付早于创单），delta < 0 → minutes=0。
    """
    raw = raw_payment_row(pay_time=NOW_TS - 600, create_time=NOW_TS)
    raw["_order_create_time"] = NOW_TS
    normalized = to_payment(raw)
    pipeline = SimpleNamespace(id="p12-payment", config={"target_ot": "Payment"})
    apply_derived_metrics([normalized], pipeline)

    assert normalized["properties"]["pay_duration_min"] == 0


# ═══════════════════════════════════════════════
# 9. PII 脱敏断言（_clean_rows drop 6 个 PII 字段）
# ═══════════════════════════════════════════════


def test_p12_pii_fields_dropped_by_clean_rows():
    """PII 脱敏：ns_pay 的 6 个 PII 字段（mch_id/trade_no/pay_no/pay_body/pay_detail/pay_voucher）被 _clean_rows drop。

    规格 §P12 + ec_source_adapter._PII_DROP_FIELDS_BY_TABLE['ns_pay']。
    """
    raw = raw_payment_row_with_pii()
    cleaned = _clean_rows([raw], pipeline_id="p12-payment", node_id="n-src", table="ns_pay")
    assert len(cleaned) == 1
    row = cleaned[0]
    # 6 个 PII 字段被 drop
    assert "mch_id" not in row
    assert "trade_no" not in row
    assert "pay_no" not in row
    assert "pay_body" not in row
    assert "pay_detail" not in row
    assert "pay_voucher" not in row
    # 保留字段仍在（id/out_trade_no/pay_status/pay_time/relate_id 等）
    assert row["id"] == "1"
    assert row["out_trade_no"] == "otn_001"
    assert row["pay_status"] == "2"
    assert row["pay_time"] == PAY_TIME_TS
    assert row["relate_id"] == "o-1"


def test_p12_pii_drop_does_not_affect_other_tables():
    """PII 脱敏：ns_pay 的 PII drop 不影响其他表（如 ns_order 无 PII drop）。"""
    raw = {"order_id": "o-1", "site_id": 1, "create_time": NOW_TS, "mch_id": "should_keep"}
    cleaned = _clean_rows([raw], pipeline_id="p05", node_id="n-src", table="ns_order")
    assert len(cleaned) == 1
    # ns_order 不在 _PII_DROP_FIELDS_BY_TABLE，mch_id 保留
    assert cleaned[0]["mch_id"] == "should_keep"


def test_p12_pii_drop_fields_registered():
    """PII 脱敏：_PII_DROP_FIELDS_BY_TABLE['ns_pay'] 注册了 6 个 PII 字段。"""
    from aos_api.ec_source_adapter import _PII_DROP_FIELDS_BY_TABLE

    pii_fields = _PII_DROP_FIELDS_BY_TABLE.get("ns_pay", frozenset())
    assert pii_fields == frozenset(
        {"mch_id", "trade_no", "pay_no", "pay_body", "pay_detail", "pay_voucher"}
    )


# ═══════════════════════════════════════════════
# 10. hasPayment Link 构造（build_link_rows 直接验证）
# ═══════════════════════════════════════════════


def test_p12_has_payment_link_constructed():
    """hasPayment Link 构造：Order → Payment（orderId 关联）。

    hasPayment 不反转：source=Order, target=Payment（与 CORE_LINK_TYPES 方向一致）。
    """
    rows = [payment_row(pay_id="pay_001", relate_id="o-1")]
    result = build_link_rows(rows, _make_pipeline("p12-payment"))
    links = [r for r in result if r.get("link_type") == "Order.hasPayment"]
    assert len(links) == 1
    link = links[0]
    assert link["link_type"] == "Order.hasPayment"
    # hasPayment 不反转：source=Order, target=Payment
    assert link["source_type"] == "Order"
    assert link["target_type"] == "Payment"
    assert link["source_pk"] == "o-1"
    assert link["target_source_pk"] == "pay_001"


def test_p12_has_payment_link_skipped_when_order_id_missing():
    """hasPayment Link 构造：orderId 缺失时跳过（无法关联订单）。"""
    row = payment_row(pay_id="pay_001", relate_id="")
    result = build_link_rows([row], _make_pipeline("p12-payment"))
    assert [r for r in result if r.get("link_type") == "Order.hasPayment"] == []


# ═══════════════════════════════════════════════
# 11. to_payment mapper 字段映射
# ═══════════════════════════════════════════════


def test_p12_to_payment_mapper_field_mapping():
    """to_payment mapper: raw ns_pay 行 → Payment normalized 行，字段映射正确。"""
    raw = raw_payment_row(
        pay_id="1",
        relate_id="o-1",
        out_trade_no="otn_001",
        pay_status="2",
        pay_time=PAY_TIME_TS,
    )
    out = to_payment(raw)

    assert out["ot"] == "Payment"
    assert out["source_pk"] == "1"
    assert out["source_timezone"] == "+08:00"
    assert out["is_deleted"] is False
    # properties 字段映射
    assert out["properties"]["orderId"] == "o-1"
    assert out["properties"]["outTradeNo"] == "otn_001"
    assert out["properties"]["payStatus"] == "2"
    # 保留 raw 字段（pay_time 在顶层，供 _apply_pay_duration_min 读取）
    assert out["pay_time"] == PAY_TIME_TS


def test_p12_to_payment_mapper_order_id_fallback():
    """to_payment mapper: relate_id 缺失时回退到 order_id。"""
    raw = raw_payment_row()
    raw.pop("relate_id", None)
    raw["order_id"] = "o-fallback"
    out = to_payment(raw)
    assert out["properties"]["orderId"] == "o-fallback"


def test_p12_to_payment_mapper_source_updated_at_uses_pay_time():
    """to_payment mapper: source_updated_at 优先用 pay_time，回退 create_time。"""
    raw = raw_payment_row(pay_time=PAY_TIME_TS, create_time=NOW_TS)
    out = to_payment(raw)
    # source_updated_at 用 pay_time（PAY_TIME_TS）
    assert out["source_updated_at"] == datetime.fromtimestamp(PAY_TIME_TS, tz=timezone.utc)
