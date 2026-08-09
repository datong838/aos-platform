"""D1-W1: Niushop SourceAdapter — 从只读源读取行流。

真实执行只允许从已登记的只读数据源读取；缺失 source_id 必须失败关闭。

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
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

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


@dataclass(frozen=True)
class BatchReadSpec:
    """公共批读的不可变 SQL 白名单；业务调用方只能传 spec_id 和值。"""

    table: str
    columns: tuple[str, ...]
    filter_column: str


BATCH_READ_SPECS: Mapping[str, BatchReadSpec] = MappingProxyType(
    {
        "payment_order_time": BatchReadSpec(
            table="ns_order",
            columns=("order_id", "create_time"),
            filter_column="order_id",
        ),
        "shipment_order_timing": BatchReadSpec(
            table="ns_order",
            columns=("order_id", "pay_time"),
            filter_column="order_id",
        ),
    }
)


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

    D4 Phase C: 统一走通用 JDBC SSH 分支，niushop-mysql 已废弃。
    所有 connector_type（包括 legacy niushop-mysql）都走 JdbcConnectorRuntime。
    """
    # 尝试找 source 节点并取其 config
    node_config = _resolve_source_node_config(nodes, node_id)

    # O1-R1：真实执行禁止 sample_input 隐式回退。
    if node_config is None or not node_config.get("source_id"):
        raise RuntimeError(
            f"Source node '{node_id or '<auto>'}' has no source_id; "
            "live execution refused"
        )

    # 查 meta_source 拿连接配置（所有分支都需要）
    source_id = node_config["source_id"]
    props = _query_meta_source_props(source_id, scope)

    # D4 Phase C: 统一走通用 JDBC SSH 分支（niushop-mysql 已废弃）
    return _fetch_from_jdbc_ssh(
        pipeline=pipeline,
        node_id=node_id or "",
        node_config=node_config,
        props=props,
    )


def batch_read_public(
    *,
    pipeline: Any,
    nodes: list[Any],
    node_id: str | None,
    scope: Any,
    spec_id: str,
    filter_values: Sequence[str],
) -> list[dict[str, Any]]:
    """O1 §5.2.11：复用当前 Pipeline Source 执行受控批读。

    表名、列名和过滤列只能来自 `BATCH_READ_SPECS`。缺 Source、
    未知规格或连接失败均向上抛出，不允许降级为部分指标。
    """
    del pipeline  # 保留公共契约参数，Source 解析以 nodes/node_id 为准。
    spec = BATCH_READ_SPECS.get(spec_id)
    if spec is None:
        raise ValueError(f"unknown batch read spec: {spec_id}")

    node_config = _resolve_source_node_config(nodes, node_id)
    if node_config is None or not node_config.get("source_id"):
        raise RuntimeError(
            f"Source node '{node_id or '<auto>'}' has no source_id; "
            "batch read refused"
        )
    values = tuple(dict.fromkeys(str(value) for value in filter_values))
    if not values:
        return []

    props = _query_meta_source_props(str(node_config["source_id"]), scope)
    with JdbcConnectorRuntime(props) as runtime:
        return runtime.read_rows_by_values(spec, values)


def _resolve_source_node_config(
    nodes: list[Any], node_id: str | None
) -> dict[str, Any] | None:
    """从 nodes 中找到 node_id 对应的节点并返回其 config。

    O1-B: 当 node_id=None 时（execute_pipeline_once 的默认调用），
    回退到第一个 source 类型的节点。
    """
    if not nodes:
        return None
    # 优先按 node_id 匹配
    if node_id is not None:
        for node in nodes:
            if getattr(node, "id", None) == node_id:
                return getattr(node, "config", None) or {}
        return None
    # node_id=None 时，找第一个 source 节点
    for node in nodes:
        nt = str(getattr(node, "node_type", "") or "").lower()
        if nt == "source":
            return getattr(node, "config", None) or {}
    return None


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
    table = node_config.get("table") or node_config.get("source_table", "")
    pk = node_config.get("pk", "id")
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
    table = node_config.get("table") or node_config.get("source_table", "")
    pk = node_config.get("pk", "id")
    watermark_col = node_config.get("watermark_col", "modify_time")
    cursor = node_config.get("cursor")
    initial = bool(node_config.get("initial", False))
    where_equals = _parse_site_filter(node_config.get("site_filter"))

    # 通用 JDBC SSH 运行时（with 上下文管理 SSH 隧道 + JDBC 连接生命周期）
    with JdbcConnectorRuntime(props) as rt:
        # 游标增量：如有 cursor 则 (watermark, pk) 二元组；初装传 None
        composite_cursor = None
        if cursor and not initial:
            composite_cursor = (
                cursor.get("watermark"), cursor.get("primary_key"),
                watermark_col, pk,
            )
        rows = rt.read_rows(
            table,
            composite_cursor=composite_cursor,
            limit=SAMPLE_LIMIT if composite_cursor is not None else None,
            where_equals=where_equals,
        )

    # 数据清洗：软删行过滤 + PII 排除 + 0 时间转 null（复用原逻辑）
    pipeline_id = getattr(pipeline, "id", "") or ""
    cleaned_rows = _clean_rows(rows, pipeline_id=pipeline_id, node_id=node_id, table=table)

    return cleaned_rows


_FILTER_TERM = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|(-?\d+(?:\.\d+)?))\s*$"
)


def _parse_site_filter(value: Any) -> dict[str, Any]:
    """把 Pipeline 的简单等值 AND 过滤转换为参数化查询条件。

    这里只接受 ``column=value AND column=value``；任何 OR、函数、注释或
    其他 SQL 语法均失败关闭，避免把配置文本直接拼接成 SQL。
    """
    if value is None or value == "":
        return {}
    if isinstance(value, bool):
        raise ValueError("site_filter only accepts simple equality terms")
    if isinstance(value, int):
        return {"site_id": value}
    if not isinstance(value, str):
        raise ValueError("site_filter only accepts simple equality terms")

    result: dict[str, Any] = {}
    for term in re.split(r"\s+AND\s+", value.strip(), flags=re.IGNORECASE):
        match = _FILTER_TERM.fullmatch(term)
        if match is None:
            raise ValueError(f"unsafe site_filter term: {term!r}")
        column, single_quoted, double_quoted, numeric = match.groups()
        if column in result:
            raise ValueError(f"duplicate site_filter column: {column!r}")
        if numeric is not None:
            parsed: Any = float(numeric) if "." in numeric else int(numeric)
        else:
            parsed = single_quoted if single_quoted is not None else double_quoted
        result[column] = parsed
    return result


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
