"""Phase 4 seed · Ontology Actions — 10 action (含参数定义)."""
from __future__ import annotations

from aos_api.ontology_action_engine import get_action_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase4_ontology_actions")


_ACTIONS_SPEC: list[dict] = [
    {
        "name": "promote_customer_tier",
        "display_name": "Promote Customer Tier",
        "description": "提升客户等级",
        "object_type_id": "",
        "params": [
            {"name": "customer_id", "datatype": "string"},
            {"name": "new_tier", "datatype": "string"},
        ],
        "body": "update customer set tier = new_tier",
        "category": "writeback",
    },
    {
        "name": "cancel_order",
        "display_name": "Cancel Order",
        "description": "取消订单",
        "params": [{"name": "order_id", "datatype": "string"}],
        "body": "update order set status='cancelled'",
        "category": "writeback",
    },
    {
        "name": "notify_shipment_delay",
        "display_name": "Notify Shipment Delay",
        "description": "通知运单延误",
        "params": [{"name": "shipment_id", "datatype": "string"}],
        "body": "send_email(customer, 'Your shipment is delayed')",
        "category": "notification",
    },
    {
        "name": "restock_product",
        "display_name": "Restock Product",
        "description": "补货",
        "params": [{"name": "product_id", "datatype": "string"}, {"name": "qty", "datatype": "int"}],
        "body": "update product set stock = stock + qty",
        "category": "writeback",
    },
    {
        "name": "send_invoice",
        "display_name": "Send Invoice",
        "description": "发送发票",
        "params": [{"name": "invoice_id", "datatype": "string"}],
        "body": "send_email(customer, invoice.pdf)",
        "category": "notification",
    },
    {
        "name": "assign_supplier",
        "display_name": "Assign Supplier",
        "description": "分配供应商",
        "params": [{"name": "product_id", "datatype": "string"}, {"name": "supplier_id", "datatype": "string"}],
        "body": "update product set supplier_id = supplier_id",
        "category": "writeback",
    },
    {
        "name": "archive_inactive_customers",
        "display_name": "Archive Inactive Customers",
        "description": "归档不活跃客户",
        "params": [],
        "body": "update customer set status='archived' where last_activity < now() - 365d",
        "category": "automation",
    },
    {
        "name": "recompute_rating",
        "display_name": "Recompute Rating",
        "description": "重算供应商评级",
        "params": [{"name": "supplier_id", "datatype": "string"}],
        "body": "select avg(score) from evaluations where supplier_id = supplier_id",
        "category": "automation",
    },
    {
        "name": "flag_overdue_invoices",
        "display_name": "Flag Overdue Invoices",
        "description": "标记逾期发票",
        "params": [],
        "body": "update invoice set status='overdue' where due_date < now() and status != 'paid'",
        "category": "automation",
    },
    {
        "name": "welcome_new_customer",
        "display_name": "Welcome New Customer",
        "description": "新客户欢迎邮件",
        "params": [{"name": "customer_id", "datatype": "string"}],
        "body": "send_email(customer, 'Welcome!')",
        "category": "notification",
    },
]


def seed_phase4_ontology_actions() -> int:
    """Seed 10 actions. Returns count."""
    eng = get_action_engine()
    count = 0
    for spec in _ACTIONS_SPEC:
        eng.create_action(**spec)
        count += 1
    log.info("seed_phase4_ontology_actions_done count=%s", count)
    return count
