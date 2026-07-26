"""Seed widgets catalog — Phase 1 Workshop backend.

16 widget catalog entries: 12 builtin + 3 marketplace + 1 custom.
Idempotent: delete by org_id then insert.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.widget_catalog import ensure_schema

log = get_logger("aos-api.demo.seed_widgets")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_WIDGETS = [
    # 12 builtin widgets
    {"id": "w-page-header", "name": "PageHeader", "nameZh": "页头", "type": "page-header", "source": "builtin", "category": "layout", "icon": "header", "description": "页面标题栏"},
    {"id": "w-stat-card", "name": "StatCard", "nameZh": "统计卡片", "type": "stat-card", "source": "builtin", "category": "data", "icon": "card", "description": "统计指标卡片"},
    {"id": "w-object-table", "name": "ObjectTable", "nameZh": "对象表格", "type": "object-table", "source": "builtin", "category": "data", "icon": "table", "description": "对象数据表格"},
    {"id": "w-filter-bar", "name": "FilterBar", "nameZh": "筛选栏", "type": "filter-bar", "source": "builtin", "category": "control", "icon": "filter", "description": "筛选条件栏"},
    {"id": "w-trend-chart", "name": "TrendChart", "nameZh": "趋势图", "type": "trend-chart", "source": "builtin", "category": "chart", "icon": "chart", "description": "趋势折线图"},
    {"id": "w-detail-drawer", "name": "DetailDrawer", "nameZh": "详情抽屉", "type": "detail-drawer", "source": "builtin", "category": "layout", "icon": "drawer", "description": "侧滑详情面板"},
    {"id": "w-horizontal-grid", "name": "HorizontalGrid", "nameZh": "横向栅格", "type": "horizontal-grid", "source": "builtin", "category": "layout", "icon": "grid", "description": "横向栅格布局"},
    {"id": "w-pie-chart", "name": "PieChart", "nameZh": "饼图", "type": "pie-chart", "source": "builtin", "category": "chart", "icon": "pie", "description": "饼图/占比图"},
    {"id": "w-bar-chart", "name": "BarChart", "nameZh": "柱状图", "type": "bar-chart", "source": "builtin", "category": "chart", "icon": "bar", "description": "柱状图"},
    {"id": "w-kpi-board", "name": "KpiBoard", "nameZh": "KPI 看板", "type": "kpi-board", "source": "builtin", "category": "data", "icon": "kpi", "description": "KPI 指标看板"},
    {"id": "w-timeline", "name": "Timeline", "nameZh": "时间线", "type": "timeline", "source": "builtin", "category": "data", "icon": "timeline", "description": "时间线组件"},
    {"id": "w-workflow", "name": "Workflow", "nameZh": "工作流", "type": "workflow", "source": "builtin", "category": "process", "icon": "workflow", "description": "工作流编排"},
    # 3 marketplace widgets
    {"id": "w-mp-gantt", "name": "GanttChart", "nameZh": "甘特图", "type": "gantt-chart", "source": "marketplace", "category": "chart", "icon": "gantt", "description": "项目甘特图（市场插件）", "version": "2.1.0"},
    {"id": "w-mp-map", "name": "MapView", "nameZh": "地图", "type": "map-view", "source": "marketplace", "category": "visual", "icon": "map", "description": "地理地图视图（市场插件）", "version": "1.5.0"},
    {"id": "w-mp-kanban", "name": "Kanban", "nameZh": "看板", "type": "kanban", "source": "marketplace", "category": "process", "icon": "kanban", "description": "看板视图（市场插件）", "version": "3.0.2"},
    # 1 custom widget
    {"id": "w-custom-order-tag", "name": "OrderTag", "nameZh": "订单标签", "type": "order-tag", "source": "custom", "category": "data", "icon": "tag", "description": "自定义订单状态标签", "version": "0.1.0"},
]


def seed_widgets() -> int:
    """Idempotently seed 16 widget catalog entries. Returns count."""
    ensure_schema()
    with connect() as conn:
        conn.execute(
            "DELETE FROM widget_catalog WHERE org_id=%s AND project_id=%s",
            (_DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        for w in _WIDGETS:
            conn.execute(
                """
                INSERT INTO widget_catalog (
                    id, name, name_zh, type, source, category, icon, description,
                    config_schema, version, installed, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, name_zh=EXCLUDED.name_zh,
                    type=EXCLUDED.type, source=EXCLUDED.source,
                    category=EXCLUDED.category, icon=EXCLUDED.icon,
                    description=EXCLUDED.description, version=EXCLUDED.version
                """,
                (
                    w["id"],
                    w["name"],
                    w["nameZh"],
                    w["type"],
                    w["source"],
                    w["category"],
                    w["icon"],
                    w["description"],
                    json.dumps({}),
                    w.get("version", "1.0.0"),
                    True,
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                ),
            )
        conn.commit()
    log.info("seed_widgets_done count=%s", len(_WIDGETS))
    return len(_WIDGETS)
