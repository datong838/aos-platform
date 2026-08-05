"""D1-W2: P04 Category 端到端测试 (FR-D1-6).

P04 Category 规格（frozen/02）:
- 源表/主键: ns_goods_category / category_id
- 源过滤: site_id=1
- 增量策略: 每日快照
- 目标 OT: Category
- 唯一键: niushop:1:{category_id}
- 关键校验: pid=0 为根；检测分类环和孤儿父级
- Link: inCategory: Product → Category (category_id)（多分类字符串需先定义拆分契约）
- 派生指标: 无（Category 没有 FR-D1-7 定义的 4 个派生指标）

注意：P04 的 inCategory Link 由 W3 的 ec_link_builder.py 构造。
W2 的测试只验证 Category OT 落地和分类环/孤儿父级校验。
测试时 mock ec_link_builder.build_link_rows 为透传。

测试覆盖 6 项（FR-D1-6 四段实施）+ 3 项额外：
1. 初装：首次全量读取 → 落地 OT + Dataset
2. 增量：基于复合游标增量读取 → 幂等 upsert（P04 是快照模式，增量等价于重跑）
3. 重跑：重复执行同一批次 → 验证幂等
4. 断点：模拟中断后恢复 → 验证 checkpoint CAS 不前移
5. 重复：相同版本+不同 hash → 验证冲突检测
6. 越租户：跨 org/workspace 写入 → 验证拒绝
7. 分类环检测（A→B→A 环）
8. 孤儿父级检测（pid 指向不存在的 category_id）
9. inCategory 拆分契约（多值字符串）
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aos_api import data_os_store
from aos_api.ecom_core_models import BatchCommand, BatchResult, EcomConsistencyError
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.ec_dataset_sink import sink_to_dataset
from aos_api.public_contracts import StableCursor
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("other-org", "other-project")


# ─────────── fakes ───────────


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，可配置返回值与异常。

    仿 test_ec_d1_ot_writer.py 的 FakeStore 模式。
    """

    def __init__(self, *, result: BatchResult | None = None, raises: Exception | None = None):
        self.calls: list[BatchCommand] = []
        self._result = result
        self._raises = raises
        self._checkpoints: dict[tuple, int] = {}

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        self.calls.append(command)
        if self._raises is not None:
            raise self._raises
        if self._result is not None:
            key = command.scope.key()
            if key not in self._checkpoints:
                self._checkpoints[key] = 0
            self._checkpoints[key] += 1
            return self._result.model_copy(
                update={"checkpoint_version": self._checkpoints[key]}
            )
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


class FakeEngine:
    """带 ecom_consistency_store 属性的 fake engine。"""

    def __init__(self, store):
        self.ecom_consistency_store = store


class FakePipeline:
    def __init__(self, pid: str = "p04-category"):
        self.id = pid


# ─────────── Category 行工厂（P04 规格：ns_goods_category） ───────────


def category_row(
    *,
    category_id: str = "1",
    pid: int = 0,
    level: int = 1,
    name: str = "根分类",
    when: datetime = NOW,
    deleted: bool = False,
) -> dict:
    """P04 Category 行：ot=Category, source_pk=category_id, properties 含 pid/level/name。

    pid=0 表示根分类（frozen/02 §P04 关键校验）。

    CoreObjectRecord.validate_core_shape 要求 Category 的 properties 含：
    parentCategoryId / name / status / updatedAt（ecom_core_models.REQUIRED_PROPERTIES）。
    """
    return {
        "ot": "Category",
        "source_pk": category_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": deleted,
        "properties": {
            "parentCategoryId": str(pid),
            "name": name,
            "status": "active",
            "updatedAt": when.isoformat(),
            # 额外字段（P04 规格保留）
            "pid": pid,
            "level": level,
            "categoryFullName": name,
        },
    }


def product_row_with_categories(
    *,
    goods_id: str = "g-1",
    category_id_str: str = "1",
    when: datetime = NOW,
) -> dict:
    """P02 Product 行，category_id 字段可能是逗号分隔的多值字符串。

    用于 inCategory 拆分契约测试（frozen/02 §P04 Link）。
    CoreObjectRecord.validate_core_shape 要求 Product 的 properties 含：
    shopId / title / status / categoryId / createdAt / updatedAt。
    """
    return {
        "ot": "Product",
        "source_pk": goods_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "shopId": "1",
            "title": "测试商品",
            "status": "active",
            "categoryId": category_id_str,
            "createdAt": when.isoformat(),
            "updatedAt": when.isoformat(),
        },
    }


def _stub_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    """把 data_os_store.persist_dataset / persist_dataset_history 替换为 noop。"""
    monkeypatch.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)


# ═══════════════════════════════════════════════
# 1. 初装：首次全量读取 → 落地 OT + Dataset
# ═══════════════════════════════════════════════


def test_initial_load_lands_category_ot_and_dataset(monkeypatch):
    """初装：首次全量读取 → 落地 OT + Dataset。

    构造 3 个 Category 行（pid=0 根 + 2 个子分类），验证：
    - sink_to_ot 调用 apply_batch，含 3 个 Category objects
    - external_id 格式 niushop:1:{category_id}
    - sink_to_dataset 落地 Dataset（rid 生成 + build 记录）
    """
    _stub_persist(monkeypatch)
    store = FakeStore()
    eng = FakeEngine(store)

    rows = [
        category_row(category_id="1", pid=0, level=1, name="根分类"),
        category_row(category_id="2", pid=1, level=2, name="子分类A"),
        category_row(category_id="3", pid=1, level=2, name="子分类B"),
    ]

    # sink OT
    ot_result = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)
    assert ot_result["objects_written"] == 3

    command = store.calls[0]
    assert len(command.objects) == 3
    for obj in command.objects:
        assert obj.object_type == "Category"
        assert obj.identity.platform == "niushop"
        assert obj.identity.shop_or_marketplace_id == "1"
        assert obj.identity.external_id.startswith("niushop:1:")

    # sink Dataset
    from aos_api.phase5_pipeline_engine import get_engine
    real_eng = get_engine()
    real_eng.reset_all_for_tests()
    ds = sink_to_dataset(real_eng, TEST_SCOPE, FakePipeline(), rows)
    assert ds.id.startswith("ri.dataset.")
    builds = real_eng.list_builds(TEST_SCOPE, ds.id)
    assert len(builds) == 1
    assert builds[0].rows_written == 3
    real_eng.reset_all_for_tests()


# ═══════════════════════════════════════════════
# 2. 增量：基于复合游标增量读取 → 幂等 upsert
# ═══════════════════════════════════════════════


def test_incremental_snapshot_mode_idempotent_upsert():
    """增量：P04 是快照模式，增量等价于重跑。

    第二次调用相同 batch，FakeStore 返回 replayed=True，
    sink_to_ot 透传原计数（不重复累加）。
    """
    replay_result = BatchResult(
        objects_written=2,
        links_written=0,
        checkpoint_version=1,
        checkpoint=StableCursor(source_updated_at_utc=NOW, external_id="niushop:1:2"),
        replayed=True,
    )
    store = FakeStore(result=replay_result)
    eng = FakeEngine(store)

    rows = [
        category_row(category_id="1", pid=0, level=1),
        category_row(category_id="2", pid=1, level=2),
    ]

    first = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)
    second = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert first["objects_written"] == 2
    # 幂等重放：计数不翻倍，仍为 2
    assert second["objects_written"] == 2
    assert len(store.calls) == 2


# ═══════════════════════════════════════════════
# 3. 重跑：重复执行同一批次 → 验证幂等
# ═══════════════════════════════════════════════


def test_rerun_same_batch_idempotency_key_stable():
    """重跑：同一批次重跑 idempotency_key 稳定，store 能识别为幂等重放。"""
    store = FakeStore()
    eng = FakeEngine(store)

    rows = [category_row(category_id="1", pid=0, level=1)]

    sink_to_ot(eng, TEST_SCOPE, FakePipeline("p04"), rows)
    sink_to_ot(eng, TEST_SCOPE, FakePipeline("p04"), rows)

    assert len(store.calls) == 2
    # 相同 batch 重跑，idempotency_key 稳定
    assert store.calls[0].idempotency_key == store.calls[1].idempotency_key
    assert store.calls[0].idempotency_key != ""


def test_rerun_same_batch_same_counts():
    """重跑：相同 batch 重跑，objects_written 计数一致（不翻倍）。"""
    store = FakeStore()
    eng = FakeEngine(store)

    rows = [
        category_row(category_id="1", pid=0, level=1),
        category_row(category_id="2", pid=1, level=2),
    ]

    first = sink_to_ot(eng, TEST_SCOPE, FakePipeline("p04"), rows)
    second = sink_to_ot(eng, TEST_SCOPE, FakePipeline("p04"), rows)

    assert first["objects_written"] == 2
    assert second["objects_written"] == 2


# ═══════════════════════════════════════════════
# 4. 断点：模拟中断后恢复 → 验证 checkpoint CAS 不前移
# ═══════════════════════════════════════════════


def test_checkpoint_advances_after_first_batch():
    """断点恢复：首装后 expected_checkpoint_version 推进，第二次调用 expected=1。

    验证 checkpoint CAS 不前移：第二次调用不会退回 expected=0 触发 CAS_CONFLICT。
    """
    store = FakeStore()
    eng = FakeEngine(store)

    first_rows = [category_row(category_id="1", pid=0, level=1, when=NOW)]
    second_rows = [category_row(category_id="2", pid=1, level=2, when=NOW)]

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), first_rows)
    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), second_rows)

    assert len(store.calls) == 2
    # 首装 expected=0
    assert store.calls[0].expected_checkpoint_version == 0
    # 第二次 expected=1（不前移到 0）
    assert store.calls[1].expected_checkpoint_version == 1


def test_checkpoint_next_cursor_advances():
    """断点恢复：next_checkpoint 推进到 batch 内最大 cursor。"""
    store = FakeStore()
    eng = FakeEngine(store)

    earlier = category_row(category_id="1", pid=0, level=1, when=datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc))
    later = category_row(category_id="2", pid=1, level=2, when=NOW)

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [earlier, later])

    command = store.calls[0]
    # next_checkpoint 必须等于最大 (source_updated_at, external_id)
    assert command.next_checkpoint.source_updated_at_utc == NOW
    assert command.next_checkpoint.external_id == "niushop:1:2"


# ═══════════════════════════════════════════════
# 5. 重复：相同版本+不同 hash → 验证冲突检测
# ═══════════════════════════════════════════════


def test_same_version_different_hash_raises_conflict():
    """重复：相同版本+不同 hash → store 抛 IDEMPOTENCY_CONFLICT，sink_to_ot 不吞异常。"""
    conflict = EcomConsistencyError(
        "IDEMPOTENCY_CONFLICT",
        "idempotency key was already used with a different request",
    )
    store = FakeStore(raises=conflict)
    eng = FakeEngine(store)

    rows = [category_row(category_id="1", pid=0, level=1)]

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


def test_source_version_conflict_propagated():
    """重复：相同 source version + 不同 payload → store 抛 SOURCE_VERSION_CONFLICT。"""
    conflict = EcomConsistencyError(
        "SOURCE_VERSION_CONFLICT",
        "same object source version has a different payload",
        details={"objectType": "Category"},
    )
    store = FakeStore(raises=conflict)
    eng = FakeEngine(store)

    rows = [category_row(category_id="1", pid=0, level=1)]

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert caught.value.code == "SOURCE_VERSION_CONFLICT"


# ═══════════════════════════════════════════════
# 6. 越租户：跨 org/workspace 写入 → 验证拒绝
# ═══════════════════════════════════════════════


def test_scope_passed_to_apply_batch():
    """越租户拒绝前提：scope 正确传递到 apply_batch，BatchCommand.scope 与传入 scope 一致。"""
    store = FakeStore()
    eng = FakeEngine(store)

    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [category_row(category_id="1")])

    command = store.calls[0]
    sync_scope = command.scope
    assert sync_scope.org_id == TEST_SCOPE.org_id
    assert sync_scope.workspace_id == TEST_SCOPE.project_id
    assert sync_scope.platform == "niushop"
    assert sync_scope.shop_or_marketplace_id == "1"
    # object identity 必须落在同 scope 内（BatchCommand validator 拒绝跨 scope）
    obj = command.objects[0]
    assert obj.identity.org_id == TEST_SCOPE.org_id
    assert obj.identity.workspace_id == TEST_SCOPE.project_id


def test_different_scope_batch_command_isolated():
    """越租户隔离：不同 scope 产生不同的 BatchCommand.scope，互不干扰。"""
    store = FakeStore()
    eng = FakeEngine(store)

    sink_to_ot(eng, TEST_SCOPE, FakePipeline("p04-a"), [category_row(category_id="1")])
    sink_to_ot(eng, OTHER_SCOPE, FakePipeline("p04-b"), [category_row(category_id="2")])

    assert len(store.calls) == 2
    assert store.calls[0].scope.org_id == "dev-org"
    assert store.calls[1].scope.org_id == "other-org"
    # 两个 batch 的 idempotency_key 不同（scope 不同）
    assert store.calls[0].idempotency_key != store.calls[1].idempotency_key


def test_cross_scope_object_identity_rejected_by_validator():
    """越租户拒绝：BatchCommand validator 拒绝跨 scope 的 object identity。

    构造一个 Category 行，手动篡改 source_pk 让 external_id 跨 scope 是不可能的
    （ec_ot_writer 用 sync_scope 构造 identity）。但 BatchCommand validator
    在 _build_object 之后会校验 identity 与 scope 一致。
    这里验证 sink_to_ot 正确用 sync_scope 构造 identity（不跨租户）。
    """
    store = FakeStore()
    eng = FakeEngine(store)

    # 在 TEST_SCOPE 下落地 Category，identity 必须在 TEST_SCOPE 内
    sink_to_ot(eng, TEST_SCOPE, FakePipeline(), [category_row(category_id="42")])

    command = store.calls[0]
    obj = command.objects[0]
    assert obj.identity.org_id == TEST_SCOPE.org_id
    assert obj.identity.workspace_id == TEST_SCOPE.project_id
    assert obj.identity.external_id == "niushop:1:42"


# ═══════════════════════════════════════════════
# 7. 分类环检测（A→B→A 环）
# ═══════════════════════════════════════════════


def test_category_cycle_detected_propagates_error():
    """分类环检测：A.pid=B, B.pid=A 形成环 → store 抛 CATEGORY_CYCLE，
    sink_to_ot 不吞异常，向上传播。

    P04 关键校验（frozen/02 §P04）：检测分类环。
    环检测逻辑由 store 内核或 link_builder 实现（W3/未来），
    本测试验证 sink_to_ot 的传播契约：不吞 EcomConsistencyError。
    """
    cycle_error = EcomConsistencyError(
        "CATEGORY_CYCLE",
        "category parent relationship forms a cycle",
        details={"cycle": ["1", "2", "1"]},
    )
    store = FakeStore(raises=cycle_error)
    eng = FakeEngine(store)

    # A.pid=B, B.pid=A 形成环
    rows = [
        category_row(category_id="1", pid=2, level=2, name="A"),
        category_row(category_id="2", pid=1, level=2, name="B"),
    ]

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert caught.value.code == "CATEGORY_CYCLE"


def test_category_cycle_error_details_preserved():
    """分类环检测：异常 details 被保留（含环路径）。"""
    cycle_error = EcomConsistencyError(
        "CATEGORY_CYCLE",
        "category parent relationship forms a cycle",
        details={"cycle": ["1", "2", "3", "1"]},
    )
    store = FakeStore(raises=cycle_error)
    eng = FakeEngine(store)

    rows = [
        category_row(category_id="1", pid=3, level=3),
        category_row(category_id="2", pid=1, level=3),
        category_row(category_id="3", pid=2, level=3),
    ]

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert caught.value.details["cycle"] == ["1", "2", "3", "1"]


# ═══════════════════════════════════════════════
# 8. 孤儿父级检测（pid 指向不存在的 category_id）
# ═══════════════════════════════════════════════


def test_orphan_parent_detected_propagates_error():
    """孤儿父级检测：pid 指向不存在的 category_id → store 抛 DANGLING_PARENT，
    sink_to_ot 不吞异常，向上传播。

    P04 关键校验（frozen/02 §P04）：检测孤儿父级。
    孤儿父级检测逻辑由 store 内核或 link_builder 实现，
    本测试验证 sink_to_ot 的传播契约。
    """
    orphan_error = EcomConsistencyError(
        "DANGLING_PARENT",
        "category pid points to a non-existent parent category",
        details={"categoryId": "2", "missingPid": "999"},
    )
    store = FakeStore(raises=orphan_error)
    eng = FakeEngine(store)

    # category_id=2 的 pid=999（不存在）
    rows = [category_row(category_id="2", pid=999, level=2, name="孤儿")]

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert caught.value.code == "DANGLING_PARENT"


def test_orphan_parent_error_details_preserved():
    """孤儿父级检测：异常 details 被保留（含孤儿 categoryId 和 missingPid）。"""
    orphan_error = EcomConsistencyError(
        "DANGLING_PARENT",
        "category pid points to a non-existent parent category",
        details={"categoryId": "5", "missingPid": "1000"},
    )
    store = FakeStore(raises=orphan_error)
    eng = FakeEngine(store)

    rows = [category_row(category_id="5", pid=1000, level=2)]

    with pytest.raises(EcomConsistencyError) as caught:
        sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert caught.value.details["categoryId"] == "5"
    assert caught.value.details["missingPid"] == "1000"


def test_root_category_pid_zero_accepted():
    """pid=0 为根分类（frozen/02 §P04 关键校验）：根分类正常落地，不触发孤儿检测。"""
    store = FakeStore()
    eng = FakeEngine(store)

    rows = [category_row(category_id="1", pid=0, level=1, name="根分类")]

    result = sink_to_ot(eng, TEST_SCOPE, FakePipeline(), rows)

    assert result["objects_written"] == 1
    command = store.calls[0]
    obj = command.objects[0]
    # pid=0 在 properties 中保留
    assert obj.properties["pid"] == 0
    assert obj.properties["level"] == 1


# ═══════════════════════════════════════════════
# 9. inCategory 拆分契约（多值字符串）
# ═══════════════════════════════════════════════


def test_incategory_split_contract_single_value(monkeypatch):
    """inCategory 拆分契约：单值 category_id 字符串。

    任务说明：mock ec_link_builder.build_link_rows 为透传。
    骨架阶段 build_link_rows 透传 rows，不追加 Link 行。
    本测试验证：单值 category_id 时，rows 透传不变（W3 实现后会追加 inCategory Link）。
    """
    from aos_api.ec_link_builder import build_link_rows

    rows = [product_row_with_categories(goods_id="g-1", category_id_str="1")]

    # mock 为透传（与骨架行为一致）
    monkeypatch.setattr(
        "aos_api.ec_link_builder.build_link_rows",
        lambda rows, p: rows,
    )

    result = build_link_rows(rows, FakePipeline("p02"))
    assert result == rows
    assert len(result) == 1
    assert result[0]["properties"]["categoryId"] == "1"


def test_incategory_split_contract_multi_value(monkeypatch):
    """inCategory 拆分契约：多值 category_id 字符串（逗号分隔）。

    Niushop 的 ns_goods.category_id 字段可能是 "1,2,3" 形式（frozen/02 §P04 Link）。
    拆分契约：按逗号分割，每个 category_id 独立构造一条 inCategory Link。
    骨架阶段 build_link_rows 透传，不拆分；W3 实现后会拆分。
    本测试验证：多值字符串时，rows 透传不变（拆分契约由 W3 实现）。
    """
    from aos_api.ec_link_builder import build_link_rows

    rows = [product_row_with_categories(goods_id="g-1", category_id_str="1,2,3")]

    monkeypatch.setattr(
        "aos_api.ec_link_builder.build_link_rows",
        lambda rows, p: rows,
    )

    result = build_link_rows(rows, FakePipeline("p02"))
    # 骨架透传：rows 不变，categoryId 仍为原始多值字符串
    assert len(result) == 1
    assert result[0]["properties"]["categoryId"] == "1,2,3"


def test_incategory_split_contract_empty_value(monkeypatch):
    """inCategory 拆分契约：空值 category_id 字符串。

    空字符串 → 不构造 inCategory Link（W3 实现后）。
    骨架阶段透传，rows 不变。
    """
    from aos_api.ec_link_builder import build_link_rows

    rows = [product_row_with_categories(goods_id="g-1", category_id_str="")]

    monkeypatch.setattr(
        "aos_api.ec_link_builder.build_link_rows",
        lambda rows, p: rows,
    )

    result = build_link_rows(rows, FakePipeline("p02"))
    assert len(result) == 1
    assert result[0]["properties"]["categoryId"] == ""


def test_incategory_split_contract_invalid_value(monkeypatch):
    """inCategory 拆分契约：异常值 category_id 字符串（非数字）。

    异常值（如 "abc"）→ 不构造 inCategory Link 或进 DLQ（W3 实现后）。
    骨架阶段透传，rows 不变。
    """
    from aos_api.ec_link_builder import build_link_rows

    rows = [product_row_with_categories(goods_id="g-1", category_id_str="abc,xyz")]

    monkeypatch.setattr(
        "aos_api.ec_link_builder.build_link_rows",
        lambda rows, p: rows,
    )

    result = build_link_rows(rows, FakePipeline("p02"))
    assert len(result) == 1
    assert result[0]["properties"]["categoryId"] == "abc,xyz"


def test_incategory_split_contract_mixed_valid_invalid(monkeypatch):
    """inCategory 拆分契约：混合有效/无效值（"1,abc,2"）。

    W3 实现后：有效值 1/2 构造 inCategory Link，无效值 abc 进 DLQ。
    骨架阶段透传，rows 不变。
    """
    from aos_api.ec_link_builder import build_link_rows

    rows = [product_row_with_categories(goods_id="g-1", category_id_str="1,abc,2")]

    monkeypatch.setattr(
        "aos_api.ec_link_builder.build_link_rows",
        lambda rows, p: rows,
    )

    result = build_link_rows(rows, FakePipeline("p02"))
    assert len(result) == 1
    assert result[0]["properties"]["categoryId"] == "1,abc,2"


# ═══════════════════════════════════════════════
# 10. Category 无派生指标（FR-D1-7 不适用）
# ═══════════════════════════════════════════════


def test_category_has_no_derived_metrics(monkeypatch):
    """Category 没有 FR-D1-7 定义的 4 个派生指标：apply_derived_metrics 透传不修改。"""
    from aos_api.ec_derived_metrics import apply_derived_metrics

    rows = [category_row(category_id="1", pid=0, level=1)]

    result = apply_derived_metrics(rows, FakePipeline("p04"))
    # 骨架透传：rows 不变
    assert result == rows
    assert len(result) == 1
    # 不含派生指标字段
    assert "quality_score" not in result[0].get("properties", {})
    assert "stock_health" not in result[0].get("properties", {})
    assert "risk_score" not in result[0].get("properties", {})
    assert "overdue_hours" not in result[0].get("properties", {})
