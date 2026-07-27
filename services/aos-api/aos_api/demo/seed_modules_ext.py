"""Seed modules — Phase 1 Workshop backend.

Ensures 9 domain modules exist (order/risk/customer/asset/analysis/workorder/inventory/finance/marketing).
Idempotent: delete by org_id then insert. Uses dev-{domain}-{n} id format.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_store import ensure_module_schema

log = get_logger("aos-api.demo.seed_modules_ext")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

# 9 domain modules mapped to existing module ids where possible
_ORDER_COMPONENTS = {
    "root": {
        "type": "page-layout",
        "config": {"padding": 24, "gap": 16},
        "children": ["page-header", "grid-stats", "filter-bar", "table-orders", "bottom-row"],
    },
    "page-header": {
        "type": "page-header",
        "config": {"title": "订单管理", "subtitle": "Order Management System"},
    },
    "grid-stats": {
        "type": "horizontal-grid",
        "config": {"cols": 4, "gap": 12},
        "children": ["stat-total", "stat-pending", "stat-completed", "stat-revenue"],
    },
    "stat-total": {
        "type": "stat-card",
        "config": {
            "title": "总订单",
            "objectType": "Order",
            "color": "blue",
        },
    },
    "stat-pending": {
        "type": "stat-card",
        "config": {
            "title": "待处理",
            "objectType": "Order",
            "color": "amber",
            "filter": {"field": "status", "op": "in", "value": ["pending", "confirmed"]},
        },
    },
    "stat-completed": {
        "type": "stat-card",
        "config": {
            "title": "已签收",
            "objectType": "Order",
            "color": "green",
            "filter": {"field": "status", "op": "eq", "value": "delivered"},
        },
    },
    "stat-revenue": {
        "type": "stat-card",
        "config": {
            "title": "总收入",
            "objectType": "Order",
            "color": "indigo",
            "metric": "sum",
            "field": "total_amount",
        },
    },
    "filter-bar": {
        "type": "filter-bar",
        "config": {
            "objectType": "Order",
            "tabs": [
                {"key": "all", "label": "全部"},
                {"key": "pending", "label": "待付款"},
                {"key": "paid", "label": "已付款"},
                {"key": "shipped", "label": "已发货"},
                {"key": "signed", "label": "已签收"},
                {"key": "cancelled", "label": "已取消"},
                {"key": "refunded", "label": "已退款"},
            ],
        },
    },
    "table-orders": {
        "type": "object-table",
        "config": {
            "objectType": "Order",
            "title": "订单列表 — all_orders",
            "columns": [
                {"key": "order_no", "label": "订单号"},
                {"key": "customer_name", "label": "客户"},
                {"key": "order_date", "label": "日期"},
                {"key": "total_amount", "label": "金额", "format": "currency"},
                {"key": "status", "label": "状态", "type": "status"},
            ],
        },
    },
    "bottom-row": {
        "type": "horizontal-grid",
        "config": {"cols": 2, "gap": 12},
        "children": ["chart-trend", "detail-order"],
    },
    "chart-trend": {
        "type": "trend-chart",
        "config": {
            "title": "订单趋势图",
            "objectType": "Order",
            "dateField": "order_date",
        },
    },
    "detail-order": {
        "type": "detail-drawer",
        "config": {
            "objectType": "Order",
            "title": "订单详情 — selected_order",
            "sections": [
                {
                    "title": "基本信息",
                    "fields": [
                        {"key": "order_no", "label": "订单号"},
                        {"key": "customer_name", "label": "客户"},
                        {"key": "total_amount", "label": "金额"},
                        {"key": "status", "label": "状态"},
                        {"key": "order_date", "label": "下单时间"},
                    ],
                },
            ],
        },
    },
}

_MODULES = [
    {
        "id": "dev-module-order",
        "name": "订单管理",
        "status": "published",
        "description": "订单全生命周期管理：创建、支付、发货、签收",
        "objectType": "Order",
        "markings": ["public"],
        "entryPath": "/workshop/order",
        "widgets": ["stats", "table", "chart", "details"],
        "components": _ORDER_COMPONENTS,
        "buddyBound": True,
        "category": "订单",
        "theme": "light",
    },
    {
        "id": "dev-module-risk",
        "name": "风控中心",
        "status": "published",
        "description": "风险事件监控、预警、处置工单",
        "objectType": "RiskEvent",
        "markings": ["restricted"],
        "entryPath": "/workshop/risk",
        "widgets": ["kpi", "table", "chart"],
        "buddyBound": True,
        "category": "风控",
        "theme": "dark",
    },
    {
        "id": "dev-module-customer",
        "name": "客户管理",
        "status": "published",
        "description": "客户档案、画像、跟进记录",
        "objectType": "Customer",
        "markings": ["public"],
        "entryPath": "/workshop/customer",
        "widgets": ["table", "details", "chart"],
        "buddyBound": True,
        "category": "客户",
        "theme": "light",
    },
    {
        "id": "dev-module-asset",
        "name": "资产管理",
        "status": "published",
        "description": "固定资产登记、折旧、盘点",
        "objectType": "Asset",
        "markings": ["public"],
        "entryPath": "/workshop/asset",
        "widgets": ["table", "stats", "chart"],
        "buddyBound": False,
        "category": "资产",
        "theme": "light",
    },
    {
        "id": "dev-module-analysis",
        "name": "数据分析",
        "status": "published",
        "description": "多维分析、报表、可视化看板",
        "objectType": "Analysis",
        "markings": ["public"],
        "entryPath": "/workshop/analysis",
        "widgets": ["chart", "table", "filters"],
        "buddyBound": False,
        "category": "分析",
        "theme": "light",
    },
    {
        "id": "dev-module-workorder",
        "name": "工单系统",
        "status": "published",
        "description": "工单创建、分派、处理、关闭",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/workorder",
        "widgets": ["table", "filters", "details"],
        "buddyBound": True,
        "category": "工单",
        "theme": "light",
    },
    {
        "id": "dev-module-inventory",
        "name": "库存管理",
        "status": "published",
        "description": "商品库存、出入库、盘点",
        "objectType": "Inventory",
        "markings": ["public"],
        "entryPath": "/workshop/inventory",
        "widgets": ["table", "stats", "chart"],
        "buddyBound": False,
        "category": "库存",
        "theme": "light",
    },
    {
        "id": "dev-module-finance",
        "name": "财务管理",
        "status": "published",
        "description": "应收应付、对账、财务报表",
        "objectType": "Finance",
        "markings": ["restricted"],
        "entryPath": "/workshop/finance",
        "widgets": ["stats", "table", "chart"],
        "buddyBound": False,
        "category": "财务",
        "theme": "dark",
    },
    {
        "id": "dev-module-marketing",
        "name": "营销活动",
        "status": "published",
        "description": "营销活动管理、效果分析、ROI",
        "objectType": "Campaign",
        "markings": ["public"],
        "entryPath": "/workshop/marketing",
        "widgets": ["stats", "chart", "table"],
        "buddyBound": False,
        "category": "营销",
        "theme": "light",
    },
]


def seed_modules() -> int:
    """Idempotently seed 9 domain modules. Returns count."""
    ensure_module_schema()
    with connect() as conn:
        # Delete our dev-module-* seeds then re-insert (idempotent)
        conn.execute(
            "DELETE FROM meta_module WHERE id LIKE 'dev-module-%%' AND org_id=%s",
            (_DEFAULT_ORG,),
        )
        for s in _MODULES:
            conn.execute(
                """
                INSERT INTO meta_module (
                    id, name, status, description, object_type, markings,
                    entry_path, widgets, components, buddy_bound, org_id, project_id,
                    category, theme
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, status=EXCLUDED.status,
                    description=EXCLUDED.description, object_type=EXCLUDED.object_type,
                    markings=EXCLUDED.markings, entry_path=EXCLUDED.entry_path,
                    widgets=EXCLUDED.widgets, components=EXCLUDED.components,
                    buddy_bound=EXCLUDED.buddy_bound,
                    category=EXCLUDED.category, theme=EXCLUDED.theme
                """,
                (
                    s["id"],
                    s["name"],
                    s["status"],
                    s["description"],
                    s["objectType"],
                    json.dumps(s["markings"]),
                    s["entryPath"],
                    json.dumps(s["widgets"]),
                    json.dumps(s.get("components", {})),
                    s["buddyBound"],
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                    s["category"],
                    s["theme"],
                ),
            )
        conn.commit()
    log.info("seed_modules_done count=%s", len(_MODULES))
    return len(_MODULES)
