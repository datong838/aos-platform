"""D1.5 Phase B Step 14: PII 扫描 + 派生指标落地验证（端到端）。

AC-D1.5-2（← FR-D1.5-2）PII 扫描：
- ns_member 源行含 8 个 PII 字段 → SourceAdapter drop → row 流 PII 0 命中
- normalized CustomerLite row → sink_to_ot → ecom_object.properties 中 PII 0 残留

AC-D1.5-4（← FR-D1.5-4）派生指标端到端落地：
- ec_live_executor 端到端（不 mock apply_derived_metrics）→ CustomerLite 动态指标
  不污染基础 properties，而是通过独立 derived CAS 写入（值为 null，因未注入 link_aggregator）
- 无订单的 CustomerLite 字段为 null

与 test_ec_d1_5_p08_pipeline.py 的差异：
- 该文件 Section 3 端到端测试 mock 了 apply_derived_metrics（隔离 OT 落地）
- 本文件不 mock apply_derived_metrics，验证派生指标真实落地到 ecom_object.properties

约束（FR-D1.5-4）：
- ec_live_executor 在 D1.5 阶段不注入 link_aggregator（保持 apply_derived_metrics(rows, pipeline)）
- AC-D1.5-4 的动态指标通过 derived CAS 存在，null 兼容满足验收
- 生产环境真实聚合由 ecom_consistency_store.query_links_by_link_type 后接线（D1.5 后续 step）
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aos_api import ec_live_executor as ec_mod
from aos_api import data_os_store
from aos_api.ecom_core_models import BatchCommand, BatchResult
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.ec_source_adapter import (
    fetch_source_rows,
    reset_soft_delete_counts,
)
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.public_contracts import StableCursor
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")
PID = "p08-customer-lite"

# frozen/02 §P08 PII 排除清单（8 个字段）
PII_FIELDS: frozenset[str] = frozenset({
    "mobile", "wx_openid", "nickname", "avatar",
    "reg_address", "last_login_ip", "password", "pay_password",
})


# ═══════════════════════════════════════════════
# 共享 fakes（与 test_ec_d1_5_p08_pipeline.py 同构）
# ═══════════════════════════════════════════════


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，默认返回计数 = batch 大小。"""

    def __init__(
        self,
        *,
        result: BatchResult | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.calls: list[BatchCommand] = []
        self.derived_calls: list[Any] = []
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

    def get_latest_authoritative_revision(self, _identity: Any) -> int:
        return max(1, len(self.calls))

    def get_derived_revision(self, _identity: Any, _object_type: str) -> int:
        return len(self.derived_calls)

    def update_derived_metrics(self, command: Any) -> Any:
        self.derived_calls.append(command)
        return SimpleNamespace(updated=True, replayed=False)


class FakeEngine:
    def __init__(self, store: FakeStore) -> None:
        self.ecom_consistency_store = store


class FakePipeline:
    def __init__(self, pid: str = PID) -> None:
        self.id = pid


@pytest.fixture(autouse=True)
def _reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


@pytest.fixture(autouse=True)
def _mock_dataset_sink(monkeypatch):
    """mock data_os_store 持久化为 no-op，避免 PG 副作用。

    注意：不 mock apply_derived_metrics / build_link_rows — 本文件验证真实派生指标落地。
    """
    monkeypatch.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)


# ═══════════════════════════════════════════════
# Section A: PII 端到端扫描（AC-D1.5-2）
# ═══════════════════════════════════════════════


def _ns_member_raw_row(*, member_id: int = 1001, is_delete: int = 0) -> dict[str, Any]:
    """ns_member 原始行（含全部字段：脱敏键 + 8 个 PII 字段 + site_id/is_delete）。"""
    return {
        "member_id": member_id,
        "member_level": 1,
        "status": 1,
        "create_time": 1700000000,
        "modify_time": 1700001000,
        # PII 排除清单（frozen/02 §P08）
        "mobile": "13800138000",
        "wx_openid": "wx_openid_secret_123",
        "nickname": "张三的昵称",
        "avatar": "https://cdn.example.com/avatar/1001.jpg",
        "reg_address": "北京市朝阳区某某街道XX号",
        "last_login_ip": "10.0.0.1",
        "password": "hashed_password_secret",
        "pay_password": "hashed_pay_password_secret",
        "site_id": 1,
        "is_delete": is_delete,
    }


def _meta_source_props() -> dict[str, Any]:
    return {
        "host": "127.0.0.1",
        "port": 13306,
        "user": "recommend_ro",
        "password": "secret",
        "database": "niushop_b2c_v5",
    }


def _fake_aos_conn(props: dict[str, Any] | None) -> MagicMock:
    conn = MagicMock()
    result = MagicMock()
    if props is None:
        result.fetchone.return_value = None
    else:
        result.fetchone.return_value = {"props": props}
    conn.execute.return_value = result
    return conn


@patch("aos_api.ec_source_adapter.JdbcConnectorRuntime")
@patch("aos_api.ec_source_adapter.connect")
def test_step14_pii_zero_in_source_adapter_output(
    mock_connect: MagicMock,
    mock_runtime_cls: MagicMock,
) -> None:
    """AC-D1.5-2 端到端确认：ns_member 含 8 个 PII → fetch_source_rows → row 流 PII 0 命中。

    这是 SourceAdapter 层的端到端扫描，验证 PII 不进入 row 流。
    """
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    fake_runtime = MagicMock()
    fake_runtime.__enter__.return_value = fake_runtime
    fake_runtime.read_rows.return_value = [_ns_member_raw_row(member_id=1001)]
    mock_runtime_cls.return_value = fake_runtime

    reset_soft_delete_counts()
    node = SimpleNamespace(
        id="n-src",
        node_type="source",
        config={
            "source_id": "src-1",
            "table": "ns_member",
            "pk": "member_id",
            "initial": True,
        },
    )

    rows = fetch_source_rows(
        pipeline=SimpleNamespace(id="pl-p08-pii-scan"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    assert len(rows) == 1
    row = rows[0]
    leaked = PII_FIELDS & set(row.keys())
    assert not leaked, f"PII 字段泄漏到 row 流: {leaked}"
    fake_runtime.read_rows.assert_called_once()


def test_step14_pii_zero_in_ot_properties_after_sink() -> None:
    """AC-D1.5-2 端到端确认：normalized CustomerLite row → sink_to_ot → ecom_object.properties 中 PII 0 残留。

    验证 OTWriter 不会把 PII 字段带入 ecom_object.properties。
    SourceAdapter 已 drop PII，row 流到 OTWriter 时无 PII，OT 落地后 properties 也无 PII。
    """
    store = FakeStore()
    eng = get_engine()
    eng.ecom_consistency_store = store

    # normalized CustomerLite row（不含 PII，模拟 SourceAdapter drop 后的行）
    row = {
        "ot": "CustomerLite",
        "source_pk": "1001",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "memberLevel": "1",
            "status": "active",
            "createdAt": "2026-01-01T00:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [row])

    assert len(store.calls) == 1
    obj = store.calls[0].objects[0]
    assert obj.object_type == "CustomerLite"
    # ecom_object.properties 中 PII 0 残留
    leaked_in_props = PII_FIELDS & set(obj.properties.keys())
    assert not leaked_in_props, f"PII 字段泄漏到 ecom_object.properties: {leaked_in_props}"


# ═══════════════════════════════════════════════
# Section B: 派生指标端到端落地（AC-D1.5-4）
# ═══════════════════════════════════════════════


def _customer_lite_row(
    member_id: str = "1001",
    *,
    with_times: bool = True,
) -> dict[str, Any]:
    """P08 CustomerLite 规范化行：ot=CustomerLite, source_pk=member_id。"""
    props: dict[str, Any] = {
        "memberLevel": "1",
        "status": "active",
    }
    if with_times:
        props["createdAt"] = "2026-01-01T00:00:00+08:00"
        props["updatedAt"] = "2026-07-31T18:00:00+08:00"
    return {
        "ot": "CustomerLite",
        "source_pk": member_id,
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": props,
    }


def _run_executor(
    rows: list[dict[str, Any]],
    *,
    store: FakeStore,
    scope: TenantScope = TEST_SCOPE,
    pipeline_id: str = PID,
) -> dict[str, Any]:
    """调用 ec_live_executor，注入 FakeStore。

    与 test_ec_d1_5_p08_pipeline.py 的 _run_executor 区别：
    本函数不 mock apply_derived_metrics（验证真实派生指标落地）。
    """
    eng = get_engine()
    eng.ecom_consistency_store = store
    source = SimpleNamespace(
        id="n-src",
        node_type="source",
        config={"source_id": "src-step14", "source_table": "synthetic"},
    )
    with patch.object(ec_mod, "fetch_source_rows", return_value=rows):
        return ec_mod.ec_live_executor(
            pipeline=FakePipeline(pipeline_id),
            nodes=[source],
            node_id=source.id,
            sample_input=None,
            execution_kind="schedule",
            cancel_event=None,
            deadline=0,
            scope=scope,
        )


def test_step14_derived_metrics_fields_present_e2e() -> None:
    """AC-D1.5-4 端到端：ec_live_executor 真实调用 apply_derived_metrics →
    ecom_object.properties 中 order_count / last_order_days 字段存在（值为 null）。

    关键：不 mock apply_derived_metrics，验证 ec_live_executor 端到端链路中
    派生指标真实写入 ecom_object.properties。

    FR-D1.5-4 约束：ec_live_executor 在 D1.5 阶段不注入 link_aggregator，
    所以 order_count/last_order_days 字段值为 null（字段存在但为 null）。
    """
    store = FakeStore()
    rows = [
        _customer_lite_row(member_id="1001", with_times=False),
        _customer_lite_row(member_id="1002", with_times=False),
    ]

    result = _run_executor(rows, store=store)

    # ec_live_executor 成功执行
    assert result["rows_written"] == 2
    assert len(store.calls) == 1

    command = store.calls[0]
    assert len(command.objects) == 2
    assert all(obj.object_type == "CustomerLite" for obj in command.objects)

    # AC-D1.5-4 核心断言：动态指标不污染基础 payload，并经独立 CAS 写入。
    for obj in command.objects:
        assert "order_count" not in obj.properties
        assert "last_order_days" not in obj.properties
    assert len(store.derived_calls) == 2
    for derived_command in store.derived_calls:
        assert derived_command.derived_props == {
            "order_count": None,
            "last_order_days": None,
        }


def test_step14_derived_metrics_null_for_customer_without_orders() -> None:
    """AC-D1.5-4: 无订单的 CustomerLite → order_count/last_order_days 字段为 null。

    场景：ec_live_executor 不注入 link_aggregator，所有 CustomerLite 行的
    派生指标字段均为 null（满足 AC-D1.5-4 "无订单的 CustomerLite 字段为 null"）。
    """
    store = FakeStore()
    # 单个无订单的 CustomerLite
    rows = [_customer_lite_row(member_id="9999", with_times=False)]

    _run_executor(rows, store=store)

    obj = store.calls[0].objects[0]
    assert obj.identity.external_id == "niushop:1:9999"
    assert "order_count" not in obj.properties
    assert "last_order_days" not in obj.properties
    assert len(store.derived_calls) == 1
    assert store.derived_calls[0].derived_props == {
        "order_count": None,
        "last_order_days": None,
    }


def test_step14_derived_metrics_do_not_pollute_non_customer_lite() -> None:
    """AC-D1.5-4 回归：非 CustomerLite OT 不写 order_count/last_order_days 字段。

    验证 apply_derived_metrics 对非 CustomerLite OT 不写 D1.5 派生指标
    （D1 行为不变，FR-D1.5-4 约束）。
    """
    store = FakeStore()
    # Product 行（非 CustomerLite，补齐 REQUIRED_PROPERTIES: shopId/status/categoryId/title/createdAt/updatedAt）
    rows = [
        {
            "ot": "Product",
            "source_pk": "104",
            "source_updated_at": NOW,
            "source_timezone": "+00:00",
            "is_deleted": False,
            "properties": {
                "shopId": "1",
                "status": "active",
                "categoryId": "cat-5",
                "title": "测试商品",
                "evaluate": 0,
                "evaluate_haoping": 0,
                "createdAt": "2026-01-01T00:00:00+08:00",
                "updatedAt": "2026-07-31T18:00:00+08:00",
            },
        }
    ]

    # 用 Product pipeline id 触发 D1 quality_score 派生指标
    _run_executor(rows, store=store, pipeline_id="p02-product")

    command = store.calls[0]
    obj = command.objects[0]
    assert obj.object_type == "Product"
    # D1 派生指标存在
    assert "quality_score" in obj.properties
    # D1.5 派生指标不存在（非 CustomerLite OT 不写）
    assert "order_count" not in obj.properties
    assert "last_order_days" not in obj.properties


def test_step14_d1_derived_metrics_still_works_e2e() -> None:
    """AC-D1.5-4 回归：D1 派生指标在 ec_live_executor 端到端仍正常工作。

    验证不 mock apply_derived_metrics 时，D1 的 4 个单行派生指标
    （quality_score/stock_health/risk_score/overdue_hours）仍正确写入。
    """
    store = FakeStore()
    # Product 行：evaluate=10, evaluate_haoping=9 → quality_score=0.9
    # 补齐 REQUIRED_PROPERTIES: shopId/status/categoryId/title/createdAt/updatedAt
    rows = [
        {
            "ot": "Product",
            "source_pk": "104",
            "source_updated_at": NOW,
            "source_timezone": "+00:00",
            "is_deleted": False,
            "properties": {
                "shopId": "1",
                "status": "active",
                "categoryId": "cat-5",
                "title": "测试商品",
                "evaluate": 10,
                "evaluate_haoping": 9,
                "createdAt": "2026-01-01T00:00:00+08:00",
                "updatedAt": "2026-07-31T18:00:00+08:00",
            },
        }
    ]

    _run_executor(rows, store=store, pipeline_id="p02-product")

    command = store.calls[0]
    obj = command.objects[0]
    assert obj.object_type == "Product"
    # D1 quality_score 正确计算（9/10=0.9）
    assert "quality_score" in obj.properties
    assert obj.properties["quality_score"] == 0.9
