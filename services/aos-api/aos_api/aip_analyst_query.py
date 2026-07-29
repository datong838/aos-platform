"""W2-A4 · AIP Analyst 内存查询引擎（SELECT + 简易 NL）。

对内存表 shops / inventory / sales 跑查询，无法解析时返回结构化样例并标 source=fallback。
"""
from __future__ import annotations

import re
import time
from typing import Any

_DANGEROUS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke)\b",
    re.IGNORECASE,
)

_TABLES: dict[str, dict[str, Any]] = {
    "shops": {
        "columns": [
            {"name": "name", "type": "string"},
            {"name": "coords", "type": "coords"},
            {"name": "rating", "type": "number"},
        ],
        "rows": [
            {"id": "s1", "name": "Walter and Sons", "coords": "52.21345,-0.94540", "rating": 5, "city": "Northampton"},
            {"id": "s2", "name": "Kuhic, Murphy and Shan", "coords": "52.18096,-1.00509", "rating": 4, "city": "Northampton"},
            {"id": "s3", "name": "Hickle - Blick", "coords": "52.19575,-0.81793", "rating": 5, "city": "Northampton"},
            {"id": "s4", "name": "Strosin Group", "coords": "52.20895,-0.88012", "rating": 3, "city": "Birmingham"},
            {"id": "s5", "name": "Hansen LLC", "coords": "52.23101,-0.86555", "rating": 4, "city": "Northampton"},
        ],
    },
    "inventory": {
        "columns": [
            {"name": "sku", "type": "string"},
            {"name": "stock", "type": "number"},
        ],
        "rows": [
            {"id": "i1", "sku": "SKU-100", "stock": 3},
            {"id": "i2", "sku": "SKU-200", "stock": 12},
            {"id": "i3", "sku": "SKU-300", "stock": 7},
            {"id": "i4", "sku": "SKU-400", "stock": 1},
        ],
    },
    "sales": {
        "columns": [
            {"name": "date", "type": "string"},
            {"name": "revenue", "type": "number"},
        ],
        "rows": [
            {"id": "sa1", "date": "2026-07-25", "revenue": 1200},
            {"id": "sa2", "date": "2026-07-26", "revenue": 980},
            {"id": "sa3", "date": "2026-07-27", "revenue": 1450},
            {"id": "sa4", "date": "2026-07-28", "revenue": 1100},
        ],
    },
}

_FALLBACK: dict[str, Any] = {
    "columns": [
        {"name": "name", "type": "string"},
        {"name": "coords", "type": "coords"},
        {"name": "rating", "type": "number"},
    ],
    "rows": [
        {"id": "s1", "name": "Walter and Sons", "coords": "52.21345,-0.94540", "rating": 5},
        {"id": "s2", "name": "Kuhic, Murphy and Shan", "coords": "52.18096,-1.00509", "rating": 4},
        {"id": "s3", "name": "Hickle - Blick", "coords": "52.19575,-0.81793", "rating": 5},
    ],
}


def is_select_query(sql: str) -> bool:
    return bool(re.match(r"^\s*select\b", sql or "", re.IGNORECASE))


def validate_select(sql: str) -> str | None:
    """返回错误信息；合法返回 None。"""
    text = (sql or "").strip()
    if not text:
        return "empty sql"
    if not is_select_query(text):
        return "only SELECT queries are allowed"
    # 多语句
    body = text.rstrip().rstrip(";").strip()
    if ";" in body:
        return "multiple statements are not allowed"
    if _DANGEROUS.search(body):
        return "dangerous keyword rejected"
    return None


def nl_to_sql(natural_language: str) -> str:
    nl = (natural_language or "").strip().lower()
    if any(k in nl for k in ("库存", "inventory", "stock", "sku")):
        return "SELECT sku, stock FROM inventory WHERE stock < 10"
    if any(k in nl for k in ("销售", "sales", "revenue", "趋势")):
        return "SELECT date, revenue FROM sales ORDER BY date DESC LIMIT 30"
    if any(k in nl for k in ("高评", "rating", "高分")):
        return "SELECT name, rating FROM shops WHERE rating >= 4 ORDER BY rating DESC"
    # 默认店铺 / 咖啡 / Northampton
    return "SELECT name, coords, rating FROM shops WHERE city = 'Northampton' ORDER BY rating DESC"


def extract_table(sql: str) -> str:
    m = re.search(r"\bfrom\s+([a-zA-Z_][\w.]*)", sql or "", re.IGNORECASE)
    if not m:
        return ""
    name = m.group(1).strip()
    if "." in name:
        name = name.split(".")[-1]
    return name.lower()


def extract_columns(sql: str) -> list[str]:
    m = re.search(r"select\s+(.+?)\s+from", sql or "", re.IGNORECASE | re.DOTALL)
    if not m:
        return ["*"]
    raw = m.group(1).strip()
    if raw == "*":
        return ["*"]
    cols: list[str] = []
    for part in raw.split(","):
        s = part.strip()
        s = re.sub(r".*\.\w+\s+as\s+", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+as\s+\w+", "", s, flags=re.IGNORECASE)
        s = s.split(".")[-1].strip()
        if s:
            cols.append(s)
    return cols or ["*"]


def _apply_where(rows: list[dict[str, Any]], sql: str) -> list[dict[str, Any]]:
    out = list(rows)
    city_m = re.search(r"city\s*=\s*'([^']+)'", sql, re.IGNORECASE)
    if city_m:
        city = city_m.group(1)
        out = [r for r in out if str(r.get("city", "")) == city]
    rating_m = re.search(r"rating\s*>=\s*(\d+(?:\.\d+)?)", sql, re.IGNORECASE)
    if rating_m:
        thr = float(rating_m.group(1))
        out = [r for r in out if float(r.get("rating", 0)) >= thr]
    stock_m = re.search(r"stock\s*<\s*(\d+(?:\.\d+)?)", sql, re.IGNORECASE)
    if stock_m:
        thr = float(stock_m.group(1))
        out = [r for r in out if float(r.get("stock", 0)) < thr]
    return out


def _project(
    columns_meta: list[dict[str, str]],
    rows: list[dict[str, Any]],
    wanted: list[str],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    if wanted == ["*"]:
        return columns_meta, [{k: v for k, v in r.items()} for r in rows]
    col_by_name = {c["name"]: c for c in columns_meta}
    cols = [col_by_name[n] for n in wanted if n in col_by_name]
    if not cols:
        cols = columns_meta
        wanted_names = [c["name"] for c in cols]
    else:
        wanted_names = [c["name"] for c in cols]
    projected: list[dict[str, Any]] = []
    for r in rows:
        item: dict[str, Any] = {}
        if "id" in r:
            item["id"] = r["id"]
        for n in wanted_names:
            if n in r:
                item[n] = r[n]
        projected.append(item)
    return cols, projected


def run_analyst_query(
    *,
    sql: str | None = None,
    natural_language: str | None = None,
) -> dict[str, Any]:
    """执行查询；非法 SELECT 抛 ValueError。"""
    t0 = time.perf_counter()
    resolved = (sql or "").strip()
    if not resolved and natural_language:
        resolved = nl_to_sql(natural_language)
    if not resolved:
        raise ValueError("sql or naturalLanguage required")

    err = validate_select(resolved)
    if err:
        raise ValueError(err)

    table = extract_table(resolved)
    wanted = extract_columns(resolved)
    meta = _TABLES.get(table)
    if meta is None:
        ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": True,
            "columns": list(_FALLBACK["columns"]),
            "rows": [dict(r) for r in _FALLBACK["rows"]],
            "durationMs": max(ms, 1),
            "cacheHit": False,
            "source": "fallback",
            "sql": resolved,
            "table": table or None,
        }

    rows = _apply_where(list(meta["rows"]), resolved)
    cols, projected = _project(list(meta["columns"]), rows, wanted)
    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "ok": True,
        "columns": cols,
        "rows": projected,
        "durationMs": max(ms, 1),
        "cacheHit": False,
        "source": "live",
        "sql": resolved,
        "table": table,
    }
