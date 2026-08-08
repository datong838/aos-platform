"""Phase 6 · Schemas 路由 (Schema 探索)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.logging_facade import get_logger
from aos_api.phase6_datasource_engine import get_engine
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.phase6-schemas")

router = APIRouter(
    prefix="/api/datasource",
    tags=["phase6-schemas"],
    dependencies=[Depends(require_principal)],
)


class PreviewRequest(BaseModel):
    schema_name: str = ""
    table_name: str = ""
    limit: int = 50


# D2.6: 通用 JDBC SSH 连接器类型集合（走 JdbcConnectorRuntime 真实发现）
_JDBC_SSH_CONNECTOR_TYPES: frozenset[str] = frozenset(
    {"jdbc-mysql-ssh", "jdbc-postgres-ssh"}
)

# 所有走真实 JDBC discover 的类型（仅 SSH 隧道通用连接器，niushop-mysql 已废弃）
_JDBC_REAL_DISCOVER_TYPES: frozenset[str] = _JDBC_SSH_CONNECTOR_TYPES | frozenset(
    {"jdbc-mysql"}
)


# ═══════════════════════════════════════════════
# D2.6: connector_type 解析 + Niushop demo schema
# ═══════════════════════════════════════════════


def _query_meta_source(source_id: str, scope: Any) -> dict[str, Any] | None:
    """查 meta_source 拿 props（含 connector_type）。

    简化实现：直接复用 ec_source_adapter._query_meta_source_props。
    返回 None 表示 source 不存在（走原 demo 行为）。
    """
    try:
        from aos_api.ec_source_adapter import _query_meta_source_props
        if scope is None:
            return None
        return _query_meta_source_props(source_id, scope)
    except Exception as exc:
        log.debug("meta_source query failed: %s", exc)
        return None


def _resolve_connector_type(source_id: str, scope: Any) -> str | None:
    """从 meta_source.props.connector_type 读取连接器类型。

    返回 None 表示未配置（走原 demo 行为，向后兼容）。
    """
    props = _query_meta_source(source_id, scope)
    if not props:
        return None
    ct = props.get("connector_type")
    return str(ct) if ct else None


# D2.6: Niushop 微商城专属 demo schema（8 张 ns_xxx 表 + 真实字段）
_NIUSHOP_DEMO_SCHEMA_NAME = "niushop_b2c_v5"

_NIUSHOP_DEMO_TABLES: list[dict[str, Any]] = [
    {
        "name": "ns_site", "row_count": 1,
        "columns": [
            {"name": "site_id", "datatype": "INT", "nullable": False, "primary_key": True},
            {"name": "site_name", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "create_time", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "modify_time", "datatype": "INT", "nullable": True, "primary_key": False},
        ],
    },
    {
        "name": "ns_goods_category", "row_count": 11,
        "columns": [
            {"name": "category_id", "datatype": "INT", "nullable": False, "primary_key": True},
            {"name": "category_name", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "parent_id", "datatype": "INT", "nullable": True, "primary_key": False},
        ],
    },
    {
        "name": "ns_goods", "row_count": 65,
        "columns": [
            {"name": "goods_id", "datatype": "INT", "nullable": False, "primary_key": True},
            {"name": "goods_name", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "category_id", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "sku_price", "datatype": "DECIMAL", "nullable": True, "primary_key": False},
            {"name": "evaluate", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "evaluate_haoping", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "create_time", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "modify_time", "datatype": "INT", "nullable": True, "primary_key": False},
        ],
    },
    {
        "name": "ns_goods_sku", "row_count": 73,
        "columns": [
            {"name": "sku_id", "datatype": "INT", "nullable": False, "primary_key": True},
            {"name": "goods_id", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "sku_name", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "price", "datatype": "DECIMAL", "nullable": True, "primary_key": False},
            {"name": "stock", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "alarm_stock", "datatype": "INT", "nullable": True, "primary_key": False},
        ],
    },
    {
        "name": "ns_member", "row_count": 53,
        "columns": [
            {"name": "member_id", "datatype": "INT", "nullable": False, "primary_key": True},
            {"name": "member_level", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "status", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "mobile", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "wx_openid", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "nickname", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "avatar", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "reg_address", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "last_login_ip", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "site_id", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "is_delete", "datatype": "INT", "nullable": True, "primary_key": False},
        ],
    },
    {
        "name": "ns_order", "row_count": 177,
        "columns": [
            {"name": "order_id", "datatype": "BIGINT", "nullable": False, "primary_key": True},
            {"name": "order_no", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "member_id", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "order_money", "datatype": "DECIMAL", "nullable": True, "primary_key": False},
            {"name": "pay_money", "datatype": "DECIMAL", "nullable": True, "primary_key": False},
            {"name": "order_status", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "pay_status", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "refund_status", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "is_lock", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "commission_risk_flag", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "create_time", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "modify_time", "datatype": "INT", "nullable": True, "primary_key": False},
        ],
    },
    {
        "name": "ns_order_goods", "row_count": 227,
        "columns": [
            {"name": "order_goods_id", "datatype": "BIGINT", "nullable": False, "primary_key": True},
            {"name": "order_id", "datatype": "BIGINT", "nullable": True, "primary_key": False},
            {"name": "goods_id", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "sku_id", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "goods_name", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "goods_money", "datatype": "DECIMAL", "nullable": True, "primary_key": False},
            {"name": "num", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "create_time", "datatype": "INT", "nullable": True, "primary_key": False},
        ],
    },
    {
        "name": "ns_express_delivery_package", "row_count": 19,
        "columns": [
            {"name": "id", "datatype": "BIGINT", "nullable": False, "primary_key": True},
            {"name": "order_id", "datatype": "BIGINT", "nullable": True, "primary_key": False},
            {"name": "express_company_id", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "express_no", "datatype": "VARCHAR", "nullable": True, "primary_key": False},
            {"name": "delivery_time", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "member_id", "datatype": "INT", "nullable": True, "primary_key": False},
            {"name": "site_id", "datatype": "INT", "nullable": True, "primary_key": False},
        ],
    },
]


def _niushop_demo_schemas(source_id: str) -> list[dict[str, Any]]:
    """Niushop 微商城专属 demo schema（8 张 ns_xxx 表）。"""
    return [
        {
            "id": f"sch-niushop-{source_id}",
            "source_id": source_id,
            "name": _NIUSHOP_DEMO_SCHEMA_NAME,
            "description": "Niushop 微商城数据库",
            "table_count": len(_NIUSHOP_DEMO_TABLES),
        }
    ]


def _niushop_demo_tables(source_id: str, schema_name: str) -> list[dict[str, Any]]:
    """Niushop demo tables（仅 schema_name=niushop_b2c_v5 时返回 8 张表）。"""
    if schema_name != _NIUSHOP_DEMO_SCHEMA_NAME:
        return []
    return [
        {
            "id": f"tbl-niushop-{schema_name}-{t['name']}",
            "source_id": source_id,
            "schema_name": schema_name,
            "name": t["name"],
            "row_count": t.get("row_count", 0),
            "size_bytes": 0,
            "description": f"Niushop {t['name']}",
        }
        for t in _NIUSHOP_DEMO_TABLES
    ]


def _niushop_demo_columns(source_id: str, schema_name: str, table_name: str) -> list[dict[str, Any]]:
    """Niushop demo columns。"""
    tbl = next((t for t in _NIUSHOP_DEMO_TABLES if t["name"] == table_name), None)
    if tbl is None:
        return []
    return [
        {
            "id": f"col-niushop-{table_name}-{c['name']}",
            "source_id": source_id,
            "schema_name": schema_name,
            "table_name": table_name,
            "name": c["name"],
            "datatype": c["datatype"],
            "nullable": c.get("nullable", True),
            "primary_key": c.get("primary_key", False),
            "default_value": "",
            "description": "",
        }
        for c in tbl["columns"]
    ]


def _jdbc_ssh_discover_schemas(source_id: str, props: dict[str, Any]) -> dict[str, Any]:
    """D2.6: jdbc-mysql-ssh / jdbc-postgres-ssh 真实 schema 发现（轻量版）。

    使用 JdbcConnectorRuntime.list_tables_only() 返回 schema + table 名列表，
    不拉字段详情（字段在用户点击表时按需加载）。
    """
    import time
    start = time.time()
    try:
        log.info("jdbc-ssh schema discover start: source=%s", source_id)
        with JdbcConnectorRuntime(props) as rt:
            tree = rt.list_tables_only()
        elapsed = time.time() - start
        log.info("jdbc-ssh schema discover done: source=%s, schemas=%d, elapsed=%.2fs",
                 source_id, len(tree), elapsed)
        items = [
            {
                "id": f"sch-jdbc-{source_id}-{s['name']}",
                "source_id": source_id,
                "name": s["name"],
                "description": f"JDBC schema {s['name']}",
                "table_count": len(s.get("tables", [])),
                "_tables": s.get("tables", []),
            }
            for s in tree
        ]
        return {"items": items, "count": len(items), "demo": False}
    except Exception as exc:
        elapsed = time.time() - start
        log.error("jdbc-ssh schema discover failed: source=%s, elapsed=%.2fs, error=%s",
                  source_id, elapsed, exc)
        raise HTTPException(
            status_code=502,
            detail=f"JDBC Schema 发现失败（耗时 {elapsed:.1f}s）：{str(exc)}",
        ) from exc


def _jdbc_ssh_list_columns(source_id: str, props: dict[str, Any], schema: str, table: str) -> list[dict[str, Any]]:
    """D2.6: 单表字段按需查询。

    使用 JdbcConnectorRuntime.list_columns_for_table() 直接查 information_schema。
    """
    import time
    start = time.time()
    try:
        with JdbcConnectorRuntime(props) as rt:
            cols = rt.list_columns_for_table(schema, table)
        elapsed = time.time() - start
        log.info("jdbc-ssh list_columns done: source=%s, table=%s.%s, columns=%d, elapsed=%.2fs",
                 source_id, schema, table, len(cols), elapsed)
        return cols
    except Exception as exc:
        elapsed = time.time() - start
        log.error("jdbc-ssh list_columns failed: source=%s, table=%s.%s, elapsed=%.2fs, error=%s",
                  source_id, schema, table, elapsed, exc)
        raise HTTPException(
            status_code=502,
            detail=f"JDBC 字段查询失败（耗时 {elapsed:.1f}s）：{str(exc)}",
        ) from exc


# ═══════════════════════════════════════════════
# 原 demo schema 函数（保留，向后兼容）
# ═══════════════════════════════════════════════


def _demo_schemas(source_id: str) -> list[dict[str, Any]]:
    """W3-C7 · demo schema tree when wave_ext source id is not in phase6 store."""
    return [
        {"id": f"sch-demo-public-{source_id}", "source_id": source_id, "name": "public",
         "description": "演示路径 · 默认 schema", "table_count": 3},
        {"id": f"sch-demo-analytics-{source_id}", "source_id": source_id, "name": "analytics",
         "description": "演示路径 · analytics", "table_count": 1},
    ]


def _demo_tables(source_id: str, schema_name: str) -> list[dict[str, Any]]:
    if schema_name == "analytics":
        names = ["events"]
    else:
        names = ["orders", "customers", "order_items"]
    return [
        {"id": f"tbl-demo-{schema_name}-{n}", "source_id": source_id, "schema_name": schema_name,
         "name": n, "row_count": 1000 + i * 200, "size_bytes": 256000, "description": f"demo {n}"}
        for i, n in enumerate(names)
    ]


def _demo_columns(source_id: str, schema_name: str, table_name: str) -> list[dict[str, Any]]:
    specs: dict[str, list[tuple[str, str, bool, bool]]] = {
        "orders": [("order_id", "BIGINT", False, True), ("customer_id", "BIGINT", False, False),
                   ("amount", "DECIMAL", True, False), ("status", "VARCHAR", True, False)],
        "customers": [("customer_id", "BIGINT", False, True), ("name", "VARCHAR", False, False),
                      ("email", "VARCHAR", True, False)],
        "order_items": [("item_id", "BIGINT", False, True), ("order_id", "BIGINT", False, False),
                        ("qty", "INT", False, False)],
        "events": [("event_id", "BIGINT", False, True), ("ts", "TIMESTAMP", False, False),
                   ("payload", "JSON", True, False)],
    }
    cols = specs.get(table_name, [("id", "BIGINT", False, True), ("name", "VARCHAR", True, False)])
    return [
        {"id": f"col-demo-{table_name}-{c}", "source_id": source_id, "schema_name": schema_name,
         "table_name": table_name, "name": c, "datatype": dt, "nullable": nullable,
         "primary_key": pk, "default_value": "", "description": ""}
        for c, dt, nullable, pk in cols
    ]


# ═══════════════════════════════════════════════
# 路由（修改：增加 connector_type 分支派发）
# ═══════════════════════════════════════════════


def _make_scope(principal: Principal) -> TenantScope:
    return TenantScope(org_id=principal.org_id, project_id=principal.project_id)


def _resolve_connector_type_with_scope(source_id: str, principal: Principal) -> str | None:
    """从 meta_source.props.connector_type 读取连接器类型（带 scope）。"""
    scope = _make_scope(principal)
    return _resolve_connector_type(source_id, scope)


def _query_meta_source_with_scope(source_id: str, principal: Principal) -> dict[str, Any]:
    """查 meta_source props（带 scope），返回空 dict 而非 None。"""
    scope = _make_scope(principal)
    result = _query_meta_source(source_id, scope)
    return result if result is not None else {}


@router.get("/sources/{source_id}/schemas")
async def list_schemas(source_id: str, principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        # 通用真实 discover：任何 jdbc 系连接器（jdbc-mysql-ssh/jdbc-postgres-ssh/niushop-mysql）
        # 都通过 JdbcConnectorRuntime 读 information_schema
        connector_type = _resolve_connector_type_with_scope(source_id, principal)
        if connector_type in _JDBC_REAL_DISCOVER_TYPES:
            props = _query_meta_source_with_scope(source_id, principal)
            return _jdbc_ssh_discover_schemas(source_id, props)
        # 非 JDBC 连接器且不在内存中，返回错误
        raise HTTPException(
            status_code=404,
            detail=f"无法获取数据源 {source_id} 的 Schema 信息：数据源未注册或连接器不支持",
        )
    items = eng.list_schemas(source_id)
    return {"items": [s.model_dump() for s in items], "count": len(items), "demo": False}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables")
async def list_tables(source_id: str, schema_name: str, principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        # 通用真实 discover：任何 jdbc 系连接器都走 JdbcConnectorRuntime
        connector_type = _resolve_connector_type_with_scope(source_id, principal)
        if connector_type in _JDBC_REAL_DISCOVER_TYPES:
            props = _query_meta_source_with_scope(source_id, principal)
            result = _jdbc_ssh_discover_schemas(source_id, props)
            items = [
                {
                    "id": f"tbl-jdbc-{schema_name}-{t['name']}",
                    "source_id": source_id,
                    "schema_name": schema_name,
                    "name": t["name"],
                    "row_count": 0,
                    "size_bytes": 0,
                    "description": f"JDBC table {t['name']}",
                    # D4 Phase C · C1: 透传 302 表分类标签
                    "classification": t.get("classification", "D"),
                    "comment": t.get("comment", ""),
                }
                for s in result["items"]
                if s["name"] == schema_name
                for t in s.get("_tables", [])
            ]
            return {"items": items, "count": len(items), "demo": False}
        # 非 JDBC 连接器且不在内存中，返回错误
        raise HTTPException(
            status_code=404,
            detail=f"无法获取 {schema_name} 的表列表：数据源未注册或连接器不支持",
        )
    items = eng.list_tables(source_id, schema_name)
    return {"items": [t.model_dump() for t in items], "count": len(items), "demo": False}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables/{table_name}/columns")
async def list_columns(source_id: str, schema_name: str, table_name: str, principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        # 通用真实 discover：任何 jdbc 系连接器都走 JdbcConnectorRuntime
        connector_type = _resolve_connector_type_with_scope(source_id, principal)
        if connector_type in _JDBC_REAL_DISCOVER_TYPES:
            props = _query_meta_source_with_scope(source_id, principal)
            cols = _jdbc_ssh_list_columns(source_id, props or {}, schema_name, table_name)
            items = [
                {
                    "id": f"col-jdbc-{table_name}-{c['name']}",
                    "source_id": source_id,
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "name": c["name"],
                    "datatype": c["datatype"],
                    "nullable": c.get("nullable", True),
                    "primary_key": c.get("primary_key", False),
                    "comment": c.get("comment", ""),
                    "default_value": "",
                    "description": c.get("comment", ""),
                }
                for c in cols
            ]
            return {"items": items, "count": len(items), "demo": False}
        # 非 JDBC 连接器且不在内存中，返回错误
        raise HTTPException(
            status_code=404,
            detail=f"无法获取 {schema_name}.{table_name} 的字段信息：数据源未注册或连接器不支持",
        )
    items = eng.list_columns(source_id, schema_name, table_name)
    return {"items": [c.model_dump() for c in items], "count": len(items), "demo": False}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables/{table_name}/foreign-keys")
async def list_foreign_keys(source_id: str, schema_name: str, table_name: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        items: list[dict[str, Any]] = []
        if table_name == "orders":
            items = [{
                "id": f"fk-demo-{table_name}", "source_id": source_id, "schema_name": schema_name,
                "table_name": table_name, "column_name": "customer_id",
                "ref_schema": schema_name, "ref_table": "customers", "ref_column": "customer_id",
            }]
        return {"items": items, "count": len(items), "demo": True}
    items = eng.list_foreign_keys(source_id, schema_name, table_name)
    return {"items": [fk.model_dump() for fk in items], "count": len(items), "demo": False}


@router.post("/sources/{source_id}/preview")
async def preview_data(source_id: str, req: PreviewRequest, principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    """获取数据源预览数据。

    优先使用 JdbcConnectorRuntime 直接查询数据库（JDBC 连接器），
    回退到内存存储（phase6 engine），最后返回明确错误而不是 demo 数据。
    """
    import time
    start = time.time()
    # 1. 尝试使用 JdbcConnectorRuntime 直接查数据库
    try:
        connector_type = _resolve_connector_type_with_scope(source_id, principal)
        if connector_type in _JDBC_REAL_DISCOVER_TYPES:
            props = _query_meta_source_with_scope(source_id, principal)
            if props:
                with JdbcConnectorRuntime(props) as rt:
                    # 获取字段列表
                    cols_data = rt.list_columns_for_table(req.schema_name, req.table_name)
                    columns = [c["name"] for c in cols_data]
                    # 读取数据行（使用 schema.table 格式）
                    rows = rt.read_rows(req.table_name, schema=req.schema_name, limit=req.limit)
                    elapsed = time.time() - start
                    log.info("jdbc-ssh preview done: source=%s, table=%s.%s, cols=%d, rows=%d, elapsed=%.2fs",
                             source_id, req.schema_name, req.table_name, len(columns), len(rows), elapsed)
                    if columns:
                        return {
                            "source_id": source_id,
                            "schema": req.schema_name,
                            "table": req.table_name,
                            "columns": columns,
                            "rows": rows,
                            "total": len(rows),
                            "returned": len(rows),
                            "demo": False,
                        }
    except Exception as exc:
        elapsed = time.time() - start
        log.warning("JDBC preview failed for %s.%s (elapsed=%.2fs): %s",
                     req.schema_name, req.table_name, elapsed, exc)
        # 继续尝试内存引擎

    # 2. 回退到内存引擎
    eng = get_engine()
    try:
        result = eng.preview_data(source_id, schema_name=req.schema_name, table_name=req.table_name, limit=req.limit)
        result["demo"] = False
        return result
    except KeyError:
        pass

    # 3. 所有方式都失败，返回错误（不再返回 demo 数据）
    raise HTTPException(
        status_code=404,
        detail=f"无法获取 {req.schema_name}.{req.table_name} 的预览数据：数据源未注册或连接失败",
    )


@router.get("/sources/{source_id}/capabilities")
async def get_source_capabilities(source_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        caps = eng.get_source_capabilities(source_id)
        return {"source_id": source_id, "capabilities": caps}
    except KeyError:
        raise HTTPException(404, f"Source {source_id} not found")
