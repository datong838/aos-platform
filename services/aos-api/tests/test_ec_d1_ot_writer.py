"""D1-W3: G5 OTWriter 专项测试（FR-D1-2）。

覆盖 sink_to_ot 调用 ecom_consistency_store.apply_batch（BatchCommand 单事务：
upsert→link→checkpoint→receipt）的关键行为，使用 fake store 验证调用契约。
一致性内核（旧版本不覆盖/同版本同 hash 幂等/同版本异 hash 冲突/tombstone/
悬挂 Link 拒绝/整事务回滚）由 ecom_consistency_store 自身保证，本测试只验证
OTWriter 正确构造 BatchCommand 并传播结果/异常。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aos_api.ecom_core_models import BatchCommand, BatchResult, EcomConsistencyError
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.public_contracts import StableCursor
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")


# ---------- fakes ----------


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，可配置返回值与异常。"""

    def __init__(self, *, result: BatchResult | None = None, raises: Exception | None = None):
        self.calls: list[BatchCommand] = []
        self._result = result
        self._raises = raises
        # checkpoint 版本表：scope_key -> version，模拟 store 内核行为
        self._checkpoints: dict[tuple, int] = {}

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        self.calls.append(command)
        if self._raises is not None:
            raise self._raises
        if self._result is not None:
            # 推进 checkpoint 版本（模拟真实 store）
            key = command.scope.key()
            if key not in self._checkpoints:
                self._checkpoints[key] = 0
            self._checkpoints[key] += 1
            return self._result.model_copy(
                update={"checkpoint_version": self._checkpoints[key]}
            )
        # 默认结果：objects/links 计数 = batch 大小
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

    def get_checkpoint(self, command: BatchCommand) -> dict | None:
        key = command.scope.key()
        version = self._checkpoints.get(key)
        if version is None:
            return None
        return {"version": version}


class FakePipeline:
    def __init__(self, pid: str = "p01-shop"):
        self.id = pid


class FakeEngine:
    """带 ecom_consistency_store 属性的 fake engine。"""

    def __init__(self, store):
        self.ecom_consistency_store = store


class NoStoreEngine:
    """没有 ecom_consistency_store 属性的 engine（骨架兼容场景）。"""


# ---------- row 工厂（约定 output_rows 字段格式） ----------


def shop_row(*, source_pk: str = "1", when: datetime = NOW, deleted: bool = False) -> dict:
    """P01 Shop 行：source_pk + properties + source_updated_at。"""
    return {
        "ot": "Shop",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": deleted,
        "properties": {
            "name": "栖月汇",
            "status": "active",
            "currency": "CNY",
            "timezone": "Asia/Shanghai",
        },
    }


def product_row(*, source_pk: str = "g-1", when: datetime = NOW) -> dict:
    return {
        "ot": "Product",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "shopId": "1",
            "title": "测试商品",
            "status": "active",
            "categoryId": "c-1",
            "createdAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def shop_sells_product_link_row(
    *,
    source_pk: str = "1",
    target_source_pk: str = "g-1",
    when: datetime = NOW,
) -> dict:
    """Shop.sellsProduct Link 行：通过 link_type 字段区分。"""
    return {
        "link_type": "Shop.sellsProduct",
        "source_type": "Shop",
        "target_type": "Product",
        "source_pk": source_pk,
        "target_source_pk": target_source_pk,
        "source_updated_at": when,
        "cursor_external_id": f"link:{source_pk}->{target_source_pk}",
    }


# ---------- 测试 ----------


def test_sink_to_ot_calls_apply_batch_with_objects():
    """sink_to_ot 调用 store.apply_batch 落地 OT 对象。"""
    store = FakeStore()
    eng = FakeEngine(store)

    result = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row()])

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    assert command.objects[0].object_type == "Shop"
    assert result["objects_written"] == 1


def test_external_id_uses_niushop_namespace():
    """唯一键格式 niushop:1:{source_pk}（frozen/02 §通用骨架）。"""
    store = FakeStore()
    eng = FakeEngine(store)

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row(source_pk="42")])

    command = store.calls[0]
    obj = command.objects[0]
    assert obj.identity.external_id == "niushop:1:42"
    assert obj.identity.platform == "niushop"
    assert obj.identity.shop_or_marketplace_id == "1"


def test_idempotent_replay_same_hash_returns_same_counts():
    """相同版本+相同 hash 幂等：第二次 apply_batch 返回 replayed=True，
    sink_to_ot 透传原计数（不重复累加）。"""
    replay_result = BatchResult(
        objects_written=1,
        links_written=0,
        checkpoint_version=1,
        checkpoint=StableCursor(source_updated_at_utc=NOW, external_id="niushop:1:1"),
        replayed=True,
    )
    store = FakeStore(result=replay_result)
    eng = FakeEngine(store)

    first = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row()])
    second = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row()])

    assert first["objects_written"] == 1
    # 幂等重放：计数不翻倍，仍为 1
    assert second["objects_written"] == 1
    assert len(store.calls) == 2


def test_same_version_different_hash_raises_conflict():
    """相同版本+不同 hash 返回冲突：store 抛 EcomConsistencyError，
    sink_to_ot 不吞异常，向上传播。"""
    conflict = EcomConsistencyError(
        "IDEMPOTENCY_CONFLICT",
        "idempotency key was already used with a different request",
    )
    store = FakeStore(raises=conflict)
    eng = FakeEngine(store)

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row()])

    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


def test_link_landed_in_same_batch_command():
    """Link 同事务落地：object 和 link 在同一个 BatchCommand 内。"""
    store = FakeStore()
    eng = FakeEngine(store)

    rows = [shop_row(), product_row(), shop_sells_product_link_row()]
    result = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 2
    assert len(command.links) == 1
    link = command.links[0]
    assert link.link_type == "Shop.sellsProduct"
    assert link.source.external_id == "niushop:1:1"
    assert link.target.external_id == "niushop:1:g-1"
    assert result["objects_written"] == 2
    assert result["links_written"] == 1


def test_scope_passed_to_apply_batch():
    """scope 被传递到 apply_batch，不丢失租户信息。"""
    store = FakeStore()
    eng = FakeEngine(store)

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row()])

    command = store.calls[0]
    sync_scope = command.scope
    assert sync_scope.org_id == TEST_SCOPE.org_id
    assert sync_scope.workspace_id == TEST_SCOPE.project_id
    assert sync_scope.platform == "niushop"
    assert sync_scope.shop_or_marketplace_id == "1"
    # object identity 必须落在同 scope 内（否则 BatchCommand validator 拒绝）
    obj = command.objects[0]
    assert obj.identity.org_id == TEST_SCOPE.org_id
    assert obj.identity.workspace_id == TEST_SCOPE.project_id


def test_skeleton_returns_zero_when_store_missing():
    """骨架向后兼容：engine 没有 ecom_consistency_store 属性时返回零计数。"""
    eng = NoStoreEngine()

    result = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row()])

    assert result == {"objects_written": 0, "links_written": 0}


def test_empty_rows_returns_zero():
    """空 batch 返回零计数（BatchCommand validator 拒绝空 batch）。"""
    store = FakeStore()
    eng = FakeEngine(store)

    result = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [])

    assert result == {"objects_written": 0, "links_written": 0}
    assert store.calls == []


def test_delete_row_passes_is_deleted_tombstone():
    """DELETE 写 tombstone：is_deleted=True 透传给 store，不物理删除。"""
    store = FakeStore()
    eng = FakeEngine(store)

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row(deleted=True)])

    command = store.calls[0]
    obj = command.objects[0]
    assert obj.is_deleted is True


def test_compound_cursor_aligned_with_batch_max():
    """复合游标 (watermark, primary_key) 稳定二元组：next_checkpoint
    必须等于 batch 内最大 cursor（BatchCommand validator 要求）。"""
    store = FakeStore()
    eng = FakeEngine(store)

    earlier = shop_row(source_pk="1", when=datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc))
    later = shop_row(source_pk="2", when=NOW)
    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [earlier, later])

    command = store.calls[0]
    # next_checkpoint 必须等于最大 (source_updated_at, external_id)
    assert command.next_checkpoint.source_updated_at_utc == NOW
    assert command.next_checkpoint.external_id == "niushop:1:2"


def test_idempotency_key_stable_for_same_batch():
    """相同 batch 重跑 idempotency_key 稳定（基于 scope+max cursor），
    保证 store 能识别为幂等重放而非新批次。"""
    store = FakeStore()
    eng = FakeEngine(store)

    sink_to_ot(eng, TEST_SCOPE, FakePipeline("p01"), [shop_row(source_pk="1")])
    sink_to_ot(eng, TEST_SCOPE, FakePipeline("p01"), [shop_row(source_pk="1")])

    assert len(store.calls) == 2
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key
    assert store.calls[0].idempotency_key != ""


def test_expected_checkpoint_version_advances_after_first_batch():
    """首装后 expected_checkpoint_version 推进：第二次调用查到 version=1，
    expected=1（支持增量，不退回 0 触发 CAS_CONFLICT）。"""
    store = FakeStore()
    eng = FakeEngine(store)

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row(source_pk="1")])
    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [shop_row(source_pk="2")])

    assert len(store.calls) == 2
    assert store.calls[0].expected_checkpoint_version == 0
    assert store.calls[1].expected_checkpoint_version == 1
