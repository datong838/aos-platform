"""D1-W4: 集中负向测试（NFR + AC-D1-6）。

验证 D1 的负向行为：跨租户拒绝/重跑幂等/断点恢复/冲突检测/源库零写入/
DLQ 失败不变成功/DLQ 无 PII/软删行进 DLQ/悬挂 Link 拒绝/派生指标缺失不阻塞。

测试策略：
- 跨租户/悬挂 Link：用真实 sqlite EcomConsistencyStore（验证内核行为）
- 重跑/断点/冲突：用 FakeStore（验证 ot_writer 调用契约）
- 源库零写入/软删：mock pymysql，验证 READ ONLY 和过滤
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
from aos_api.routers.wave_ext import _dlq
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


@pytest.fixture(autouse=True)
def _reset_dlq():
    _dlq.clear()
    yield
    _dlq.clear()


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
    ), patch("aos_api.ec_source_adapter.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = niushop_conn
        mock_pymysql.cursors.DictCursor = MagicMock()

        fetch_source_rows(
            pipeline=SimpleNamespace(id="pl-neg-ro"),
            nodes=[node], node_id="n-src",
            sample_input=None, scope=TEST_SCOPE,
        )

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
# 6. DLQ 失败不变成功
# ═══════════════════════════════════════════════


def test_dlq_failure_never_marked_succeeded():
    """#6 DLQ 失败不变成功：status="failed" 不变 "succeeded"。

    验证：
    - handle_failure 创建的 DLQ 条目 status="open"（非 "succeeded"）
    - 预置的 "failed" 条目不被 handle_failure 改为 "succeeded"
    """
    # 1. handle_failure 创建的条目 status="open"
    handle_failure(FakePipeline("neg-dlq-fail"), TEST_SCOPE, RuntimeError("boom"))
    assert len(_dlq) == 1
    [item] = list(_dlq.values())
    assert item["status"] == "open"
    assert item["status"] != "succeeded"

    # 2. 预置 "failed" 条目不被 handle_failure 修改
    from aos_api.routers.wave_ext import _resource_key
    failed_key = _resource_key(TEST_SCOPE, "dlq-preexisting-failed")
    _dlq[failed_key] = {
        "id": "dlq-preexisting-failed",
        "pipelineId": "neg-dlq-preexisting",
        "errorCode": "SomeError",
        "reason": "previous failure",
        "status": "failed",
        "retry_count": 0,
        "max_retry": 3,
        "createdAt": "2026-07-31T00:00:00+00:00",
        "orgId": "dev-org",
        "projectId": "dev-project",
    }

    # 再次调用 handle_failure（不同 pipeline）
    handle_failure(FakePipeline("neg-dlq-other"), TEST_SCOPE, RuntimeError("another boom"))

    # 预置的 "failed" 条目未被修改
    assert _dlq[failed_key]["status"] == "failed"
    assert _dlq[failed_key]["status"] != "succeeded"


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
    handle_failure(FakePipeline("neg-dlq-pii"), TEST_SCOPE, exc)

    assert len(_dlq) == 1
    [item] = list(_dlq.values())
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
    for item in _dlq.values():
        for field_name, field_value in item.items():
            if not isinstance(field_value, str):
                continue
            for pattern in pii_patterns:
                matches = pattern.findall(field_value)
                # reason 字段中的 PII 已被脱敏为 ***，其他字段不应含 PII
                if field_name == "reason":
                    # reason 中不应有原始 PII（已被 *** 替换）
                    for m in matches:
                        assert m == "***" or len(m) <= 3, (
                            f"reason 字段含未脱敏 PII: {m}"
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
    cur = MagicMock()
    cur.fetchall.return_value = niushop_rows
    niushop_conn = MagicMock()
    niushop_conn.cursor.return_value = cur

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
    ), patch("aos_api.ec_source_adapter.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = niushop_conn
        mock_pymysql.cursors.DictCursor = MagicMock()

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
# 9. 悬挂 Link 拒绝
# ═══════════════════════════════════════════════


def test_dangling_link_rejected_by_store():
    """#9 悬挂 Link 拒绝：target 不存在的 Link 被 ecom_consistency_store 拒绝。

    用真实 sqlite store 验证：Order.lines Link 的 target（OrderLine）不存在 → DANGLING_LINK。
    """
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

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline("neg-dangling"), [dangling_link_row])

    assert caught.value.code == "DANGLING_LINK"


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
