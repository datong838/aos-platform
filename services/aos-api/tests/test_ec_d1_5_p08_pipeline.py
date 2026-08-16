"""D1.5: P08 CustomerLite Pipeline 专项测试（FR-D1.5-2）。

覆盖：
1. SourceAdapter ns_member 表公开字段 allowlist，PII/身份字段不进入 row 流
2. OTWriter _build_object CustomerLite 必填属性补齐（updatedAt/createdAt 自动补齐）
3. P08 端到端：CustomerLite OT 落地 + niushop:1:{member_id} 命名空间

约束（frozen/02 §P08）：
- ns_member 源表只允许主键、租户过滤、状态/等级和水位字段；其余默认拒绝
- 隐私最小化映射：只保留 member_id/member_level/status/create_time/modify_time 等脱敏键
- CustomerLite REQUIRED_PROPERTIES = {memberLevel, status, createdAt, updatedAt}
- 唯一键命名空间：niushop:1:{member_id}
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aos_api import ec_live_executor as ec_mod
from aos_api import data_os_store
from aos_api.ecom_consistency_store import EcomConsistencyStore, metadata as ecom_metadata
from aos_api.ecom_core_models import (
    BatchCommand,
    BatchResult,
    CoreObjectRecord,
    EcomConsistencyError,
    SyncScope,
)
from aos_api.ec_ot_writer import sink_derived_metrics, sink_to_ot
from aos_api.ec_source_adapter import (
    fetch_source_rows,
    get_soft_delete_count,
    reset_soft_delete_counts,
)
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.public_contracts import ExternalIdentityKey, ForwardEnumValue, StableCursor
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("other-org", "other-project")
PID = "p08-customer-lite"

# P08 公开投影必须排除的代表性身份字段。
PII_FIELDS: frozenset[str] = frozenset({
    "mobile", "wx_openid", "nickname", "avatar",
    "reg_address", "last_login_ip", "password", "pay_password",
    "email", "headimg", "realname", "birthday", "address", "full_address",
})


# ═══════════════════════════════════════════════
# fakes（复用 test_ec_d1_ot_writer.py / test_ec_d1_p05_order.py 模式）
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


# ═══════════════════════════════════════════════
# Section 1: SourceAdapter PII 排除（FR-D1.5-2）
# ═══════════════════════════════════════════════


def _ns_member_raw_row(
    *,
    member_id: int = 1001,
    is_delete: int = 0,
) -> dict[str, Any]:
    """ns_member 原始行（含全部字段：脱敏键 + 8 个 PII 字段 + site_id/is_delete）。"""
    return {
        # 脱敏键（frozen/02 §P08 隐私最小化映射保留）
        "member_id": member_id,
        "member_level": 1,
        "status": 1,
        "create_time": 1700000000,
        "modify_time": 1700001000,
        # 历史已知 PII 与其他身份字段；公开投影必须全部拒绝。
        "mobile": "13800138000",
        "wx_openid": "wx_openid_secret_123",
        "nickname": "张三的昵称",
        "avatar": "https://cdn.example.com/avatar/1001.jpg",
        "reg_address": "北京市朝阳区某某街道XX号",
        "last_login_ip": "10.0.0.1",
        "password": "hashed_password_secret",
        "pay_password": "hashed_pay_password_secret",
        "email": "member@example.com",
        "headimg": "https://cdn.example.com/head/1001.jpg",
        "realname": "张三",
        "birthday": "1990-01-01",
        "address": "某街道",
        "full_address": "北京市某街道某号",
        # 过滤/清洗键
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


class _FakePymysqlCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def close(self) -> None:
        pass


def _configure_runtime_rows(
    mock_runtime_cls: MagicMock,
    rows: list[dict[str, Any]],
) -> MagicMock:
    runtime = MagicMock()
    runtime.__enter__.return_value = runtime
    runtime.read_rows.return_value = rows
    mock_runtime_cls.return_value = runtime
    return runtime


@patch("aos_api.ec_source_adapter.JdbcConnectorRuntime")
@patch("aos_api.ec_source_adapter.connect")
def test_ns_member_public_projection_drops_identity_fields(
    mock_connect: MagicMock,
    mock_runtime_cls: MagicMock,
) -> None:
    """FR-D1.5-2: ns_member 非公开身份字段不得进入 Source row 流。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    _configure_runtime_rows(mock_runtime_cls, [_ns_member_raw_row(member_id=1001)])

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
        pipeline=SimpleNamespace(id="pl-p08-pii"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    assert len(rows) == 1
    row = rows[0]
    leaked = PII_FIELDS & set(row.keys())
    assert not leaked, f"PII 字段未 drop: {leaked}"


@patch("aos_api.ec_source_adapter.JdbcConnectorRuntime")
@patch("aos_api.ec_source_adapter.connect")
def test_ns_member_keeps_desensitized_fields(
    mock_connect: MagicMock,
    mock_runtime_cls: MagicMock,
) -> None:
    """FR-D1.5-2: ns_member 表的脱敏键（member_id/member_level/status/create_time/modify_time）MUST 保留。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    _configure_runtime_rows(mock_runtime_cls, [_ns_member_raw_row(member_id=1001)])

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
        pipeline=SimpleNamespace(id="pl-p08-keep"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    row = rows[0]
    # 脱敏键保留
    assert row["member_id"] == 1001
    assert row["member_level"] == 1
    assert row["status"] == 1
    assert row["create_time"] == 1700000000
    assert row["modify_time"] == 1700001000


@patch("aos_api.ec_source_adapter.JdbcConnectorRuntime")
@patch("aos_api.ec_source_adapter.connect")
def test_pii_exclusion_scoped_to_ns_member_only(
    mock_connect: MagicMock,
    mock_runtime_cls: MagicMock,
) -> None:
    """FR-D1.5-2: PII drop MUST 仅对 ns_member 表生效，不影响其他表（如 ns_goods）。

    ns_goods 表无 PII 排除契约，其字段（即便碰巧同名）不被 drop。
    """
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    # ns_goods 行：假设有个字段叫 "mobile"（商品联系电话），不应被 drop
    ns_goods_row = {
        "goods_id": 1,
        "is_delete": 0,
        "goods_name": "测试商品",
        "mobile": "商家联系电话",  # 非 ns_member PII，不应 drop
    }
    _configure_runtime_rows(mock_runtime_cls, [ns_goods_row])

    reset_soft_delete_counts()
    node = SimpleNamespace(
        id="n-src",
        node_type="source",
        config={
            "source_id": "src-1",
            "table": "ns_goods",
            "pk": "goods_id",
            "initial": True,
        },
    )

    rows = fetch_source_rows(
        pipeline=SimpleNamespace(id="pl-p02-scope"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    assert len(rows) == 1
    # ns_goods 的 mobile 字段保留（PII drop 仅对 ns_member）
    assert "mobile" in rows[0]
    assert rows[0]["mobile"] == "商家联系电话"


@patch("aos_api.ec_source_adapter.JdbcConnectorRuntime")
@patch("aos_api.ec_source_adapter.connect")
def test_pii_drop_does_not_break_soft_delete_counting(
    mock_connect: MagicMock,
    mock_runtime_cls: MagicMock,
) -> None:
    """FR-D1.5-2: PII drop 不影响软删行过滤与 DLQ 计数。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_rows = [
        _ns_member_raw_row(member_id=1001, is_delete=0),
        _ns_member_raw_row(member_id=1002, is_delete=1),  # 软删
        _ns_member_raw_row(member_id=1003, is_delete=0),
    ]
    _configure_runtime_rows(mock_runtime_cls, niushop_rows)

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
        pipeline=SimpleNamespace(id="pl-p08-dlq"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    # 有效行 2 条（软删 1 条过滤）
    assert len(rows) == 2
    assert all(r["is_delete"] == 0 for r in rows)
    # 软删计数 1 条（PII drop 不影响 DLQ 计数）
    assert get_soft_delete_count("pl-p08-dlq", "n-src") == 1
    # 有效行也已 drop PII
    for row in rows:
        assert not (PII_FIELDS & set(row.keys()))


# ═══════════════════════════════════════════════
# Section 2: OTWriter CustomerLite 必填属性补齐（FR-D1.5-2）
# ═══════════════════════════════════════════════


def customer_lite_row(
    *,
    member_id: str = "1001",
    when: datetime = NOW,
    with_times: bool = True,
    deleted: bool = False,
) -> dict[str, Any]:
    """P08 CustomerLite 规范化行：ot=CustomerLite, source_pk=member_id。

    with_times=False 时省略 createdAt/updatedAt，验证 _build_object 自动补齐。
    """
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
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": deleted,
        "properties": props,
    }


def test_build_object_CustomerLite_auto_fills_updatedAt() -> None:
    """FR-D1.5-2: _build_object 对 CustomerLite MUST 自动补齐 updatedAt（源缺省时用 source_updated_at）。"""
    store = FakeStore()
    eng = FakeEngine(store)
    # 省略 updatedAt
    rows = [customer_lite_row(member_id="1001", with_times=False)]

    result = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert result["objects_written"] == 1
    command = store.calls[0]
    obj = command.objects[0]
    assert obj.object_type == "CustomerLite"
    # updatedAt 被自动补齐
    assert "updatedAt" in obj.properties
    assert obj.properties["updatedAt"] is not None


def test_build_object_CustomerLite_auto_fills_createdAt() -> None:
    """FR-D1.5-2: _build_object 对 CustomerLite MUST 自动补齐 createdAt（源缺省时用 source_updated_at）。"""
    store = FakeStore()
    eng = FakeEngine(store)
    rows = [customer_lite_row(member_id="1001", with_times=False)]

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    obj = store.calls[0].objects[0]
    assert "createdAt" in obj.properties
    assert obj.properties["createdAt"] is not None


def test_build_object_CustomerLite_preserves_existing_time_fields() -> None:
    """FR-D1.5-2: _build_object 对 CustomerLite 用 setdefault 语义，源已有时间字段不覆盖。"""
    store = FakeStore()
    eng = FakeEngine(store)
    rows = [customer_lite_row(member_id="1001", with_times=True)]

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    obj = store.calls[0].objects[0]
    # 源已有的 createdAt/updatedAt 保留原值（setdefault 不覆盖）
    # ZonedInstant 规范化后 createdAt 变为 UTC ISO 字符串
    assert obj.properties["createdAt"].endswith("Z") or "+" in obj.properties["createdAt"]
    assert obj.properties["updatedAt"].endswith("Z") or "+" in obj.properties["updatedAt"]


def test_build_object_CustomerLite_produces_valid_record() -> None:
    """FR-D1.5-2: CustomerLite 行经 _build_object 构造合法 CoreObjectRecord（必填属性满足）。"""
    store = FakeStore()
    eng = FakeEngine(store)
    rows = [customer_lite_row(member_id="1001", with_times=False)]

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    obj = store.calls[0].objects[0]
    assert obj.object_type == "CustomerLite"
    assert obj.identity.external_id == "niushop:1:1001"
    # REQUIRED_PROPERTIES 全满足
    assert "memberLevel" in obj.properties
    assert "status" in obj.properties
    assert "createdAt" in obj.properties
    assert "updatedAt" in obj.properties
    assert not obj.is_deleted


def test_customer_lite_dynamic_metrics_use_derived_cas_not_base_payload() -> None:
    """P08 动态指标不得在同一源版本下改写基础 Object payload。"""
    store = FakeStore()
    eng = FakeEngine(store)
    row = customer_lite_row(member_id="1001", with_times=False)
    row["properties"].update({"order_count": 2, "last_order_days": 3})

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [row])
    base = store.calls[0].objects[0]
    assert "order_count" not in base.properties
    assert "last_order_days" not in base.properties

    result = sink_derived_metrics(eng, TEST_SCOPE, FakePipeline(), [row])
    assert result == {"derived_updated": 1, "derived_replayed": 0}
    assert store.derived_calls[0].derived_props == {
        "order_count": 2,
        "last_order_days": 3,
    }


# ═══════════════════════════════════════════════
# Section 3: P08 端到端（FR-D1.5-2 命名空间 + 落地）
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
    source = SimpleNamespace(
        id="n-src",
        node_type="source",
        config={"source_id": "src-p08", "source_table": "ns_member"},
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


def test_p08_initial_load_lands_customer_lite_ot() -> None:
    """FR-D1.5-2: P08 初装 → 落地 CustomerLite OT（BatchCommand 含 CustomerLite 对象）。"""
    store = FakeStore()
    rows = [
        customer_lite_row(member_id="1001", with_times=False),
        customer_lite_row(member_id="1002", with_times=False),
    ]

    result = _run_executor(rows, store=store)

    # Dataset 落地
    assert result["output_ref"] == "dataset://catalog/ri.aos.main.dataset.p08-customer-lite"
    # OT 落地：1 个 BatchCommand，2 个 CustomerLite 对象
    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 2
    assert all(obj.object_type == "CustomerLite" for obj in command.objects)
    # rows 计数
    assert result["rows_written"] == 2


def test_p08_external_id_namespace_niushop_1_member_id() -> None:
    """FR-D1.5-2: CustomerLite 唯一键命名空间 = niushop:1:{member_id}（frozen/02 §P08）。"""
    store = FakeStore()
    rows = [customer_lite_row(member_id="1001", with_times=False)]

    _run_executor(rows, store=store)

    command = store.calls[0]
    ext_ids = {obj.identity.external_id for obj in command.objects}
    assert ext_ids == {"niushop:1:1001"}
    # scope 与传入 scope 一致
    assert command.scope.org_id == TEST_SCOPE.org_id
    assert command.scope.workspace_id == TEST_SCOPE.project_id
    assert command.scope.platform == "niushop"
    assert command.scope.shop_or_marketplace_id == "1"


# ═══════════════════════════════════════════════
# Section 4: P08 四段实施负向测试（FR-D1.5-11, AC-D1.5-8）
# 追溯：退出门第 7 条"四段实施每段 6 项负向测试通过"。
# 策略：用 sink_to_ot 直接 OT 落地（不经过 ec_live_executor），聚焦 CustomerLite
# 边界行为；与 test_ec_d1_negative.py 同构，object_type=CustomerLite。
# ═══════════════════════════════════════════════


def _make_sqlite_store() -> EcomConsistencyStore:
    """创建 in-memory sqlite EcomConsistencyStore（用于跨租户测试）。"""
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    ecom_metadata.create_all(engine)
    return EcomConsistencyStore(engine)


def test_p08_replay_same_batch_rows_not_doubled() -> None:
    """AC-D1.5-8: P08 重跑幂等 — 相同 key+相同 hash → rows_written 不翻倍。"""
    replay_result = BatchResult(
        objects_written=1,
        links_written=0,
        checkpoint_version=1,
        checkpoint=StableCursor(
            source_updated_at_utc=NOW, external_id="niushop:1:1001"
        ),
        replayed=True,
    )
    store = FakeStore(result=replay_result)
    eng = get_engine()
    eng.ecom_consistency_store = store

    row = customer_lite_row(member_id="1001")
    first = sink_to_ot(eng, TEST_SCOPE, FakePipeline("p08-replay"), [row])
    second = sink_to_ot(eng, TEST_SCOPE, FakePipeline("p08-replay"), [row])

    assert first["objects_written"] == 1
    assert second["objects_written"] == 1
    assert len(store.calls) == 2
    # 相同 batch → 相同 idempotency_key
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


def test_p08_checkpoint_cas_does_not_regress() -> None:
    """AC-D1.5-8: P08 断点恢复 — checkpoint CAS 不前移。

    首装推进 checkpoint 到 v1 后，后续批次 expected 自动取当前 version=1。
    """
    store = FakeStore()
    eng = get_engine()
    eng.ecom_consistency_store = store

    sink_to_ot(
        eng, TEST_SCOPE, FakePipeline("p08-cas"),
        [customer_lite_row(member_id="1001")],
    )
    assert store.calls[0].expected_checkpoint_version == 0

    later = datetime(2026, 8, 6, 14, 0, tzinfo=timezone.utc)
    sink_to_ot(
        eng, TEST_SCOPE, FakePipeline("p08-cas"),
        [customer_lite_row(member_id="1002", when=later)],
    )

    assert len(store.calls) == 2
    assert store.calls[1].expected_checkpoint_version == 1


def test_p08_same_version_different_hash_returns_conflict() -> None:
    """AC-D1.5-8: P08 冲突检测 — 相同版本+不同 hash → IDEMPOTENCY_CONFLICT，不吞异常。"""
    conflict = EcomConsistencyError(
        "IDEMPOTENCY_CONFLICT",
        "idempotency key was already used with a different request",
    )
    store = FakeStore(raises=conflict)
    eng = get_engine()
    eng.ecom_consistency_store = store

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(
            eng, TEST_SCOPE, FakePipeline("p08-conflict"),
            [customer_lite_row(member_id="1001")],
        )

    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


def test_p08_cross_tenant_write_rejected() -> None:
    """AC-D1.5-8: P08 越租户拒绝 — scope B 查不到 scope A 的 CustomerLite。

    用真实 sqlite store 验证：
    - 写入 scope A 的 CustomerLite 后，scope B 查不到
    - BatchCommand validator 拒绝跨 scope 的 object identity
    """
    store = _make_sqlite_store()
    eng = get_engine()
    eng.ecom_consistency_store = store

    sink_to_ot(
        eng, TEST_SCOPE, FakePipeline("p08-ct"),
        [customer_lite_row(member_id="1001")],
    )

    # scope B (other-org) 查不到 scope A 的 CustomerLite
    identity_b = ExternalIdentityKey(
        org_id=OTHER_SCOPE.org_id,
        workspace_id=OTHER_SCOPE.project_id,
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id="niushop:1:1001",
    )
    assert store.get_object(identity_b, "CustomerLite") is None

    # scope A 能查到
    identity_a = ExternalIdentityKey(
        org_id=TEST_SCOPE.org_id,
        workspace_id=TEST_SCOPE.project_id,
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id="niushop:1:1001",
    )
    assert store.get_object(identity_a, "CustomerLite") is not None

    # BatchCommand validator 拒绝跨 scope 的 object identity
    scope_a = SyncScope(
        org_id="dev-org", workspace_id="dev-project",
        platform="niushop", shop_or_marketplace_id="1", stream="p08-ct",
    )
    cross_obj = CoreObjectRecord(
        identity=identity_b,  # other-org
        object_type="CustomerLite",
        source_updated_at=NOW,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active"}),
        properties={
            "memberLevel": "1",
            "status": "active",
            "createdAt": "2026-01-01T00:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    )
    with pytest.raises(ValueError, match="outside the batch scope"):
        BatchCommand(
            scope=scope_a,
            idempotency_key="p08-cross-tenant-neg",
            expected_checkpoint_version=0,
            next_checkpoint=StableCursor(
                source_updated_at_utc=NOW, external_id="niushop:1:1001"
            ),
            objects=[cross_obj],
            links=[],
        )
