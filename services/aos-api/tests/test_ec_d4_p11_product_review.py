"""D4 Phase A: P11 ProductReview OT 管道执行测试（frozen/02 §P11）。

P11 ProductReview 规格：
- 源表/主键: ns_goods_evaluate / id
- 增量策略: (create_time, id) 复合游标 + 每日重扫 24h 窗口
- 目标 OT: ProductReview
- normalize mapper to_product_review: productId=goods_id, memberId=member_id, score=scores/score
- 3 Link:
  · Product.hasReview（goods_id 关联）
  · ProductReview.ofSku（sku_id 关联，sku_id=0 跳过）
  · ProductReview.byMember（member_id 关联）
- 派生指标: review_quality_bucket（score≥4.5→high / ≤3.0→low / 其他→mid）

测试覆盖 5 项（FR-D1-6 四段实施）：
1. 初装：首次全量读取 → 落地 OT + Dataset（含 review_quality_bucket 派生指标）
2. 增量：复合游标推进 → checkpoint 推进（CAS 不前移）
3. 重跑：重复执行同一批次 → 幂等（replayed=True）
4. 断点：模拟中断后恢复 → checkpoint CAS 不前移
5. 越租户：跨 org/workspace 写入 → 拒绝（fail-closed）

额外覆盖：
6. review_quality_bucket 边界值（score=3.0→low, score=4.5→high, score=4.0→mid）
7. 3 Link 构造（hasReview / ofSku / byMember，build_link_rows 直接验证）
8. ofSku 跳过 sku_id=0 场景
9. to_product_review mapper 字段映射

mock 策略（照搬 test_ec_d1_p01_shop.py）：
- fetch_source_rows: mock 返回 normalized ProductReview 行（绕过 MySQL + normalize）
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
from aos_api.ec_derived_metrics import apply_derived_metrics
from aos_api.ec_link_builder import build_link_rows
from aos_api.ec_normalizer import to_product_review
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
    with patch("aos_api.ec_live_executor.fetch_source_rows") as m:
        yield m


# ═══════════════════════════════════════════════
# 管道配置工厂（A3-3，内嵌测试文件）
# ═══════════════════════════════════════════════


def define_p11_pipeline_config(pid: str = "p11-product-review") -> dict:
    """P11 ProductReview Pipeline 完整配置（5 节点 graph）。"""
    return {
        "id": pid,
        "sourceId": "niushop-goods-evaluate",
        "name": "P11 ProductReview Pipeline",
        "objectTypeHint": "ProductReview",
        "config": {
            "target_ot": "ProductReview",
            "source_table": "ns_goods_evaluate",
            "primary_key": "id",
            "unique_key_template": "niushop:1:eval_{id}",
            "incremental_strategy": "cursor",
            "cursor_fields": ["create_time", "id"],
            "rescan_window_hours": 24,
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": "niushop-goods-evaluate",
                    "source_table": "ns_goods_evaluate",
                    "primary_key": "id",
                    "watermark_col": "create_time",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {"target_ot": "ProductReview"},
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {"required_fields": ["goods_id", "member_id"]},
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {"target_ot": "ProductReview"},
            },
            {
                "id": "sink",
                "name": "Sink",
                "type": "sink",
                "config": {"target_ot": "ProductReview"},
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


def review_row(
    *,
    review_id: str = "rev_001",
    goods_id: str = "g-1",
    sku_id: str = "sku-1",
    member_id: str = "m-1",
    score: str = "4.5",
    when: datetime = NOW,
) -> dict:
    """P11 ProductReview normalized 行（含 ot 字段，绕过 normalize_rows）。

    properties 含 REQUIRED_PROPERTIES['ProductReview'] 要求的 productId/memberId/score/updatedAt。
    顶层保留 sku_id（供 build_link_rows 的 _build_review_links 读取）。
    """
    return {
        "ot": "ProductReview",
        "source_pk": review_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "sku_id": sku_id,
        "properties": {
            "productId": goods_id,
            "memberId": member_id,
            "score": score,
            "updatedAt": "2026-08-06T10:00:00Z",
        },
    }


def raw_review_row(
    *,
    review_id: str = "1",
    goods_id: str = "g-1",
    sku_id: str = "sku-1",
    member_id: str = "m-1",
    scores: float = 4.5,
    create_time: int = NOW_TS,
) -> dict:
    """P11 raw ns_goods_evaluate 行（未 normalize，供 to_product_review mapper 单测）。"""
    return {
        "id": review_id,
        "goods_id": goods_id,
        "sku_id": sku_id,
        "member_id": member_id,
        "scores": scores,
        "create_time": create_time,
    }


def _make_pipeline(pid: str = "p11-product-review") -> SimpleNamespace:
    cfg = define_p11_pipeline_config(pid)
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
# 1. 初装：首次全量读取 → 落地 OT + Dataset（含 review_quality_bucket 派生指标）
# ═══════════════════════════════════════════════


def test_p11_initial_load_lands_ot_and_dataset(mock_fetch):
    """初装：首次全量读取 → 落地 ProductReview OT + Dataset + review_quality_bucket 派生指标。"""
    mock_fetch.return_value = [review_row(score="4.5")]
    store = FakeStore()
    _inject_store(store)

    result = _run_executor(mock_fetch=mock_fetch)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    obj = command.objects[0]
    assert obj.object_type == "ProductReview"
    assert obj.identity.external_id == "niushop:1:rev_001"
    assert obj.properties.get("productId") == "g-1"
    assert obj.properties.get("memberId") == "m-1"
    assert obj.properties.get("score") == "4.5"
    # 派生指标 review_quality_bucket（score=4.5 → high）
    assert obj.properties.get("review_quality_bucket") == "high"
    # updatedAt 经 ZonedInstant 规范化
    assert obj.properties.get("updatedAt", "").startswith("2026-08-06T10:00:00")

    # Dataset 落地验证
    assert result["output_ref"].startswith("dataset://catalog/")
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1


# ═══════════════════════════════════════════════
# 2. 增量：复合游标推进 → checkpoint 推进（CAS 不前移）
# ═══════════════════════════════════════════════


def test_p11_incremental_cursor_mode_checkpoint_advances(mock_fetch):
    """增量：P11 是游标模式，第二次执行 → checkpoint 推进。"""
    mock_fetch.return_value = [review_row()]
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


def test_p11_rerun_same_batch_idempotent_replayed(mock_fetch):
    """重跑：相同 key+相同 hash → replayed=True，计数不翻倍。"""
    mock_fetch.return_value = [review_row()]
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


def test_p11_checkpoint_recovery_cas_not_moved_backward(mock_fetch):
    """断点恢复：首装后中断，重跑时 expected_checkpoint_version 不退回 0。"""
    mock_fetch.return_value = [review_row()]
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


def test_p11_cross_tenant_write_rejected_fail_closed(mock_fetch):
    """跨 org/workspace 写入 → EcomConsistencyError(TENANT_MISMATCH)。"""
    from aos_api.ecom_core_models import SyncScope

    allowed_scope = SyncScope(
        org_id="dev-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        stream="p11-product-review",
    )
    store = TenantGuardStore(allowed_scope_key=allowed_scope.key())
    _inject_store(store)

    other_scope = TenantScope("other-org", "other-project")
    mock_fetch.return_value = [review_row()]
    with pytest.raises(EcomConsistencyError) as caught:
        _run_executor(scope=other_scope, mock_fetch=mock_fetch)

    assert caught.value.code == "TENANT_MISMATCH"


# ═══════════════════════════════════════════════
# 6. review_quality_bucket 边界值（score=3.0/4.5/4.0）
# ═══════════════════════════════════════════════


def _apply_review_bucket(raw_row: dict) -> str | None:
    """便捷工具：raw 行 → to_product_review → apply_derived_metrics → 返回 review_quality_bucket。"""
    normalized = to_product_review(raw_row)
    pipeline = SimpleNamespace(id="p11-product-review", config={"target_ot": "ProductReview"})
    apply_derived_metrics([normalized], pipeline)
    return normalized["properties"].get("review_quality_bucket")


def test_p11_review_quality_bucket_score_3_0_is_low():
    """边界值: score=3.0 → low（含等号，frozen/02 §3.6）。"""
    raw = raw_review_row(scores=3.0)
    assert _apply_review_bucket(raw) == "low"


def test_p11_review_quality_bucket_score_4_5_is_high():
    """边界值: score=4.5 → high（含等号，frozen/02 §3.6）。"""
    raw = raw_review_row(scores=4.5)
    assert _apply_review_bucket(raw) == "high"


def test_p11_review_quality_bucket_score_4_0_is_mid():
    """边界值: score=4.0 → mid（3.0 < score < 4.5）。"""
    raw = raw_review_row(scores=4.0)
    assert _apply_review_bucket(raw) == "mid"


def test_p11_review_quality_bucket_score_below_3_is_low():
    """边界值: score=2.0 → low。"""
    raw = raw_review_row(scores=2.0)
    assert _apply_review_bucket(raw) == "low"


def test_p11_review_quality_bucket_score_above_4_5_is_high():
    """边界值: score=5.0 → high。"""
    raw = raw_review_row(scores=5.0)
    assert _apply_review_bucket(raw) == "high"


def test_p11_review_quality_bucket_score_missing_is_null():
    """边界值: score 缺失 → null（不阻塞 Pipeline）。"""
    raw = raw_review_row()
    raw.pop("scores", None)
    raw["score"] = None  # to_product_review 的 _str(row.get("scores"), _str(row.get("score")))
    bucket = _apply_review_bucket(raw)
    assert bucket is None


# ═══════════════════════════════════════════════
# 7. 3 Link 构造（hasReview / ofSku / byMember，build_link_rows 直接验证）
# ═══════════════════════════════════════════════


def test_p11_has_review_link_constructed():
    """hasReview Link 构造：Product → ProductReview（goods_id 关联）。

    hasReview 不反转：source=Product, target=ProductReview（与 CORE_LINK_TYPES 方向一致）。
    """
    rows = [review_row(review_id="rev_001", goods_id="g-1")]
    result = build_link_rows(rows, _make_pipeline("p11-product-review"))
    links = [r for r in result if r.get("link_type") == "Product.hasReview"]
    assert len(links) == 1
    link = links[0]
    assert link["link_type"] == "Product.hasReview"
    # hasReview 不反转：source=Product, target=ProductReview
    assert link["source_type"] == "Product"
    assert link["target_type"] == "ProductReview"
    assert link["source_pk"] == "g-1"
    assert link["target_source_pk"] == "rev_001"


def test_p11_of_sku_link_constructed():
    """ofSku Link 构造：ProductReview → ProductSku（sku_id 关联）。

    ofSku 不在 _REVERSED_LINKS，方向不反转。
    """
    rows = [review_row(review_id="rev_001", sku_id="sku-1")]
    result = build_link_rows(rows, _make_pipeline("p11-product-review"))
    links = [r for r in result if r.get("link_type") == "ProductReview.ofSku"]
    assert len(links) == 1
    link = links[0]
    assert link["link_type"] == "ProductReview.ofSku"
    assert link["source_type"] == "ProductReview"
    assert link["target_type"] == "ProductSku"
    assert link["source_pk"] == "rev_001"
    assert link["target_source_pk"] == "sku-1"


def test_p11_of_sku_link_skipped_when_sku_id_zero():
    """ofSku Link 构造：sku_id=0 时跳过（frozen/02 §P11）。"""
    rows = [review_row(review_id="rev_001", sku_id="0")]
    result = build_link_rows(rows, _make_pipeline("p11-product-review"))
    assert [r for r in result if r.get("link_type") == "ProductReview.ofSku"] == []


def test_p11_by_member_link_constructed():
    """byMember Link 构造：ProductReview → CustomerLite（member_id 关联）。

    byMember 不在 _REVERSED_LINKS，方向不反转。
    """
    rows = [review_row(review_id="rev_001", member_id="m-1")]
    result = build_link_rows(rows, _make_pipeline("p11-product-review"))
    links = [r for r in result if r.get("link_type") == "ProductReview.byMember"]
    assert len(links) == 1
    link = links[0]
    assert link["link_type"] == "ProductReview.byMember"
    assert link["source_type"] == "ProductReview"
    assert link["target_type"] == "CustomerLite"
    assert link["source_pk"] == "rev_001"
    assert link["target_source_pk"] == "m-1"


def test_p11_three_links_constructed_for_one_review():
    """单条 ProductReview 同时构造 hasReview + ofSku + byMember 三条 Link。"""
    rows = [review_row(review_id="rev_001", goods_id="g-1", sku_id="sku-1", member_id="m-1")]
    result = build_link_rows(rows, _make_pipeline("p11-product-review"))
    link_types = {r["link_type"] for r in result if r.get("link_type")}
    assert link_types == {
        "Product.hasReview",
        "ProductReview.ofSku",
        "ProductReview.byMember",
    }


# ═══════════════════════════════════════════════
# 8. to_product_review mapper 字段映射
# ═══════════════════════════════════════════════


def test_p11_to_product_review_mapper_field_mapping():
    """to_product_review mapper: raw ns_goods_evaluate → ProductReview normalized 行。"""
    raw = raw_review_row(
        review_id="1",
        goods_id="g-1",
        sku_id="sku-1",
        member_id="m-1",
        scores=4.5,
    )
    out = to_product_review(raw)

    assert out["ot"] == "ProductReview"
    assert out["source_pk"] == "1"
    assert out["source_timezone"] == "+08:00"
    assert out["is_deleted"] is False
    # properties 字段映射
    assert out["properties"]["productId"] == "g-1"
    assert out["properties"]["memberId"] == "m-1"
    assert out["properties"]["score"] == "4.5"
    # 保留 raw 字段（供 build_link_rows 读取 sku_id）
    assert out["sku_id"] == "sku-1"
    assert out["goods_id"] == "g-1"
    assert out["member_id"] == "m-1"


def test_p11_to_product_review_mapper_score_fallback_to_score_field():
    """to_product_review mapper: scores 缺失时回退到 score 字段。"""
    raw = raw_review_row()
    raw.pop("scores", None)
    raw["score"] = 3.5
    out = to_product_review(raw)
    assert out["properties"]["score"] == "3.5"
