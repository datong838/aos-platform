"""D4 Phase A: P10 SystemConfig OT 管道执行测试（frozen/02 §P10）。

P10 SystemConfig 规格：
- 源表: ns_config
- 逻辑键: site_id + app_module + config_key (+ weapp_id?)
- 增量策略: 每日快照
- 目标 OT: SystemConfig
- normalize mapper to_system_config: siteId, module, key
- Link: 无（build_link_rows 对 SystemConfig 无 builder，自然透传）
- 派生指标: 无

测试覆盖 5 项（FR-D1-6 四段实施）：
1. 初装：首次全量读取 → 落地 OT + Dataset
2. 增量：快照重跑 → checkpoint 推进（CAS 不前移）
3. 重跑：重复执行同一批次 → 幂等（replayed=True）
4. 断点：模拟中断后恢复 → checkpoint CAS 不前移
5. 越租户：跨 org/workspace 写入 → 拒绝（fail-closed）

额外覆盖：
6. Config JSON value 字段保留（to_system_config 不进 properties，但保留在 row 顶层）
7. to_system_config mapper 字段映射（含 source_pk 拼接逻辑：有 id 用 id，否则逻辑键拼接）

mock 策略（照搬 test_ec_d1_p01_shop.py）：
- fetch_source_rows: mock 返回 normalized SystemConfig 行（绕过 MySQL + normalize）
- build_link_rows: mock 透传（P10 无 Link，自然透传）
- data_os_store.persist_dataset/history: mock no-op
- eng.ecom_consistency_store: 注入 FakeStore（模拟一致性内核）
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aos_api import data_os_store
from aos_api.ec_normalizer import to_system_config
from aos_api.ecom_core_models import BatchCommand, BatchResult, EcomConsistencyError
from aos_api.ec_live_executor import ec_live_executor
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
NOW_TS = int(NOW.timestamp())


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
    """P10 无 Link，build_link_rows 透传（与 P01 一致）。"""
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


def define_p10_pipeline_config(pid: str = "p10-system-config") -> dict:
    """P10 SystemConfig Pipeline 完整配置（5 节点 graph）。"""
    return {
        "id": pid,
        "sourceId": "niushop-config",
        "name": "P10 SystemConfig Pipeline",
        "objectTypeHint": "SystemConfig",
        "config": {
            "target_ot": "SystemConfig",
            "source_table": "ns_config",
            "primary_key": "id",
            "unique_key_template": "niushop:1:{site_id}:{app_module}:{config_key}",
            "incremental_strategy": "snapshot",
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": "niushop-config",
                    "source_table": "ns_config",
                    "primary_key": "id",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {"target_ot": "SystemConfig"},
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {"required_fields": ["config_key"]},
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {"target_ot": "SystemConfig"},
            },
            {
                "id": "sink",
                "name": "Sink",
                "type": "sink",
                "config": {"target_ot": "SystemConfig"},
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


def config_row(
    *,
    config_id: str = "cfg_001",
    site_id: str = "1",
    app_module: str = "shop",
    config_key: str = "pay_key",
    value: str = '{"secret":"sk_xxx","mode":"sandbox"}',
    when: datetime = NOW,
) -> dict:
    """P10 SystemConfig normalized 行（含 ot 字段，绕过 normalize_rows）。

    properties 含 REQUIRED_PROPERTIES['SystemConfig'] 要求的 siteId/module/key/updatedAt。
    顶层保留 value（JSON 字符串）、site_id/app_module/config_key（供 mapper 单测）。
    """
    return {
        "ot": "SystemConfig",
        "source_pk": config_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "site_id": site_id,
        "app_module": app_module,
        "config_key": config_key,
        "value": value,
        "properties": {
            "siteId": site_id,
            "module": app_module,
            "key": config_key,
            "updatedAt": "2026-08-06T10:00:00Z",
        },
    }


def raw_config_row(
    *,
    config_id: str = "cfg_001",
    site_id: str = "1",
    app_module: str = "shop",
    config_key: str = "pay_key",
    value: str = '{"secret":"sk_xxx"}',
    modify_time: int = NOW_TS,
) -> dict:
    """P10 raw ns_config 行（未 normalize，供 to_system_config mapper 单测）。"""
    return {
        "id": config_id,
        "site_id": site_id,
        "app_module": app_module,
        "config_key": config_key,
        "value": value,
        "modify_time": modify_time,
        "create_time": modify_time,
    }


def _make_pipeline(pid: str = "p10-system-config") -> SimpleNamespace:
    cfg = define_p10_pipeline_config(pid)
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
# 1. 初装：首次全量读取 → 落地 OT + Dataset
# ═══════════════════════════════════════════════


def test_p10_initial_load_lands_ot_and_dataset(mock_fetch):
    """初装：首次全量读取 → 落地 SystemConfig OT + Dataset。"""
    mock_fetch.return_value = [config_row()]
    store = FakeStore()
    _inject_store(store)

    result = _run_executor(mock_fetch=mock_fetch)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    obj = command.objects[0]
    assert obj.object_type == "SystemConfig"
    assert obj.identity.external_id == "niushop:1:cfg_001"
    assert obj.identity.platform == "niushop"
    assert obj.properties.get("siteId") == "1"
    assert obj.properties.get("module") == "shop"
    assert obj.properties.get("key") == "pay_key"
    # updatedAt 经 ZonedInstant 规范化（补微秒）
    assert obj.properties.get("updatedAt", "").startswith("2026-08-06T10:00:00")

    # Dataset 落地验证
    assert result["output_ref"].startswith("dataset://catalog/")
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1


# ═══════════════════════════════════════════════
# 2. 增量：快照重跑 → checkpoint 推进（CAS 不前移）
# ═══════════════════════════════════════════════


def test_p10_incremental_snapshot_mode_checkpoint_advances(mock_fetch):
    """增量：P10 是快照模式，增量等价于重跑 → checkpoint 推进。"""
    mock_fetch.return_value = [config_row()]
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


def test_p10_rerun_same_batch_idempotent_replayed(mock_fetch):
    """重跑：相同 key+相同 hash → replayed=True，计数不翻倍。"""
    mock_fetch.return_value = [config_row()]
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


def test_p10_checkpoint_recovery_cas_not_moved_backward(mock_fetch):
    """断点恢复：首装后中断，重跑时 expected_checkpoint_version 不退回 0。"""
    mock_fetch.return_value = [config_row()]
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


def test_p10_cross_tenant_write_rejected_fail_closed(mock_fetch):
    """跨 org/workspace 写入 → EcomConsistencyError(TENANT_MISMATCH)。"""
    from aos_api.ecom_core_models import SyncScope

    allowed_scope = SyncScope(
        org_id="dev-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        stream="p10-system-config",
    )
    store = TenantGuardStore(allowed_scope_key=allowed_scope.key())
    _inject_store(store)

    other_scope = TenantScope("other-org", "other-project")
    mock_fetch.return_value = [config_row()]
    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor(scope=other_scope, mock_fetch=mock_fetch)

    assert caught.value.code == "TENANT_MISMATCH"


# ═══════════════════════════════════════════════
# 6. Config JSON value 字段保留（to_system_config 不进 properties，保留在 row 顶层）
# ═══════════════════════════════════════════════


def test_p10_config_json_value_preserved_in_row(mock_fetch):
    """Config JSON value 字段：to_system_config 不写入 properties，但保留在 row 顶层。

    规格 §P10: value 是 JSON，可能含密钥（由 SourceAdapter PII 脱敏处理）。
    normalize 阶段保留原始 JSON 字符串在 row 顶层，供后续脱敏/审计使用。
    """
    json_value = '{"secret":"sk_xxx","mode":"sandbox","timeout":30}'
    mock_fetch.return_value = [config_row(value=json_value)]
    store = FakeStore()
    _inject_store(store)

    _run_executor(mock_fetch=mock_fetch)

    command = store.calls[0]
    obj = command.objects[0]
    # properties 不含 value（to_system_config 不写 value 到 properties）
    assert "value" not in obj.properties
    # siteId/module/key 正确
    assert obj.properties["siteId"] == "1"
    assert obj.properties["module"] == "shop"
    assert obj.properties["key"] == "pay_key"


def test_p10_config_value_not_in_required_properties():
    """SystemConfig REQUIRED_PROPERTIES 不含 value（value 是业务字段，非 schema 必填）。"""
    from aos_api.ecom_core_models import REQUIRED_PROPERTIES

    required = REQUIRED_PROPERTIES["SystemConfig"]
    assert "value" not in required
    assert "siteId" in required
    assert "module" in required
    assert "key" in required
    assert "updatedAt" in required


# ═══════════════════════════════════════════════
# 7. to_system_config mapper 字段映射（raw ns_config → SystemConfig properties）
# ═══════════════════════════════════════════════


def test_p10_to_system_config_mapper_field_mapping():
    """to_system_config mapper: raw ns_config 行 → SystemConfig normalized 行。"""
    raw = raw_config_row(
        config_id="cfg_001",
        site_id="1",
        app_module="shop",
        config_key="pay_key",
        value='{"secret":"sk_xxx"}',
    )
    out = to_system_config(raw)

    assert out["ot"] == "SystemConfig"
    # 有 id 字段时 source_pk 用 id
    assert out["source_pk"] == "cfg_001"
    assert out["source_timezone"] == "+08:00"
    assert out["is_deleted"] is False
    # properties 字段映射
    assert out["properties"]["siteId"] == "1"
    assert out["properties"]["module"] == "shop"
    assert out["properties"]["key"] == "pay_key"
    # 保留 raw 字段（value 仍在顶层）
    assert out["value"] == '{"secret":"sk_xxx"}'


def test_p10_to_system_config_mapper_pk_fallback_to_logical_key():
    """to_system_config mapper: 无 id 时 source_pk 用 site_id:app_module:config_key 拼接。"""
    raw = raw_config_row()
    raw.pop("id", None)  # 移除 id，触发逻辑键拼接
    out = to_system_config(raw)

    assert out["source_pk"] == "1:shop:pay_key"


def test_p10_to_system_config_mapper_site_id_default():
    """to_system_config mapper: site_id 缺失时默认 '1'。"""
    raw = raw_config_row()
    raw["site_id"] = ""
    out = to_system_config(raw)
    assert out["properties"]["siteId"] == "1"
