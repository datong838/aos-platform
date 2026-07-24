"""W2-M · Object Explorer 增强：高级搜索 + 保存探索 + 批量导出."""
from __future__ import annotations

import csv
import io
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ─────────────── #48 高级搜索 ───────────────

class SearchError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _tokenize(expr: str) -> list[tuple[str, str]]:
    """将表达式分词。返回 (type, value) 列表。"""
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(expr)
    while i < n:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue
        # 字符串字面量
        if ch in ('"', "'"):
            quote = ch
            j = i + 1
            while j < n and expr[j] != quote:
                j += 1
            if j >= n:
                raise SearchError("PARSE_ERROR", f"未闭合的字符串: 位置 {i}")
            tokens.append(("STRING", expr[i + 1:j]))
            i = j + 1
            continue
        # 数字
        if ch.isdigit() or (ch == "-" and i + 1 < n and expr[i + 1].isdigit()):
            j = i + 1
            while j < n and (expr[j].isdigit() or expr[j] == "."):
                j += 1
            tokens.append(("NUMBER", expr[i:j]))
            i = j
            continue
        # 标识符 / 关键字
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (expr[j].isalnum() or expr[j] in "_."):
                j += 1
            word = expr[i:j]
            upper = word.upper()
            if upper in ("AND", "OR", "NOT", "LIKE", "IN", "LINKS", "TO", "FROM", "WHERE"):
                tokens.append((upper, word))
            else:
                tokens.append(("IDENT", word))
            i = j
            continue
        # 多字符操作符
        two = expr[i:i + 2]
        if two in (">=", "<=", "!=", "==", "~="):
            tokens.append(("OP", two))
            i += 2
            continue
        # 单字符操作符
        if ch in "=<>":
            tokens.append(("OP", ch))
            i += 1
            continue
        if ch == "(":
            tokens.append(("LPAREN", ch))
            i += 1
            continue
        if ch == ")":
            tokens.append(("RPAREN", ch))
            i += 1
            continue
        if ch == ",":
            tokens.append(("COMMA", ch))
            i += 1
            continue
        raise SearchError("PARSE_ERROR", f"无法识别的字符 {ch!r} 于位置 {i}")
    return tokens


class _Parser:
    """递归下降解析器，生成 dict AST。"""

    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> tuple[str, str] | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> tuple[str, str]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> dict[str, Any]:
        node = self._parse_or()
        if self.pos < len(self.tokens):
            raise SearchError("PARSE_ERROR", f"多余的 token: {self.tokens[self.pos]}")
        return node

    def _parse_or(self) -> dict[str, Any]:
        left = self._parse_and()
        while self._peek() and self._peek()[0] == "OR":
            self._advance()
            right = self._parse_and()
            left = {"type": "or", "left": left, "right": right}
        return left

    def _parse_and(self) -> dict[str, Any]:
        left = self._parse_not()
        while self._peek() and self._peek()[0] == "AND":
            self._advance()
            right = self._parse_not()
            left = {"type": "and", "left": left, "right": right}
        return left

    def _parse_not(self) -> dict[str, Any]:
        if self._peek() and self._peek()[0] == "NOT":
            self._advance()
            operand = self._parse_not()
            return {"type": "not", "operand": operand}
        return self._parse_atom()

    def _parse_atom(self) -> dict[str, Any]:
        tok = self._peek()
        if tok is None:
            raise SearchError("PARSE_ERROR", "表达式不完整")
        if tok[0] == "LPAREN":
            self._advance()
            node = self._parse_or()
            if not self._peek() or self._peek()[0] != "RPAREN":
                raise SearchError("PARSE_ERROR", "缺少右括号 )")
            self._advance()
            return node
        if tok[0] == "LINKS":
            return self._parse_links()
        return self._parse_comparison()

    def _parse_links(self) -> dict[str, Any]:
        self._advance()  # LINKS
        direction_tok = self._peek()
        if direction_tok is None or direction_tok[0] not in ("TO", "FROM"):
            raise SearchError("PARSE_ERROR", "LINKS 后需要 TO 或 FROM")
        direction = self._advance()[0]  # TO / FROM
        target_tok = self._peek()
        if target_tok is None or target_tok[0] != "IDENT":
            raise SearchError("PARSE_ERROR", "LINKS TO/FROM 后需要目标类型")
        target_type = self._advance()[1]
        where_clause: dict[str, Any] | None = None
        if self._peek() and self._peek()[0] == "WHERE":
            self._advance()
            where_clause = self._parse_or()
        return {
            "type": "links",
            "direction": direction.lower(),
            "target_type": target_type,
            "where": where_clause,
        }

    def _parse_comparison(self) -> dict[str, Any]:
        field_tok = self._peek()
        if field_tok is None or field_tok[0] != "IDENT":
            raise SearchError("PARSE_ERROR", f"期望字段名，得到 {field_tok}")
        field = self._advance()[1]
        op_tok = self._peek()
        if op_tok is None:
            raise SearchError("PARSE_ERROR", "缺少操作符")
        if op_tok[0] == "OP":
            op = self._advance()[1]
            value = self._parse_value()
            return {"type": "comparison", "field": field, "op": op, "value": value}
        if op_tok[0] == "LIKE":
            self._advance()
            value = self._parse_value()
            return {"type": "comparison", "field": field, "op": "LIKE", "value": value}
        if op_tok[0] == "IN":
            self._advance()
            if not self._peek() or self._peek()[0] != "LPAREN":
                raise SearchError("PARSE_ERROR", "IN 后需要 (")
            self._advance()
            values: list[Any] = []
            while True:
                values.append(self._parse_value())
                nxt = self._peek()
                if nxt is None:
                    raise SearchError("PARSE_ERROR", "IN 列表未闭合")
                if nxt[0] == "COMMA":
                    self._advance()
                    continue
                if nxt[0] == "RPAREN":
                    self._advance()
                    break
            return {"type": "comparison", "field": field, "op": "IN", "value": values}
        raise SearchError("PARSE_ERROR", f"未知操作符 {op_tok}")

    def _parse_value(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise SearchError("PARSE_ERROR", "缺少值")
        if tok[0] == "STRING":
            return self._advance()[1]
        if tok[0] == "NUMBER":
            raw = self._advance()[1]
            if "." in raw:
                return float(raw)
            return int(raw)
        raise SearchError("PARSE_ERROR", f"期望值，得到 {tok}")


def parse_expression(expr: str) -> dict[str, Any]:
    """解析搜索表达式为 AST。"""
    tokens = _tokenize(expr)
    if not tokens:
        raise SearchError("PARSE_ERROR", "空表达式")
    return _Parser(tokens).parse()


def _get_field(obj: dict[str, Any], field: str) -> Any:
    """支持点号路径访问嵌套字段。"""
    parts = field.split(".")
    val: Any = obj
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return None
    return val


def _like_to_regex(pattern: str) -> re.Pattern:
    """将 SQL LIKE 模式（% 通配）转为正则。"""
    regex_parts: list[str] = []
    for ch in pattern:
        if ch == "%":
            regex_parts.append(".*")
        elif ch == "_":
            regex_parts.append(".")
        else:
            regex_parts.append(re.escape(ch))
    return re.compile("^" + "".join(regex_parts) + "$", re.IGNORECASE)


def _eval_comparison(node: dict[str, Any], obj: dict[str, Any]) -> bool:
    field = node["field"]
    op = node["op"]
    value = node["value"]
    actual = _get_field(obj, field)

    if op in ("=", "=="):
        return actual == value
    if op == "!=":
        return actual != value
    if op == ">":
        return actual is not None and value is not None and actual > value
    if op == ">=":
        return actual is not None and value is not None and actual >= value
    if op == "<":
        return actual is not None and value is not None and actual < value
    if op == "<=":
        return actual is not None and value is not None and actual <= value
    if op == "LIKE":
        if actual is None:
            return False
        return bool(_like_to_regex(str(value)).match(str(actual)))
    if op == "~=":
        if actual is None:
            return False
        try:
            return bool(re.search(str(value), str(actual)))
        except re.error:
            return False
    if op == "IN":
        return actual in value
    raise SearchError("EVAL_ERROR", f"未知操作符 {op}")


def _eval_ast(node: dict[str, Any], obj: dict[str, Any], links: dict[str, list[dict]] | None = None) -> bool:
    ntype = node["type"]
    if ntype == "and":
        return _eval_ast(node["left"], obj, links) and _eval_ast(node["right"], obj, links)
    if ntype == "or":
        return _eval_ast(node["left"], obj, links) or _eval_ast(node["right"], obj, links)
    if ntype == "not":
        return not _eval_ast(node["operand"], obj, links)
    if ntype == "comparison":
        return _eval_comparison(node, obj)
    if ntype == "links":
        # LINKS 筛选需要外部提供邻接信息
        if links is None:
            return False
        obj_id = obj.get("id") or obj.get("_id") or ""
        direction = node["direction"]  # to / from
        target_type = node["target_type"]
        where_clause = node["where"]
        neighbors = links.get(obj_id, [])
        for neighbor in neighbors:
            if neighbor.get("_type") != target_type and neighbor.get("type") != target_type:
                continue
            if direction == "to" and not neighbor.get("_is_incoming", False):
                continue
            if direction == "from" and neighbor.get("_is_incoming", False):
                continue
            if where_clause is None or _eval_ast(where_clause, neighbor, links):
                return True
        return False
    raise SearchError("EVAL_ERROR", f"未知节点类型 {ntype}")


class SearchEngine:
    """高级搜索引擎：表达式解析 + 求值。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # 对象存储: object_type -> list[dict]
        self._objects: dict[str, list[dict[str, Any]]] = {}
        # 链接邻接: src_id -> [{dst_obj, _is_incoming=False}, ...] + dst_id -> [{src_obj, _is_incoming=True}, ...]
        self._links: dict[str, list[dict[str, Any]]] = {}

    def index(self, object_type: str, objects: list[dict[str, Any]]) -> None:
        """索引对象列表。"""
        with self._lock:
            self._objects[object_type] = list(objects)

    def add_link(self, src_id: str, dst_id: str, dst_obj: dict[str, Any] | None = None) -> None:
        """添加链接关系。"""
        with self._lock:
            entry = dict(dst_obj or {})
            entry["_is_incoming"] = False
            self._links.setdefault(src_id, []).append(entry)
            # 反向
            rev = dict(dst_obj or {})
            rev["_is_incoming"] = True
            rev["_type"] = rev.get("type", "")
            self._links.setdefault(dst_id, []).append(rev)

    def search(
        self,
        object_type: str,
        expression: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """执行搜索。"""
        ast = parse_expression(expression)
        with self._lock:
            objects = list(self._objects.get(object_type, []))
            links = dict(self._links)
        matched = [obj for obj in objects if _eval_ast(ast, obj, links)]
        total = len(matched)
        page = matched[offset:offset + limit]
        return {
            "object_type": object_type,
            "total": total,
            "objects": page,
            "parsed_expression": ast,
            "limit": limit,
            "offset": offset,
        }

    def reset(self) -> None:
        with self._lock:
            self._objects.clear()
            self._links.clear()


# ─────────────── #49 保存探索 ───────────────

class SavedExploration(BaseModel):
    id: str = Field(default_factory=lambda: _uid("exp"))
    name: str
    object_type: str
    kind: str = "dynamic"       # dynamic / static
    visibility: str = "private" # private / public
    owner: str = ""
    query: dict[str, Any] = Field(default_factory=dict)
    object_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ExplorationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ExplorationEngine:
    """保存探索管理引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._explorations: dict[str, SavedExploration] = {}

    def create(self, exp: SavedExploration) -> SavedExploration:
        with self._lock:
            self._explorations[exp.id] = exp
        return exp

    def get(self, exp_id: str) -> SavedExploration:
        exp = self._explorations.get(exp_id)
        if not exp:
            raise ExplorationError("NOT_FOUND", f"探索 {exp_id} 不存在")
        return exp

    def list(
        self,
        *,
        owner: str | None = None,
        object_type: str | None = None,
        kind: str | None = None,
        include_public: bool = True,
    ) -> list[SavedExploration]:
        with self._lock:
            items = list(self._explorations.values())
        result: list[SavedExploration] = []
        for e in items:
            if owner and e.owner != owner and not (include_public and e.visibility == "public"):
                continue
            if object_type and e.object_type != object_type:
                continue
            if kind and e.kind != kind:
                continue
            result.append(e)
        return result

    def update(self, exp_id: str, updates: dict[str, Any]) -> SavedExploration:
        with self._lock:
            exp = self._explorations.get(exp_id)
            if not exp:
                raise ExplorationError("NOT_FOUND", f"探索 {exp_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(exp, k, v)
            exp.updated_at = _now()
            return exp

    def delete(self, exp_id: str) -> bool:
        with self._lock:
            if exp_id not in self._explorations:
                raise ExplorationError("NOT_FOUND", f"探索 {exp_id} 不存在")
            del self._explorations[exp_id]
            return True

    def execute(self, exp_id: str, search_engine: SearchEngine) -> dict[str, Any]:
        """执行动态探索。"""
        exp = self.get(exp_id)
        if exp.kind != "dynamic":
            raise ExplorationError("NOT_DYNAMIC", f"探索 {exp_id} 不是动态探索")
        expression = exp.query.get("expression", "")
        limit = exp.query.get("limit", 100)
        offset = exp.query.get("offset", 0)
        return search_engine.search(exp.object_type, expression, limit=limit, offset=offset)

    def reset(self) -> None:
        with self._lock:
            self._explorations.clear()


# ─────────────── #50 批量导出 ───────────────

class ExportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ExportEngine:
    """批量导出引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def export(
        self,
        object_type: str,
        objects: list[dict[str, Any]],
        *,
        fmt: str = "csv",
        columns: list[str] | None = None,
        object_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """导出对象数据。"""
        if fmt not in ("csv", "excel", "json"):
            raise ExportError("INVALID_FORMAT", f"不支持的格式: {fmt}")

        # 按 ID 筛选
        if object_ids:
            id_set = set(object_ids)
            objects = [o for o in objects if (o.get("id") or o.get("_id")) in id_set]

        # 确定列
        if not columns:
            col_set: set[str] = set()
            for o in objects:
                col_set.update(k for k in o.keys() if not k.startswith("_"))
            columns = sorted(col_set)

        rows: list[list[Any]] = []
        for obj in objects:
            rows.append([_get_field(obj, c) for c in columns])

        result: dict[str, Any] = {
            "object_type": object_type,
            "format": fmt,
            "total_rows": len(rows),
            "columns": columns,
            "rows": rows,
        }

        if fmt == "csv":
            result["content"] = self._to_csv(columns, rows)
        elif fmt == "excel":
            # Excel 兼容：CSV + BOM
            result["content"] = "\ufeff" + self._to_csv(columns, rows)
        elif fmt == "json":
            result["content"] = [
                {col: row[i] for i, col in enumerate(columns)}
                for row in rows
            ]

        return result

    def _to_csv(self, columns: list[str], rows: list[list[Any]]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([("" if v is None else str(v)) for v in row])
        return output.getvalue()

    def bulk_update(
        self,
        objects: list[dict[str, Any]],
        updates: dict[str, Any],
        *,
        object_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """批量更新对象。"""
        updated: list[dict[str, Any]] = []
        id_set = set(object_ids) if object_ids else None
        for obj in objects:
            oid = obj.get("id") or obj.get("_id")
            if id_set and oid not in id_set:
                continue
            for k, v in updates.items():
                obj[k] = v
            updated.append(obj)
        return {
            "updated": len(updated),
            "objects": updated,
        }

    def bulk_delete(
        self,
        objects: list[dict[str, Any]],
        *,
        object_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """批量删除对象（返回剩余列表）。"""
        id_set = set(object_ids) if object_ids else None
        remaining: list[dict[str, Any]] = []
        deleted = 0
        for obj in objects:
            oid = obj.get("id") or obj.get("_id")
            if id_set and oid in id_set:
                deleted += 1
            else:
                remaining.append(obj)
        return {
            "deleted": deleted,
            "remaining": len(remaining),
            "objects": remaining,
        }

    def reset(self) -> None:
        pass


# ─────────────── 单例 ───────────────

_search_engine: SearchEngine | None = None
_exploration_engine: ExplorationEngine | None = None
_export_engine: ExportEngine | None = None
_lock = threading.Lock()


def get_search_engine() -> SearchEngine:
    global _search_engine
    if _search_engine is None:
        with _lock:
            if _search_engine is None:
                _search_engine = SearchEngine()
    return _search_engine


def get_exploration_engine() -> ExplorationEngine:
    global _exploration_engine
    if _exploration_engine is None:
        with _lock:
            if _exploration_engine is None:
                _exploration_engine = ExplorationEngine()
    return _exploration_engine


def get_export_engine() -> ExportEngine:
    global _export_engine
    if _export_engine is None:
        with _lock:
            if _export_engine is None:
                _export_engine = ExportEngine()
    return _export_engine
