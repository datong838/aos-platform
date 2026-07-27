"""Phase 4 seed · Ontology Links — 10 link type + 10 link instance (合计 20)."""
from __future__ import annotations

from aos_api.ontology_engine import get_engine
from aos_api.ontology_link_engine import get_link_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase4_ontology_links")


_LINK_TYPES_SPEC: list[dict] = [
    {"name": "customer_places_order", "display_name": "Customer Places Order", "cardinality": "one_to_many", "description": "客户下单关系"},
    {"name": "order_contains_product", "display_name": "Order Contains Product", "cardinality": "many_to_many", "description": "订单包含产品"},
    {"name": "supplier_supplies_product", "display_name": "Supplier Supplies Product", "cardinality": "many_to_many", "description": "供应商供货"},
    {"name": "order_generates_shipment", "display_name": "Order Generates Shipment", "cardinality": "one_to_many", "description": "订单生成运单"},
    {"name": "order_generates_invoice", "display_name": "Order Generates Invoice", "cardinality": "one_to_one", "description": "订单生成发票"},
    {"name": "customer_receives_invoice", "display_name": "Customer Receives Invoice", "cardinality": "one_to_many", "description": "客户收发票"},
    {"name": "shipment_delivers_product", "display_name": "Shipment Delivers Product", "cardinality": "many_to_many", "description": "运单交付产品"},
    {"name": "product_has_supplier", "display_name": "Product Has Supplier", "cardinality": "many_to_one", "description": "产品的供应商"},
    {"name": "customer_buys_product", "display_name": "Customer Buys Product", "cardinality": "many_to_many", "description": "客户购买产品"},
    {"name": "shipment_to_customer", "display_name": "Shipment To Customer", "cardinality": "many_to_one", "description": "运单送达客户"},
]


def seed_phase4_ontology_links() -> int:
    """Seed 10 link types + 10 link instances. Returns total."""
    oe = get_engine()
    le = get_link_engine()
    types_by_name = {ot.name: ot for ot in oe.list_object_types(page=1, page_size=200)[0]}
    objs_by_type = {}
    for ot in types_by_name.values():
        objs, _ = oe.list_objects(object_type_id=ot.id, page=1, page_size=50)
        objs_by_type[ot.name] = objs

    # 创建 10 link types
    lt_ids: list[str] = []
    for spec in _LINK_TYPES_SPEC:
        # 简单：source/target 留空（也可基于名称推断）
        lt = le.create_link_type(**spec)
        lt_ids.append(lt.id)

    # 创建 10 link instances，引用第一批 objects
    instances_data = [
        ("customer_places_order", "customer", "order"),
        ("order_contains_product", "order", "product"),
        ("supplier_supplies_product", "supplier", "product"),
        ("order_generates_shipment", "order", "shipment"),
        ("order_generates_invoice", "order", "invoice"),
        ("customer_receives_invoice", "customer", "invoice"),
        ("shipment_delivers_product", "shipment", "product"),
        ("product_has_supplier", "product", "supplier"),
        ("customer_buys_product", "customer", "product"),
        ("shipment_to_customer", "shipment", "customer"),
    ]
    inst_count = 0
    for i, (lt_name, src_t, tgt_t) in enumerate(instances_data):
        lt = next((l for l in le.list_link_types() if l.name == lt_name), None)
        if not lt:
            continue
        src_objs = objs_by_type.get(src_t, [])
        tgt_objs = objs_by_type.get(tgt_t, [])
        if not src_objs or not tgt_objs:
            continue
        src = src_objs[i % len(src_objs)]
        tgt = tgt_objs[i % len(tgt_objs)]
        le.create_link(
            link_type_id=lt.id,
            source_object_id=src.id,
            target_object_id=tgt.id,
            properties={"weight": 1.0 + i * 0.1},
        )
        inst_count += 1

    total = len(lt_ids) + inst_count
    log.info("seed_phase4_ontology_links_done types=%s instances=%s total=%s", len(lt_ids), inst_count, total)
    return total
