"""Module Meta Store on PostgreSQL (T08) — replaces in-memory mock for modules.

TWA.5: rows scoped by org_id + project_id (configured instances are per-workspace).
"""
from __future__ import annotations

import json
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import resolve_module_pk, stable_module_pk
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.module_store")

def _iso(v: object) -> str | None:
    """Convert a datetime (or None) to ISO 8601 string for JSON-safe output."""
    if v is None:
        return None
    # datetime objects have .isoformat(); fall back to str for unexpected types
    iso = getattr(v, "isoformat", None)
    return iso() if callable(iso) else str(v)

_ORDER_COMPONENTS = {
    "root": {
        "type": "page-layout",
        "config": {"padding": 24, "gap": 16},
        "children": ["page-header", "stat-row", "filter-bar", "order-table", "detail-drawer", "trend-chart"],
    },
    "page-header": {
        "type": "page-header",
        "config": {
            "title": "订单管理",
            "subtitle": "Order Management System",
            "icon": "orders",
            "actions": [
                {"type": "button", "label": "新建订单", "variant": "primary"},
                {"type": "button", "label": "导出", "variant": "secondary"},
            ],
        },
    },
    "stat-row": {
        "type": "horizontal-grid",
        "config": {"cols": 4, "gap": 16},
        "children": ["stat-total", "stat-pending", "stat-shipped", "stat-revenue"],
    },
    "stat-total": {
        "type": "stat-card",
        "config": {
            "title": "总订单数",
            "value": "1,284",
            "trend": "+12.5%",
            "trendUp": True,
            "icon": "package",
            "color": "blue",
            "objectType": "Order",
            "metric": "count",
        },
    },
    "stat-pending": {
        "type": "stat-card",
        "config": {
            "title": "待处理",
            "value": "86",
            "trend": "-3.2%",
            "trendUp": False,
            "icon": "clock",
            "color": "amber",
            "objectType": "Order",
            "metric": "count",
            "filter": {"field": "status", "op": "in", "value": ["pending", "paid"]},
        },
    },
    "stat-shipped": {
        "type": "stat-card",
        "config": {
            "title": "已发货",
            "value": "1,052",
            "trend": "+8.1%",
            "trendUp": True,
            "icon": "truck",
            "color": "green",
            "objectType": "Order",
            "metric": "count",
            "filter": {"field": "status", "op": "eq", "value": "shipped"},
        },
    },
    "stat-revenue": {
        "type": "stat-card",
        "config": {
            "title": "营收总额",
            "value": "¥3,867,420",
            "trend": "+15.3%",
            "trendUp": True,
            "icon": "dollar",
            "color": "indigo",
            "objectType": "Order",
            "metric": "sum",
            "field": "total_amount",
            "filter": {"field": "status", "op": "in", "value": ["shipped", "delivered"]},
        },
    },
    "filter-bar": {
        "type": "filter-bar",
        "config": {
            "objectType": "Order",
            "tabs": [
                {"key": "all", "label": "全部", "count": 1284},
                {"key": "pending", "label": "待付款", "count": 86},
                {"key": "paid", "label": "已付款", "count": 240},
                {"key": "shipped", "label": "已发货", "count": 1052},
                {"key": "delivered", "label": "已签收", "count": 128},
                {"key": "cancelled", "label": "已取消", "count": 18},
                {"key": "refunded", "label": "已退款", "count": 6},
            ],
            "search": {"placeholder": "搜索订单号、客户名、商品..."},
            "filters": [
                {"type": "date-range", "label": "下单时间", "field": "order_date"},
                {"type": "select", "label": "状态", "field": "status", "options": ["全部", "pending", "paid", "shipped", "delivered", "cancelled", "refunded"]},
            ],
        },
    },
    "order-table": {
        "type": "object-table",
        "config": {
            "objectType": "Order",
            "columns": [
                {"key": "order_no", "label": "订单号", "width": 160, "mono": True, "sortable": True},
                {"key": "customer_name", "label": "客户", "width": 140, "subKey": "customer_id"},
                {"key": "order_date", "label": "下单日期", "width": 120, "sortable": True},
                {"key": "total_amount", "label": "金额", "width": 120, "align": "right", "format": "currency"},
                {"key": "status", "label": "状态", "width": 100, "type": "status"},
                {"key": "tracking_no", "label": "物流单号", "width": 140, "mono": True},
            ],
            "rowActions": [
                {"key": "view", "label": "查看", "variant": "link"},
                {"key": "edit", "label": "编辑", "variant": "link"},
                {"key": "ship", "label": "发货", "variant": "primary"},
                {"key": "cancel", "label": "取消", "variant": "danger"},
            ],
            "pagination": {"pageSize": 20},
            "selectable": True,
            "bordered": False,
        },
    },
    "detail-drawer": {
        "type": "detail-drawer",
        "config": {
            "objectType": "Order",
            "width": 480,
            "sections": [
                {
                    "title": "基本信息",
                    "fields": [
                        {"key": "order_no", "label": "订单号", "mono": True},
                        {"key": "order_date", "label": "下单日期"},
                        {"key": "status", "label": "订单状态", "type": "status"},
                        {"key": "total_amount", "label": "金额", "format": "currency"},
                    ],
                },
                {
                    "title": "收货信息",
                    "fields": [
                        {"key": "customer_name", "label": "客户姓名"},
                        {"key": "customer_id", "label": "客户ID", "mono": True},
                        {"key": "shipping_address", "label": "收货地址"},
                        {"key": "tracking_no", "label": "物流单号", "mono": True},
                    ],
                },
                {
                    "title": "商品明细",
                    "type": "table",
                    "objectKey": "items",
                    "columns": [
                        {"key": "product", "label": "商品"},
                        {"key": "qty", "label": "数量"},
                        {"key": "price", "label": "单价", "format": "currency"},
                    ],
                },
            ],
            "actions": [
                {"key": "edit", "label": "编辑订单", "variant": "secondary"},
                {"key": "ship", "label": "确认发货", "variant": "primary"},
            ],
        },
    },
    "trend-chart": {
        "type": "trend-chart",
        "config": {
            "title": "近 7 天订单趋势",
            "objectType": "Order",
            "dateField": "order_date",
            "days": 7,
            "endDate": "2026-07-22",
        },
    },
}


_SEED = [
    {
        "id": "mod-ops-inbox",
        "name": "运营台 Inbox",
        "status": "published",
        "description": "Demo-aligned Module for Workshop Inbox",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/inbox",
        "widgets": ["table", "filters", "selection"],
        "buddyBound": True,
        "category": "风控",
        "theme": "light",
    },
    {
        "id": "mod-canvas-draft",
        "name": "画布草稿",
        "status": "draft",
        "description": "Canvas editor placeholder",
        "objectType": "WorkOrder",
        "markings": ["restricted"],
        "entryPath": "/workshop/canvas",
        "widgets": ["canvas"],
        "buddyBound": False,
        "category": "分析",
        "theme": "dark",
    },
    {
        "id": "mod-buddy-assist",
        "name": "Buddy 助手",
        "status": "published",
        "description": "AIP Assist Module",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/buddy",
        "widgets": ["chat"],
        "buddyBound": True,
        "category": "AI 助手",
        "theme": "light",
    },
    {
        "id": "mod-order-management",
        "name": "订单管理系统",
        "status": "published",
        "description": "统计卡片 · 订单列表 · 趋势图 · 详情面板",
        "objectType": "Order",
        "markings": ["public"],
        "entryPath": "/workshop/orders",
        "widgets": ["stats", "table", "chart", "details"],
        "components": _ORDER_COMPONENTS,
        "buddyBound": True,
        "category": "运营",
        "theme": "dark",
    },
    {
        "id": "mod-object-explorer",
        "name": "对象探索",
        "status": "published",
        "description": "对象实例 · 属性筛选 · 图表探索 · Actions",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/graph",
        "widgets": ["graph", "table", "filters"],
        "buddyBound": False,
        "category": "本体前端",
        "theme": "light",
    },
    {
        "id": "mod-cop-dashboard",
        "name": "态势大屏",
        "status": "published",
        "description": "供应链网络 · 实时监控 · KPI 仪表盘",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/cop",
        "widgets": ["kpi", "map", "events"],
        "buddyBound": False,
        "category": "态势感知",
        "theme": "dark",
    },
    {
        "id": "mod-analytics-report",
        "name": "分析报表",
        "status": "published",
        "description": "多维分析 · 数据钻取 · 可视化报表",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/analytics",
        "widgets": ["chart", "table", "filters"],
        "buddyBound": False,
        "category": "分析",
        "theme": "light",
    },
    {
        "id": "mod-workflow-automation",
        "name": "流程自动化",
        "status": "draft",
        "description": "工作流编排 · 自动化任务 · 触发器管理",
        "objectType": "WorkOrder",
        "markings": ["restricted"],
        "entryPath": "/workshop/events",
        "widgets": ["workflow", "triggers"],
        "buddyBound": False,
        "category": "智能嵌入",
        "theme": "light",
    },
    {
        "id": "mod-api-integration",
        "name": "API 集成",
        "status": "published",
        "description": "外部系统连接 · API 调用 · 数据同步",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/module-interface",
        "widgets": ["api", "connections"],
        "buddyBound": False,
        "category": "系统集成",
        "theme": "light",
    },
]


def ensure_module_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_module (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'draft',
              description TEXT NOT NULL DEFAULT '',
              object_type TEXT NOT NULL DEFAULT 'WorkOrder',
              markings JSONB NOT NULL DEFAULT '["public"]'::jsonb,
              entry_path TEXT NOT NULL DEFAULT '/workshop/inbox',
              widgets JSONB NOT NULL DEFAULT '["table"]'::jsonb,
              buddy_bound BOOLEAN NOT NULL DEFAULT TRUE,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              category TEXT NOT NULL DEFAULT '运营',
              theme TEXT NOT NULL DEFAULT 'light',
              last_opened_at TIMESTAMPTZ,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            ALTER TABLE meta_module
              ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT 'dev-org'
            """
        )
        conn.execute(
            """
            ALTER TABLE meta_module
              ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'dev-project'
            """
        )
        conn.execute(
            """
            ALTER TABLE meta_module
              ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT '运营'
            """
        )
        conn.execute(
            """
            ALTER TABLE meta_module
              ADD COLUMN IF NOT EXISTS theme TEXT NOT NULL DEFAULT 'light'
            """
        )
        conn.execute(
            """
            ALTER TABLE meta_module
              ADD COLUMN IF NOT EXISTS last_opened_at TIMESTAMPTZ
            """
        )
        conn.execute(
            """
            ALTER TABLE meta_module
              ADD COLUMN IF NOT EXISTS components JSONB NOT NULL DEFAULT '{}'::jsonb
            """
        )
        conn.execute(
            """
            UPDATE meta_module
               SET org_id = COALESCE(NULLIF(org_id, ''), 'dev-org'),
                   project_id = COALESCE(NULLIF(project_id, ''), 'dev-project'),
                   category = COALESCE(NULLIF(category, ''), '运营'),
                   theme = COALESCE(NULLIF(theme, ''), 'light')
            """
        )
        conn.commit()


def _row_to_mod(r: dict[str, Any]) -> dict[str, Any]:
    comps = r.get("components") or {}
    if isinstance(comps, str):
        try:
            comps = json.loads(comps)
        except Exception:
            comps = {}
    return {
        "id": r["id"],
        "name": r["name"],
        "status": r["status"],
        "description": r["description"] or "",
        "objectType": r["object_type"],
        "markings": r["markings"] if isinstance(r["markings"], list) else list(r["markings"] or []),
        "entryPath": r["entry_path"],
        "widgets": r["widgets"] if isinstance(r["widgets"], list) else list(r["widgets"] or []),
        "components": comps if isinstance(comps, dict) else {},
        "buddyBound": bool(r["buddy_bound"]),
        "category": r.get("category") or "运营",
        "theme": r.get("theme") or "light",
        "lastOpenedAt": _iso(r.get("last_opened_at")),
        "orgId": r["org_id"],
        "projectId": r["project_id"],
        "createdAt": _iso(r.get("created_at")),
    }


def seed_modules_if_empty(scope: TenantScope) -> None:
    ensure_module_schema()
    with connect(scope) as conn:
        for s in _SEED:
            conn.execute(
                """
                INSERT INTO meta_module (
                  id, name, status, description, object_type, markings,
                  entry_path, widgets, components, buddy_bound, org_id, project_id,
                  category, theme, module_pk, module_id
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                  name=EXCLUDED.name, status=EXCLUDED.status,
                  description=EXCLUDED.description, object_type=EXCLUDED.object_type,
                  markings=EXCLUDED.markings, entry_path=EXCLUDED.entry_path,
                  widgets=EXCLUDED.widgets, components=EXCLUDED.components,
                  buddy_bound=EXCLUDED.buddy_bound,
                  category=EXCLUDED.category, theme=EXCLUDED.theme,
                  module_pk=COALESCE(meta_module.module_pk, EXCLUDED.module_pk),
                  module_id=COALESCE(meta_module.module_id, EXCLUDED.module_id)
                WHERE meta_module.org_id=EXCLUDED.org_id
                  AND meta_module.project_id=EXCLUDED.project_id
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
                    json.dumps(s.get("components") or {}),
                    s["buddyBound"],
                    *scope.key,
                    s.get("category") or "运营",
                    s.get("theme") or "light",
                    stable_module_pk(scope.org_id, scope.project_id, s["id"]),
                    s["id"],
                ),
            )
        conn.commit()
    log.info(
        "module_store_seed_ensured org=%s project=%s",
        *scope.key,
    )


def list_modules(scope: TenantScope) -> list[dict[str, Any]]:
    ensure_module_schema()
    with connect(scope) as conn:
        rows = conn.execute(
            """
            SELECT * FROM meta_module
             WHERE org_id=%s AND project_id=%s
             ORDER BY id
            """,
            scope.key,
        ).fetchall()
    log.info(
        "module_list org=%s project=%s count=%s",
        *scope.key,
        len(rows),
    )
    return [_row_to_mod(r) for r in rows]


def get_module(
    scope: TenantScope, module_id: str
) -> dict[str, Any] | None:
    ensure_module_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            row = None
        else:
            row = conn.execute(
                """
                SELECT * FROM meta_module
                 WHERE module_pk=%s AND org_id=%s AND project_id=%s
                """,
                (module_pk, *scope.key),
            ).fetchone()
    if not row:
        log.warning(
            "module_miss id=%s org=%s project=%s",
            module_id,
            *scope.key,
        )
        return None
    return _row_to_mod(row)


def create_module(
    scope: TenantScope, payload: dict[str, Any]
) -> dict[str, Any]:
    ensure_module_schema()
    import uuid

    mid = payload.get("id") or f"mod-{uuid.uuid4().hex[:8]}"
    item = {
        "id": mid,
        "name": payload.get("name") or mid,
        "status": payload.get("status") or "draft",
        "description": payload.get("description") or "",
        "objectType": payload.get("objectType") or "WorkOrder",
        "markings": payload.get("markings") or ["public"],
        "entryPath": payload.get("entryPath") or "/workshop/inbox",
        "widgets": payload.get("widgets") or ["table", "filters"],
        "components": payload.get("components") or {},
        "buddyBound": bool(payload.get("buddyBound", True)),
        "category": payload.get("category") or "运营",
        "theme": payload.get("theme") or "light",
        "orgId": scope.org_id,
        "projectId": scope.project_id,
    }
    with connect(scope) as conn:
        conn.execute(
            """
            INSERT INTO meta_module (
              id, name, status, description, object_type, markings,
              entry_path, widgets, components, buddy_bound, org_id, project_id,
              category, theme, module_pk, module_id
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                item["id"],
                item["name"],
                item["status"],
                item["description"],
                item["objectType"],
                json.dumps(item["markings"]),
                item["entryPath"],
                json.dumps(item["widgets"]),
                json.dumps(item["components"]),
                item["buddyBound"],
                *scope.key,
                item["category"],
                item["theme"],
                stable_module_pk(scope.org_id, scope.project_id, mid),
                mid,
            ),
        )
        conn.commit()
    log.info(
        "module_create id=%s org=%s project=%s",
        mid,
        *scope.key,
    )
    return item


def update_module(
    scope: TenantScope,
    module_id: str,
    patch: dict[str, Any],
) -> dict[str, Any] | None:
    cur = get_module(scope, module_id)
    if not cur:
        return None
    mapping = {
        "name": "name",
        "description": "description",
        "objectType": "objectType",
        "markings": "markings",
        "entryPath": "entryPath",
        "widgets": "widgets",
        "components": "components",
        "buddyBound": "buddyBound",
        "status": "status",
        "category": "category",
        "theme": "theme",
    }
    for k, v in patch.items():
        if k in mapping and v is not None:
            cur[mapping[k]] = v
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            return None
        conn.execute(
            """
            UPDATE meta_module SET
              name=%s, status=%s, description=%s, object_type=%s,
              markings=%s::jsonb, entry_path=%s, widgets=%s::jsonb,
              components=%s::jsonb, buddy_bound=%s,
              category=%s, theme=%s
            WHERE module_pk=%s AND org_id=%s AND project_id=%s
            """,
            (
                cur["name"],
                cur["status"],
                cur["description"],
                cur["objectType"],
                json.dumps(cur["markings"]),
                cur["entryPath"],
                json.dumps(cur["widgets"]),
                json.dumps(cur["components"]),
                cur["buddyBound"],
                cur.get("category") or "运营",
                cur.get("theme") or "light",
                module_pk,
                *scope.key,
            ),
        )
        conn.commit()
    return get_module(scope, module_id)


def touch_module(
    scope: TenantScope, module_id: str
) -> bool:
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            return False
        rows = conn.execute(
            """
            UPDATE meta_module
               SET last_opened_at = NOW()
             WHERE module_pk=%s AND org_id=%s AND project_id=%s
            """,
            (module_pk, *scope.key),
        ).rowcount
    if rows == 0:
        log.warning("module_touch_not_found id=%s", module_id)
        return False
    log.info("module_touch id=%s org=%s project=%s", module_id, *scope.key)
    return True


def publish_module(
    scope: TenantScope, module_id: str
) -> dict[str, Any] | None:
    mod = update_module(
        scope, module_id, {"status": "published"}
    )
    if not mod:
        return None
    return {
        **mod,
        "publish": {
            "adapter": "apollo-lite",
            "channel": "dev",
            "status": "ACCEPTED",
        },
    }


def module_runtime(
    scope: TenantScope, module_id: str
) -> dict[str, Any] | None:
    mod = get_module(scope, module_id)
    if not mod:
        return None
    return {
        "moduleId": module_id,
        "layout": {
            "widgets": mod.get("widgets") or ["table", "filters", "selection"],
            "components": mod.get("components") or {},
        },
        "variables": {"selectionLimit": 10},
        "events": [{"id": "refresh", "type": "query"}],
        "objectType": mod["objectType"],
        "entryPath": mod.get("entryPath") or "/workshop/inbox",
        "buddyBound": bool(mod.get("buddyBound", False)),
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "store": "postgres",
    }
