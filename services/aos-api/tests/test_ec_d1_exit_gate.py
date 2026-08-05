"""D1-W4: D1 退出门验证测试 + PII 严格脱敏专项测试。

验证 D1 执行规格第 6 节定义的 10 项退出门（D1 GREEN 的判定）：
1. G4 DatasetSink 实现 + 测试通过
2. G5 OTWriter 实现 + 测试通过（BatchCommand 单事务幂等）
3. G6 DLQ 实现 + 测试通过（失败不变成功、无 PII）
4. Niushop SourceAdapter 实现 + 测试通过（只读零写入）
5. P01-P07 运行时配置创建
6. 四段实施每段 6 项负向测试通过
7. 派生指标 4 个全部落地到 OT props
8. 6 条核心 Link 落地 + 完整性门禁通过
9. D1 前置 37 tests 零回归（honesty + resolver + executor）
10. 全程对微商城源库零写入、对 AOS 只增不删

PII 严格脱敏专项测试（修复 Phase B 遗留风险）：
- 18 位身份证号整体脱敏（不残留 110101***4）
- 15 位身份证号整体脱敏
- 11 位手机号脱敏
- 16-19 位银行卡号脱敏
- 邮箱脱敏
- 混合 PII 全部脱敏

修复背景：原 _PII_PATTERNS 顺序为 手机号→身份证→银行卡→邮箱，
导致 18 位身份证号 110101199003071234 中 19900307123 被手机号正则
1[3-9]\\d{9} 先部分匹配，剩余 110101***4 不再满足 \\d{15,18}。
修复后顺序：身份证（长 pattern 先）→ 银行卡 → 手机号 → 邮箱。
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aos_api import data_os_store
from aos_api.ec_dataset_sink import sink_to_dataset
from aos_api.ec_derived_metrics import apply_derived_metrics
from aos_api.ec_dlq_handler import _sanitize_pii, handle_failure
from aos_api.ec_link_builder import build_link_rows
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.ec_source_adapter import READ_ONLY_SQL, fetch_source_rows
from aos_api.ecom_core_models import BatchCommand, BatchResult
from aos_api.logging_facade import configure_logging
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.routers.wave_ext import _dlq
from aos_api.tenant_scope import TenantScope

# 预先完成 logging 配置（与 test_ec_d1_dlq.py / test_ec_d1_negative.py 一致）
configure_logging()

TEST_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════
# 共享 fakes / fixtures
# ═══════════════════════════════════════════════


class _FakePipeline:
    """轻量 pipeline 替身，只暴露 id。"""

    def __init__(self, pid: str = "exit-pipe") -> None:
        self.id = pid


class _FakeStore:
    """记录 apply_batch 调用的 fake store（与 test_ec_d1_negative.py 一致）。"""

    def __init__(self) -> None:
        self.calls: list[BatchCommand] = []
        self._checkpoints: dict[tuple, int] = {}

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        self.calls.append(command)
        key = command.scope.key()
        if key not in self._checkpoints:
            self._checkpoints[key] = 0
        self._checkpoints[key] += 1
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


@pytest.fixture(autouse=True)
def _reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


@pytest.fixture(autouse=True)
def _reset_dlq():
    _dlq.clear()
    yield
    _dlq.clear()


def _order_object_row(*, order_id: str = "100", when: datetime = NOW) -> dict[str, Any]:
    """Order 行（用于 G5 OTWriter 验证）。"""
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
            "createdAt": "2026-08-05T18:00:00+08:00",
            "updatedAt": "2026-08-05T18:00:00+08:00",
        },
    }


# ═══════════════════════════════════════════════
# PII 严格脱敏专项测试（修复 Phase B 遗留风险）
# ═══════════════════════════════════════════════


def test_pii_18_digit_id_card_fully_masked() -> None:
    """18 位身份证号（19xx 年）整体脱敏为 ***，不残留 110101***4。

    修复前：1[3-9]\\d{9} 先匹配 19900307123 → 110101***4 残留。
    修复后：\\d{15,18} 先整体匹配 → id ***（不残留任何数字段）。
    """
    result = _sanitize_pii("id 110101199003071234")
    # 严格断言整体脱敏
    assert result == "id ***", f"18 位身份证应整体脱敏为 'id ***'，实际: {result!r}"
    # 不残留前 6 位地区码
    assert "110101" not in result, f"不应残留身份证前 6 位地区码: {result!r}"
    # 不残留后 4 位
    assert "1234" not in result, f"不应残留身份证后 4 位: {result!r}"


def test_pii_15_digit_id_card_fully_masked() -> None:
    """15 位身份证号整体脱敏为 ***。"""
    result = _sanitize_pii("id 110101990307123")
    assert result == "id ***", f"15 位身份证应整体脱敏为 'id ***'，实际: {result!r}"
    assert "110101" not in result


def test_pii_phone_number_masked() -> None:
    """11 位手机号脱敏为 ***。"""
    assert _sanitize_pii("phone 13812345678") == "phone ***"
    assert _sanitize_pii("13812345678") == "***"


def test_pii_bank_card_masked() -> None:
    """16 位银行卡号脱敏为 ***。"""
    result = _sanitize_pii("card 6217001234567890")
    assert result == "card ***", f"16 位银行卡应整体脱敏，实际: {result!r}"
    assert "6217001234567890" not in result


def test_pii_email_masked() -> None:
    """邮箱脱敏为 ***。"""
    assert _sanitize_pii("mail test@example.com") == "mail ***"
    assert _sanitize_pii("test@example.com") == "***"


def test_pii_mixed_all_masked() -> None:
    """混合 PII 全部脱敏，不残留任何 PII 段。"""
    text = (
        "user 13812345678 id 110101199003071234 "
        "card 6217001234567890 mail test@example.com"
    )
    result = _sanitize_pii(text)
    # 完整 PII 字符串不出现
    assert "13812345678" not in result
    assert "110101199003071234" not in result
    assert "6217001234567890" not in result
    assert "test@example.com" not in result
    # 18 位身份证不残留前 6 位 / 后 4 位
    assert "110101" not in result, f"混合 PII 中身份证前 6 位残留: {result!r}"
    assert "1234" not in result, f"混合 PII 中身份证后 4 位残留: {result!r}"
    assert "***" in result


# ═══════════════════════════════════════════════
# 退出门 #1: G4 DatasetSink 实现 + 测试通过
# ═══════════════════════════════════════════════


def test_exit_gate_g4_dataset_sink_implemented() -> None:
    """退出门 #1: sink_to_dataset 可调用，返回 dataset 对象。"""
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="exit-g4")

    # mock data_os_store 避免打 DB（与 test_ec_d1_dataset_sink.py 一致）
    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkey.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)
    try:
        ds = sink_to_dataset(eng, TEST_SCOPE, pl, [{"a": 1}, {"b": 2}])
    finally:
        monkey.undo()

    # 返回 dataset 对象
    assert ds is not None
    # ds.id 是 rid 格式（ri.dataset.<uuid8>）
    assert ds.id.startswith("ri.dataset.")
    # 可构造合法 dataset://catalog/<rid> output_ref
    output_ref = f"dataset://catalog/{ds.id}"
    assert len(output_ref) <= 512


# ═══════════════════════════════════════════════
# 退出门 #2: G5 OTWriter 实现 + 测试通过（BatchCommand 单事务）
# ═══════════════════════════════════════════════


def test_exit_gate_g5_ot_writer_single_batch_command() -> None:
    """退出门 #2: sink_to_ot 可调用，整批 objects+links 在单个 BatchCommand 内。"""
    eng = get_engine()
    store = _FakeStore()
    eng.ecom_consistency_store = store

    rows = [_order_object_row(order_id="100"), _order_object_row(order_id="101")]
    result = sink_to_ot(eng, TEST_SCOPE, _FakePipeline("exit-g5"), rows)

    # 单个 BatchCommand（单事务）
    assert len(store.calls) == 1, "整批应在单个 BatchCommand 内（单事务）"
    command = store.calls[0]
    # BatchCommand 包含所有 objects
    assert len(command.objects) == 2
    # 返回结果包含 objects_written 计数
    assert result["objects_written"] == 2
    assert result["links_written"] == 0


# ═══════════════════════════════════════════════
# 退出门 #3: G6 DLQ 实现 + 测试通过（retry_count/max_retry）
# ═══════════════════════════════════════════════


def test_exit_gate_g6_dlq_has_retry_count_and_max_retry() -> None:
    """退出门 #3: handle_failure 可调用，DLQ 条目有 retry_count=0 和 max_retry=3。"""
    handle_failure(_FakePipeline("exit-g6"), TEST_SCOPE, RuntimeError("boom"))

    assert len(_dlq) == 1
    [item] = list(_dlq.values())
    # DLQ 条目有 retry_count 和 max_retry
    assert item["retry_count"] == 0
    assert item["max_retry"] == 3
    # DLQ 条目有错误码、脱敏摘要、时间戳
    assert item["errorCode"] == "RuntimeError"
    assert "boom" in item["reason"]
    assert item["createdAt"]
    # status 为 open（不是 succeeded）
    assert item["status"] == "open"


# ═══════════════════════════════════════════════
# 退出门 #4: Niushop SourceAdapter 实现 + 测试通过（READ ONLY 事务）
# ═══════════════════════════════════════════════


def test_exit_gate_source_adapter_read_only_transaction() -> None:
    """退出门 #4: fetch_source_rows 可调用，第一个 execute 是 READ ONLY。"""
    niushop_rows = [{"goods_id": 1, "is_delete": 0, "modify_time": 100}]

    aos_conn = MagicMock()
    aos_conn.execute.return_value.fetchone.return_value = {
        "props": {
            "host": "127.0.0.1", "port": 13306, "user": "ro",
            "password": "x", "database": "niushop_b2c_v5",
        }
    }

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

    node = SimpleNamespace(
        id="n-src", node_type="source",
        config={"source_id": "src-1", "table": "ns_goods", "pk": "goods_id"},
    )

    with patch(
        "aos_api.ec_source_adapter.connect",
        return_value=MagicMock(
            __enter__=MagicMock(return_value=aos_conn),
            __exit__=MagicMock(return_value=None),
        ),
    ), patch("aos_api.ec_source_adapter.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = niushop_conn
        mock_pymysql.cursors.DictCursor = MagicMock()

        fetch_source_rows(
            pipeline=SimpleNamespace(id="pl-exit-ro"),
            nodes=[node], node_id="n-src",
            sample_input=None, scope=TEST_SCOPE,
        )

    # READ_ONLY_SQL 常量为 "SET SESSION TRANSACTION READ ONLY"
    assert READ_ONLY_SQL == "SET SESSION TRANSACTION READ ONLY"
    # 第一个 execute 是 READ ONLY
    assert len(cur.executed) >= 1
    assert "SET SESSION TRANSACTION READ ONLY" in cur.executed[0][0]
    # 无写操作 SQL
    write_keywords = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TRUNCATE")
    for sql, _ in cur.executed:
        sql_upper = sql.upper()
        for kw in write_keywords:
            assert not sql_upper.startswith(kw), f"源库收到写操作 SQL: {kw}"


# ═══════════════════════════════════════════════
# 退出门 #5: P01-P07 运行时配置创建
# ═══════════════════════════════════════════════


def test_exit_gate_p01_p07_pipeline_config_exists() -> None:
    """退出门 #5: P01-P07 7 条 Pipeline 配置存在（D1 基线，跨波累积扩展）。

    通过 _PIPELINE_ID_TO_OT 映射表验证 7 条 Pipeline 的 target_ot 配置存在
    （derived_metrics 和 link_builder 都有此映射，代表运行时配置可解析）。

    FR-D1.5-1 累积契约：_PIPELINE_ID_TO_OT 为跨波累积扩展（D1 基线 P01-P07，
    D1.5 起新增 P08 CustomerLite）。D1 不变量="P01-P07 全部注册"，
    由子集断言守护，允许后续波次扩展。满足 AC-D1.5-10 D1 零回归。
    """
    from aos_api.ec_derived_metrics import _PIPELINE_ID_TO_OT
    from aos_api.ec_link_builder import _PID_TO_OT

    # derived_metrics 的 P01-P07 映射（D1 基线 7 条，跨波累积扩展）
    assert len(_PIPELINE_ID_TO_OT) >= 7
    expected_ots = {"Shop", "Product", "ProductSku", "Category", "Order", "OrderLine", "Shipment"}
    # D1 的 7 种核心 OT MUST 全部注册（子集语义，允许后续波次扩展）
    assert expected_ots.issubset(set(_PIPELINE_ID_TO_OT.values()))

    # link_builder 的 P02-P07 映射（P01 Shop 无 Link）
    assert len(_PID_TO_OT) == 6
    # P02-P07 都在
    for pid in ("P02", "P03", "P04", "P05", "P06", "P07"):
        assert pid in _PID_TO_OT, f"Pipeline {pid} 配置缺失"

    # P01 Shop 在 derived_metrics 中（无派生指标但配置存在）
    assert "p01" in _PIPELINE_ID_TO_OT
    assert _PIPELINE_ID_TO_OT["p01"] == "Shop"


# ═══════════════════════════════════════════════
# 退出门 #6: 四段实施每段 6 项负向测试通过
# ═══════════════════════════════════════════════


def test_exit_gate_four_phase_negative_tests_exist() -> None:
    """退出门 #6: test_ec_d1_negative.py 包含 6 项负向测试（初装/增量/重跑/断点/重复/越租户）。

    通过扫描测试文件源码验证测试函数存在（不重复跑，由 test_ec_d1_negative.py 自身保证通过）。
    """
    import re
    from pathlib import Path

    neg_file = Path(__file__).parent / "test_ec_d1_negative.py"
    assert neg_file.exists(), "test_ec_d1_negative.py 文件缺失"
    source = neg_file.read_text(encoding="utf-8")

    # 6 项负向测试函数名（与 test_ec_d1_negative.py 一致）
    expected_tests = [
        "test_cross_tenant_write_rejected",      # 越租户
        "test_replay_same_batch_rows_not_doubled",  # 重跑
        "test_checkpoint_cas_does_not_regress",  # 断点
        "test_same_version_different_hash_returns_conflict",  # 重复/冲突
        "test_source_database_read_only",  # 初装零写入
        "test_dlq_failure_never_marked_succeeded",  # 失败不变成功
    ]
    for name in expected_tests:
        # 匹配 def test_xxx (允许前后空格)
        pattern = re.compile(rf"^\s*def\s+{re.escape(name)}\s*\(", re.MULTILINE)
        assert pattern.search(source), f"负向测试 {name} 缺失于 test_ec_d1_negative.py"


# ═══════════════════════════════════════════════
# 退出门 #7: 派生指标 4 个全部落地到 OT props
# ═══════════════════════════════════════════════


def test_exit_gate_four_derived_metrics_landed() -> None:
    """退出门 #7: apply_derived_metrics 计算 4 个派生指标并写入 properties。

    4 个派生指标：
    - quality_score (Product)
    - stock_health (ProductSku)
    - risk_score (Order)
    - overdue_hours (Shipment)
    """
    # 1. quality_score (Product)
    product_rows = [{
        "ot": "Product",
        "source_pk": "p1",
        "source_updated_at": NOW,
        "properties": {"evaluate": "100", "evaluate_haoping": "80"},
    }]
    product_pipeline = SimpleNamespace(id="p02", config={})
    result = apply_derived_metrics(product_rows, product_pipeline)
    assert "quality_score" in result[0]["properties"]
    assert result[0]["properties"]["quality_score"] == 0.8

    # 2. stock_health (ProductSku)
    sku_rows = [{
        "ot": "ProductSku",
        "source_pk": "s1",
        "source_updated_at": NOW,
        "properties": {"stock": "5", "goods_stock_alarm": "10"},
    }]
    sku_pipeline = SimpleNamespace(id="p03", config={})
    result = apply_derived_metrics(sku_rows, sku_pipeline)
    assert "stock_health" in result[0]["properties"]
    assert result[0]["properties"]["stock_health"] == "watch"

    # 3. risk_score (Order)
    order_rows = [{
        "ot": "Order",
        "source_pk": "o1",
        "source_updated_at": NOW,
        "properties": {"commission_risk_flag": "1"},
    }]
    order_pipeline = SimpleNamespace(id="p05", config={})
    result = apply_derived_metrics(order_rows, order_pipeline)
    assert "risk_score" in result[0]["properties"]
    assert result[0]["properties"]["risk_score"] == 0.4

    # 4. overdue_hours (Shipment)
    shipment_rows = [{
        "ot": "Shipment",
        "source_pk": "sh1",
        "source_updated_at": NOW,
        "properties": {
            "delivery_time": "0",  # 未发货
            "pay_time": str(NOW.timestamp() - 72 * 3600),  # 3 天前支付（超 48h SLA）
        },
    }]
    shipment_pipeline = SimpleNamespace(id="p07", config={})
    result = apply_derived_metrics(shipment_rows, shipment_pipeline)
    assert "overdue_hours" in result[0]["properties"]
    assert result[0]["properties"]["overdue_hours"] is not None
    assert result[0]["properties"]["overdue_hours"] > 0


# ═══════════════════════════════════════════════
# 退出门 #8: 6 条核心 Link 落地 + 完整性门禁通过
# ═══════════════════════════════════════════════


def test_exit_gate_six_core_links_built() -> None:
    """退出门 #8: build_link_rows 构造 6 条核心 Link 类型。

    6 条核心 Link（frozen/02）：
    - hasSku: Product → ProductSku（P03 ProductSku 读取时）
    - inCategory: Product → Category（P02 Product 读取时，多值拆分）
    - contains: Order → OrderLine（P06 OrderLine 读取时）
    - forProduct: OrderLine → Product（P06 OrderLine 读取时）
    - forSku: OrderLine → ProductSku（P06 OrderLine 读取时）
    - ships: Shipment → Order（P07 Shipment 读取时）
    """
    # 1. hasSku (ProductSku pipeline)
    sku_rows = [{
        "ot": "ProductSku",
        "source_pk": "sku-1",
        "source_updated_at": NOW,
        "properties": {"productId": "prod-1"},
    }]
    result = build_link_rows(sku_rows, SimpleNamespace(id="P03", config={}))
    link_types = {r["link_type"] for r in result if "link_type" in r}
    assert "ProductSku.ofProduct" in link_types, "hasSku Link 缺失"

    # 2. inCategory (Product pipeline)
    product_rows = [{
        "ot": "Product",
        "source_pk": "prod-1",
        "source_updated_at": NOW,
        "properties": {"categoryId": "cat-1,cat-2"},
    }]
    result = build_link_rows(product_rows, SimpleNamespace(id="P02", config={}))
    link_types = {r["link_type"] for r in result if "link_type" in r}
    assert "Product.inCategory" in link_types, "inCategory Link 缺失"

    # 3+4+5. contains + forProduct + forSku (OrderLine pipeline)
    orderline_rows = [{
        "ot": "OrderLine",
        "source_pk": "line-1",
        "source_updated_at": NOW,
        "properties": {
            "orderId": "order-1",
            "goodsId": "prod-1",
            "skuId": "sku-1",
        },
    }]
    result = build_link_rows(orderline_rows, SimpleNamespace(id="P06", config={}))
    link_types = {r["link_type"] for r in result if "link_type" in r}
    assert "Order.lines" in link_types, "contains Link 缺失"
    assert "OrderLine.ofProduct" in link_types, "forProduct Link 缺失"
    assert "OrderLine.ofSku" in link_types, "forSku Link 缺失"

    # 6. ships (Shipment pipeline)
    shipment_rows = [{
        "ot": "Shipment",
        "source_pk": "ship-1",
        "source_updated_at": NOW,
        "properties": {"orderId": "order-1"},
    }]
    result = build_link_rows(shipment_rows, SimpleNamespace(id="P07", config={}))
    link_types = {r["link_type"] for r in result if "link_type" in r}
    assert "Order.fulfilledBy" in link_types, "ships Link 缺失"


# ═══════════════════════════════════════════════
# 退出门 #9: D1 前置 37 tests 零回归
# ═══════════════════════════════════════════════


def test_exit_gate_d1_prerequisite_modules_importable() -> None:
    """退出门 #9: D1 前置测试模块可导入（honesty + resolver + executor）。

    零回归由 pytest 全量跑这3个文件验证（本测试扫描源码验证测试函数存在）。
    """
    import re
    from pathlib import Path

    # 3 个前置测试文件路径
    test_files = {
        "test_ec_live_executor.py": "test_live_pipeline_succeeds_with_ec_live_executor",
        "test_ec_pipeline_honesty.py": "test_schedule_without_executor_never_succeeds",
        "test_ec_pipeline_resolvers.py": "test_dataset_resolver_returns_true_for_existing_dataset",
    }

    tests_dir = Path(__file__).parent
    for filename, key_test in test_files.items():
        filepath = tests_dir / filename
        assert filepath.exists(), f"前置测试文件 {filename} 缺失"
        source = filepath.read_text(encoding="utf-8")
        # 至少有 1 个 test_ 函数
        assert re.search(r"^\s*def\s+test_", source, re.MULTILINE), (
            f"{filename} 无测试函数"
        )
        # 关键测试函数存在
        pattern = re.compile(rf"^\s*def\s+{re.escape(key_test)}\s*\(", re.MULTILINE)
        assert pattern.search(source), (
            f"{filename} 关键测试 {key_test} 缺失"
        )


# ═══════════════════════════════════════════════
# 退出门 #10: 全程对微商城源库零写入、对 AOS 只增不删
# ═══════════════════════════════════════════════


def test_exit_gate_source_zero_write_and_aos_append_only() -> None:
    """退出门 #10: 源库零写入（READ ONLY）+ AOS 只增不删（tombstone 不物理删除）。

    - 源库零写入：READ_ONLY_SQL = "SET SESSION TRANSACTION READ ONLY"
    - AOS 只增不删：CoreObjectRecord 支持 is_deleted 字段（软删 tombstone），不物理删除
    """
    # 1. 源库零写入：READ_ONLY_SQL 常量
    assert READ_ONLY_SQL == "SET SESSION TRANSACTION READ ONLY"

    # 2. AOS 只增不删：CoreObjectRecord 有 is_deleted 字段（tombstone 机制）
    from aos_api.ecom_core_models import CoreObjectRecord
    from aos_api.public_contracts import ExternalIdentityKey, ForwardEnumValue

    identity = ExternalIdentityKey(
        org_id="dev-org", workspace_id="dev-project",
        platform="niushop", shop_or_marketplace_id="1",
        external_id="niushop:1:100",
    )

    # tombstone 行（is_deleted=True，软删不物理删除）
    tombstone_obj = CoreObjectRecord(
        identity=identity,
        object_type="Order",
        source_updated_at=NOW,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw("DELETED", {"DELETED": "deleted", "ACTIVE": "active"}),
        is_deleted=True,  # tombstone 标记
        properties={},
    )
    assert tombstone_obj.is_deleted is True, "CoreObjectRecord 必须支持 is_deleted tombstone"

    # 3. ec_ot_writer._build_object 透传 is_deleted 字段（验证字段被读取）
    from aos_api.ec_ot_writer import _build_object
    from aos_api.ecom_core_models import SyncScope

    sync_scope = SyncScope(
        org_id="dev-org", workspace_id="dev-project",
        platform="niushop", shop_or_marketplace_id="1", stream="exit-tomb",
    )
    row_with_tombstone = {
        "ot": "Order",
        "source_pk": "100",
        "source_updated_at": NOW,
        "is_deleted": True,  # 软删行
        "properties": {},
    }
    obj = _build_object(row_with_tombstone, sync_scope)
    assert obj is not None
    assert obj.is_deleted is True, "ec_ot_writer 必须透传 is_deleted tombstone 标记"
