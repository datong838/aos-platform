"""D1-W1: Niushop SourceAdapter — 从只读源读取行流。

骨架阶段：回退到合成 fixture（sample_input 透传），与原 ec_live_executor 行为等价。
Worker W1 实现：切换到 Niushop 只读 MySQL 源（meta_source 查连接配置 + READ ONLY 事务）。

FR-D1-4 关键约束：
1. 从 node.config 取 source_id → 查 meta_source 拿连接配置（不接 config 直传连接串）
2. 用只读事务（SET SESSION TRANSACTION READ ONLY，复用 qyh_discover_readonly.py 模式）
3. 按 node.config.cursor 做增量游标读取（复合游标 (watermark, primary_key) 二元组）
4. 连接级 LIMIT 100 行采样上限（初装不受限，增量受游标控制）
5. 单查询超时 30s，隧道断开时 fail-closed
6. 软删行（is_delete=1）不入 OT，进 DLQ 计数
7. 0 时间转 null（Unix 秒 → UTC）
"""

from __future__ import annotations

import json
from typing import Any

import pymysql

from aos_api.db import connect
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.ec-source")

# 只读事务 SQL（复用 qyh_discover_readonly.py 模式）
READ_ONLY_SQL: str = "SET SESSION TRANSACTION READ ONLY"

# 连接级 LIMIT 100 行采样上限（初装不受限）
SAMPLE_LIMIT: int = 100

# 单查询超时 30s
QUERY_TIMEOUT_SECONDS: int = 30

# PII 排除（frozen/02 §P08 隐私最小化 + D4 §P12 ns_pay 支付凭证脱敏）
# 按表名 → 字段集合：SourceAdapter 层显式 drop，不进入 row 流
_PII_DROP_FIELDS_BY_TABLE: dict[str, frozenset[str]] = {
    # D1.5: ns_member 的 8 个 PII 字段
    "ns_member": frozenset(
        {
            "mobile", "wx_openid", "nickname", "avatar",
            "reg_address", "last_login_ip", "password", "pay_password",
        }
    ),
    # D4: ns_pay 的 6 个支付凭证/敏感字段（DDL niushop_b2c_v5.sql L11956-11971）
    # 保留：id/site_id/weapp_id/out_trade_no/pay_type/pay_money/pay_status/pay_time/create_time/relate_id/event
    "ns_pay": frozenset(
        {
            "mch_id",       # wechat 商户号
            "trade_no",     # 第三方交易单号
            "pay_no",       # 支付账号
            "pay_body",     # 支付主体（可能含敏感信息）
            "pay_detail",   # 支付详情（可能含敏感信息）
            "pay_voucher",  # 支付票据
        }
    ),
}

# D2.6: 通用 JDBC SSH 连接器类型集合（走 JdbcConnectorRuntime 分支）
# 其他类型（niushop-mysql / mysql / 缺失）走原 pymysql 直连分支（向后兼容）
_JDBC_SSH_CONNECTOR_TYPES: frozenset[str] = frozenset(
    {"jdbc-mysql-ssh", "jdbc-postgres-ssh"}
)

# 软删行计数（module-level dict，key=(pipeline_id, node_id)），供 G6 DLQ 取用
_SOFT_DELETE_COUNTS: dict[tuple[str, str], int] = {}


def get_soft_delete_count(pipeline_id: str, node_id: str) -> int:
    """获取指定 (pipeline_id, node_id) 的软删行计数，供 G6 DLQ 取用。"""
    return _SOFT_DELETE_COUNTS.get((pipeline_id, node_id), 0)


def reset_soft_delete_counts() -> None:
    """清空软删计数（测试用）。"""
    _SOFT_DELETE_COUNTS.clear()


def fetch_source_rows(
    *,
    pipeline: Any,
    nodes: list[Any],
    node_id: str | None,
    sample_input: Any,
    scope: Any = None,
) -> list[dict[str, Any]]:
    """从源读取行流。

    行为分支：
    1. 向后兼容：node_id 为 None / 找不到 source 节点 / node.config 无 source_id
       → 回退 sample_input 透传（与原 ec_live_executor 骨架行为等价）
    2. D2.6 通用 JDBC SSH：meta_source.connector_type ∈ {jdbc-mysql-ssh, jdbc-postgres-ssh}
       → 走 JdbcConnectorRuntime（SSH 隧道 + JDBC 连接）
    3. Niushop 只读源：其他 connector_type（niushop-mysql / mysql / 缺失）
       → 保留 pymysql 直连分支（向后兼容）
    """
    # 尝试找 source 节点并取其 config
    node_config = _resolve_source_node_config(nodes, node_id)

    # 无 source_id → 回退 sample_input 透传（骨架行为，向后兼容）
    if node_config is None or not node_config.get("source_id"):
        return _fallback_sample_input(sample_input)

    # 查 meta_source 拿连接配置（所有分支都需要）
    source_id = node_config["source_id"]
    props = _query_meta_source_props(source_id, scope)

    # D2.6 分支派发：connector_type 决定走哪个运行时
    connector_type = props.get("connector_type", "")
    if connector_type in _JDBC_SSH_CONNECTOR_TYPES:
        # 通用 JDBC SSH 分支
        return _fetch_from_jdbc_ssh(
            pipeline=pipeline,
            node_id=node_id or "",
            node_config=node_config,
            props=props,
        )

    # 保留原 Niushop pymysql 直连分支（向后兼容）
    return _fetch_from_niushop(
        pipeline=pipeline,
        node_id=node_id or "",
        node_config=node_config,
        props=props,
    )


def _resolve_source_node_config(
    nodes: list[Any], node_id: str | None
) -> dict[str, Any] | None:
    """从 nodes 中找到 node_id 对应的节点并返回其 config。"""
    if node_id is None or not nodes:
        return None
    for node in nodes:
        if getattr(node, "id", None) == node_id:
            return getattr(node, "config", None) or {}
    return None


def _fallback_sample_input(sample_input: Any) -> list[dict[str, Any]]:
    """骨架行为：从 sample_input 构造行流（与原 ec_live_executor 行为等价）。"""
    if isinstance(sample_input, dict):
        return [sample_input]
    elif isinstance(sample_input, list):
        return [r for r in sample_input if isinstance(r, dict)]
    return []


def _fetch_from_niushop(
    *,
    pipeline: Any,
    node_id: str,
    node_config: dict[str, Any],
    props: dict[str, Any],
) -> list[dict[str, Any]]:
    """从 Niushop 只读源按游标增量读取（原 pymysql 直连分支，向后兼容）。

    D2.6: 连接配置由 fetch_source_rows 统一查询后传入（不再内部查 meta_source）
    """
    table = node_config["table"]
    pk = node_config["pk"]
    watermark_col = node_config.get("watermark_col", "modify_time")
    site_filter = node_config.get("site_filter", 1)
    cursor = node_config.get("cursor")
    initial = node_config.get("initial", False)

    # pymysql 只读连接（隧道断开时 fail-closed：异常向上抛出）
    conn = pymysql.connect(
        host=props["host"],
        port=int(props["port"]),
        user=props["user"],
        password=props["password"],
        database=props["database"],
        connect_timeout=QUERY_TIMEOUT_SECONDS,
        read_timeout=QUERY_TIMEOUT_SECONDS,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        cur = conn.cursor()
        # 只读事务（fail-closed：异常向上抛出）
        cur.execute(READ_ONLY_SQL)

        # 构造 SQL（初装/增量 + LIMIT 控制）并查询
        sql, params = _build_query_sql(
            table=table,
            pk=pk,
            watermark_col=watermark_col,
            site_filter=site_filter,
            cursor=cursor,
            initial=initial,
        )
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    # 数据清洗：软删行过滤 + PII 排除 + 0 时间转 null
    pipeline_id = getattr(pipeline, "id", "") or ""
    cleaned_rows = _clean_rows(rows, pipeline_id=pipeline_id, node_id=node_id, table=table)

    return cleaned_rows


def _fetch_from_jdbc_ssh(
    *,
    pipeline: Any,
    node_id: str,
    node_config: dict[str, Any],
    props: dict[str, Any],
) -> list[dict[str, Any]]:
    """D2.6: 从通用 JDBC SSH 连接器读取行流。

    使用 JdbcConnectorRuntime（SSH 隧道 + JDBC 连接），不绑 niushop。
    支持任意 MySQL / PostgreSQL 数据源，适合本地开发与生产。

    数据清洗与 niushop 分支一致（软删行过滤 + PII 排除 + 0 时间转 null）。
    """
    table = node_config["table"]
    pk = node_config.get("pk", "id")
    cursor = node_config.get("cursor")

    # 通用 JDBC SSH 运行时（with 上下文管理 SSH 隧道 + JDBC 连接生命周期）
    with JdbcConnectorRuntime(props) as rt:
        # 游标增量：如有 cursor 则 (watermark, pk) 二元组；初装传 None
        if cursor:
            watermark = cursor.get("watermark")
            primary_key = cursor.get("primary_key", pk)
            read_cursor: tuple[Any, str] | None = (watermark, primary_key)
        else:
            read_cursor = None
        rows = rt.read_rows(table, cursor=read_cursor)

    # 数据清洗：软删行过滤 + PII 排除 + 0 时间转 null（复用原逻辑）
    pipeline_id = getattr(pipeline, "id", "") or ""
    cleaned_rows = _clean_rows(rows, pipeline_id=pipeline_id, node_id=node_id, table=table)

    return cleaned_rows


def _query_meta_source_props(source_id: str, scope: Any) -> dict[str, Any]:
    """查 meta_source 拿连接配置（props JSONB）。

    强制走 meta_source：不接 config 直传连接串。
    """
    if scope is None:
        raise ValueError("meta_source query requires scope")
    org_id = getattr(scope, "org_id", "")
    project_id = getattr(scope, "project_id", "")
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT props FROM meta_source WHERE id=%s AND org_id=%s AND project_id=%s",
            (source_id, org_id, project_id),
        ).fetchone()
    if row is None:
        raise ValueError(
            f"meta_source not found: source_id={source_id} scope=({org_id},{project_id})"
        )
    # psycopg dict_row 时 row 是 dict；其他情况 row[0]
    props = row["props"] if isinstance(row, dict) else row[0]
    if isinstance(props, str):
        props = json.loads(props)
    return props


def _build_query_sql(
    *,
    table: str,
    pk: str,
    watermark_col: str,
    site_filter: int,
    cursor: dict[str, Any] | None,
    initial: bool,
) -> tuple[str, tuple[Any, ...]]:
    """构造查询 SQL（初装/增量 + LIMIT 控制）。

    - 初装（initial=True 或无 cursor）：不受 LIMIT 限制
    - 增量（有 cursor 且非 initial）：复合游标 (watermark, primary_key) + LIMIT 100

    注：is_delete 过滤在 Python 层做（_clean_rows），以便计数软删行进 DLQ。
    """
    # 基础 WHERE：site_id 过滤
    where_parts: list[str] = [f"{table}.site_id = %s"]
    params: list[Any] = [site_filter]

    # 增量游标（复合游标二元组）
    if cursor and not initial:
        watermark = cursor.get("watermark")
        primary_key = cursor.get("primary_key")
        where_parts.append(
            f"({table}.{watermark_col} > %s "
            f"OR ({table}.{watermark_col} = %s AND {table}.{pk} > %s))"
        )
        params.extend([watermark, watermark, primary_key])

    where_clause = " AND ".join(where_parts)
    sql = (
        f"SELECT * FROM niushop_b2c_v5.{table} WHERE {where_clause} "
        f"ORDER BY {table}.{watermark_col}, {table}.{pk}"
    )

    # LIMIT 100 采样上限（仅增量模式；初装不受限）
    if cursor and not initial:
        sql += " LIMIT %s"
        params.append(SAMPLE_LIMIT)

    return sql, tuple(params)


def _clean_rows(
    rows: list[dict[str, Any]],
    *,
    pipeline_id: str,
    node_id: str,
    table: str | None = None,
) -> list[dict[str, Any]]:
    """数据清洗：软删行过滤 + PII 排除 + 0 时间转 null。

    - 软删行（is_delete=1）不入 OT，进 DLQ 计数（记录到 module-level dict）
    - PII 排除（frozen/02 §P08）：ns_member 表的 8 个 PII 字段显式 drop，不进入 row 流
    - 0 时间转 null（Unix 秒 → UTC）：*_time 字段值为 0 时变 None
    """
    cleaned: list[dict[str, Any]] = []
    soft_delete_count = 0
    pii_fields = _PII_DROP_FIELDS_BY_TABLE.get(table or "", frozenset())

    for row in rows:
        # 软删行过滤（is_delete=1 不入 OT，进 DLQ 计数）
        if row.get("is_delete") == 1:
            soft_delete_count += 1
            continue

        cleaned_row = dict(row)
        # PII 排除（frozen/02 §P08 + D4 §P12）：按表名 drop 敏感字段，不进入 row 流
        if pii_fields:
            for pii_field in pii_fields:
                cleaned_row.pop(pii_field, None)
        # 0 时间转 null（Unix 秒 → UTC）：*_time 字段值为 0 时变 None
        for key, value in cleaned_row.items():
            if key.endswith("_time") and value == 0:
                cleaned_row[key] = None

        cleaned.append(cleaned_row)

    # 记录软删计数（供 G6 DLQ 取用）
    if pipeline_id and node_id:
        _SOFT_DELETE_COUNTS[(pipeline_id, node_id)] = soft_delete_count

    return cleaned
