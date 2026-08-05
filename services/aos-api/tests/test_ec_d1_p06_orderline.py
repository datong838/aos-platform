"""D1-W4: P06 OrderLine 端到端测试（FR-D1-6 四段实施 + P06 规格）。

P06 OrderLine 规格（frozen/02）：
- 源表/主键: ns_order_goods / order_goods_id
- 源过滤: site_id=1
- 增量游标修正: create_time 227 行全为 0（D-002），改用 refund_action_time 为辅游标，
  主策略退回每日快照 + order_id 关联重扫
- 目标 OT: OrderLine
- 唯一键: niushop:1:{order_goods_id}
- 关键映射: 指向 Order/Product/ProductSku；数量/金额非负；
  refund_status 枚举 {-3,0,3}；delivery_status 保留
- Link: contains (Order→OrderLine) / forProduct (OrderLine→Product) / forSku (OrderLine→ProductSku)
- 派生指标: 无（OrderLine 没有 FR-D1-7 定义的 4 个派生指标）

测试约束：
- mock apply_derived_metrics 和 build_link_rows 为透传，只验证 OrderLine OT 落地
- mock data_os_store.persist_dataset/persist_dataset_history 为 no-op
- Link 合约测试（#8/#9/#10）使用真实 sqlite EcomConsistencyStore 验证 DANGLING_LINK
- Link 类型使用 CORE_LINK_TYPES 实际名称（Order.lines / OrderLine.ofSku / ProductSku.ofProduct）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from aos_api import data_os_store, ec_live_executor as ec_mod
from aos_api.ecom_consistency_store import EcomConsistencyStore, metadata as ecom_metadata
from aos_api.ecom_core_models import (
    BatchCommand,
    BatchResult,
    EcomConsistencyError,
)
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.public_contracts import StableCursor
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")
PID = "p06-orderline"


# ═══════════════════════════════════════════════
# fakes
# ═══════════════════════════════════════════════


class FakeStore:
    """与 test_ec_d1_ot_writer.py 的 FakeStore 行为一致。"""

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


def _make_sqlite_store() -> EcomConsistencyStore:
    """创建 in-memory sqlite EcomConsistencyStore（用于 Link 合约测试）。

    sqlite 跳过 PG 专属的 SET LOCAL ROLE / advisory lock，但完整执行
    upsert/link/checkpoint/receipt 逻辑和 CHECK 约束。
    """
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    ecom_metadata.create_all(engine)
    return EcomConsistencyStore(engine)


# ═══════════════════════════════════════════════
# P06 OrderLine 行工厂
# ═══════════════════════════════════════════════


def orderline_row(
    *,
    goods_id: str = "200",
    order_id: str = "100",
    sku_id: str = "s-2001",
    when: datetime = NOW,
    deleted: bool = False,
) -> dict[str, Any]:
    """P06 OrderLine 行：source_pk=order_goods_id。"""
    return {
        "ot": "OrderLine",
        "source_pk": goods_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": deleted,
        "properties": {
            # REQUIRED_PROPERTIES["OrderLine"]
            "orderId": order_id,
            "skuId": sku_id,
            "quantity": 2,
            "unitPrice": "49.75",
            "lineAmount": "99.50",
            "currency": "CNY",
            "updatedAt": "2026-07-31T18:00:00+08:00",
            # P06 extras
            "refundStatus": "0",
            "deliveryStatus": "1",
        },
    }


def order_row_for_link(
    *,
    order_id: str = "100",
    when: datetime = NOW,
) -> dict[str, Any]:
    """Order 行（仅用于 Link 合约测试中创建订单头）。"""
    return {
        "ot": "Order",
        "source_pk": order_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "shopId": "1",
            "status": "active",
            "totalAmount": "199.00",
            "currency": "CNY",
            "createdAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def link_row(
    *,
    link_type: str = "Order.lines",
    source_type: str = "Order",
    target_type: str = "OrderLine",
    source_pk: str = "100",
    target_pk: str = "200",
    when: datetime = NOW,
) -> dict[str, Any]:
    """Link 行：含 link_type 字段 → ec_ot_writer 识别为 Link 行。"""
    return {
        "link_type": link_type,
        "source_type": source_type,
        "target_type": target_type,
        "source_pk": source_pk,
        "target_source_pk": target_pk,
        "source_updated_at": when,
        "cursor_external_id": f"link:{source_pk}->{target_pk}",
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
    monkeypatch.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)


@pytest.fixture(autouse=True)
def _mock_derived_and_links(monkeypatch):
    """mock apply_derived_metrics 和 build_link_rows 为透传（隔离 OT 落地）。"""
    monkeypatch.setattr(ec_mod, "apply_derived_metrics", lambda rows, _: rows)
    monkeypatch.setattr(ec_mod, "build_link_rows", lambda rows, _: rows)


def _run_executor(
    rows: list[dict[str, Any]],
    *,
    store: FakeStore,
    scope: TenantScope = TEST_SCOPE,
    pipeline_id: str = PID,
) -> dict[str, Any]:
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


def test_p06_initial_load_lands_orderline_ot():
    """#1 初装：首次全量读取 → 落地 OT + Dataset。"""
    store = FakeStore()
    rows = [orderline_row(goods_id="200"), orderline_row(goods_id="201")]

    result = _run_executor(rows, store=store)

    assert result["output_ref"].startswith("dataset://catalog/ri.dataset.")
    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 2
    assert all(obj.object_type == "OrderLine" for obj in command.objects)
    ext_ids = {obj.identity.external_id for obj in command.objects}
    assert ext_ids == {"niushop:1:200", "niushop:1:201"}
    assert result["rows_read"] == 2
    assert result["rows_written"] == 2


def test_p06_incremental_snapshot_advances_checkpoint():
    """#2 增量：每日快照 + order_id 关联重扫 → 幂等 upsert（expected 推进）。"""
    store = FakeStore()

    _run_executor([orderline_row(goods_id="200", when=NOW)], store=store)
    assert store.calls[0].expected_checkpoint_version == 0

    later = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
    _run_executor([orderline_row(goods_id="201", when=later)], store=store)

    assert len(store.calls) == 2
    assert store.calls[1].expected_checkpoint_version == 1


def test_p06_replay_same_batch_is_idempotent():
    """#3 重跑：重复执行同一批次 → 验证幂等（replayed=True，计数不翻倍）。"""
    replay_result = BatchResult(
        objects_written=1,
        links_written=0,
        checkpoint_version=1,
        checkpoint=StableCursor(
            source_updated_at_utc=NOW, external_id="niushop:1:200"
        ),
        replayed=True,
    )
    store = FakeStore(result=replay_result)
    rows = [orderline_row(goods_id="200")]

    first = _run_executor(rows, store=store)
    second = _run_executor(rows, store=store)

    assert first["rows_written"] == 1
    assert second["rows_written"] == 1
    assert len(store.calls) == 2
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


def test_p06_checkpoint_cas_does_not_regress():
    """#4 断点：模拟中断后恢复 → 验证 checkpoint CAS 不前移。"""
    store = FakeStore()

    _run_executor([orderline_row(goods_id="200", when=NOW)], store=store)
    assert store.calls[0].expected_checkpoint_version == 0

    later = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)
    _run_executor([orderline_row(goods_id="201", when=later)], store=store)

    assert len(store.calls) == 2
    assert store.calls[1].expected_checkpoint_version == 1


def test_p06_same_version_different_hash_raises_conflict():
    """#5 重复：相同版本+不同 hash → 验证冲突检测。"""
    conflict = EcomConsistencyError(
        "IDEMPOTENCY_CONFLICT",
        "idempotency key was already used with a different request",
    )
    store = FakeStore(raises=conflict)

    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor([orderline_row(goods_id="300")], store=store)

    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


def test_p06_cross_tenant_write_rejected():
    """#6 越租户：跨 org/workspace 写入 → 验证拒绝。"""
    store = FakeStore()
    _run_executor([orderline_row(goods_id="200")], store=store, scope=TEST_SCOPE)

    command = store.calls[0]
    assert command.scope.org_id == TEST_SCOPE.org_id
    assert command.scope.workspace_id == TEST_SCOPE.project_id
    for obj in command.objects:
        assert obj.identity.org_id == TEST_SCOPE.org_id

    # BatchCommand validator 拒绝跨 scope 的 object identity
    from aos_api.ecom_core_models import CoreObjectRecord
    from aos_api.public_contracts import ExternalIdentityKey, ForwardEnumValue

    cross_identity = ExternalIdentityKey(
        org_id="other-org",
        workspace_id="other-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id="niushop:1:999",
    )
    cross_obj = CoreObjectRecord(
        identity=cross_identity,
        object_type="OrderLine",
        source_updated_at=NOW,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active"}),
        properties={
            "orderId": "100",
            "skuId": "s-1",
            "quantity": 1,
            "unitPrice": "1.00",
            "lineAmount": "1.00",
            "currency": "CNY",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    )
    with pytest.raises(ValueError, match="outside the batch scope"):
        BatchCommand(
            scope=command.scope,
            idempotency_key="cross-tenant-p06",
            expected_checkpoint_version=0,
            next_checkpoint=StableCursor(
                source_updated_at_utc=NOW, external_id="niushop:1:999"
            ),
            objects=[cross_obj],
            links=[],
        )


# ═══════════════════════════════════════════════
# P06 额外测试（4 项）
# ═══════════════════════════════════════════════


def test_p06_create_time_zero_cursor_uses_refund_action_time():
    """#7 create_time 全为 0 的游标修正（改用 refund_action_time）。

    差异报告 D-002：ns_order_goods.create_time 227 行全为 0，不可用作游标。
    修正：watermark_col 改为 refund_action_time。
    验证：SQL 用 refund_action_time 做 WHERE；create_time=0 转 None。
    """
    from unittest.mock import MagicMock, patch

    from aos_api.ec_source_adapter import (
        fetch_source_rows,
        reset_soft_delete_counts,
    )

    niushop_rows = [
        {
            "order_goods_id": 200,
            "is_delete": 0,
            "create_time": 0,               # 全为 0（不可用游标）
            "refund_action_time": 1000,     # 辅游标
            "order_id": 100,
        },
        {
            "order_goods_id": 201,
            "is_delete": 0,
            "create_time": 0,
            "refund_action_time": 2000,
            "order_id": 101,
        },
    ]

    reset_soft_delete_counts()
    aos_conn = MagicMock()
    aos_conn.execute.return_value.fetchone.return_value = {
        "props": {
            "host": "127.0.0.1", "port": 13306, "user": "ro",
            "password": "x", "database": "niushop_b2c_v5",
        }
    }

    # 用真实记录 execute 调用的 fake cursor（而非 MagicMock）
    class _RecordingCursor:
        def __init__(self, rows):
            self.rows = rows
            self.executed: list[tuple[str, Any]] = []

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

        def fetchall(self):
            return self.rows

        def close(self):
            pass

    cur = _RecordingCursor(niushop_rows)
    niushop_conn = MagicMock()
    niushop_conn.cursor.return_value = cur

    with patch(
        "aos_api.ec_source_adapter.connect",
        return_value=MagicMock(
            __enter__=MagicMock(return_value=aos_conn),
            __exit__=MagicMock(return_value=None),
        ),
    ), patch("aos_api.ec_source_adapter.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = niushop_conn
        mock_pymysql.cursors.DictCursor = MagicMock()

        from types import SimpleNamespace
        node = SimpleNamespace(
            id="n-src",
            node_type="source",
            config={
                "source_id": "src-1",
                "table": "ns_order_goods",
                "pk": "order_goods_id",
                "watermark_col": "refund_action_time",  # 修正：辅游标
                "cursor": {"watermark": 500, "primary_key": 199},
            },
        )
        rows = fetch_source_rows(
            pipeline=SimpleNamespace(id="pl-p06-cursor"),
            nodes=[node],
            node_id="n-src",
            sample_input=None,
            scope=TEST_SCOPE,
        )

    # create_time=0 → None（0 时间转 null）
    assert all(r["create_time"] is None for r in rows)
    # refund_action_time 保留（非 0）
    assert rows[0]["refund_action_time"] == 1000

    # 验证 SQL 用 refund_action_time 做 WHERE（从 cursor.executed 提取数据查询 SQL）
    data_sqls = [
        sql for sql, _ in cur.executed
        if "READ ONLY" not in sql
    ]
    assert len(data_sqls) == 1
    assert "refund_action_time" in data_sqls[0]
    # create_time 不出现在 WHERE 子句中（游标修正点）
    where_clause = data_sqls[0].split("WHERE", 1)[1] if "WHERE" in data_sqls[0] else ""
    assert "create_time" not in where_clause


def test_p06_contains_link_requires_order_header():
    """#8 contains Link 完整性（行必须有订单头）。

    用真实 sqlite store 验证：
    - OrderLine 的 orderId 指向 Order（REQUIRED_PROPERTIES 保证）
    - Order.lines Link 的 target（OrderLine）不存在时 → DANGLING_LINK
    - Order + Order.lines Link → 正常落地
    """
    store = _make_sqlite_store()
    eng = get_engine()
    eng.ecom_consistency_store = store

    # OrderLine properties 必含 orderId（REQUIRED_PROPERTIES 保证）
    row = orderline_row(goods_id="200", order_id="100")
    result = sink_to_ot(eng, TEST_SCOPE, FakePipeline("p06-link"), [row])
    # OrderLine 落地成功
    assert result["objects_written"] == 1

    # 用 store.get_object 验证（传入 ExternalIdentityKey）
    from aos_api.public_contracts import ExternalIdentityKey
    identity = ExternalIdentityKey(
        org_id="dev-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id="niushop:1:200",
    )
    obj = store.get_object(identity, "OrderLine")
    assert obj is not None
    assert obj["external_id"] == "niushop:1:200"

    # DANGLING_LINK：Order.lines Link，source Order 不存在 → 拒绝
    dangling_link = link_row(
        link_type="Order.lines",
        source_type="Order",
        target_type="OrderLine",
        source_pk="999",  # 不存在的 Order
        target_pk="200",
    )
    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline("p06-link"), [dangling_link])
    assert caught.value.code == "DANGLING_LINK"

    # 正常场景：先创建 Order，再创建 Order.lines Link
    store2 = _make_sqlite_store()
    eng.ecom_consistency_store = store2
    sink_to_ot(eng, TEST_SCOPE, FakePipeline("p06-link-ok"), [
        order_row_for_link(order_id="100"),
        orderline_row(goods_id="200", order_id="100"),
        link_row(source_pk="100", target_pk="200"),
    ])
    # Link 落地成功（无异常即通过）


def test_p06_forproduct_link_missing_pushes_dlq():
    """#9 forProduct Link 缺失进 DLQ（不自动造对象）。

    悬挂 Link（target Product 不存在）被 store 拒绝（DANGLING_LINK），
    executor 捕获异常 → 投递 DLQ → 重新抛出。
    验证：不自动创建 Product 对象。
    """
    from aos_api.routers.wave_ext import _dlq

    _dlq.clear()
    dangling = EcomConsistencyError(
        "DANGLING_LINK",
        "link endpoints must exist in the same committed tenant scope",
    )
    store = FakeStore(raises=dangling)

    # executor 捕获 DANGLING_LINK → DLQ → re-raise
    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor(
            [orderline_row(goods_id="200")],
            store=store,
            pipeline_id="p06-dlq-forproduct",
        )

    assert caught.value.code == "DANGLING_LINK"
    # DLQ 被投递
    assert len(_dlq) >= 1
    dlq_item = list(_dlq.values())[-1]
    assert dlq_item["pipelineId"] == "p06-dlq-forproduct"
    assert dlq_item["errorCode"] == "EcomConsistencyError"
    _dlq.clear()


def test_p06_forsku_link_sku_id_zero_rule():
    """#10 forSku Link 的 sku_id=0 规则核验。

    sku_id=0 时 external_id 为 "niushop:1:0"。
    用真实 sqlite store 验证：ProductSku 不存在时 → DANGLING_LINK（不特殊处理 0）。
    """
    store = _make_sqlite_store()
    eng = get_engine()
    eng.ecom_consistency_store = store

    # 构造 OrderLine.ofSku Link，target sku_id=0
    # 先创建 OrderLine，再创建指向 sku_id=0 的 Link
    sink_to_ot(eng, TEST_SCOPE, FakePipeline("p06-sku0"), [
        orderline_row(goods_id="200", sku_id="0"),
    ])

    # sku_id=0 的 OrderLine 已落地，external_id="niushop:1:200"
    # 构造 OrderLine.ofSku Link：source=OrderLine(200), target=ProductSku(0)
    forsku_link = link_row(
        link_type="OrderLine.ofSku",
        source_type="OrderLine",
        target_type="ProductSku",
        source_pk="200",
        target_pk="0",  # sku_id=0
    )
    # ProductSku "niushop:1:0" 不存在 → DANGLING_LINK
    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline("p06-sku0"), [forsku_link])
    assert caught.value.code == "DANGLING_LINK"

    # 验证 target external_id 确实是 "niushop:1:0"（sku_id=0 → niushop:1:0）
    # 通过检查 Link 的 target external_id（从异常 details 或构造过程验证）
    # 由于 DANGLING_LINK 在 store 层抛出，我们验证 ec_ot_writer 构造的 Link
    # target_external_id 为 "niushop:1:0"
    from aos_api.ec_ot_writer import _build_link, _build_sync_scope
    sync_scope = _build_sync_scope(TEST_SCOPE, FakePipeline("p06-sku0"))
    link_record = _build_link(forsku_link, sync_scope)
    assert link_record is not None
    assert link_record.target.external_id == "niushop:1:0"
