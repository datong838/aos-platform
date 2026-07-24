"""W2-Q · Action 增强延伸：参数筛选 + 提交标准 + 通知副作用."""
from __future__ import annotations

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


# ─────────────── #61 Action 参数筛选 ───────────────

class ParameterFilter(BaseModel):
    id: str = Field(default_factory=lambda: _uid("pf"))
    action_id: str
    param_name: str
    target_object_type: str = ""
    base_set: str = ""                # 起始集 ID
    search_scope: dict[str, Any] = Field(default_factory=dict)
    security_filter: str = ""
    ordering: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class FilterError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class FilterEngine:
    """Action 参数筛选引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._filters: dict[str, ParameterFilter] = {}
        # 对象集合缓存: object_type -> list[dict]
        self._object_pools: dict[str, list[dict[str, Any]]] = {}
        # Object Set 缓存: set_id -> list[dict]
        self._object_sets: dict[str, list[dict[str, Any]]] = {}

    def register_object_pool(self, object_type: str, objects: list[dict[str, Any]]) -> None:
        with self._lock:
            self._object_pools[object_type] = list(objects)

    def register_object_set(self, set_id: str, objects: list[dict[str, Any]]) -> None:
        with self._lock:
            self._object_sets[set_id] = list(objects)

    def create(self, flt: ParameterFilter) -> ParameterFilter:
        with self._lock:
            self._filters[flt.id] = flt
        return flt

    def get(self, filter_id: str) -> ParameterFilter:
        f = self._filters.get(filter_id)
        if not f:
            raise FilterError("NOT_FOUND", f"筛选 {filter_id} 不存在")
        return f

    def list(self, *, action_id: str | None = None) -> list[ParameterFilter]:
        with self._lock:
            items = list(self._filters.values())
        if action_id:
            items = [f for f in items if f.action_id == action_id]
        return items

    def update(self, filter_id: str, updates: dict[str, Any]) -> ParameterFilter:
        with self._lock:
            f = self._filters.get(filter_id)
            if not f:
                raise FilterError("NOT_FOUND", f"筛选 {filter_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(f, k, v)
            return f

    def delete(self, filter_id: str) -> bool:
        with self._lock:
            if filter_id not in self._filters:
                raise FilterError("NOT_FOUND", f"筛选 {filter_id} 不存在")
            del self._filters[filter_id]
            return True

    def apply(self, filter_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """应用筛选：起始集 → 搜索范围 → 安全筛选 → 排序。"""
        f = self.get(filter_id)
        context = context or {}

        # 1. 起始集
        candidates: list[dict[str, Any]] = []
        if f.base_set and f.base_set in self._object_sets:
            candidates = list(self._object_sets[f.base_set])
        elif f.target_object_type and f.target_object_type in self._object_pools:
            candidates = list(self._object_pools[f.target_object_type])
        else:
            candidates = []

        # 2. 搜索范围（属性=值限定）
        if f.search_scope:
            candidates = [
                obj for obj in candidates
                if self._match_scope(obj, f.search_scope, context)
            ]

        # 3. 安全筛选（简单表达式 field op value）
        if f.security_filter:
            candidates = [
                obj for obj in candidates
                if self._eval_security(obj, f.security_filter, context)
            ]

        # 4. 排序
        if f.ordering:
            for rule in reversed(f.ordering):
                field = rule.get("field", "")
                direction = rule.get("direction", "asc")
                try:
                    candidates.sort(
                        key=lambda o: (o.get(field) is None, o.get(field)),
                        reverse=(direction == "desc"),
                    )
                except TypeError:
                    # 异构类型排序：按字符串
                    candidates.sort(
                        key=lambda o: str(o.get(field, "")),
                        reverse=(direction == "desc"),
                    )

        return {
            "filter_id": filter_id,
            "count": len(candidates),
            "objects": candidates,
        }

    def _match_scope(
        self, obj: dict[str, Any], scope: dict[str, Any], context: dict[str, Any],
    ) -> bool:
        for key, expected in scope.items():
            actual = obj.get(key)
            # 上下文变量替换 {{var}}
            if isinstance(expected, str):
                expected = self._resolve_template(expected, context)
            if actual != expected:
                return False
        return True

    def _eval_security(
        self, obj: dict[str, Any], expr: str, context: dict[str, Any],
    ) -> bool:
        """简单安全筛选表达式：field op value。"""
        expr = expr.strip()
        if not expr:
            return True
        for op in ("!=", ">=", "<=", "==", "=", ">", "<"):
            if op in expr:
                parts = expr.split(op, 1)
                if len(parts) != 2:
                    continue
                field = parts[0].strip()
                target = parts[1].strip().strip("'\"")
                target = self._resolve_template(target, context)
                actual = obj.get(field)
                if op in ("=", "=="):
                    return str(actual) == str(target)
                elif op == "!=":
                    return str(actual) != str(target)
                else:
                    try:
                        actual_n = float(actual)
                        target_n = float(target)
                    except (ValueError, TypeError):
                        return False
                    if op == ">":
                        return actual_n > target_n
                    elif op == "<":
                        return actual_n < target_n
                    elif op == ">=":
                        return actual_n >= target_n
                    elif op == "<=":
                        return actual_n <= target_n
        return True

    def _resolve_template(self, text: str, context: dict[str, Any]) -> str:
        def _replace(m: re.Match) -> str:
            var = m.group(1).strip()
            return str(context.get(var, m.group(0)))
        return re.sub(r"\{\{(\w+)\}\}", _replace, text)

    def reset(self) -> None:
        with self._lock:
            self._filters.clear()
            self._object_pools.clear()
            self._object_sets.clear()


# ─────────────── #62 Action 提交标准可视化 ───────────────

class SubmissionCriteria(BaseModel):
    id: str = Field(default_factory=lambda: _uid("sc"))
    action_id: str
    name: str
    condition_tree: dict[str, Any] = Field(default_factory=dict)
    failure_message: str = ""
    severity: str = "error"  # error / warning
    created_at: str = Field(default_factory=_now)


class CriteriaError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_SEVERITIES = {"error", "warning"}
_VALID_LEAF_OPS = {"=", "==", "!=", ">", "<", ">=", "<=", "contains", "in", "exists"}


class CriteriaEngine:
    """Action 提交标准可视化引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._criteria: dict[str, SubmissionCriteria] = {}

    def create(self, criteria: SubmissionCriteria) -> SubmissionCriteria:
        if criteria.severity not in _VALID_SEVERITIES:
            raise CriteriaError("INVALID_SEVERITY", f"未知严重级别: {criteria.severity}")
        if not criteria.condition_tree:
            raise CriteriaError("EMPTY_TREE", "条件树不能为空")
        with self._lock:
            self._criteria[criteria.id] = criteria
        return criteria

    def get(self, criteria_id: str) -> SubmissionCriteria:
        c = self._criteria.get(criteria_id)
        if not c:
            raise CriteriaError("NOT_FOUND", f"提交标准 {criteria_id} 不存在")
        return c

    def list(self, *, action_id: str | None = None) -> list[SubmissionCriteria]:
        with self._lock:
            items = list(self._criteria.values())
        if action_id:
            items = [c for c in items if c.action_id == action_id]
        return items

    def update(self, criteria_id: str, updates: dict[str, Any]) -> SubmissionCriteria:
        with self._lock:
            c = self._criteria.get(criteria_id)
            if not c:
                raise CriteriaError("NOT_FOUND", f"提交标准 {criteria_id} 不存在")
            if "severity" in updates and updates["severity"] not in _VALID_SEVERITIES:
                raise CriteriaError("INVALID_SEVERITY", f"未知严重级别: {updates['severity']}")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(c, k, v)
            return c

    def delete(self, criteria_id: str) -> bool:
        with self._lock:
            if criteria_id not in self._criteria:
                raise CriteriaError("NOT_FOUND", f"提交标准 {criteria_id} 不存在")
            del self._criteria[criteria_id]
            return True

    def evaluate(
        self, criteria_id: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        c = self.get(criteria_id)
        context = context or {}
        passed = self._eval_node(c.condition_tree, context)
        return {
            "criteria_id": criteria_id,
            "name": c.name,
            "passed": passed,
            "severity": c.severity,
            "failure_message": c.failure_message if not passed else "",
        }

    def _eval_node(self, node: dict[str, Any], context: dict[str, Any]) -> bool:
        op = node.get("op", "").upper()
        if op in ("AND", "OR"):
            children = node.get("children", [])
            if not children:
                return True
            results = [self._eval_node(child, context) for child in children]
            return all(results) if op == "AND" else any(results)
        elif op == "NOT":
            children = node.get("children", [])
            if not children:
                return True
            return not self._eval_node(children[0], context)
        else:
            # 叶子节点
            return self._eval_leaf(node, context)

    def _eval_leaf(self, node: dict[str, Any], context: dict[str, Any]) -> bool:
        field = node.get("field", "")
        op = node.get("op", "=")
        expected = node.get("value")
        actual = context.get(field)

        if op not in _VALID_LEAF_OPS:
            return False

        if op == "exists":
            return (actual is not None) == bool(expected)

        if op == "in":
            if not isinstance(expected, list):
                return False
            return actual in expected

        if op == "contains":
            if actual is None:
                return False
            if isinstance(actual, str):
                return str(expected) in actual
            if isinstance(actual, (list, dict)):
                return expected in actual
            return False

        # 数值/字符串比较
        if op in ("=", "=="):
            return actual == expected
        elif op == "!=":
            return actual != expected
        else:
            try:
                actual_n = float(actual)
                expected_n = float(expected)
            except (ValueError, TypeError):
                return False
            if op == ">":
                return actual_n > expected_n
            elif op == "<":
                return actual_n < expected_n
            elif op == ">=":
                return actual_n >= expected_n
            elif op == "<=":
                return actual_n <= expected_n
        return False

    def reset(self) -> None:
        with self._lock:
            self._criteria.clear()


# ─────────────── #63 Action 通知副作用 ───────────────

class NotificationSideEffect(BaseModel):
    id: str = Field(default_factory=lambda: _uid("nse"))
    action_id: str
    name: str
    recipient_source: str = "static"  # static / parameter / object_property / function
    recipients: list[str] = Field(default_factory=list)
    recipient_ref: str = ""           # 引用键（parameter/object_property）或函数名（function）
    subject_template: str = ""
    body_template: str = ""
    channel: str = "email"            # email / sms / in_app
    created_at: str = Field(default_factory=_now)


class NotificationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_RECIPIENT_SOURCES = {"static", "parameter", "object_property", "function"}
_VALID_CHANNELS = {"email", "sms", "in_app"}


class NotificationEngine:
    """Action 通知副作用引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._effects: dict[str, NotificationSideEffect] = {}
        # 对象缓存: object_type -> {id -> obj}
        self._objects: dict[str, dict[str, dict[str, Any]]] = {}
        # 函数收件人解析器: func_name -> callable(ctx) -> list[str]
        self._functions: dict[str, Any] = {}
        # 派发队列
        self._dispatch_log: list[dict[str, Any]] = []

    def register_object(self, object_type: str, obj: dict[str, Any]) -> None:
        with self._lock:
            self._objects.setdefault(object_type, {})[obj.get("id", "")] = obj

    def register_function(self, func_name: str, func: Any) -> None:
        with self._lock:
            self._functions[func_name] = func

    def create(self, effect: NotificationSideEffect) -> NotificationSideEffect:
        if effect.recipient_source not in _VALID_RECIPIENT_SOURCES:
            raise NotificationError(
                "INVALID_SOURCE", f"未知收件人来源: {effect.recipient_source}",
            )
        if effect.channel not in _VALID_CHANNELS:
            raise NotificationError("INVALID_CHANNEL", f"未知渠道: {effect.channel}")
        with self._lock:
            self._effects[effect.id] = effect
        return effect

    def get(self, effect_id: str) -> NotificationSideEffect:
        e = self._effects.get(effect_id)
        if not e:
            raise NotificationError("NOT_FOUND", f"通知副作用 {effect_id} 不存在")
        return e

    def list(self, *, action_id: str | None = None) -> list[NotificationSideEffect]:
        with self._lock:
            items = list(self._effects.values())
        if action_id:
            items = [e for e in items if e.action_id == action_id]
        return items

    def update(self, effect_id: str, updates: dict[str, Any]) -> NotificationSideEffect:
        with self._lock:
            e = self._effects.get(effect_id)
            if not e:
                raise NotificationError("NOT_FOUND", f"通知副作用 {effect_id} 不存在")
            if "recipient_source" in updates and updates["recipient_source"] not in _VALID_RECIPIENT_SOURCES:
                raise NotificationError(
                    "INVALID_SOURCE", f"未知收件人来源: {updates['recipient_source']}",
                )
            if "channel" in updates and updates["channel"] not in _VALID_CHANNELS:
                raise NotificationError("INVALID_CHANNEL", f"未知渠道: {updates['channel']}")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(e, k, v)
            return e

    def delete(self, effect_id: str) -> bool:
        with self._lock:
            if effect_id not in self._effects:
                raise NotificationError("NOT_FOUND", f"通知副作用 {effect_id} 不存在")
            del self._effects[effect_id]
            return True

    def render(
        self, effect_id: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        e = self.get(effect_id)
        context = context or {}
        recipients = self._resolve_recipients(e, context)
        subject = self._render_template(e.subject_template, context)
        body = self._render_template(e.body_template, context)
        return {
            "effect_id": effect_id,
            "name": e.name,
            "channel": e.channel,
            "recipients": recipients,
            "subject": subject,
            "body": body,
        }

    def dispatch(
        self, effect_id: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rendered = self.render(effect_id, context)
        record = {
            "dispatch_id": _uid("disp"),
            "effect_id": effect_id,
            "channel": rendered["channel"],
            "recipients": rendered["recipients"],
            "subject": rendered["subject"],
            "body": rendered["body"],
            "status": "queued",
            "dispatched_at": _now(),
        }
        with self._lock:
            self._dispatch_log.append(record)
        return record

    def list_dispatches(self, effect_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._dispatch_log)
        if effect_id:
            items = [d for d in items if d["effect_id"] == effect_id]
        return items

    def _resolve_recipients(
        self, e: NotificationSideEffect, context: dict[str, Any],
    ) -> list[str]:
        if e.recipient_source == "static":
            return list(e.recipients)
        elif e.recipient_source == "parameter":
            # recipient_ref 指向 context 中的参数名
            val = context.get(e.recipient_ref, [])
            if isinstance(val, list):
                return [str(v) for v in val]
            return [str(val)] if val else []
        elif e.recipient_source == "object_property":
            # recipient_ref 格式: "object_type.object_id.field"
            parts = e.recipient_ref.split(".")
            if len(parts) == 3:
                otype, oid, field = parts
                obj = self._objects.get(otype, {}).get(oid)
                if obj:
                    val = obj.get(field, [])
                    if isinstance(val, list):
                        return [str(v) for v in val]
                    return [str(val)] if val else []
            return []
        elif e.recipient_source == "function":
            func = self._functions.get(e.recipient_ref)
            if callable(func):
                try:
                    result = func(context)
                    if isinstance(result, list):
                        return [str(v) for v in result]
                    return [str(result)] if result else []
                except Exception:
                    return []
            return []
        return []

    def _render_template(self, template: str, context: dict[str, Any]) -> str:
        if not template:
            return ""
        def _replace(m: re.Match) -> str:
            var = m.group(1).strip()
            return str(context.get(var, m.group(0)))
        return re.sub(r"\{\{(\w+)\}\}", _replace, template)

    def reset(self) -> None:
        with self._lock:
            self._effects.clear()
            self._objects.clear()
            self._functions.clear()
            self._dispatch_log.clear()


# ─────────────── 单例 ───────────────

_filter_engine: FilterEngine | None = None
_criteria_engine: CriteriaEngine | None = None
_notification_engine: NotificationEngine | None = None
_lock = threading.Lock()


def get_filter_engine() -> FilterEngine:
    global _filter_engine
    if _filter_engine is None:
        with _lock:
            if _filter_engine is None:
                _filter_engine = FilterEngine()
    return _filter_engine


def get_criteria_engine() -> CriteriaEngine:
    global _criteria_engine
    if _criteria_engine is None:
        with _lock:
            if _criteria_engine is None:
                _criteria_engine = CriteriaEngine()
    return _criteria_engine


def get_notification_engine() -> NotificationEngine:
    global _notification_engine
    if _notification_engine is None:
        with _lock:
            if _notification_engine is None:
                _notification_engine = NotificationEngine()
    return _notification_engine
