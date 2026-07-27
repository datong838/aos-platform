"""Phase 4 seed · Ontology Types — 6 对象类型 + 属性 (≥60)."""
from __future__ import annotations

from aos_api.ontology_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase4_ontology_types")

# 6 对象类型定义：每个有 8-12 个属性
_TYPES_SPEC: list[dict] = [
    {
        "name": "customer",
        "display_name": "Customer",
        "plural_name": "Customers",
        "icon": "user",
        "description": "客户主数据",
        "backing_dataset": "ds/customers",
        "category": "business",
        "properties": [
            ("customer_id", "string", True, True, "客户唯一标识"),
            ("name", "string", False, False, "客户名称"),
            ("email", "string", True, False, "邮箱"),
            ("phone", "string", True, False, "电话"),
            ("region", "string", True, False, "区域"),
            ("tier", "string", True, False, "客户等级"),
            ("annual_revenue", "double", True, False, "年收入"),
            ("employee_count", "int", True, False, "员工数"),
            ("industry", "string", True, False, "行业"),
            ("status", "string", True, False, "状态"),
            ("created_date", "date", True, False, "创建日期"),
            ("last_activity", "datetime", True, False, "最后活动"),
        ],
    },
    {
        "name": "order",
        "display_name": "Order",
        "plural_name": "Orders",
        "icon": "cart",
        "description": "销售订单",
        "backing_dataset": "ds/orders",
        "category": "business",
        "properties": [
            ("order_id", "string", False, True, "订单号"),
            ("customer_id", "string", False, False, "客户ID"),
            ("order_date", "date", False, False, "下单日期"),
            ("ship_date", "date", True, False, "发货日期"),
            ("total_amount", "double", False, False, "总金额"),
            ("currency", "string", False, False, "币种"),
            ("status", "string", False, False, "订单状态"),
            ("channel", "string", True, False, "销售渠道"),
            ("discount", "double", True, False, "折扣"),
            ("payment_method", "string", True, False, "支付方式"),
        ],
    },
    {
        "name": "product",
        "display_name": "Product",
        "plural_name": "Products",
        "icon": "box",
        "description": "产品主数据",
        "backing_dataset": "ds/products",
        "category": "business",
        "properties": [
            ("product_id", "string", False, True, "产品ID"),
            ("sku", "string", False, False, "SKU"),
            ("name", "string", False, False, "产品名称"),
            ("category", "string", True, False, "类别"),
            ("price", "double", False, False, "单价"),
            ("cost", "double", True, False, "成本"),
            ("weight", "double", True, False, "重量"),
            ("in_stock", "boolean", False, False, "是否库存"),
            ("description", "string", True, False, "描述"),
            ("launch_date", "date", True, False, "上市日期"),
            ("supplier_id", "string", True, False, "供应商ID"),
        ],
    },
    {
        "name": "supplier",
        "display_name": "Supplier",
        "plural_name": "Suppliers",
        "icon": "truck",
        "description": "供应商",
        "backing_dataset": "ds/suppliers",
        "category": "business",
        "properties": [
            ("supplier_id", "string", False, True, "供应商ID"),
            ("name", "string", False, False, "名称"),
            ("country", "string", True, False, "国家"),
            ("contact_email", "string", True, False, "联系邮箱"),
            ("contact_phone", "string", True, False, "联系电话"),
            ("rating", "double", True, False, "评级"),
            ("lead_time_days", "int", True, False, "交付周期(天)"),
            ("payment_terms", "string", True, False, "付款条款"),
            ("active", "boolean", False, False, "是否活跃"),
        ],
    },
    {
        "name": "shipment",
        "display_name": "Shipment",
        "plural_name": "Shipments",
        "icon": "ship",
        "description": "物流运单",
        "backing_dataset": "ds/shipments",
        "category": "business",
        "properties": [
            ("shipment_id", "string", False, True, "运单号"),
            ("order_id", "string", False, False, "关联订单"),
            ("origin", "string", False, False, "发货地"),
            ("destination", "string", False, False, "目的地"),
            ("carrier", "string", True, False, "承运商"),
            ("tracking_no", "string", True, False, "追踪号"),
            ("weight_kg", "double", True, False, "重量(kg)"),
            ("shipped_at", "datetime", True, False, "发货时间"),
            ("delivered_at", "datetime", True, False, "送达时间"),
            ("status", "string", False, False, "运单状态"),
            ("cost", "double", True, False, "运费"),
        ],
    },
    {
        "name": "invoice",
        "display_name": "Invoice",
        "plural_name": "Invoices",
        "icon": "receipt",
        "description": "发票",
        "backing_dataset": "ds/invoices",
        "category": "business",
        "properties": [
            ("invoice_id", "string", False, True, "发票号"),
            ("order_id", "string", False, False, "关联订单"),
            ("customer_id", "string", False, False, "客户ID"),
            ("issue_date", "date", False, False, "开票日期"),
            ("due_date", "date", False, False, "到期日期"),
            ("amount", "double", False, False, "金额"),
            ("tax", "double", True, False, "税额"),
            ("status", "string", False, False, "状态"),
            ("paid_date", "date", True, False, "支付日期"),
        ],
    },
]


def seed_phase4_ontology_types() -> int:
    """Seed 6 object types with properties (≥60 total). Returns property count."""
    eng = get_engine()
    type_count = 0
    prop_count = 0
    for spec in _TYPES_SPEC:
        props = spec.pop("properties")
        ot = eng.create_object_type(**spec)
        type_count += 1
        for name, dt, nullable, is_pk, desc in props:
            eng.add_property(
                ot.id,
                name=name,
                display_name=name.replace("_", " ").title(),
                datatype=dt,
                nullable=nullable,
                is_primary_key=is_pk,
                is_display_name=is_pk,
                description=desc,
            )
            prop_count += 1
    log.info(
        "seed_phase4_ontology_types_done types=%s properties=%s",
        type_count,
        prop_count,
    )
    return prop_count
