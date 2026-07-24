"""W1-15 · Dataset Preview SQL Console。

用 sqlite3 内存库对 list[dict] 执行 SQL 查询（完整方言子集）+ 白名单安全 + 自动补全 + 历史。

详见 docs/palantier/20_tech/220tech_sql-console.md。
"""
from __future__ import annotations

import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "qh-" + uuid.uuid4().hex[:12]


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|MERGE|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

_SQL_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "ORDER BY", "GROUP BY", "HAVING",
    "LIMIT", "OFFSET", "AND", "OR", "NOT", "NULL", "IS", "IN",
    "JOIN", "LEFT JOIN", "INNER JOIN", "ON", "AS", "DISTINCT",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "ASC", "DESC",
]


class QueryResult(BaseModel):
    sql: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    duration_ms: float = 0.0
    error: str | None = None


class QueryHistory(BaseModel):
    id: str
    sql: str
    row_count: int
    duration_ms: float
    executed_at: str = Field(default_factory=_now)
    success: bool
    error: str = ""


class ColumnSuggestion(BaseModel):
    text: str
    kind: Literal["column", "table", "keyword"] = "column"
    description: str = ""


class SqlConsoleError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _infer_sqlite_type(value: Any) -> str:
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


class SqlConsole:
    def __init__(self) -> None:
        self._history: list[QueryHistory] = []
        self._lock = threading.Lock()

    def validate(self, sql: str) -> list[str]:
        errors: list[str] = []
        if not sql or not sql.strip():
            errors.append("SQL_EMPTY: SQL 不能为空")
            return errors
        stripped = sql.strip()
        upper = stripped.upper()
        if not upper.startswith("SELECT") and not upper.startswith("WITH"):
            errors.append("SQL_NOT_SELECT: 仅允许 SELECT 或 WITH 开头的查询")
        forbidden = _FORBIDDEN.findall(stripped)
        if forbidden:
            errors.append(f"SQL_FORBIDDEN: 检测到禁止关键词 {set(k.upper() for k in forbidden)}")
        return errors

    def execute(self, rows: list[dict[str, Any]], table_name: str, sql: str) -> QueryResult:
        errors = self.validate(sql)
        if errors:
            return QueryResult(sql=sql, error="; ".join(errors))
        if not rows:
            err = "EMPTY_DATASET: 数据集为空，无法推断 schema，请先提供数据行"
            self._record(sql, 0, 0.0, False, err)
            return QueryResult(sql=sql, error=err)
        safe_table = re.sub(r"[^a-zA-Z0-9_]", "_", table_name or "dataset")
        start = time.perf_counter()
        try:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if rows:
                columns = list(rows[0].keys())
                col_defs = ", ".join(
                    f'"{c}" {_infer_sqlite_type(rows[0].get(c))}' for c in columns
                )
                cursor.execute(f'CREATE TABLE "{safe_table}" ({col_defs})')
                placeholders = ", ".join("?" for _ in columns)
                col_list = ", ".join(f'"{c}"' for c in columns)
                for row in rows:
                    cursor.execute(
                        f'INSERT INTO "{safe_table}" ({col_list}) VALUES ({placeholders})',
                        [row.get(c) for c in columns],
                    )
            cursor.execute(sql)
            fetched = cursor.fetchall()
            result_columns = [d[0] for d in cursor.description] if cursor.description else []
            result_rows = [dict(r) for r in fetched]
            conn.close()
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._record(sql, len(result_rows), duration_ms, True, "")
            return QueryResult(
                sql=sql, columns=result_columns, rows=result_rows,
                row_count=len(result_rows), duration_ms=round(duration_ms, 2),
            )
        except sqlite3.Error as exc:
            duration_ms = (time.perf_counter() - start) * 1000.0
            err_msg = str(exc)
            self._record(sql, 0, duration_ms, False, err_msg)
            return QueryResult(sql=sql, error=f"SQL_EXEC_ERROR: {err_msg}",
                               duration_ms=round(duration_ms, 2))

    def autocomplete(self, columns: list[str], prefix: str) -> list[ColumnSuggestion]:
        suggestions: list[ColumnSuggestion] = []
        prefix_lower = (prefix or "").lower()
        for col in columns:
            if not prefix_lower or col.lower().startswith(prefix_lower):
                suggestions.append(ColumnSuggestion(text=col, kind="column"))
        for kw in _SQL_KEYWORDS:
            if not prefix_lower or kw.lower().startswith(prefix_lower):
                suggestions.append(ColumnSuggestion(text=kw, kind="keyword"))
        return suggestions

    def _record(self, sql: str, row_count: int, duration_ms: float, success: bool, error: str) -> None:
        record = QueryHistory(
            id=_new_id(), sql=sql, row_count=row_count,
            duration_ms=round(duration_ms, 2), success=success, error=error,
        )
        with self._lock:
            self._history.append(record)
            if len(self._history) > 200:
                self._history = self._history[-200:]

    def list_history(self, limit: int = 50) -> list[QueryHistory]:
        with self._lock:
            return list(reversed(self._history[-limit:]))


_console = SqlConsole()


def get_console() -> SqlConsole:
    return _console
