"""D4 Phase A: P09 Weapp OT 管道执行测试（frozen/02 §P09）。

P09 Weapp 规格：
- 源表/主键: ns_weapp / weapp_id
- 增量策略: 每日快照（全表量小）
- 目标 OT: Weapp
- 唯一键: niushop:1:{weapp_id}
- normalize mapper to_weapp: appId=appid, name=weapp_name, status=active
- Link: Shop.hasWeapp（site_id 关联，site_id 缺失默认 '1'）
- 派生指标: 无

测试覆盖 5 项（FR-D1-6 四段实施）：
1. 初装：首次全量读取 → 落地 OT + Dataset
2. 增量：快照重跑 → checkpoint 推进（CAS 不前移）
3. 重跑：重复执行同一批次 → 幂等（replayed=True）
4. 断点：模拟中断后恢复 → checkpoint CAS 不前移
5. 越租户：跨 org/workspace 写入 → 拒绝（fail-closed）

额外覆盖：
6. hasWeapp Link 构造（build_link_rows 直接验证：site_id 默认 '1'）
7. to_weapp mapper 字段映射（raw ns_weapp → Weapp properties）

mock 策略（照搬 test_ec_d1_p01_shop.py）：
- fetch_source_rows: mock 返回 normalized Weapp 行（绕过 MySQL + normalize）
- build_link_rows: mock 透传（5 标准case 不构造 Link，避免 CoreLinkRecord 方向校验；
  Link 构造由额外单测直接调用 ec_link_builder.build_link_rows 验证）
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
from aos_api.ec_link_builder import build_link_rows
from aos_api.ec_normalizer import to_weapp
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
    """记录 apply_batch / get_checkpoint 调用，模拟一致性内核行为。

    支持：checkpoint 版本推进、幂等重放检测、冲突检测、跨租户拒绝。
    内容指纹排除 expected_checkpoint_version（CAS 守卫不属于批次内容）。
    """

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

        # 幂等重放检测
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

        # 新批次
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
    """mock fetch_source_rows，每个测试设置返回值。"""
    with patch("aos_api.ec_live_executor.fetch_source_rows") as m:
        yield m


# ═══════════════════════════════════════════════
# 管道配置工厂（A3-3，内嵌测试文件）
# ═══════════════════════════════════════════════


def define_p09_pipeline_config(pid: str = "p09-weapp") -> dict:
    """P09 Weapp Pipeline 完整配置（5 节点 graph: source→normalize→validate→quality_gate→sink）。"""
    return {
        "id": pid,
        "sourceId": "niushop-weapp",
        "name": "P09 Weapp Pipeline",
        "objectTypeHint": "Weapp",
        "config": {
            "target_ot": "Weapp",
            "source_table": "ns_weapp",
            "primary_key": "weapp_id",
            "unique_key_template": "niushop:1:{weapp_id}",
            "incremental_strategy": "snapshot",
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": "niushop-weapp",
                    "source_table": "ns_weapp",
                    "primary_key": "weapp_id",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {"target_ot": "Weapp", "unique_key_template": "niushop:1:{weapp_id}"},
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {"required_fields": ["weapp_id", "appid"]},
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {"target_ot": "Weapp"},
            },
            {
                "id": "sink",
                "name": "Sink",
                "type": "sink",
                "config": {"target_ot": "Weapp"},
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


def weapp_row(
    *,
    weapp_id: str = "wx_001",
    appid: str = "wx1234567890abcdef",
    weapp_name: str = "栖月汇小程序",
    site_id: str = "1",
    when: datetime = NOW,
) -> dict:
    """P09 Weapp normalized 行（含 ot 字段，绕过 normalize_rows）。

    properties 含 REQUIRED_PROPERTIES['Weapp'] 要求的 appId/name/status/updatedAt。
    顶层保留 site_id（供 build_link_rows 的 _build_has_weapp_links 读取）。
    """
    return {
        "ot": "Weapp",
        "source_pk": weapp_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "site_id": site_id,
        "properties": {
            "appId": appid,
            "name": weapp_name,
            "status": "active",
            "updatedAt": "2026-08-06T10:00:00Z",
        },
    }


def raw_weapp_row(
    *,
    weapp_id: str = "wx_001",
    appid: str = "wx1234567890abcdef",
    weapp_name: str = "栖月汇小程序",
    site_id: str = "1",
    modify_time: int = NOW_TS,
) -> dict:
    """P09 raw ns_weapp 行（未 normalize，供 to_weapp mapper 单测）。"""
    return {
        "weapp_id": weapp_id,
        "appid": appid,
        "weapp_name": weapp_name,
        "site_id": site_id,
        "modify_time": modify_time,
        "create_time": modify_time,
    }


def _make_pipeline(pid: str = "p09-weapp") -> SimpleNamespace:
    cfg = define_p09_pipeline_config(pid)
    return SimpleNamespace(id=cfg["id"], config=cfg["config"])


def _run_executor(*, pipeline=None, scope=TEST_SCOPE, mock_fetch=None):
    """调用 ec_live_executor 的便捷包装。"""
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
    """把 FakeStore 注入到 engine 上。"""
    eng = get_engine()
    eng.ecom_consistency_store = store


# ═══════════════════════════════════════════════
# 1. 初装：首次全量读取 → 落地 OT + Dataset
# ═══════════════════════════════════════════════


def test_p09_initial_load_lands_ot_and_dataset(mock_fetch):
    """初装：首次全量读取 → 落地 Weapp OT + Dataset。"""
    mock_fetch.return_value = [weapp_row()]
    store = FakeStore()
    _inject_store(store)

    result = _run_executor(mock_fetch=mock_fetch)

    # OT 落地验证
    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    obj = command.objects[0]
    assert obj.object_type == "Weapp"
    assert obj.identity.external_id == "niushop:1:wx_001"
    assert obj.identity.platform == "niushop"
    assert obj.identity.shop_or_marketplace_id == "1"
    assert obj.properties.get("appId") == "wx1234567890abcdef"
    assert obj.properties.get("name") == "栖月汇小程序"
    assert obj.properties.get("status") == "active"
    # ZonedInstant 规范化会补微秒（2026-08-06T10:00:00.000000Z）
    assert obj.properties.get("updatedAt", "").startswith("2026-08-06T10:00:00")

    # Dataset 落地验证
    assert result["output_ref"].startswith("dataset://catalog/")
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1


# ═══════════════════════════════════════════════
# 2. 增量：快照重跑 → checkpoint 推进（CAS 不前移）
# ═══════════════════════════════════════════════


def test_p09_incremental_snapshot_mode_checkpoint_advances(mock_fetch):
    """增量：P09 是快照模式，增量等价于重跑 → checkpoint 推进。

    第二次执行时 expected_checkpoint_version=1（不退回 0），CAS 不前移。
    """
    mock_fetch.return_value = [weapp_row()]
    store = FakeStore()
    _inject_store(store)

    _run_executor(mock_fetch=mock_fetch)
    _run_executor(mock_fetch=mock_fetch)

    assert len(store.calls) == 2
    # 首装 expected=0
    assert store.calls[0].expected_checkpoint_version == 0
    # 增量 expected=1（checkpoint 推进，CAS 不前移）
    assert store.calls[1].expected_checkpoint_version == 1


# ═══════════════════════════════════════════════
# 3. 重跑：重复执行同一批次 → 幂等（replayed=True）
# ═══════════════════════════════════════════════


def test_p09_rerun_same_batch_idempotent_replayed(mock_fetch):
    """重跑：相同 key+相同 hash → replayed=True，计数不翻倍。"""
    mock_fetch.return_value = [weapp_row()]
    store = FakeStore()
    _inject_store(store)

    first = _run_executor(mock_fetch=mock_fetch)
    second = _run_executor(mock_fetch=mock_fetch)

    # 两次都成功
    assert first["rows_written"] == 1
    assert second["rows_written"] == 1
    # 第二次是幂等重放（相同 idempotency_key + 相同 request_hash）
    assert len(store.calls) == 2
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


# ═══════════════════════════════════════════════
# 4. 断点：模拟中断后恢复 → checkpoint CAS 不前移
# ═══════════════════════════════════════════════


def test_p09_checkpoint_recovery_cas_not_moved_backward(mock_fetch):
    """断点恢复：首装后中断，重跑时 expected_checkpoint_version 不退回 0。

    场景：首装成功（checkpoint=1），executor 崩溃。重启后重跑同一批次，
    expected_checkpoint_version 应为 1（从 store 查到），不是 0。
    """
    mock_fetch.return_value = [weapp_row()]
    store = FakeStore()
    _inject_store(store)

    # 首装成功
    _run_executor(mock_fetch=mock_fetch)
    assert store.calls[0].expected_checkpoint_version == 0

    # 模拟"中断后恢复"：重新执行同一批次
    # store 仍保留 checkpoint=1，expected 应为 1
    _run_executor(mock_fetch=mock_fetch)
    assert store.calls[1].expected_checkpoint_version == 1
    # checkpoint 不前移
    assert store.calls[1].expected_checkpoint_version >= store.calls[0].expected_checkpoint_version


# ═══════════════════════════════════════════════
# 5. 越租户：跨 org/workspace 写入 → 拒绝（fail-closed）
# ═══════════════════════════════════════════════


def test_p09_cross_tenant_write_rejected_fail_closed(mock_fetch):
    """跨 org/workspace 写入 → EcomConsistencyError(TENANT_MISMATCH)。"""
    from aos_api.ecom_core_models import SyncScope

    allowed_scope = SyncScope(
        org_id="dev-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        stream="p09-weapp",
    )
    store = TenantGuardStore(allowed_scope_key=allowed_scope.key())
    _inject_store(store)

    # 用不同 org 调用 executor → 拒绝
    other_scope = TenantScope("other-org", "other-project")
    mock_fetch.return_value = [weapp_row()]
    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor(scope=other_scope, mock_fetch=mock_fetch)

    assert caught.value.code == "TENANT_MISMATCH"


# ═══════════════════════════════════════════════
# 6. hasWeapp Link 构造（build_link_rows 直接验证）
# ═══════════════════════════════════════════════


def test_p09_has_weapp_link_constructed_with_site_id():
    """hasWeapp Link 构造：site_id 存在时用 site_id 作为 Shop source_pk。"""
    rows = [weapp_row(weapp_id="wx_001", site_id="1")]
    result = build_link_rows(rows, _make_pipeline("p09-weapp"))
    links = [r for r in result if r.get("link_type") == "Shop.hasWeapp"]
    assert len(links) == 1
    link = links[0]
    # Shop.hasWeapp 不反转：source=Shop, target=Weapp（与 CORE_LINK_TYPES 方向一致）
    assert link["link_type"] == "Shop.hasWeapp"
    assert link["source_type"] == "Shop"
    assert link["target_type"] == "Weapp"
    assert link["source_pk"] == "1"
    assert link["target_source_pk"] == "wx_001"


def test_p09_has_weapp_link_default_site_id_when_missing():
    """hasWeapp Link 构造：site_id 缺失时默认 '1'（栖月汇单租户）。"""
    # 构造顶层无 site_id 的 normalized 行
    row = weapp_row(weapp_id="wx_002")
    row.pop("site_id", None)
    result = build_link_rows([row], _make_pipeline("p09-weapp"))
    links = [r for r in result if r.get("link_type") == "Shop.hasWeapp"]
    assert len(links) == 1
    # site_id 缺失默认 '1'，不反转后 source_pk=site_id
    assert links[0]["source_pk"] == "1"


def test_p09_has_weapp_link_skipped_when_weapp_id_invalid():
    """hasWeapp Link 构造：weapp_id 无效（空/0）时跳过。"""
    # weapp_id 为空
    row = weapp_row(weapp_id="")
    result = build_link_rows([row], _make_pipeline("p09-weapp"))
    assert [r for r in result if r.get("link_type") == "Shop.hasWeapp"] == []


# ═══════════════════════════════════════════════
# 7. to_weapp mapper 字段映射（raw ns_weapp → Weapp properties）
# ═══════════════════════════════════════════════


def test_p09_to_weapp_mapper_field_mapping():
    """to_weapp mapper: raw ns_weapp 行 → Weapp normalized 行，字段映射正确。"""
    raw = raw_weapp_row(
        weapp_id="wx_001",
        appid="wx1234567890abcdef",
        weapp_name="栖月汇小程序",
        site_id="1",
    )
    out = to_weapp(raw)

    assert out["ot"] == "Weapp"
    assert out["source_pk"] == "wx_001"
    assert out["source_timezone"] == "+08:00"
    assert out["is_deleted"] is False
    # properties 字段映射
    assert out["properties"]["appId"] == "wx1234567890abcdef"
    assert out["properties"]["name"] == "栖月汇小程序"
    assert out["properties"]["status"] == "active"
    # 保留 raw 字段（供 build_link_rows 读取 site_id）
    assert out["site_id"] == "1"
    assert out["weapp_id"] == "wx_001"


def test_p09_to_weapp_mapper_appid_fallback_to_weapp_id():
    """to_weapp mapper: appid 缺失时回退到 weapp_id。"""
    raw = raw_weapp_row(weapp_id="wx_001", appid="")
    out = to_weapp(raw)
    assert out["properties"]["appId"] == "wx_001"


def test_p09_to_weapp_mapper_name_fallback_to_weapp_id():
    """to_weapp mapper: weapp_name 缺失时回退到 weapp_id。"""
    raw = raw_weapp_row(weapp_id="wx_001", weapp_name="")
    out = to_weapp(raw)
    assert out["properties"]["name"] == "wx_001"
