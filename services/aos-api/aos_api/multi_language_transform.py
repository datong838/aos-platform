"""W2-#25 · 多语言 Transform（Python/SQL/Java/R）。

- Python：复用 functions_python_builder（真实沙箱执行）
- SQL：轻量 SELECT/WHERE 解释器（list[dict] → list[dict]）
- Java/R：stub，注册可用但 invoke 抛 NOT_IMPLEMENTED

统一注册表 RuntimeTransform，按 language 分发。

详见 docs/palantier/20_tech/220tech_w2-b-aip-functions.md §2.4。
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from .function_engine import evaluate, parse


LanguageKind = Literal["python", "sql", "java", "r"]


class MultiLanguageError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_LANGUAGE_AVAILABLE: dict[str, bool] = {
    "python": True,
    "sql": True,
    "java": False,
    "r": False,
}


class RuntimeTransform(BaseModel):
    id: str = Field(default_factory=lambda: "mlt-" + uuid.uuid4().hex[:8])
    name: str
    language: LanguageKind
    source: str
    available: bool = True
    description: str = ""


def list_supported_languages() -> list[dict[str, Any]]:
    return [
        {"language": lang, "available": avail}
        for lang, avail in _LANGUAGE_AVAILABLE.items()
    ]


_SELECT_RE = re.compile(
    r"^\s*SELECT\s+(?P<cols>[\w\s,.*]+?)\s+FROM\s+(?P<src>\w+)"
    r"(?:\s+WHERE\s+(?P<where>.+))?\s*$",
    re.IGNORECASE,
)


def _run_sql(source: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    match = _SELECT_RE.match(source)
    if not match:
        raise MultiLanguageError("SQL_PARSE_ERROR", f"无法解析 SQL：{source!r}（仅支持 SELECT ... FROM ... [WHERE ...]）")
    cols_raw = match.group("cols").strip()
    where_expr = match.group("where")
    selected: list[dict[str, Any]] = []
    for row in rows:
        if where_expr:
            try:
                ok = bool(evaluate(parse(where_expr), row))
            except Exception as exc:
                raise MultiLanguageError("SQL_WHERE_ERROR", f"WHERE 表达式错误：{exc}") from exc
            if not ok:
                continue
        if cols_raw == "*":
            selected.append(dict(row))
        else:
            cols = [c.strip() for c in cols_raw.split(",") if c.strip()]
            picked = {c: row.get(c) for c in cols if c in row}
            selected.append(picked)
    return selected


class MultiLanguageTransform:
    """多语言 Transform 注册表 + 执行分发。"""

    def __init__(self) -> None:
        self._transforms: dict[str, RuntimeTransform] = {}

    def register(
        self, language: LanguageKind, source: str, name: str, description: str = ""
    ) -> RuntimeTransform:
        if not name:
            raise MultiLanguageError("MISSING_NAME", "Transform 缺少 name")
        if language not in _LANGUAGE_AVAILABLE:
            raise MultiLanguageError("UNSUPPORTED_LANGUAGE", f"不支持的语言 {language!r}")
        if language == "python":
            from .functions_python_builder import get_builder
            try:
                get_builder().register(name, source, description)
            except Exception as exc:
                raise MultiLanguageError("REGISTER_FAILED", str(exc)) from exc
        available = _LANGUAGE_AVAILABLE[language]
        tf = RuntimeTransform(
            name=name, language=language, source=source, available=available, description=description
        )
        self._transforms[tf.id] = tf
        return tf

    def get(self, transform_id: str) -> RuntimeTransform | None:
        return self._transforms.get(transform_id)

    def find_by_name(self, name: str) -> RuntimeTransform | None:
        for tf in self._transforms.values():
            if tf.name == name:
                return tf
        return None

    def list_all(self) -> list[RuntimeTransform]:
        return list(self._transforms.values())

    def delete(self, transform_id: str) -> bool:
        existed = transform_id in self._transforms
        self._transforms.pop(transform_id, None)
        return existed

    def invoke(self, transform_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tf = self._transforms.get(transform_id)
        if tf is None:
            raise MultiLanguageError("UNKNOWN_TRANSFORM", f"未知 Transform {transform_id!r}")
        if not tf.available:
            raise MultiLanguageError(
                "NOT_IMPLEMENTED",
                f"语言 {tf.language!r} 运行时未实现（仅注册元信息）",
            )
        if tf.language == "python":
            from .functions_python_builder import get_builder
            try:
                return get_builder().call_raw(tf.name, rows)
            except Exception as exc:
                raise MultiLanguageError("EXEC_FAILED", str(exc)) from exc
        if tf.language == "sql":
            return _run_sql(tf.source, rows)
        raise MultiLanguageError("NOT_IMPLEMENTED", f"语言 {tf.language!r} 不可执行")


_engine = MultiLanguageTransform()


def get_engine() -> MultiLanguageTransform:
    return _engine
