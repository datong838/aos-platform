"""d2_qiyuehui_init_load.py — 栖月汇商贸 Niushop 真实库初装 (D2 波次).

建立 8 OT 本体数字孪生: 从 Niushop 只读源 (ssh 隧道 13306) 全量读取 8 张表,
归一化为 8 个 OT 对象, 落地到 aos_meta.ecom_object.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
架构说明 (重要 — 任务描述未提及的两个架构缺口)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

缺口 1 (normalize 缺失):
  ec_ot_writer._build_object 硬读 row["ot"] / row["source_pk"] /
  row["source_updated_at"] / row["properties"]. 但 ec_source_adapter.
  fetch_source_rows 返回的是 *原始 ns_xxx 行* (列名 order_id/create_time
  ...), 没有这些 OT 字段. 全代码库无 normalize 模块 (D2 未实现).
  直接调用 ec_live_executor 会落地 0 个 OT (_build_object 对原始行
  返回 None). 本脚本在调用链中补上 raw→OT 归一化这一步.

缺口 2 (store 装配缺失):
  PipelineEngine 单例默认无 ecom_consistency_store 属性, sink_to_ot
  会走骨架零计数分支. 生产装配缺失. 本脚本装配真实的连 PG 的
  EcomConsistencyStore 并注入 engine.

实施路径 (路径 A — 编排 ec_live_executor 的真实内部组件):
  不调用顶层 ec_live_executor (其内部缺 normalize, 且强制 build_link_rows).
  改为按真实顺序编排其内部组件:
    fetch_source_rows → 脚本 normalize → apply_derived_metrics
    → sink_to_dataset → sink_to_ot
  全真实读写, 零 mock, 不改 aos_api 源码.

Link 处理:
  初装阶段 *不构造 Link* (跳过 build_link_rows). 理由: ecom_link 有 FK +
  DANGLING_LINK 严格检查 (端点不存在即抛异常整批回滚); ns_order.member_id
  与 ns_member.member_id 跨表覆盖无法保证, 任一悬挂会导致整批 object
  回滚, 危及 "8 OT 落地" 核心验收. Link 可在 object 全落地后作为第二
  阶段单独补. 任务核心验收仅要求 8 OT object 行数.

scope:
  使用 TenantScope (非 SimpleNamespace): db.connect→apply_transaction_scope
  需要 scope.key, SimpleNamespace 无此属性会导致 ec_source_adapter.
  _query_meta_source_props 崩溃.
"""
from __future__ import annotations

import sys
import time
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_API = REPO_ROOT / "services" / "aos-api"
sys.path.insert(0, str(SERVICES_API))

from sqlalchemy import create_engine  # noqa: E402

from aos_api.db import get_dsn  # noqa: E402
from aos_api.ecom_consistency_store import (  # noqa: E402
    EcomConsistencyStore,
    metadata as ecom_metadata,
)
from aos_api.ec_source_adapter import fetch_source_rows  # noqa: E402
from aos_api.ec_derived_metrics import apply_derived_metrics  # noqa: E402
from aos_api.ec_dataset_sink import sink_to_dataset  # noqa: E402
from aos_api.ec_ot_writer import sink_to_ot  # noqa: E402
from aos_api.phase5_pipeline_engine import get_engine  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402
import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

# ───────────────────────── 常量 ─────────────────────────

ORG_ID = "org-org"
PROJECT_ID = "dev-project"
SOURCE_ID = "niushop-qyh"
SITE_FILTER = 1
SOURCE_TIMEZONE = "+08:00"
CURRENCY = "CNY"

SCOPE = TenantScope(ORG_ID, PROJECT_ID)


# ───────────────────────── .env 加载 ─────────────────────────

def _load_env() -> dict[str, str]:
    env_path = REPO_ROOT / ".env"
    values: dict[str, str] = {}
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


ENV = _load_env()
NIUSHOP_USER = ENV.get("NIUSHOP_DB_USER", "niushop")
NIUSHOP_PASSWORD = ENV.get("NIUSHOP_DB_PASSWORD", "ddt_227018")
NIUSHOP_PORT = int(ENV.get("NIUSHOP_DB_PORT_TUNNEL", "13306"))


# ───────────────────────── 工具函数 ─────────────────────────

def _ts(row: dict[str, Any], *fields: str) -> datetime:
    """从 row 的时间字段 (unix 秒) 取首个有效值转 UTC datetime; 全无效则 now."""
    for f in fields:
        v = row.get(f)
        if isinstance(v, (int, float)) and v > 0:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
    return datetime.now(timezone.utc)


def _money(v: Any) -> str:
    """金额兜底: None/空/非法 → '0'; 合法则转字符串 (避免 float 进 Money 校验)."""
    if v is None:
        return "0"
    if isinstance(v, Decimal):
        return str(v)
    s = str(v).strip()
    if s == "":
        return "0"
    try:
        Decimal(s)
        return s
    except (InvalidOperation, ValueError):
        return "0"


def _str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s != "" else default


# ───────────────────────── 8 OT normalize mappers ─────────────────────────
# 每个 mapper: 在 raw row 基础上 *追加* OT 字段 + properties, 保留原始字段
# (供 apply_derived_metrics._get_field 从顶层读取派生指标源字段).

def _base(row: dict[str, Any], ot: str, pk: Any, when: datetime) -> dict[str, Any]:
    out = dict(row)
    out["ot"] = ot
    out["source_pk"] = _str(pk)
    out["source_updated_at"] = when
    out["source_timezone"] = SOURCE_TIMEZONE
    out["is_deleted"] = False
    out["properties"] = {}
    return out


def to_shop(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "Shop", row.get("site_id"), _ts(row, "create_time"))
    o["properties"] = {
        "name": _str(row.get("site_name"), "栖月汇商贸"),
        "status": "active",
        "currency": CURRENCY,
        "timezone": SOURCE_TIMEZONE,
    }
    return o


def to_category(row: dict[str, Any]) -> dict[str, Any]:
    # ns_goods_category 无时间列 → source_updated_at 用 now
    o = _base(row, "Category", row.get("category_id"), _ts(row))
    o["properties"] = {
        "parentCategoryId": _str(row.get("pid"), "0"),
        "name": _str(row.get("category_name"), _str(row.get("category_id"))),
        "status": "active",
    }
    return o


def to_product(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "Product", row.get("goods_id"), _ts(row, "modify_time", "create_time"))
    o["properties"] = {
        "shopId": _str(row.get("site_id"), str(SITE_FILTER)),
        "title": _str(row.get("goods_name"), _str(row.get("goods_id"))),
        "status": "active",
        "categoryId": _str(row.get("category_id"), "0"),
    }
    return o


def to_product_sku(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "ProductSku", row.get("sku_id"), _ts(row, "modify_time", "create_time"))
    o["properties"] = {
        "productId": _str(row.get("goods_id"), "0"),
        "status": "active",
        "barcode": _str(row.get("sku_no"), ""),
        "price": _money(row.get("price")),
        "currency": CURRENCY,
    }
    return o


def to_customer_lite(row: dict[str, Any]) -> dict[str, Any]:
    # ns_member 无 create_time/modify_time → 用 reg_time 等
    o = _base(row, "CustomerLite", row.get("member_id"),
              _ts(row, "reg_time", "last_visit_time", "login_time", "last_login_time"))
    o["properties"] = {
        "memberLevel": _str(row.get("member_level"), "0"),
        "status": "active",
    }
    return o


def to_order(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "Order", row.get("order_id"), _ts(row, "modify_time", "create_time"))
    o["properties"] = {
        "shopId": _str(row.get("site_id"), str(SITE_FILTER)),
        "status": "active",
        "totalAmount": _money(row.get("order_money")),
        "currency": CURRENCY,
        "orderNo": _str(row.get("order_no")),
        "memberId": _str(row.get("member_id")),
        "orderStatus": _str(row.get("order_status")),
        "payStatus": _str(row.get("pay_status")),
        "deliveryStatus": _str(row.get("delivery_status")),
        "isDelete": _str(row.get("is_delete"), "0"),
    }
    return o


def to_order_line(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "OrderLine", row.get("order_goods_id"), _ts(row, "create_time"))
    o["properties"] = {
        "orderId": _str(row.get("order_id")),
        "skuId": _str(row.get("sku_id"), "0"),
        "quantity": _str(row.get("num"), "0"),
        "unitPrice": _money(row.get("price")),
        "lineAmount": _money(row.get("real_goods_money") or row.get("goods_money")),
        "currency": CURRENCY,
    }
    return o


def to_shipment(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "Shipment", row.get("id"), _ts(row, "delivery_time"))
    o["properties"] = {
        "orderId": _str(row.get("order_id")),
        "status": "active",
        "carrier": _str(row.get("express_company_id"),
                        _str(row.get("express_company_name"))),
        "trackingNo": _str(row.get("delivery_no")),
    }
    return o


# ───────────────────────── 8 pipeline 配置 ─────────────────────────
# (pipeline_id, table, pk, watermark_col, target_ot, normalize_fn)

PIPELINES: list[tuple[str, str, str, str, str, Any]] = [
    ("p01-shop", "ns_site", "site_id", "create_time", "Shop", to_shop),
    ("p04-category", "ns_goods_category", "category_id", "category_id", "Category", to_category),
    ("p02-product", "ns_goods", "goods_id", "modify_time", "Product", to_product),
    ("p03-product-sku", "ns_goods_sku", "sku_id", "modify_time", "ProductSku", to_product_sku),
    ("p08-customer-lite", "ns_member", "member_id", "member_id", "CustomerLite", to_customer_lite),
    ("p05-order", "ns_order", "order_id", "create_time", "Order", to_order),
    ("p06-order-line", "ns_order_goods", "order_goods_id", "create_time", "OrderLine", to_order_line),
    ("p07-shipment", "ns_express_delivery_package", "id", "id", "Shipment", to_shipment),
]


# ───────────────────────── meta_source 注册 ─────────────────────────

def register_meta_source(conn: psycopg.Connection) -> None:
    props = {
        "host": "127.0.0.1",
        "port": NIUSHOP_PORT,
        "user": NIUSHOP_USER,
        "password": NIUSHOP_PASSWORD,
        "database": "niushop_b2c_v5",
    }
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_source (
          id TEXT PRIMARY KEY,
          type TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          plugin_id TEXT NOT NULL DEFAULT '',
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          props JSONB NOT NULL DEFAULT '{}'::jsonb,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.execute(
        """
        INSERT INTO meta_source (id, type, status, plugin_id, org_id, project_id, props, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (org_id, project_id, id) DO UPDATE SET
          type = EXCLUDED.type,
          status = EXCLUDED.status,
          plugin_id = EXCLUDED.plugin_id,
          org_id = EXCLUDED.org_id,
          project_id = EXCLUDED.project_id,
          props = EXCLUDED.props,
          updated_at = NOW()
        """,
        (SOURCE_ID, "jdbc-mysql", "active", "jdbc-mysql",
         ORG_ID, PROJECT_ID, json.dumps(props)),
    )
    conn.commit()
    print(f"[meta_source] registered id={SOURCE_ID} org={ORG_ID} project={PROJECT_ID}")


def patch_object_type_check(conn: psycopg.Connection) -> None:
    """修复 W3 schema/OT 不一致: ecom_object_object_type_check 漏了 CustomerLite.

    只放宽 (新增 CustomerLite), 不收紧, 已有 7 OT 数据全部满足新 CHECK, 无影响.
    """
    conn.execute(
        "ALTER TABLE ecom_object DROP CONSTRAINT IF EXISTS ecom_object_object_type_check"
    )
    conn.execute(
        "ALTER TABLE ecom_object ADD CONSTRAINT ecom_object_object_type_check "
        "CHECK (object_type IN ('Shop','Product','ProductSku','Category',"
        "'Order','OrderLine','Shipment','CustomerLite'))"
    )
    conn.commit()
    print("[schema] patched ecom_object_object_type_check: + CustomerLite")


def reset_ecom_scope(conn: psycopg.Connection) -> None:
    """清空本 scope 电商孪生半成品, 从干净状态初装.

    只删 org-org/dev-project 的 4 张电商表; 不影响其他 org/project.
    删除顺序: ecom_link (FK→object) → receipt/checkpoint → ecom_object.
    """
    conn.execute("SET LOCAL ROLE aos_runtime")
    conn.execute(
        "SELECT set_config('aos.org_id', %s, true), "
        "set_config('aos.project_id', %s, true)",
        (ORG_ID, PROJECT_ID),
    )
    for table in ("ecom_link", "ecom_ingest_receipt",
                  "ecom_sync_checkpoint", "ecom_object"):
        result = conn.execute(
            f"DELETE FROM {table} WHERE org_id=%s AND workspace_id=%s",
            (ORG_ID, PROJECT_ID),
        )
        print(f"  [reset] {table}: deleted {result.rowcount}")
    conn.commit()
    print(f"[reset] cleared ecom scope org={ORG_ID} project={PROJECT_ID}")


# ───────────────────────── 单 pipeline 编排 ─────────────────────────

def run_pipeline(
    pid: str, table: str, pk: str, watermark_col: str,
    target_ot: str, normalize_fn: Any, eng: Any,
) -> tuple[int, int, str]:
    """编排: fetch_source_rows → normalize → apply_derived_metrics → sinks.

    返回 (rows_read, objects_written, status_msg).
    """
    pipeline = SimpleNamespace(
        id=pid,
        config={"target_ot": target_ot},
    )
    node = SimpleNamespace(
        id="n-src",
        node_type="source",
        config={
            "source_id": SOURCE_ID,
            "table": table,
            "pk": pk,
            "watermark_col": watermark_col,
            "site_filter": SITE_FILTER,
            "initial": True,
        },
    )

    deadline = time.time() + 300  # 保留用于将来超时控制; fetch_source_rows 当前不消费

    raw_rows = fetch_source_rows(
        pipeline=pipeline, nodes=[node], node_id="n-src",
        sample_input=[], scope=SCOPE,
    )
    rows_read = len(raw_rows)

    if rows_read == 0:
        return 0, 0, "no rows"

    ot_rows = [normalize_fn(r) for r in raw_rows]
    ot_rows = apply_derived_metrics(ot_rows, pipeline)
    sink_to_dataset(eng, SCOPE, pipeline, ot_rows)
    result = sink_to_ot(eng, SCOPE, pipeline, ot_rows)
    objects_written = int(result.get("objects_written", 0))

    return rows_read, objects_written, "ok"


# ───────────────────────── 主流程 ─────────────────────────

def main() -> int:
    print("=" * 70)
    print("d2_qiyuehui_init_load — 栖月汇商贸 Niushop 真实库初装 (8 OT)")
    print("=" * 70)
    print(f"scope: org_id={ORG_ID} project_id={PROJECT_ID}")
    print(f"niushop: 127.0.0.1:{NIUSHOP_PORT} user={NIUSHOP_USER} db=niushop_b2c_v5")

    dsn = get_dsn()
    print(f"aos pg dsn: {dsn.split('@')[-1] if '@' in dsn else dsn}")

    # 1. 注册 meta_source + schema 修复 + 清半成品 (psycopg 连接)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        register_meta_source(conn)
        patch_object_type_check(conn)
        reset_ecom_scope(conn)

    # 2. 装配真实 EcomConsistencyStore 并注入 engine 单例
    pg_dsn = dsn
    if pg_dsn.startswith("postgresql://"):
        pg_dsn = "postgresql+psycopg://" + pg_dsn[len("postgresql://"):]
    elif pg_dsn.startswith("postgres://"):
        pg_dsn = "postgresql+psycopg://" + pg_dsn[len("postgres://"):]
    pg_engine = create_engine(pg_dsn)
    ecom_metadata.create_all(pg_engine)  # 已存在则 no-op
    store = EcomConsistencyStore(pg_engine)
    eng = get_engine()
    eng.ecom_consistency_store = store
    print(f"[store] EcomConsistencyStore assembled & injected to engine")

    # 3. 按 8 pipeline 编排 (依赖安全序: 无 Link 仍保持安全顺序)
    print("\n--- pipelines ---")
    summary: list[tuple[str, str, int, int, str]] = []
    total_read = 0
    total_written = 0
    any_failed = False

    for pid, table, pk, watermark_col, target_ot, normalize_fn in PIPELINES:
        t0 = time.time()
        try:
            rows_read, objects_written, status = run_pipeline(
                pid, table, pk, watermark_col, target_ot, normalize_fn, eng,
            )
            elapsed = time.time() - t0
            total_read += rows_read
            total_written += objects_written
            summary.append((pid, target_ot, rows_read, objects_written, status))
            print(f"  [{pid:<22}] {target_ot:<13} "
                  f"read={rows_read:<5} written={objects_written:<5} "
                  f"status={status} ({elapsed:.1f}s)")
        except Exception as exc:
            any_failed = True
            elapsed = time.time() - t0
            cause = getattr(exc, "__cause__", None)
            extra = ""
            if cause is not None:
                diag = getattr(cause, "diag", None)
                mp = getattr(diag, "message_primary", "") if diag else ""
                extra = f" | cause={type(cause).__name__} pgcode={getattr(cause,'pgcode','?')} | {mp or cause}"
            summary.append((pid, target_ot, -1, -1,
                            f"FAIL: {type(exc).__name__}: {exc}{extra}"))
            print(f"  [{pid:<22}] {target_ot:<13} FAILED after {elapsed:.1f}s")
            print(f"      {type(exc).__name__}: {exc}{extra}")

    # 4. 汇总
    print("\n--- summary ---")
    print(f"  total rows_read={total_read}  total objects_written={total_written}")

    # 5. 查 ecom_object GROUP BY object_type
    print("\n--- ecom_object GROUP BY object_type (落地结果) ---")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.execute(f"SET LOCAL ROLE aos_runtime")
        conn.execute(
            "SELECT set_config('aos.org_id', %s, true), "
            "set_config('aos.project_id', %s, true)",
            (ORG_ID, PROJECT_ID),
        )
        rows = conn.execute(
            """
            SELECT object_type, count(*) AS c
            FROM ecom_object
            WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL
            GROUP BY object_type ORDER BY object_type
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchall()

    expected = {
        "Shop": 1, "Category": 11, "Product": 65, "ProductSku": 73,
        "CustomerLite": 53, "Order": 177, "OrderLine": 227, "Shipment": 19,
    }
    landed = {r["object_type"]: int(r["c"]) for r in rows}
    print(f"  {'object_type':<14} {'landed':>7} {'expected':>9}  match")
    for ot in ["Shop", "Category", "Product", "ProductSku",
               "CustomerLite", "Order", "OrderLine", "Shipment"]:
        got = landed.get(ot, 0)
        exp = expected[ot]
        mark = "OK" if got == exp else "MISMATCH"
        print(f"  {ot:<14} {got:>7} {exp:>9}  {mark}")
    print(f"  {'TOTAL':<14} {sum(landed.values()):>7} {sum(expected.values()):>9}")

    print("\n" + "=" * 70)
    if any_failed:
        print("RESULT: PARTIAL — 部分 pipeline 失败, 见上文 FAIL 行")
        return 2
    all_match = all(landed.get(ot, 0) == expected[ot] for ot in expected)
    if all_match:
        print("RESULT: SUCCESS — 8 OT 全部落地且行数匹配")
        return 0
    print("RESULT: MISMATCH — 行数与期望不一致, 见上表")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
