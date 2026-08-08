"""D1-W4: P05 Order 端到端测试（FR-D1-6 四段实施 + P05 规格）。

P05 Order 规格（frozen/02）：
- 源表/主键: ns_order / order_id
- 源过滤: site_id=1 AND is_delete=0
- 增量游标: 初装 (create_time, order_id)；每小时重扫最近 7 天；每日全状态对账
- 目标 OT: Order
- 唯一键: niushop:1:{order_id}
- 关键映射: order_no；member_id 仅保留关联键（不引 PII）；
  状态四元组（order_status/pay_status/delivery_status/is_delete）；金额 decimal
- 状态字段修正: delivery_status（非 shipping_status）
- 软删处置: is_delete=1 不入 OT，进 DLQ 计数
- 派生指标: risk_score（由 W1 ec_derived_metrics 计算，本测试 mock 为透传）
- Link: P05 侧保留 member_id 关联键（placedByLite 在 D1.5 落地，D1 不构造 Link）

测试约束：
- mock apply_derived_metrics 和 build_link_rows 为透传，只验证 Order OT 落地
- mock data_os_store.persist_dataset/persist_dataset_history 为 no-op
- 使用 FakeStore（复用 test_ec_d1_ot_writer 模式）验证调用契约
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from aos_api import data_os_store, ec_live_executor as ec_mod
from aos_api.ecom_core_models import BatchCommand, BatchResult, EcomConsistencyError
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.public_contracts import StableCursor
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("other-org", "other-project")

PID = "p05-order"  # 统一 pipeline_id，保证 checkpoint scope 一致


# ═══════════════════════════════════════════════
# fakes（复用 test_ec_d1_ot_writer.py 模式）
# ═══════════════════════════════════════════════


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，可配置返回值与异常。

    与 test_ec_d1_ot_writer.py 的 FakeStore 行为一致：
    - 默认：返回 objects/links 计数 = batch 大小，推进 checkpoint version
    - result 配置：始终返回指定 BatchResult（用于 replay 测试）
    - raises 配置：始终抛指定异常（用于冲突测试）
    """

    def __init__(
        self,
        *,
        result: BatchResult | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.calls: list[BatchCommand] = []
        self._result = result
        self._raises = raises
        self._checkpoints: dict[tuple, int] = {}

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        self.calls.append(command)
        if self._raises is not None:
            raise self._raises
        key = command.scope.key()
        if key not in self._checkpoints:
            self._checkpoints[key] = 0
        self._checkpoints[key] += 1
        if self._result is not None:
            return self._result.model_copy(
                update={"checkpoint_version": self._checkpoints[key]}
            )
        return BatchResult(
            objects_written=len(command.objects),
            links_written=len(command.links),
            checkpoint_version=self._checkpoints[key],
            checkpoint=command.next_checkpoint,
        )

    def get_checkpoint(self, command: BatchCommand) -> dict[str, Any] | None:
        version = self._checkpoints.get(command.scope.key())
        if version is None:
            return None
        return {"version": version}


class FakePipeline:
    def __init__(self, pid: str = PID) -> None:
        self.id = pid


# ═══════════════════════════════════════════════
# P05 Order 行工厂
# ═══════════════════════════════════════════════


def order_row(
    *,
    order_id: str = "100",
    when: datetime = NOW,
    deleted: bool = False,
) -> dict[str, Any]:
    """P05 Order 行：source_pk=order_id，properties 含状态四元组 + member_id 关联键。

    状态字段修正：delivery_status（非 shipping_status）。
    member_id 仅保留关联键，不引 PII（手机/身份证/邮箱/银行卡）。
    """
    return {
        "ot": "Order",
        "source_pk": order_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": deleted,
        "properties": {
            # REQUIRED_PROPERTIES["Order"]
            "shopId": "1",
            "status": "active",
            "totalAmount": "199.00",
            "currency": "CNY",
            "createdAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
            # P05 关键映射
            "orderNo": "NO20260731001",
            "memberId": "m-1001",  # 关联键，无 PII
            "orderStatus": "1",
            "payStatus": "2",
            "deliveryStatus": "1",  # 修正字段（非 shipping_status）
            "isDelete": "0",
        },
    }


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
def _mock_dataset_sink(monkeypatch):
    """mock data_os_store 持久化为 no-op，避免 PG 副作用。"""
    monkeypatch.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)


@pytest.fixture(autouse=True)
def _mock_derived_and_links(monkeypatch):
    """mock apply_derived_metrics 和 build_link_rows 为透传（隔离 OT 落地）。"""
    monkeypatch.setattr(ec_mod, "apply_derived_metrics", lambda rows, pipeline, **kw: rows)
    monkeypatch.setattr(ec_mod, "build_link_rows", lambda rows, _: rows)


def _run_executor(
    rows: list[dict[str, Any]],
    *,
    store: FakeStore,
    scope: TenantScope = TEST_SCOPE,
    pipeline_id: str = PID,
) -> dict[str, Any]:
    """调用 ec_live_executor，注入 FakeStore 到 engine。"""
    eng = get_engine()
    eng.ecom_consistency_store = store
    return ec_mod.ec_live_executor(
        pipeline=FakePipeline(pipeline_id),
        nodes=[],
        node_id=None,
        sample_input=rows,
        execution_kind="schedule",
        cancel_event=None,
        deadline=0,
        scope=scope,
    )


# ═══════════════════════════════════════════════
# FR-D1-6 四段实施（6 项）
# ═══════════════════════════════════════════════


def test_p05_initial_load_lands_order_ot():
    """#1 初装：首次全量读取 → 落地 OT + Dataset。"""
    store = FakeStore()
    rows = [order_row(order_id="100"), order_row(order_id="101")]

    result = _run_executor(rows, store=store)

    # Dataset 落地
    assert result["output_ref"].startswith("dataset://catalog/ri.dataset.")
    # OT 落地：1 个 BatchCommand，2 个 Order 对象
    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 2
    assert all(obj.object_type == "Order" for obj in command.objects)
    # 唯一键 niushop:1:{order_id}
    ext_ids = {obj.identity.external_id for obj in command.objects}
    assert ext_ids == {"niushop:1:100", "niushop:1:101"}
    # rows 计数
    assert result["rows_read"] == 2
    assert result["rows_written"] == 2


def test_p05_incremental_upsert_advances_checkpoint():
    """#2 增量：基于复合游标增量读取 → 幂等 upsert（expected_checkpoint_version 推进）。

    同一 pipeline_id 下首装推进 checkpoint 到 v1，第二批 expected=1（增量，不退回 0）。
    """
    store = FakeStore()

    # 首装批次（同一 pipeline_id 保证 checkpoint scope 一致）
    _run_executor([order_row(order_id="100", when=NOW)], store=store)
    assert store.calls[0].expected_checkpoint_version == 0

    # 增量批次（新 order_id，更新时间更晚）
    later = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
    _run_executor([order_row(order_id="101", when=later)], store=store)

    # 第二批次 expected=1（增量模式，不退回 0）
    assert len(store.calls) == 2
    assert store.calls[1].expected_checkpoint_version == 1


def test_p05_replay_same_batch_is_idempotent():
    """#3 重跑：重复执行同一批次 → 验证幂等（replayed=True，计数不翻倍）。

    配置 FakeStore 返回 replayed=True，验证 sink_to_ot 透传 replay 结果，
    计数不翻倍（与 test_ec_d1_ot_writer::test_idempotent_replay_same_hash_returns_same_counts 一致）。
    """
    replay_result = BatchResult(
        objects_written=1,
        links_written=0,
        checkpoint_version=1,
        checkpoint=StableCursor(
            source_updated_at_utc=NOW, external_id="niushop:1:100"
        ),
        replayed=True,
    )
    store = FakeStore(result=replay_result)
    rows = [order_row(order_id="100")]

    first = _run_executor(rows, store=store)
    second = _run_executor(rows, store=store)

    # 两次都返回 rows_written=1（不翻倍）
    assert first["rows_written"] == 1
    assert second["rows_written"] == 1
    # store 被调用两次
    assert len(store.calls) == 2
    # 相同 batch → 相同 idempotency_key（store 据此识别 replay）
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


def test_p05_checkpoint_cas_does_not_regress():
    """#4 断点：模拟中断后恢复 → 验证 checkpoint CAS 不前移。

    首装推进 checkpoint 到 v1 后，后续批次 expected 自动取当前 version=1（不前移到 0）。
    """
    store = FakeStore()

    _run_executor([order_row(order_id="100", when=NOW)], store=store)
    assert store.calls[0].expected_checkpoint_version == 0

    # 模拟断点恢复：同一 pipeline 再跑一批新数据
    later = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)
    _run_executor([order_row(order_id="101", when=later)], store=store)

    # expected=1（取当前 checkpoint version），不前移到 0
    assert len(store.calls) == 2
    assert store.calls[1].expected_checkpoint_version == 1


def test_p05_same_version_different_hash_raises_conflict():
    """#5 重复：相同版本+不同 hash → 验证冲突检测。

    配置 FakeStore 抛 IDEMPOTENCY_CONFLICT，验证 sink_to_ot 不吞异常，向上传播。
    """
    conflict = EcomConsistencyError(
        "IDEMPOTENCY_CONFLICT",
        "idempotency key was already used with a different request",
    )
    store = FakeStore(raises=conflict)

    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor([order_row(order_id="200")], store=store)

    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


def test_p05_cross_tenant_write_rejected():
    """#6 越租户：跨 org/workspace 写入 → 验证拒绝。

    executor 总是从传入 scope 派生 SyncScope（不从 row 数据取），因此跨租户注入
    不可能经由 executor 发生。验证：
    1. executor 的 BatchCommand scope 与传入 scope 一致
    2. BatchCommand validator 拒绝跨 scope 的 object identity
    """
    store = FakeStore()
    _run_executor([order_row(order_id="100")], store=store, scope=TEST_SCOPE)

    # 1. BatchCommand scope 与传入 scope 一致
    command = store.calls[0]
    assert command.scope.org_id == TEST_SCOPE.org_id
    assert command.scope.workspace_id == TEST_SCOPE.project_id
    for obj in command.objects:
        assert obj.identity.org_id == TEST_SCOPE.org_id
        assert obj.identity.workspace_id == TEST_SCOPE.project_id

    # 2. BatchCommand validator 拒绝跨 scope 的 object identity
    from aos_api.ecom_core_models import CoreObjectRecord
    from aos_api.public_contracts import ExternalIdentityKey, ForwardEnumValue

    cross_identity = ExternalIdentityKey(
        org_id=OTHER_SCOPE.org_id,
        workspace_id=OTHER_SCOPE.project_id,
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id="niushop:1:999",
    )
    cross_obj = CoreObjectRecord(
        identity=cross_identity,
        object_type="Order",
        source_updated_at=NOW,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active"}),
        properties={
            "shopId": "1",
            "status": "active",
            "totalAmount": "1.00",
            "currency": "CNY",
            "createdAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    )
    with pytest.raises(ValueError, match="outside the batch scope"):
        BatchCommand(
            scope=command.scope,
            idempotency_key="cross-tenant-test",
            expected_checkpoint_version=0,
            next_checkpoint=StableCursor(
                source_updated_at_utc=NOW, external_id="niushop:1:999"
            ),
            objects=[cross_obj],
            links=[],
        )


# ═══════════════════════════════════════════════
# P05 额外测试（3 项）
# ═══════════════════════════════════════════════


def test_p05_member_id_kept_as_association_key_no_pii():
    """#7 member_id 关联键保留（不引 PII）。

    P05 Order properties 含 memberId（关联键），但不含 PII 字段
    （手机号/身份证/邮箱/银行卡）。
    """
    store = FakeStore()
    _run_executor([order_row(order_id="100")], store=store)

    command = store.calls[0]
    props = command.objects[0].properties
    # member_id 保留为关联键
    assert "memberId" in props
    assert props["memberId"] == "m-1001"
    # 不含 PII 字段
    pii_keys = {"phone", "mobile", "idCard", "id_card", "email", "bankCard", "bank_card"}
    assert not (pii_keys & set(props.keys())), (
        f"properties 含 PII 字段: {pii_keys & set(props.keys())}"
    )


def test_p05_delivery_status_not_shipping_status():
    """#8 delivery_status 字段修正验证（不是 shipping_status）。

    上位方案写的 shipping_status 不存在，真实字段是 delivery_status。
    """
    store = FakeStore()
    _run_executor([order_row(order_id="100")], store=store)

    props = store.calls[0].objects[0].properties
    # delivery_status 存在
    assert "deliveryStatus" in props
    # shipping_status 不存在（修正点）
    assert "shippingStatus" not in props
    assert "shipping_status" not in props
    # 状态四元组完整
    for key in ("orderStatus", "payStatus", "deliveryStatus", "isDelete"):
        assert key in props, f"状态四元组缺 {key}"


def test_p05_soft_deleted_rows_filtered_to_dlq():
    """#9 软删行过滤（is_delete=1 不入 OT，进 DLQ 计数）。

    软删过滤在 source_adapter._clean_rows 完成。用 P05 的 ns_order 表配置
    验证 is_delete=1 的行被过滤且计数。
    """
    from unittest.mock import MagicMock, patch

    from aos_api.ec_source_adapter import (
        fetch_source_rows,
        get_soft_delete_count,
        reset_soft_delete_counts,
    )

    # fake niushop 返回 5 行：2 行软删
    niushop_rows = [
        {"order_id": 100, "is_delete": 0, "create_time": 1000, "modify_time": 1100},
        {"order_id": 101, "is_delete": 1, "create_time": 1000, "modify_time": 1200},  # 软删
        {"order_id": 102, "is_delete": 0, "create_time": 1000, "modify_time": 1300},
        {"order_id": 103, "is_delete": 1, "create_time": 1000, "modify_time": 1400},  # 软删
        {"order_id": 104, "is_delete": 0, "create_time": 1000, "modify_time": 1500},
    ]

    reset_soft_delete_counts()
    aos_conn = MagicMock()
    aos_conn.execute.return_value.fetchone.return_value = {
        "props": {
            "host": "127.0.0.1",
            "port": 13306,
            "user": "ro",
            "password": "x",
            "database": "niushop_b2c_v5",
        }
    }
    cur = MagicMock()
    cur.fetchall.return_value = niushop_rows
    niushop_conn = MagicMock()
    niushop_conn.cursor.return_value = cur

    with patch(
        "aos_api.ec_source_adapter.connect",
        return_value=MagicMock(
            __enter__=MagicMock(return_value=aos_conn),
            __exit__=MagicMock(return_value=None),
        ),
    ) as _, patch("aos_api.ec_source_adapter.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = niushop_conn
        mock_pymysql.cursors.DictCursor = MagicMock()

        from types import SimpleNamespace
        node = SimpleNamespace(
            id="n-src",
            node_type="source",
            config={
                "source_id": "src-1",
                "table": "ns_order",
                "pk": "order_id",
                "initial": True,
            },
        )
        rows = fetch_source_rows(
            pipeline=SimpleNamespace(id="pl-p05-softdel"),
            nodes=[node],
            node_id="n-src",
            sample_input=None,
            scope=TEST_SCOPE,
        )

    # 有效行 3 条（is_delete=0）
    assert len(rows) == 3
    assert all(r["is_delete"] == 0 for r in rows)
    # 软删计数 2 条（进 DLQ 计数）
    assert get_soft_delete_count("pl-p05-softdel", "n-src") == 2
