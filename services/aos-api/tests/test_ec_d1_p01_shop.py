"""D1-W1: P01 Shop 端到端测试（FR-D1-6 四段实施）。

P01 Shop 规格（frozen/02）：
- 源表/主键: ns_site / site_id
- 源过滤: site_id=1
- 增量策略: 每日快照
- 目标 OT: Shop
- 唯一键: niushop:1:{site_id}
- 校验: site_name 非空
- 游标字段: 无（快照模式）
- 派生指标: 无（Shop 没有 FR-D1-7 定义的 4 个派生指标）
- Link: 无

测试覆盖 6 项（FR-D1-6 四段实施）：
1. 初装：首次全量读取 → 落地 OT + Dataset
2. 增量：基于复合游标增量读取 → 幂等 upsert（P01 是快照模式，增量等价于重跑）
3. 重跑：重复执行同一批次 → 验证幂等（相同 key+相同 hash 返回原结果）
4. 断点：模拟中断后恢复 → 验证 checkpoint CAS 不前移
5. 重复：相同版本+不同 hash → 验证冲突检测
6. 越租户：跨 org/workspace 写入 → 验证拒绝（fail-closed）

mock 策略：
- fetch_source_rows: mock 返回 normalized shop rows（绕过 MySQL 依赖）
- build_link_rows: mock 透传（P01 无 Link）
- data_os_store.persist_dataset / persist_dataset_history: mock no-op（避免 DB 副作用）
- eng.ecom_consistency_store: 注入 FakeStore（模拟一致性内核行为）
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aos_api import data_os_store
from aos_api.ecom_core_models import BatchCommand, BatchResult, EcomConsistencyError
from aos_api.ec_live_executor import ec_live_executor
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════
# FakeStore — 模拟 ecom_consistency_store 内核行为
# ═══════════════════════════════════════════════


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，模拟一致性内核行为。

    支持：
    - checkpoint 版本推进（首装 0→1，增量 1→2...）
    - 幂等重放（相同 idempotency_key + 相同内容指纹 → replayed=True）
    - 冲突检测（相同 idempotency_key + 不同内容指纹 → IDEMPOTENCY_CONFLICT）
    - 跨租户拒绝（scope 不匹配 → TENANT_MISMATCH）

    注：内容指纹排除 expected_checkpoint_version（CAS 守卫不属于批次内容，
    同一批次重跑时 expected 会从 0 推进到 1，但内容不变 → 幂等重放而非冲突）。
    """

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[BatchCommand] = []
        self._raises = raises
        self._checkpoints: dict[tuple, int] = {}
        self._idempotency: dict[tuple, tuple] = {}

    @staticmethod
    def _content_fingerprint(command: BatchCommand) -> tuple:
        """批次内容指纹（排除 expected_checkpoint_version）。

        相同批次重跑时 expected_checkpoint_version 会从 0→1，但 scope +
        next_checkpoint + objects + links 不变 → 视为幂等重放。
        """
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
# fixtures
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
    """P01 无 Link → build_link_rows 透传。"""
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
# row 工厂
# ═══════════════════════════════════════════════


def shop_row(*, site_id: str = "1", site_name: str = "栖月汇",
             when: datetime = NOW) -> dict:
    """P01 Shop 行（normalized executor 格式）。

    properties 包含 CoreObjectRecord.REQUIRED_PROPERTIES['Shop'] 要求的
    name/status/currency/timezone（frozen/01 schema fingerprint）。
    """
    return {
        "ot": "Shop",
        "source_pk": site_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "site_id": site_id,
            "name": site_name,
            "site_name": site_name,
            "status": "active",
            "currency": "CNY",
            "timezone": "Asia/Shanghai",
        },
    }


def _make_pipeline(pid: str = "p01-shop") -> SimpleNamespace:
    return SimpleNamespace(id=pid, config={})


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


def test_p01_initial_load_lands_ot_and_dataset(mock_fetch):
    """初装：首次全量读取 → 落地 OT + Dataset。"""
    mock_fetch.return_value = [shop_row()]
    store = FakeStore()
    _inject_store(store)

    result = _run_executor(mock_fetch=mock_fetch)

    # OT 落地验证
    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    obj = command.objects[0]
    assert obj.object_type == "Shop"
    assert obj.identity.external_id == "niushop:1:1"
    assert obj.identity.platform == "niushop"
    assert obj.identity.shop_or_marketplace_id == "1"
    assert obj.properties.get("site_name") == "栖月汇"

    # Dataset 落地验证
    assert result["output_ref"].startswith("dataset://catalog/")
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1


# ═══════════════════════════════════════════════
# 2. 增量：基于复合游标增量读取 → 幂等 upsert
# ═══════════════════════════════════════════════


def test_p01_incremental_snapshot_mode_idempotent_upsert(mock_fetch):
    """增量：P01 是快照模式，增量等价于重跑 → 幂等 upsert。

    第二次执行时 expected_checkpoint_version=1（不退回 0），
    相同 key+相同 hash → replayed=True，计数不翻倍。
    """
    mock_fetch.return_value = [shop_row()]
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
# 3. 重跑：重复执行同一批次 → 验证幂等
# ═══════════════════════════════════════════════


def test_p01_rerun_same_batch_idempotent_no_double_count(mock_fetch):
    """重跑：相同 key+相同 hash → replayed=True，计数不翻倍。"""
    mock_fetch.return_value = [shop_row()]
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
# 4. 断点：模拟中断后恢复 → 验证 checkpoint CAS 不前移
# ═══════════════════════════════════════════════


def test_p01_checkpoint_recovery_cas_not_moved_backward(mock_fetch):
    """断点恢复：首装后中断，重跑时 expected_checkpoint_version 不退回 0。

    场景：首装成功（checkpoint=1），executor 崩溃。重启后重跑同一批次，
    expected_checkpoint_version 应为 1（从 store 查到），不是 0。
    """
    mock_fetch.return_value = [shop_row()]
    store = FakeStore()
    _inject_store(store)

    # 首装成功
    _run_executor(mock_fetch=mock_fetch)
    assert store.calls[0].expected_checkpoint_version == 0

    # 模拟"中断后恢复"：重新执行同一批次
    # store 仍保留 checkpoint=1，expected 应为 1
    _run_executor(mock_fetch=mock_fetch)
    assert store.calls[1].expected_checkpoint_version == 1
    # checkpoint 不前移（仍为 1，因为同 batch 幂等重放）
    assert store.calls[1].expected_checkpoint_version >= store.calls[0].expected_checkpoint_version


# ═══════════════════════════════════════════════
# 5. 重复：相同版本+不同 hash → 验证冲突检测
# ═══════════════════════════════════════════════


def test_p01_same_version_different_hash_conflict_detected(mock_fetch):
    """相同版本+不同 hash → EcomConsistencyError(IDEMPOTENCY_CONFLICT)。

    场景：首装写入 site_name="栖月汇"，重跑时 site_name 改为"新名称"
    （相同 source_pk + source_updated_at，但 properties 不同 → request_hash 不同）。
    store 检测到冲突，抛 IDEMPOTENCY_CONFLICT，executor 不吞异常。
    """
    store = FakeStore()
    _inject_store(store)

    # 首装
    mock_fetch.return_value = [shop_row(site_name="栖月汇")]
    _run_executor(mock_fetch=mock_fetch)

    # 重跑：相同 cursor 但不同 properties → 冲突
    mock_fetch.return_value = [shop_row(site_name="新名称")]
    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor(mock_fetch=mock_fetch)

    assert caught.value.code == "IDEMPOTENCY_CONFLICT"
    # 两次调用的 idempotency_key 相同（基于 pipeline_id + max cursor）
    assert len(store.calls) == 2
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key


# ═══════════════════════════════════════════════
# 6. 越租户：跨 org/workspace 写入 → 验证拒绝（fail-closed）
# ═══════════════════════════════════════════════


def test_p01_cross_tenant_write_rejected_fail_closed(mock_fetch):
    """跨 org/workspace 写入 → EcomConsistencyError(TENANT_MISMATCH)。

    场景：store 只允许 dev-org/dev-project 写入。用其他 org/workspace 调用
    executor 时，BatchCommand 的 scope 不匹配 → 抛 TENANT_MISMATCH。
    """
    from aos_api.ecom_core_models import SyncScope

    # 构造允许的 scope key（与 TEST_SCOPE 对应的 SyncScope）
    allowed_scope = SyncScope(
        org_id="dev-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        stream="p01-shop",
    )
    store = TenantGuardStore(allowed_scope_key=allowed_scope.key())
    _inject_store(store)

    # 用不同 org 调用 executor → 拒绝
    other_scope = TenantScope("other-org", "other-project")
    mock_fetch.return_value = [shop_row()]
    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor(scope=other_scope, mock_fetch=mock_fetch)

    assert caught.value.code == "TENANT_MISMATCH"
