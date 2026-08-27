"""D1-W3: P01-P07 端到端 Link 落地验证（FR-D1 Phase C）。

验证 6 条核心 Link 经过 ``ec_link_builder.build_link_rows`` →
``ec_ot_writer.sink_to_ot``（真实 ``_build_link`` + ``CoreLinkRecord`` 构造 +
``validate_link`` 校验）→ ``ecom_consistency_store.apply_batch`` 的真实落地。

与 ``test_ec_d1_ot_writer.py`` 的区别：本测试 **不 Mock sink_to_ot**，
让 Link 行真实经过 ``_normalize_rows`` → ``_build_link`` → ``CoreLinkRecord``
构造 → ``validate_link`` 校验。如果 C1 映射层（点号名 + 方向反转）有 bug，
``CoreLinkRecord.validate_link`` 会抛 ``ValueError``，测试会失败。

由于真实 ``ecom_consistency_store`` 需要 PostgreSQL，使用 ``FakeStore``
（只 mock ``apply_batch`` / ``get_checkpoint``），但 ``sink_to_ot`` 内部的
行拆分、``CoreObjectRecord`` / ``CoreLinkRecord`` 构造、validator 校验全部
真实执行。

覆盖 6 条核心 Link（与 ``CORE_LINK_TYPES`` 对齐）：
| frozen/02 简短名 | CORE 点号名           | CORE 方向             | 处理     |
|------------------|-----------------------|-----------------------|----------|
| hasSku           | ProductSku.ofProduct  | ProductSku → Product  | 反转方向 |
| inCategory       | Product.inCategory    | Product → Category    | 同向改名 |
| contains         | Order.lines           | Order → OrderLine     | 同向改名 |
| forProduct       | OrderLine.ofProduct   | OrderLine → Product   | 同向改名 |
| forSku           | OrderLine.ofSku       | OrderLine → ProductSku| 同向改名 |
| ships            | Order.fulfilledBy     | Order → Shipment      | 反转方向 |
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from aos_api.ec_link_builder import build_link_rows
from aos_api.ecom_core_models import (
    BatchCommand,
    BatchResult,
    CORE_LINK_TYPES,
    EcomConsistencyError,
)
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")


# ═══════════════════════════════════════════════
# fakes（参考 test_ec_d1_ot_writer.py，保持独立不跨文件 import）
# ═══════════════════════════════════════════════


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，可配置返回值与异常。

    默认行为：objects_written / links_written = batch 内计数，checkpoint
    版本自增（模拟真实 store 的 CAS 推进）。
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


class NoStoreEngine:
    """没有 ecom_consistency_store 属性的 engine（骨架兼容场景）。"""


# ═══════════════════════════════════════════════
# row 工厂（OT 行格式，properties 包含全部 REQUIRED_PROPERTIES）
# ═══════════════════════════════════════════════


def _sku_row(*, source_pk: str = "s-1", product_id: str = "g-1", when: datetime = NOW) -> dict:
    """P03 ProductSku 行：productId 指向 Product。"""
    return {
        "ot": "ProductSku",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "productId": product_id,
            "status": "active",
            "barcode": "BC-001",
            "price": "99.00",
            "currency": "CNY",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def _product_row(*, source_pk: str = "g-1", category_id: str = "c-1", when: datetime = NOW) -> dict:
    """P02 Product 行：categoryId 多值字符串。"""
    return {
        "ot": "Product",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "shopId": "1",
            "title": "测试商品",
            "status": "active",
            "categoryId": category_id,
            "createdAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def _orderline_row(
    *,
    source_pk: str = "og-1",
    order_id: str = "o-1",
    goods_id: str = "g-1",
    sku_id: str = "s-1",
    when: datetime = NOW,
) -> dict:
    """P06 OrderLine 行：orderId/goodsId/skuId 指向多端。"""
    return {
        "ot": "OrderLine",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "orderId": order_id,
            "skuId": sku_id,
            "goodsId": goods_id,
            "quantity": 1,
            "unitPrice": "99.00",
            "lineAmount": "99.00",
            "currency": "CNY",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def _shipment_row(*, source_pk: str = "sh-1", order_id: str = "o-1", when: datetime = NOW) -> dict:
    """P07 Shipment 行：orderId 指向 Order。"""
    return {
        "ot": "Shipment",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "orderId": order_id,
            "status": "shipped",
            "carrier": "SF",
            "trackingNo": "SF123",
            "shippedAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def _make_pipeline(pid: str, target_ot: str) -> SimpleNamespace:
    """构造 pipeline mock：config.target_ot 优先。"""
    return SimpleNamespace(id=pid, config={"target_ot": target_ot})


def _links(rows: list[dict]) -> list[dict]:
    """从 build_link_rows 输出中提取 Link 行。"""
    return [r for r in rows if "link_type" in r]


def _sink(eng: FakeEngine, pipeline: SimpleNamespace, rows: list[dict]) -> dict:
    """调用真实 sink_to_ot（不 Mock）。"""
    return sink_to_ot(eng, TEST_SCOPE, pipeline, rows)


# ═══════════════════════════════════════════════
# 1. hasSku → ProductSku.ofProduct（方向反转）
# ═══════════════════════════════════════════════


def test_e2e_hasSku_lands_as_ProductSku_ofProduct_reversed() -> None:
    """hasSku: P03 ProductSku 行 → build_link_rows → sink_to_ot 真实落地。

    frozen/02: Product(g-1) → ProductSku(s-1)
    CORE:      ProductSku(s-1) → Product(g-1)  （方向反转）

    验证 CoreLinkRecord.validate_link 通过（link_type + 方向 + 同 scope），
    且 source/target external_id 使用 niushop:1:{source_pk} 命名空间。
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P03", "ProductSku")
    rows = build_link_rows([_sku_row(source_pk="s-1", product_id="g-1")], pipeline)

    result = _sink(eng, pipeline, rows)

    # sink_to_ot 不抛异常 = CoreLinkRecord.validate_link 通过
    assert len(store.calls) == 1
    command = store.calls[0]
    # 1 Object (ProductSku) + 1 Link (ProductSku.ofProduct)
    assert len(command.objects) == 1
    assert len(command.links) == 1
    link = command.links[0]
    assert link.link_type == "ProductSku.ofProduct"
    assert link.source_type == "ProductSku"
    assert link.target_type == "Product"
    # 反转后：source 是 ProductSku(s-1)，target 是 Product(g-1)
    assert link.source.external_id == "niushop:1:s-1"
    assert link.target.external_id == "niushop:1:g-1"
    # 与 CORE_LINK_TYPES 定义一致
    assert CORE_LINK_TYPES["ProductSku.ofProduct"] == ("ProductSku", "Product")
    assert result["objects_written"] == 1
    assert result["links_written"] == 1


# ═══════════════════════════════════════════════
# 2. inCategory → Product.inCategory（同向）
# ═══════════════════════════════════════════════


def test_e2e_inCategory_lands_as_Product_inCategory() -> None:
    """inCategory: P02 Product 行 → build_link_rows → sink_to_ot 真实落地。

    Product(g-1) → Category(c-1)，同向改名。
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P02", "Product")
    rows = build_link_rows([_product_row(source_pk="g-1", category_id="c-1")], pipeline)

    result = _sink(eng, pipeline, rows)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    assert len(command.links) == 2
    links = {link.link_type: link for link in command.links}
    category_link = links["Product.inCategory"]
    assert category_link.source_type == "Product"
    assert category_link.target_type == "Category"
    assert category_link.source.external_id == "niushop:1:g-1"
    assert category_link.target.external_id == "niushop:1:c-1"
    shop_link = links["Shop.sellsProduct"]
    assert shop_link.source_type == "Shop"
    assert shop_link.target_type == "Product"
    assert shop_link.source.external_id == "niushop:1:1"
    assert shop_link.target.external_id == "niushop:1:g-1"
    assert CORE_LINK_TYPES["Product.inCategory"] == ("Product", "Category")
    assert CORE_LINK_TYPES["Shop.sellsProduct"] == ("Shop", "Product")
    assert result["objects_written"] == 1
    assert result["links_written"] == 2


# ═══════════════════════════════════════════════
# 3. contains → Order.lines（同向）
# ═══════════════════════════════════════════════


def test_e2e_contains_lands_as_Order_lines() -> None:
    """contains: P06 OrderLine 行 → build_link_rows → sink_to_ot 真实落地。

    Order(o-1) → OrderLine(og-1)，同向改名。
    只验证 contains 这一条 Link（OrderLine 行还会构造 forProduct/forSku，
    但通过 sku_id="0" / goods_id="0" 跳过）。
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P06", "OrderLine")
    rows = build_link_rows(
        [_orderline_row(source_pk="og-1", order_id="o-1", goods_id="0", sku_id="0")],
        pipeline,
    )

    result = _sink(eng, pipeline, rows)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.links) == 1
    link = command.links[0]
    assert link.link_type == "Order.lines"
    assert link.source_type == "Order"
    assert link.target_type == "OrderLine"
    assert link.source.external_id == "niushop:1:o-1"
    assert link.target.external_id == "niushop:1:og-1"
    assert CORE_LINK_TYPES["Order.lines"] == ("Order", "OrderLine")
    assert result["links_written"] == 1


# ═══════════════════════════════════════════════
# 4. forProduct → OrderLine.ofProduct（同向）
# ═══════════════════════════════════════════════


def test_e2e_forProduct_lands_as_OrderLine_ofProduct() -> None:
    """forProduct: P06 OrderLine 行 → build_link_rows → sink_to_ot 真实落地。

    OrderLine(og-1) → Product(g-1)，同向改名。
    只验证 forProduct（通过 order_id="0" / sku_id="0" 跳过 contains/forSku）。
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P06", "OrderLine")
    rows = build_link_rows(
        [_orderline_row(source_pk="og-1", order_id="0", goods_id="g-1", sku_id="0")],
        pipeline,
    )

    result = _sink(eng, pipeline, rows)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.links) == 1
    link = command.links[0]
    assert link.link_type == "OrderLine.ofProduct"
    assert link.source_type == "OrderLine"
    assert link.target_type == "Product"
    assert link.source.external_id == "niushop:1:og-1"
    assert link.target.external_id == "niushop:1:g-1"
    assert CORE_LINK_TYPES["OrderLine.ofProduct"] == ("OrderLine", "Product")
    assert result["links_written"] == 1


# ═══════════════════════════════════════════════
# 5. forSku → OrderLine.ofSku（同向）
# ═══════════════════════════════════════════════


def test_e2e_forSku_lands_as_OrderLine_ofSku() -> None:
    """forSku: P06 OrderLine 行 → build_link_rows → sink_to_ot 真实落地。

    OrderLine(og-1) → ProductSku(s-1)，同向改名。
    只验证 forSku（通过 order_id="0" / goods_id="0" 跳过 contains/forProduct）。
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P06", "OrderLine")
    rows = build_link_rows(
        [_orderline_row(source_pk="og-1", order_id="0", goods_id="0", sku_id="s-1")],
        pipeline,
    )

    result = _sink(eng, pipeline, rows)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.links) == 1
    link = command.links[0]
    assert link.link_type == "OrderLine.ofSku"
    assert link.source_type == "OrderLine"
    assert link.target_type == "ProductSku"
    assert link.source.external_id == "niushop:1:og-1"
    assert link.target.external_id == "niushop:1:s-1"
    assert CORE_LINK_TYPES["OrderLine.ofSku"] == ("OrderLine", "ProductSku")
    assert result["links_written"] == 1


# ═══════════════════════════════════════════════
# 6. ships → Order.fulfilledBy（方向反转）
# ═══════════════════════════════════════════════


def test_e2e_ships_lands_as_Order_fulfilledBy_reversed() -> None:
    """ships: P07 Shipment 行 → build_link_rows → sink_to_ot 真实落地。

    frozen/02: Shipment(sh-1) → Order(o-1)
    CORE:      Order(o-1) → Shipment(sh-1)  （方向反转）
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P07", "Shipment")
    rows = build_link_rows([_shipment_row(source_pk="sh-1", order_id="o-1")], pipeline)

    result = _sink(eng, pipeline, rows)

    assert len(store.calls) == 1
    command = store.calls[0]
    assert len(command.objects) == 1
    assert len(command.links) == 1
    link = command.links[0]
    assert link.link_type == "Order.fulfilledBy"
    assert link.source_type == "Order"
    assert link.target_type == "Shipment"
    # 反转后：source 是 Order(o-1)，target 是 Shipment(sh-1)
    assert link.source.external_id == "niushop:1:o-1"
    assert link.target.external_id == "niushop:1:sh-1"
    assert CORE_LINK_TYPES["Order.fulfilledBy"] == ("Order", "Shipment")
    assert result["objects_written"] == 1
    assert result["links_written"] == 1


# ═══════════════════════════════════════════════
# 7. 混合 Object + Link 行同事务落地
# ═══════════════════════════════════════════════


def test_e2e_mixed_object_and_link_rows_landed_in_same_batch() -> None:
    """混合 Object + Link 行：build_link_rows 输出 [Object, Link]，
    sink_to_ot 正确拆分并在同一 BatchCommand 内落地。
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P03", "ProductSku")
    rows = build_link_rows([_sku_row(source_pk="s-1", product_id="g-1")], pipeline)

    # build_link_rows 输出 = 1 Object + 1 Link
    assert len(rows) == 2
    assert "ot" in rows[0]
    assert "link_type" in rows[1]

    result = _sink(eng, pipeline, rows)

    assert len(store.calls) == 1
    command = store.calls[0]
    # _normalize_rows 拆分：1 Object + 1 Link
    assert len(command.objects) == 1
    assert len(command.links) == 1
    assert command.objects[0].object_type == "ProductSku"
    assert command.links[0].link_type == "ProductSku.ofProduct"
    assert result["objects_written"] == 1
    assert result["links_written"] == 1


# ═══════════════════════════════════════════════
# 8. 悬挂 Link 拒绝（store 抛 DANGLING_LINK，sink_to_ot 不吞异常）
# ═══════════════════════════════════════════════


def test_e2e_dangling_link_propagates_store_rejection() -> None:
    """悬挂 Link：target 不存在时 ecom_consistency_store 拒绝（抛
    EcomConsistencyError("DANGLING_LINK")），sink_to_ot 不吞异常、向上传播。

    构造一条 target 不存在的 Link 行（target_source_pk 指向不存在的 Object），
    sink_to_ot 构造 CoreLinkRecord（通过 validate_link，因为 validate_link
    不检查 target 存在性，只检查 link_type + 方向 + 同 scope），调用
    store.apply_batch，store 检测 target 不存在并拒绝。

    悬挂检查在 ecom_consistency_store 内核，本测试用 FakeStore 模拟拒绝行为，
    验证 sink_to_ot 正确传播异常（不吞、不包装）。
    """
    dangling = EcomConsistencyError(
        "DANGLING_LINK",
        "link target does not exist in store",
    )
    store = FakeStore(raises=dangling)
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P03", "ProductSku")
    # 构造一条悬挂 Link 行：target 指向不存在的 Product
    dangling_link_row = {
        "link_type": "ProductSku.ofProduct",
        "source_type": "ProductSku",
        "source_pk": "s-1",
        "target_type": "Product",
        "target_source_pk": "g-nonexistent",
        "source_updated_at": NOW,
        "is_deleted": False,
        "properties": {},
    }

    with pytest.raises(EcomConsistencyError) as caught:
        _sink(eng, pipeline, [dangling_link_row])

    assert caught.value.code == "DANGLING_LINK"
    # sink_to_ot 确实调用了 store（异常来自 store，不是 sink_to_ot 自己抛的）
    assert len(store.calls) == 1
    command = store.calls[0]
    # Link 行真实经过 _build_link → CoreLinkRecord 构造 → validate_link 校验通过
    assert len(command.links) == 1
    assert command.links[0].link_type == "ProductSku.ofProduct"


# ═══════════════════════════════════════════════
# 9. 空 rows 透传返回零计数
# ═══════════════════════════════════════════════


def test_e2e_empty_rows_passthrough_returns_zero() -> None:
    """空 rows：sink_to_ot 返回零计数，不调用 store（BatchCommand validator
    拒绝空 batch）。
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("P03", "ProductSku")

    result = _sink(eng, pipeline, [])

    assert result == {"objects_written": 0, "links_written": 0}
    assert store.calls == []


# ═══════════════════════════════════════════════
# 10. 失败关闭：engine 无 store 时拒绝写入
# ═══════════════════════════════════════════════


def test_e2e_no_store_engine_fails_closed() -> None:
    """engine 未注入权威 store 时必须失败关闭。"""
    eng = NoStoreEngine()
    pipeline = _make_pipeline("P03", "ProductSku")
    rows = build_link_rows([_sku_row(source_pk="s-1", product_id="g-1")], pipeline)

    with pytest.raises(RuntimeError, match="authoritative layer without store"):
        sink_to_ot(eng, TEST_SCOPE, pipeline, rows)
