"""D1-W2: CORE_LINK_TYPES + OrderLine.ofProduct 专项测试（FR-D1-C1）。

验证总控前置新增的 OrderLine.ofProduct 与全部 7 条 CORE_LINK_TYPES 的正确性、
CoreLinkRecord 校验逻辑（合法/非法 link_type、source/target 类型不匹配）、
CORE_OBJECT_TYPES 完整性、REQUIRED_PROPERTIES 完整性。

被测对象：aos_api/ecom_core_models.py（只读验证，不修改）。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aos_api.ecom_core_models import (
    CORE_LINK_TYPES,
    CORE_OBJECT_TYPES,
    REQUIRED_PROPERTIES,
    CoreLinkRecord,
)
from aos_api.public_contracts import ExternalIdentityKey

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)

# 7 条 CORE_LINK_TYPES 的期望 (link_type, source_type, target_type) 三元组
EXPECTED_LINKS: list[tuple[str, str, str]] = [
    ("Order.lines", "Order", "OrderLine"),
    ("OrderLine.ofSku", "OrderLine", "ProductSku"),
    ("OrderLine.ofProduct", "OrderLine", "Product"),
    ("ProductSku.ofProduct", "ProductSku", "Product"),
    ("Product.inCategory", "Product", "Category"),
    ("Shop.sellsProduct", "Shop", "Product"),
    ("Order.fulfilledBy", "Order", "Shipment"),
]


# ---------- helpers ----------


def _identity(external_id: str = "id-1") -> ExternalIdentityKey:
    """构造同 scope 的 ExternalIdentityKey（org/workspace/platform/shop 一致，
    避免触发 cross-tenant 校验）。"""
    return ExternalIdentityKey(
        org_id="dev-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id=external_id,
    )


def _make_link(
    link_type: str,
    source_type: str,
    target_type: str,
    *,
    source_id: str = "s-1",
    target_id: str = "t-1",
) -> CoreLinkRecord:
    """构造 CoreLinkRecord：source/target 同 scope，cursor_external_id 非空。"""
    return CoreLinkRecord(
        link_type=link_type,
        source_type=source_type,
        source=_identity(source_id),
        target_type=target_type,
        target=_identity(target_id),
        source_updated_at=NOW,
        cursor_external_id=f"link:{source_id}->{target_id}",
    )


# ---------- 1. CORE_LINK_TYPES 完整性 ----------


class TestCoreLinkTypesCompleteness:
    """CORE_LINK_TYPES 完整性：7 条 / 点号格式 / 二元组结构。"""

    def test_has_seven_link_types(self):
        assert len(CORE_LINK_TYPES) == 7

    def test_all_keys_are_dot_format(self):
        for key in CORE_LINK_TYPES:
            assert "." in key, f"link key must contain dot: {key}"

    def test_all_values_are_two_string_tuples(self):
        for key, value in CORE_LINK_TYPES.items():
            assert isinstance(value, tuple), f"{key} value must be tuple"
            assert len(value) == 2, f"{key} value must be 2-tuple"
            src, tgt = value
            assert isinstance(src, str) and src, f"{key} source_type must be non-empty str"
            assert isinstance(tgt, str) and tgt, f"{key} target_type must be non-empty str"

    def test_keys_match_expected_set(self):
        assert set(CORE_LINK_TYPES.keys()) == {item[0] for item in EXPECTED_LINKS}


# ---------- 2. OrderLine.ofProduct 专项 ----------


class TestOrderLineOfProduct:
    """OrderLine.ofProduct 新增项专项验证。"""

    def test_link_type_registered(self):
        assert "OrderLine.ofProduct" in CORE_LINK_TYPES

    def test_link_type_value(self):
        assert CORE_LINK_TYPES["OrderLine.ofProduct"] == ("OrderLine", "Product")

    def test_source_type_is_orderline(self):
        assert CORE_LINK_TYPES["OrderLine.ofProduct"][0] == "OrderLine"

    def test_target_type_is_product(self):
        assert CORE_LINK_TYPES["OrderLine.ofProduct"][1] == "Product"

    def test_valid_record_passes_validation(self):
        """合法 CoreLinkRecord(link_type=OrderLine.ofProduct, source=OrderLine, target=Product) 通过。"""
        record = _make_link("OrderLine.ofProduct", "OrderLine", "Product",
                            source_id="ol-1", target_id="p-1")
        assert record.link_type == "OrderLine.ofProduct"
        assert record.source_type == "OrderLine"
        assert record.target_type == "Product"
        assert record.source.external_id == "ol-1"
        assert record.target.external_id == "p-1"

    def test_unknown_link_type_raises_value_error(self):
        """link_type='未知' 不在 CORE_LINK_TYPES → ValueError。"""
        with pytest.raises(ValueError):
            _make_link("未知", "OrderLine", "Product")

    def test_source_type_mismatch_raises_value_error(self):
        """link_type=OrderLine.ofProduct 但 source_type=Shop（不匹配 OrderLine）→ ValueError。"""
        with pytest.raises(ValueError):
            _make_link("OrderLine.ofProduct", "Shop", "Product")

    def test_target_type_mismatch_raises_value_error(self):
        """link_type=OrderLine.ofProduct 但 target_type=Category（不匹配 Product）→ ValueError。"""
        with pytest.raises(ValueError):
            _make_link("OrderLine.ofProduct", "OrderLine", "Category")


# ---------- 3. 所有 7 条 Link 的 CoreLinkRecord 校验 ----------


class TestAllLinksValidation:
    """对每条 Link 类型：合法 record 通过 + source_type 不匹配抛 ValueError。"""

    @pytest.mark.parametrize(
        "link_type,source_type,target_type",
        EXPECTED_LINKS,
        ids=[item[0] for item in EXPECTED_LINKS],
    )
    def test_valid_record_for_each_link(self, link_type, source_type, target_type):
        """每条 Link 的合法 CoreLinkRecord 通过校验。"""
        record = _make_link(link_type, source_type, target_type)
        assert record.link_type == link_type
        assert record.source_type == source_type
        assert record.target_type == target_type

    @pytest.mark.parametrize(
        "link_type,source_type,target_type",
        EXPECTED_LINKS,
        ids=[item[0] for item in EXPECTED_LINKS],
    )
    def test_source_type_mismatch_raises(self, link_type, source_type, target_type):
        """每条 Link 构造 source_type 不匹配的 record → ValueError。

        选一个与合法 source_type 不同的 OT 作为错误 source_type。
        """
        wrong_source = "Shop" if source_type != "Shop" else "Product"
        with pytest.raises(ValueError):
            _make_link(link_type, wrong_source, target_type)

    @pytest.mark.parametrize(
        "link_type,source_type,target_type",
        EXPECTED_LINKS,
        ids=[item[0] for item in EXPECTED_LINKS],
    )
    def test_target_type_mismatch_raises(self, link_type, source_type, target_type):
        """每条 Link 构造 target_type 不匹配的 record → ValueError。"""
        wrong_target = "Category" if target_type != "Category" else "Shipment"
        with pytest.raises(ValueError):
            _make_link(link_type, source_type, wrong_target)


# ---------- 4. CORE_OBJECT_TYPES 完整性 ----------


class TestCoreObjectTypes:
    """CORE_OBJECT_TYPES 完整性：7 种 OT。"""

    EXPECTED_OTS = frozenset(
        {"Shop", "Product", "ProductSku", "Category", "Order", "OrderLine", "Shipment"}
    )

    def test_has_seven_object_types(self):
        assert len(CORE_OBJECT_TYPES) == 7

    def test_contains_all_expected_types(self):
        assert set(CORE_OBJECT_TYPES) == self.EXPECTED_OTS

    def test_orderline_is_registered(self):
        """OrderLine 必须注册（ofProduct 的 source_type 依赖）。"""
        assert "OrderLine" in CORE_OBJECT_TYPES

    def test_product_is_registered(self):
        """Product 必须注册（ofProduct 的 target_type 依赖）。"""
        assert "Product" in CORE_OBJECT_TYPES


# ---------- 5. REQUIRED_PROPERTIES 完整性 ----------


class TestRequiredProperties:
    """REQUIRED_PROPERTIES 完整性：7 种 OT 都有定义。"""

    def test_all_object_types_have_required_properties(self):
        for ot in CORE_OBJECT_TYPES:
            assert ot in REQUIRED_PROPERTIES, f"{ot} missing REQUIRED_PROPERTIES"

    def test_required_properties_keys_match_core_object_types(self):
        assert set(REQUIRED_PROPERTIES.keys()) == set(CORE_OBJECT_TYPES)

    def test_required_properties_are_nonempty_frozensets(self):
        for ot, props in REQUIRED_PROPERTIES.items():
            assert isinstance(props, frozenset), f"{ot} props must be frozenset"
            assert len(props) > 0, f"{ot} props must be non-empty"

    def test_orderline_required_properties_includes_sku_and_product_fields(self):
        """OrderLine 必须有 REQUIRED_PROPERTIES（ofProduct 的 source OT）。"""
        assert "OrderLine" in REQUIRED_PROPERTIES
        assert "skuId" in REQUIRED_PROPERTIES["OrderLine"]

    def test_product_required_properties_includes_required_fields(self):
        """Product 必须有 REQUIRED_PROPERTIES（ofProduct 的 target OT）。"""
        assert "Product" in REQUIRED_PROPERTIES
        assert "shopId" in REQUIRED_PROPERTIES["Product"]
