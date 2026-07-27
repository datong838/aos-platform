"""Seed module canvas configs + widget instances — Phase 1 Workshop backend.

9 modules, each with a canvas config + 10+ widget instances.
Idempotent: delete by org_id then insert.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.canvas_config import ensure_schema as ensure_config_schema
from aos_api.widget_instances import ensure_schema as ensure_instance_schema

log = get_logger("aos-api.demo.seed_module_widgets")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_MODULE_IDS = [
    "dev-module-order",
    "dev-module-risk",
    "dev-module-customer",
    "dev-module-asset",
    "dev-module-analysis",
    "dev-module-workorder",
    "dev-module-inventory",
    "dev-module-finance",
    "dev-module-marketing",
]


def _build_widget_instances(module_id: str) -> list[dict]:
    """Generate 10+ widget instances for a module."""
    base = [
        ("w-page-header", "page-header", "页面标题", 0),
        ("w-stat-card", "stat-card", "总览统计", 1),
        ("w-object-table", "object-table", "数据表格", 2),
        ("w-filter-bar", "filter-bar", "筛选栏", 3),
        ("w-trend-chart", "trend-chart", "趋势图", 4),
        ("w-detail-drawer", "detail-drawer", "详情抽屉", 5),
        ("w-horizontal-grid", "horizontal-grid", "栅格布局", 6),
        ("w-pie-chart", "pie-chart", "占比图", 7),
        ("w-bar-chart", "bar-chart", "柱状图", 8),
        ("w-kpi-board", "kpi-board", "KPI 看板", 9),
        ("w-timeline", "timeline", "时间线", 10),
        ("w-workflow", "workflow", "工作流", 11),
    ]
    items = []
    for i, (wid, wtype, title, order) in enumerate(base):
        items.append(
            {
                "id": f"wi-{module_id}-{i+1}",
                "module_id": module_id,
                "widget_id": wid,
                "type": wtype,
                "title": title,
                "config": {"moduleId": module_id},
                "layout": {"x": (i % 4) * 6, "y": (i // 4) * 8, "w": 6, "h": 8},
                "sort_order": order,
            }
        )
    return items


def _build_canvas_config(module_id: str) -> dict:
    """Generate a canvas config for a module."""
    if module_id == "dev-module-order":
        return _build_order_canvas_config()

    instances = _build_widget_instances(module_id)
    children = [wi["id"] for wi in instances]
    return {
        "layout": {
            "type": "page-layout",
            "config": {"padding": 24, "gap": 16},
            "children": children,
        },
        "components": {wi["id"]: {"type": wi["type"], "config": wi["config"]} for wi in instances},
    }


def _build_order_canvas_config() -> dict:
    """Order Management Dashboard — aligns with workshop-app-order.html visual."""
    components = {
        "root": {
            "type": "page-layout",
            "config": {"padding": 24, "gap": 16},
            "children": ["grid-stats", "filter-order", "table-orders", "chart-trend"],
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
                "value": "1,847",
                "sublabel": "本周新增 142",
                "color": "blue",
                "trend": "+12.3%",
                "trendUp": True,
            },
        },
        "stat-pending": {
            "type": "stat-card",
            "config": {
                "title": "待处理",
                "value": "23",
                "sublabel": "需关注",
                "color": "amber",
            },
        },
        "stat-completed": {
            "type": "stat-card",
            "config": {
                "title": "已完成",
                "value": "1,782",
                "sublabel": "完成率 96.5%",
                "color": "green",
            },
        },
        "stat-revenue": {
            "type": "stat-card",
            "config": {
                "title": "总收入",
                "value": "¥486K",
                "sublabel": "本周 +12.3%",
                "color": "indigo",
                "trend": "+12.3%",
                "trendUp": True,
            },
        },
        "filter-order": {
            "type": "filter-bar",
            "config": {
                "objectType": "Order",
                "tabs": [
                    {"key": "all", "label": "全部", "count": 1847},
                    {"key": "pending", "label": "待处理", "count": 23},
                    {"key": "shipped", "label": "已发货", "count": 42},
                    {"key": "delivered", "label": "已签收", "count": 1782},
                ],
            },
        },
        "table-orders": {
            "type": "object-table",
            "config": {
                "objectType": "Order",
                "title": "订单列表",
                "columns": [
                    {"key": "order_no", "label": "订单号"},
                    {"key": "customer_name", "label": "客户"},
                    {"key": "order_date", "label": "日期"},
                    {"key": "total_amount", "label": "金额"},
                    {"key": "status", "label": "状态"},
                ],
            },
        },
        "chart-trend": {
            "type": "trend-chart",
            "config": {
                "title": "近 7 天订单趋势",
                "objectType": "Order",
            },
        },
    }
    return {
        "layout": components["root"],
        "components": components,
    }


def seed_module_widgets() -> int:
    """Idempotently seed canvas configs + widget instances for 9 modules.
    Returns total instance count."""
    ensure_config_schema()
    ensure_instance_schema()
    total = 0
    with connect() as conn:
        # Clear existing
        conn.execute(
            "DELETE FROM module_canvas_config WHERE org_id=%s AND project_id=%s",
            (_DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        conn.execute(
            "DELETE FROM module_widget_instance WHERE org_id=%s AND project_id=%s",
            (_DEFAULT_ORG, _DEFAULT_PROJECT),
        )

        for module_id in _MODULE_IDS:
            # Canvas config
            cfg = _build_canvas_config(module_id)
            conn.execute(
                """
                INSERT INTO module_canvas_config (
                    module_id, layout, components, version, org_id, project_id
                ) VALUES (%s, %s::jsonb, %s::jsonb, 1, %s, %s)
                """,
                (
                    module_id,
                    json.dumps(cfg["layout"]),
                    json.dumps(cfg["components"]),
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                ),
            )

            # Widget instances
            instances = _build_widget_instances(module_id)
            for wi in instances:
                conn.execute(
                    """
                    INSERT INTO module_widget_instance (
                        id, module_id, widget_id, type, title, config, layout,
                        sort_order, org_id, project_id
                    ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                    """,
                    (
                        wi["id"],
                        wi["module_id"],
                        wi["widget_id"],
                        wi["type"],
                        wi["title"],
                        json.dumps(wi["config"]),
                        json.dumps(wi["layout"]),
                        wi["sort_order"],
                        _DEFAULT_ORG,
                        _DEFAULT_PROJECT,
                    ),
                )
            total += len(instances)

        conn.commit()
    log.info("seed_module_widgets_done modules=%s instances=%s", len(_MODULE_IDS), total)
    return total
