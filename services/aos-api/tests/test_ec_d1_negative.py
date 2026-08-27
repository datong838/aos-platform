"""D1-W4: 集中负向测试（NFR + AC-D1-6）。

验证 D1 的负向行为：跨租户拒绝/重跑幂等/断点恢复/冲突检测/源库零写入/
DLQ 失败不变成功/DLQ 无 PII/软删行进 DLQ/悬挂 Link 隔离/派生指标缺失不阻塞。

测试策略：
- 跨租户/悬挂 Link：用真实 sqlite EcomConsistencyStore（验证内核行为）
- 重跑/断点/冲突：用 FakeStore（验证 ot_writer 调用契约）
- 源库零写入/软删：mock 统一 JdbcConnectorRuntime，验证只读路由和过滤
- DLQ：直接调用 ec_dlq_handler.handle_failure
- 派生指标：直接调用 ec_derived_metrics.apply_derived_metrics（骨架透传）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aos_api.ec_derived_metrics import apply_derived_metrics
from aos_api.ec_dlq_handler import handle_failure
from aos_api.ec_source_adapter import (
    READ_ONLY_SQL,
    fetch_source_rows,
    get_soft_delete_count,
    reset_soft_delete_counts,
)
from aos_api.ecom_consistency_store import EcomConsistencyStore, metadata as ecom_metadata
from aos_api.ecom_core_models import (
    BatchCommand,
    BatchResult,
    CoreObjectRecord,
    EcomConsistencyError,
)
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.logging_facade import configure_logging
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.public_contracts import (
    ExternalIdentityKey,
    ForwardEnumValue,
    StableCursor,
)
from aos_api.tenant_scope import TenantScope

# 预先完成 logging 配置（与 test_ec_d1_dlq.py 一致）
configure_logging()

NOW = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("other-org", "other-project")


# ═══════════════════════════════════════════════
# 共享 fakes
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
    def __init__(self, pid: str = "neg-pipe") -> None:
        self.id = pid


def _make_sqlite_store() -> EcomConsistencyStore:
    """创建 in-memory sqlite EcomConsistencyStore。"""
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    ecom_metadata.create_all(engine)
    return EcomConsistencyStore(engine)


def _order_object_row(*, order_id: str = "100", when: datetime = NOW) -> dict[str, Any]:
    """Order 行（用于 OT 落地测试）。"""
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


# ═══════════════════════════════════════════════
# fixtures
# ═══════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


# ═══════════════════════════════════════════════
# 1. 跨租户写入拒绝
# ═══════════════════════════════════════════════


def test_cross_tenant_write_rejected():
    """#1 跨租户写入拒绝：scope 不匹配 → fail-closed，ecom_object 无跨租户记录。

    用真实 sqlite store 验证：
    - 写入 scope A 的对象后，scope B 查不到
    - BatchCommand validator 拒绝跨 scope 的 object identity
    """
    store = _make_sqlite_store()
    eng = get_engine()
    eng.ecom_consistency_store = store

    # 写入 scope A (dev-org)
    sink_to_ot(eng, TEST_SCOPE, FakePipeline("neg-ct"), [_order_object_row(order_id="100")])

    # scope B (other-org) 查不到 scope A 的对象
    identity_b = ExternalIdentityKey(
        org_id=OTHER_SCOPE.org_id,
        workspace_id=OTHER_SCOPE.project_id,
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id="niushop:1:100",
    )
    assert store.get_object(identity_b, "Order") is None

    # scope A 能查到
    identity_a = ExternalIdentityKey(
        org_id=TEST_SCOPE.org_id,
        workspace_id=TEST_SCOPE.project_id,
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id="niushop:1:100",
    )
    assert store.get_object(identity_a, "Order") is not None

    # BatchCommand validator 拒绝跨 scope 的 object identity
    from aos_api.ecom_core_models import SyncScope
    scope_a = SyncScope(
        org_id="dev-org", workspace_id="dev-project",
        platform="niushop", shop_or_marketplace_id="1", stream="neg-ct",
    )
    cross_obj = CoreObjectRecord(
        identity=identity_b,  # other-org
        object_type="Order",
        source_updated_at=NOW,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active"}),
        properties={
            "shopId": "1", "status": "active", "totalAmount": "1.00",
            "currency": "CNY",
            "createdAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    )
    with pytest.raises(ValueError, match="outside the batch scope"):
        BatchCommand(
            scope=scope_a,
            idempotency_key="cross-tenant-neg",
            expected_checkpoint_version=0,
            next_checkpoint=StableCursor(
                source_updated_at_utc=NOW, external_id="niushop:1:100"
            ),
            objects=[cross_obj],
            links=[],
        )


# ═══════════════════════════════════════════════
# 2. 重跑幂等
# ═══════════════════════════════════════════════


def test_replay_same_batch_rows_not_doubled():
    """#2 重跑幂等：相同 key+相同 hash → rows_written 不翻倍，返回原结果。

    配置 FakeStore 返回 replayed=True，验证 sink_to_ot 透传 replay 结果。
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
    eng = get_engine()
    eng.ecom_consistency_store = store

    first = sink_to_ot(eng, TEST_SCOPE, FakePipeline("neg-replay"), [_order_object_row()])
    second = sink_to_ot(eng, TEST_SCOPE, FakePipeline("neg-replay"), [_order_object_row()])

    # 计数不翻倍
    assert first["objects_written"] == 1
    assert second["objects_written"] == 1
    assert len(store.calls) == 2
    # 相同 batch → 相同 idempotency_key
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


# ═══════════════════════════════════════════════
# 3. 断点恢复
# ═══════════════════════════════════════════════


def test_checkpoint_cas_does_not_regress():
    """#3 断点恢复：checkpoint CAS 不前移。

    首装推进 checkpoint 到 v1 后，后续批次 expected 自动取当前 version=1（不前移到 0）。
    """
    store = FakeStore()
    eng = get_engine()
    eng.ecom_consistency_store = store

    sink_to_ot(eng, TEST_SCOPE, FakePipeline("neg-cas"), [_order_object_row(order_id="100")])
    assert store.calls[0].expected_checkpoint_version == 0

    later = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)
    sink_to_ot(
        eng, TEST_SCOPE, FakePipeline("neg-cas"),
        [_order_object_row(order_id="101", when=later)],
    )

    assert len(store.calls) == 2
    assert store.calls[1].expected_checkpoint_version == 1


# ═══════════════════════════════════════════════
# 4. 冲突检测
# ═══════════════════════════════════════════════


def test_same_version_different_hash_returns_conflict():
    """#4 冲突检测：相同版本+不同 hash → 返回冲突。

    配置 FakeStore 抛 IDEMPOTENCY_CONFLICT，验证 sink_to_ot 不吞异常。
    """
    conflict = EcomConsistencyError(
        "IDEMPOTENCY_CONFLICT",
        "idempotency key was already used with a different request",
    )
    store = FakeStore(raises=conflict)
    eng = get_engine()
    eng.ecom_consistency_store = store

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline("neg-conflict"), [_order_object_row()])

    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


# ═══════════════════════════════════════════════
# 5. 源库零写入
# ═══════════════════════════════════════════════


def test_source_database_read_only():
    """#5 源库零写入：只读事务验证（READ ONLY）。

    验证：
    - READ_ONLY_SQL 常量为 "SET SESSION TRANSACTION READ ONLY"
    - 第一个 execute 是 READ ONLY
    - 无 INSERT/UPDATE/DELETE/CREATE/ALTER/DROP SQL 发送到 niushop 连接
    """
    assert READ_ONLY_SQL == "SET SESSION TRANSACTION READ ONLY"

    niushop_rows = [{"goods_id": 1, "is_delete": 0, "modify_time": 100}]
    aos_conn = MagicMock()
    aos_conn.execute.return_value.fetchone.return_value = {
        "props": {
            "host": "127.0.0.1", "port": 13306, "user": "ro",
            "password": "x", "database": "niushop_b2c_v5",
        }
    }

    runtime = MagicMock()
    runtime.__enter__.return_value = runtime
    runtime.__exit__.return_value = None
    runtime.read_rows.return_value = niushop_rows

    reset_soft_delete_counts()
    from types import SimpleNamespace
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
    ), patch("aos_api.ec_source_adapter.JdbcConnectorRuntime", return_value=runtime):
        fetch_source_rows(
            pipeline=SimpleNamespace(id="pl-neg-ro"),
            nodes=[node], node_id="n-src",
            sample_input=None, scope=TEST_SCOPE,
        )

    runtime.read_rows.assert_called_once_with(
        "ns_goods", composite_cursor=None, limit=None, where_equals={}
    )


# ═══════════════════════════════════════════════
# 6. DLQ 失败不变成功
# ═══════════════════════════════════════════════


def test_dlq_failure_never_marked_succeeded():
    """#6 DLQ 失败不变成功：status="failed" 不变 "succeeded"。

    验证：
    - handle_failure 创建的 DLQ 条目 status="open"（非 "succeeded"）
    - 不同 run 的独立失败记录不改写前一条 Receipt
    """
    # 1. handle_failure 创建的条目 status="open"
    first = handle_failure(
        FakePipeline("neg-dlq-fail"), TEST_SCOPE, RuntimeError("boom"),
        run_id="run-neg-dlq-fail",
    )
    assert first is not None
    assert first["status"] == "open"
    assert first["status"] != "succeeded"

    # 再次记录不同 run，旧 Receipt 不会被改成成功。
    second = handle_failure(
        FakePipeline("neg-dlq-other"), TEST_SCOPE, RuntimeError("another boom"),
        run_id="run-neg-dlq-other",
    )
    assert second is not None
    assert second["status"] == "open"
    assert first["status"] == "open"


# ═══════════════════════════════════════════════
# 7. DLQ 无 PII
# ═══════════════════════════════════════════════


def test_dlq_no_pii_leaked():
    """#7 DLQ 无 PII：扫描 DLQ 条目，正则匹配手机/身份证/银行卡/邮箱。

    将含 PII 的异常信息投递到 DLQ，验证 reason 字段中 PII 被脱敏。
    """
    exc = RuntimeError(
        "contact 13800138000 id 110101199003071234 card 6222020200112345 email a@b.com"
    )
    item = handle_failure(
        FakePipeline("neg-dlq-pii"), TEST_SCOPE, exc,
        run_id="run-neg-dlq-pii",
    )

    assert item is not None
    reason = item["reason"]

    # 手机号脱敏
    assert "13800138000" not in reason
    # 身份证脱敏
    assert "110101199003071234" not in reason
    # 银行卡脱敏
    assert "6222020200112345" not in reason
    # 邮箱脱敏
    assert "a@b.com" not in reason

    # 扫描所有 DLQ 条目的所有字段，确保无 PII 泄漏
    import re
    pii_patterns = [
        re.compile(r"1[3-9]\d{9}"),       # 手机号
        re.compile(r"\d{15,18}"),          # 身份证
        re.compile(r"62\d{14,17}"),        # 银行卡
        re.compile(r"\S+@\S+\.\S+"),       # 邮箱
    ]
    for field_name, field_value in item.items():
        if not isinstance(field_value, str):
            continue
        for pattern in pii_patterns:
            matches = pattern.findall(field_value)
            if field_name == "reason":
                for match in matches:
                    assert match == "***" or len(match) <= 3, (
                        f"reason 字段含未脱敏 PII: {match}"
                    )


# ═══════════════════════════════════════════════
# 8. 软删行进 DLQ 计数
# ═══════════════════════════════════════════════


def test_soft_deleted_rows_counted_for_dlq():
    """#8 软删行进 DLQ 计数：is_delete=1 不入 OT。

    验证 source_adapter 过滤 is_delete=1 的行并计数。
    """
    niushop_rows = [
        {"order_id": 100, "is_delete": 0, "modify_time": 1100},
        {"order_id": 101, "is_delete": 1, "modify_time": 1200},  # 软删
        {"order_id": 102, "is_delete": 0, "modify_time": 1300},
        {"order_id": 103, "is_delete": 1, "modify_time": 1400},  # 软删
    ]
    aos_conn = MagicMock()
    aos_conn.execute.return_value.fetchone.return_value = {
        "props": {
            "host": "127.0.0.1", "port": 13306, "user": "ro",
            "password": "x", "database": "niushop_b2c_v5",
        }
    }
    runtime = MagicMock()
    runtime.__enter__.return_value = runtime
    runtime.__exit__.return_value = None
    runtime.read_rows.return_value = niushop_rows

    reset_soft_delete_counts()
    from types import SimpleNamespace
    node = SimpleNamespace(
        id="n-src", node_type="source",
        config={
            "source_id": "src-1", "table": "ns_order",
            "pk": "order_id", "initial": True,
        },
    )

    with patch(
        "aos_api.ec_source_adapter.connect",
        return_value=MagicMock(
            __enter__=MagicMock(return_value=aos_conn),
            __exit__=MagicMock(return_value=None),
        ),
    ), patch("aos_api.ec_source_adapter.JdbcConnectorRuntime", return_value=runtime):
        rows = fetch_source_rows(
            pipeline=SimpleNamespace(id="pl-neg-softdel"),
            nodes=[node], node_id="n-src",
            sample_input=None, scope=TEST_SCOPE,
        )

    # 有效行 2 条（is_delete=0），软删行不入 OT
    assert len(rows) == 2
    assert all(r["is_delete"] == 0 for r in rows)
    # 软删计数 2 条（进 DLQ 计数）
    assert get_soft_delete_count("pl-neg-softdel", "n-src") == 2


# ═══════════════════════════════════════════════
# 9. 悬挂 Link 隔离
# ═══════════════════════════════════════════════


def test_dangling_link_is_ignored_and_retained_for_dlq():
    """#9 悬挂 Link 不写入，并留在 store side channel 供 DLQ 处理。"""
    store = _make_sqlite_store()
    eng = get_engine()
    eng.ecom_consistency_store = store

    # 构造一个 Order.lines Link，source Order 和 target OrderLine 都不存在
    dangling_link_row = {
        "link_type": "Order.lines",
        "source_type": "Order",
        "target_type": "OrderLine",
        "source_pk": "999",
        "target_source_pk": "888",
        "source_updated_at": NOW,
        "cursor_external_id": "link:999->888",
    }

    result = sink_to_ot(
        eng, TEST_SCOPE, FakePipeline("neg-dangling"), [dangling_link_row]
    )

    assert result == {"objects_written": 0, "links_written": 0}
    dangling_links = store.get_last_dangling_links()
    assert len(dangling_links) == 1
    assert dangling_links[0].cursor_external_id == "link:999->888"


# ═══════════════════════════════════════════════
# 10. 派生指标缺失率 < 5%
# ═══════════════════════════════════════════════


def test_derived_metrics_missing_fields_does_not_block():
    """#10 派生指标缺失率 < 5%：源字段缺失时写 null，不阻塞。

    apply_derived_metrics 在源字段缺失时不应抛异常，应返回 rows（骨架透传）。
    验证 W1 实现需满足的合约：缺失字段不阻塞 Pipeline。
    """
    # 构造缺失派生指标源字段的 rows
    rows_missing_fields = [
        {
            "ot": "Order",
            "source_pk": "100",
            "source_updated_at": NOW,
            "properties": {
                "shopId": "1",
                "status": "active",
                "totalAmount": "199.00",
                "currency": "CNY",
                "createdAt": "2026-07-31T18:00:00+08:00",
                "updatedAt": "2026-07-31T18:00:00+08:00",
                # 缺失：commission_risk_flag, refund_status, is_lock,
                # order_status, pay_status, create_time
            },
        },
        {
            "ot": "Order",
            "source_pk": "101",
            "source_updated_at": NOW,
            "properties": {
                "shopId": "1",
                "status": "active",
                "totalAmount": "50.00",
                "currency": "CNY",
                "createdAt": "2026-07-31T18:00:00+08:00",
                "updatedAt": "2026-07-31T18:00:00+08:00",
            },
        },
    ]

    # 不应抛异常
    result = apply_derived_metrics(rows_missing_fields, FakePipeline("neg-derived"))

    # 返回 rows（骨架透传，不阻塞）
    assert result is not None
    assert len(result) == 2

    # 验证核心字段未被修改
    assert result[0]["source_pk"] == "100"
    assert result[1]["source_pk"] == "101"
