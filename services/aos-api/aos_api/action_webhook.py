"""W2-R · Action Webhook/Sections/Revert：Webhook 副作用 + Section 分组 + 撤销规则."""
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


# ─────────────── #64 Action Webhook 副作用 ───────────────

class WebhookSideEffect(BaseModel):
    id: str = Field(default_factory=lambda: _uid("wh"))
    action_id: str
    name: str
    url: str
    mode: str = "data_output"        # data_output / side_effect
    method: str = "POST"             # GET/POST/PUT/PATCH
    headers: dict[str, str] = Field(default_factory=dict)
    input_mapping: dict[str, Any] = Field(default_factory=dict)
    output_mapping: dict[str, Any] = Field(default_factory=dict)
    auth_type: str = "none"          # none / bearer / basic / hmac
    auth_config: dict[str, Any] = Field(default_factory=dict)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class WebhookError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_MODES = {"data_output", "side_effect"}
_VALID_METHODS = {"GET", "POST", "PUT", "PATCH"}
_VALID_AUTH = {"none", "bearer", "basic", "hmac"}


class WebhookEngine:
    """Action Webhook 副作用引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._effects: dict[str, WebhookSideEffect] = {}

    def create(self, effect: WebhookSideEffect) -> WebhookSideEffect:
        if effect.mode not in _VALID_MODES:
            raise WebhookError("INVALID_MODE", f"未知模式: {effect.mode}")
        if effect.method.upper() not in _VALID_METHODS:
            raise WebhookError("INVALID_METHOD", f"未知方法: {effect.method}")
        if effect.auth_type not in _VALID_AUTH:
            raise WebhookError("INVALID_AUTH", f"未知认证类型: {effect.auth_type}")
        effect.method = effect.method.upper()
        with self._lock:
            self._effects[effect.id] = effect
        return effect

    def get(self, effect_id: str) -> WebhookSideEffect:
        e = self._effects.get(effect_id)
        if not e:
            raise WebhookError("NOT_FOUND", f"Webhook 副作用 {effect_id} 不存在")
        return e

    def list(self, *, action_id: str | None = None) -> list[WebhookSideEffect]:
        with self._lock:
            items = list(self._effects.values())
        if action_id:
            items = [e for e in items if e.action_id == action_id]
        return items

    def update(self, effect_id: str, updates: dict[str, Any]) -> WebhookSideEffect:
        with self._lock:
            e = self._effects.get(effect_id)
            if not e:
                raise WebhookError("NOT_FOUND", f"Webhook 副作用 {effect_id} 不存在")
            if "mode" in updates and updates["mode"] not in _VALID_MODES:
                raise WebhookError("INVALID_MODE", f"未知模式: {updates['mode']}")
            if "method" in updates and updates["method"].upper() not in _VALID_METHODS:
                raise WebhookError("INVALID_METHOD", f"未知方法: {updates['method']}")
            if "auth_type" in updates and updates["auth_type"] not in _VALID_AUTH:
                raise WebhookError("INVALID_AUTH", f"未知认证类型: {updates['auth_type']}")
            for k, v in updates.items():
                if k == "method":
                    v = v.upper()
                if k not in ("id", "created_at"):
                    setattr(e, k, v)
            return e

    def delete(self, effect_id: str) -> bool:
        with self._lock:
            if effect_id not in self._effects:
                raise WebhookError("NOT_FOUND", f"Webhook 副作用 {effect_id} 不存在")
            del self._effects[effect_id]
            return True

    def build_request(
        self, effect_id: str, action_params: dict[str, Any],
    ) -> dict[str, Any]:
        """根据 input_mapping 构建 Webhook 请求 payload。"""
        e = self.get(effect_id)
        payload: dict[str, Any] = {}
        for webhook_field, source_expr in e.input_mapping.items():
            payload[webhook_field] = self._resolve_source(source_expr, action_params)
        # 构造完整请求
        request: dict[str, Any] = {
            "url": self._render_template(e.url, action_params),
            "method": e.method,
            "headers": dict(e.headers),
            "payload": payload,
            "auth_type": e.auth_type,
        }
        # 添加 auth 头
        if e.auth_type == "bearer":
            token = e.auth_config.get("token", "")
            request["headers"]["Authorization"] = f"Bearer {token}"
        elif e.auth_type == "basic":
            import base64
            user = e.auth_config.get("username", "")
            pwd = e.auth_config.get("password", "")
            cred = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            request["headers"]["Authorization"] = f"Basic {cred}"
        return request

    def apply_response(
        self, effect_id: str, response: dict[str, Any],
    ) -> dict[str, Any]:
        """将 Webhook 响应按 output_mapping 写回 Action 输出字段。"""
        e = self.get(effect_id)
        if e.mode != "data_output":
            raise WebhookError(
                "NOT_DATA_OUTPUT_MODE",
                "仅 data_output 模式支持 apply_response",
            )
        output: dict[str, Any] = {}
        for action_field, response_path in e.output_mapping.items():
            output[action_field] = self._extract_path(response, response_path)
        return output

    def _resolve_source(self, source_expr: Any, params: dict[str, Any]) -> Any:
        """source_expr 可以是：直接值 / "{{param_name}}" / 嵌套字典。"""
        if isinstance(source_expr, str):
            return self._render_template(source_expr, params)
        if isinstance(source_expr, dict):
            return {k: self._resolve_source(v, params) for k, v in source_expr.items()}
        if isinstance(source_expr, list):
            return [self._resolve_source(v, params) for v in source_expr]
        return source_expr

    def _render_template(self, text: str, params: dict[str, Any]) -> str:
        if not isinstance(text, str):
            return text
        def _replace(m: re.Match) -> str:
            var = m.group(1).strip()
            val = params.get(var, m.group(0))
            return str(val)
        return re.sub(r"\{\{(\w+)\}\}", _replace, text)

    def _extract_path(self, data: dict[str, Any], path: str) -> Any:
        """从响应中按点分路径取值。"""
        if not path:
            return data
        current: Any = data
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def reset(self) -> None:
        with self._lock:
            self._effects.clear()


# ─────────────── #65 Action Sections 分组 ───────────────

class SectionField(BaseModel):
    param_name: str
    span: int = 1  # 1=半宽（双列时）, 2=全宽


class ActionSection(BaseModel):
    id: str = Field(default_factory=lambda: _uid("sec"))
    action_id: str
    name: str
    display_name: str = ""
    layout: str = "single_column"  # single_column / double_column
    collapsed: bool = False
    visible_condition: str = ""
    fields: list[SectionField] = Field(default_factory=list)
    order: int = 0
    created_at: str = Field(default_factory=_now)


class SectionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_LAYOUTS = {"single_column", "double_column"}


class SectionEngine:
    """Action Section 分组引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sections: dict[str, ActionSection] = {}

    def create(self, section: ActionSection) -> ActionSection:
        if section.layout not in _VALID_LAYOUTS:
            raise SectionError("INVALID_LAYOUT", f"未知布局: {section.layout}")
        with self._lock:
            self._sections[section.id] = section
        return section

    def get(self, section_id: str) -> ActionSection:
        s = self._sections.get(section_id)
        if not s:
            raise SectionError("NOT_FOUND", f"Section {section_id} 不存在")
        return s

    def list(self, *, action_id: str | None = None) -> list[ActionSection]:
        with self._lock:
            items = list(self._sections.values())
        if action_id:
            items = [s for s in items if s.action_id == action_id]
        items.sort(key=lambda s: s.order)
        return items

    def update(self, section_id: str, updates: dict[str, Any]) -> ActionSection:
        with self._lock:
            s = self._sections.get(section_id)
            if not s:
                raise SectionError("NOT_FOUND", f"Section {section_id} 不存在")
            if "layout" in updates and updates["layout"] not in _VALID_LAYOUTS:
                raise SectionError("INVALID_LAYOUT", f"未知布局: {updates['layout']}")
            for k, v in updates.items():
                if k == "fields" and isinstance(v, list):
                    s.fields = [SectionField(**f) if isinstance(f, dict) else f for f in v]
                elif k not in ("id", "created_at"):
                    setattr(s, k, v)
            return s

    def delete(self, section_id: str) -> bool:
        with self._lock:
            if section_id not in self._sections:
                raise SectionError("NOT_FOUND", f"Section {section_id} 不存在")
            del self._sections[section_id]
            return True

    def reorder(self, action_id: str, ordered_ids: list[str]) -> list[ActionSection]:
        """批量重排序。"""
        with self._lock:
            for idx, sid in enumerate(ordered_ids):
                s = self._sections.get(sid)
                if s and s.action_id == action_id:
                    s.order = idx
            items = [s for s in self._sections.values() if s.action_id == action_id]
            items.sort(key=lambda s: s.order)
            return items

    def evaluate_visibility(
        self, section_id: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        s = self.get(section_id)
        context = context or {}
        visible = True
        if s.visible_condition:
            visible = self._eval_condition(s.visible_condition, context)
        return {
            "section_id": section_id,
            "name": s.name,
            "visible": visible,
            "collapsed": s.collapsed,
        }

    def _eval_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """简单条件评估（同 OverrideEngine 风格）。"""
        condition = condition.strip()
        if not condition:
            return True
        for op in ("!=", ">=", "<=", "==", "=", ">", "<"):
            if op in condition:
                parts = condition.split(op, 1)
                if len(parts) != 2:
                    continue
                field = parts[0].strip()
                target = parts[1].strip().strip("'\"")
                actual = context.get(field)
                if op in ("=", "=="):
                    return str(actual) == target
                elif op == "!=":
                    return str(actual) != target
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
        return False

    def reset(self) -> None:
        with self._lock:
            self._sections.clear()


# ─────────────── #66 Action 撤销（Revert） ───────────────

class RevertRule(BaseModel):
    id: str = Field(default_factory=lambda: _uid("rr"))
    action_id: str
    name: str
    revert_window_seconds: int = 0  # 0=不限时
    pre_revert_check: dict[str, Any] = Field(default_factory=dict)
    on_revert_action_id: str = ""
    requires_confirmation: bool = True
    created_at: str = Field(default_factory=_now)


class RevertRecord(BaseModel):
    id: str = Field(default_factory=lambda: _uid("rev"))
    original_action_id: str
    original_submission_id: str
    revert_rule_id: str
    status: str = "pending"  # pending / eligible / in_progress / completed / failed / blocked
    reason: str = ""
    created_at: str = Field(default_factory=_now)
    completed_at: str = ""


class RevertError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_STATUSES = {"pending", "eligible", "in_progress", "completed", "failed", "blocked"}
_TRANSITIONS = {
    "pending": {"eligible", "blocked"},
    "eligible": {"in_progress", "blocked"},
    "in_progress": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
    "blocked": set(),
}


class RevertEngine:
    """Action 撤销引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: dict[str, RevertRule] = {}
        self._records: dict[str, RevertRecord] = {}

    def create_rule(self, rule: RevertRule) -> RevertRule:
        with self._lock:
            self._rules[rule.id] = rule
        return rule

    def get_rule(self, rule_id: str) -> RevertRule:
        r = self._rules.get(rule_id)
        if not r:
            raise RevertError("NOT_FOUND", f"撤销规则 {rule_id} 不存在")
        return r

    def list_rules(self, *, action_id: str | None = None) -> list[RevertRule]:
        with self._lock:
            items = list(self._rules.values())
        if action_id:
            items = [r for r in items if r.action_id == action_id]
        return items

    def update_rule(self, rule_id: str, updates: dict[str, Any]) -> RevertRule:
        with self._lock:
            r = self._rules.get(rule_id)
            if not r:
                raise RevertError("NOT_FOUND", f"撤销规则 {rule_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(r, k, v)
            return r

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id not in self._rules:
                raise RevertError("NOT_FOUND", f"撤销规则 {rule_id} 不存在")
            del self._rules[rule_id]
            return True

    def check(
        self,
        rule_id: str,
        submission_context: dict[str, Any],
    ) -> dict[str, Any]:
        """检查提交是否符合撤销条件。"""
        r = self.get_rule(rule_id)
        submission_context = submission_context or {}
        # 1. 时间窗口检查
        submitted_at = submission_context.get("submitted_at")
        if r.revert_window_seconds > 0 and submitted_at:
            try:
                # 支持 ISO 字符串或 epoch 秒
                if isinstance(submitted_at, str):
                    sub_dt = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
                    elapsed = (datetime.now(timezone.utc) - sub_dt).total_seconds()
                else:
                    elapsed = datetime.now(timezone.utc).timestamp() - float(submitted_at)
                if elapsed > r.revert_window_seconds:
                    return {
                        "rule_id": rule_id,
                        "eligible": False,
                        "reason": f"撤销窗口已过（{int(elapsed)}s > {r.revert_window_seconds}s）",
                    }
            except (ValueError, TypeError):
                pass
        # 2. 条件检查
        if r.pre_revert_check:
            passed = self._eval_node(r.pre_revert_check, submission_context)
            if not passed:
                return {
                    "rule_id": rule_id,
                    "eligible": False,
                    "reason": "前置条件未满足",
                }
        return {
            "rule_id": rule_id,
            "eligible": True,
            "reason": "",
            "requires_confirmation": r.requires_confirmation,
        }

    def execute(
        self,
        rule_id: str,
        submission_id: str,
        submission_context: dict[str, Any] | None = None,
    ) -> RevertRecord:
        """执行撤销，生成 RevertRecord（状态机：pending → eligible → in_progress → completed）。"""
        r = self.get_rule(rule_id)
        submission_context = submission_context or {}
        check_result = self.check(rule_id, submission_context)
        record = RevertRecord(
            original_action_id=r.action_id,
            original_submission_id=submission_id,
            revert_rule_id=rule_id,
            status="pending",
            created_at=_now(),
        )
        if not check_result["eligible"]:
            record.status = "blocked"
            record.reason = check_result["reason"]
        else:
            record.status = "completed"
            record.reason = "撤销已执行"
            record.completed_at = _now()
        with self._lock:
            self._records[record.id] = record
        return record

    def list_records(
        self,
        *,
        rule_id: str | None = None,
        submission_id: str | None = None,
        status: str | None = None,
    ) -> list[RevertRecord]:
        with self._lock:
            items = list(self._records.values())
        if rule_id:
            items = [r for r in items if r.revert_rule_id == rule_id]
        if submission_id:
            items = [r for r in items if r.original_submission_id == submission_id]
        if status:
            items = [r for r in items if r.status == status]
        return items

    def get_record(self, record_id: str) -> RevertRecord:
        rec = self._records.get(record_id)
        if not rec:
            raise RevertError("NOT_FOUND", f"撤销记录 {record_id} 不存在")
        return rec

    def update_record_status(self, record_id: str, new_status: str) -> RevertRecord:
        if new_status not in _VALID_STATUSES:
            raise RevertError("INVALID_STATUS", f"未知状态: {new_status}")
        with self._lock:
            rec = self._records.get(record_id)
            if not rec:
                raise RevertError("NOT_FOUND", f"撤销记录 {record_id} 不存在")
            allowed = _TRANSITIONS.get(rec.status, set())
            if new_status not in allowed:
                raise RevertError(
                    "INVALID_TRANSITION",
                    f"不允许的状态转换: {rec.status} → {new_status}",
                )
            rec.status = new_status
            if new_status in ("completed", "failed", "blocked"):
                rec.completed_at = _now()
            return rec

    def _eval_node(self, node: dict[str, Any], context: dict[str, Any]) -> bool:
        op = node.get("op", "").upper()
        if op in ("AND", "OR"):
            children = node.get("children", [])
            if not children:
                return True
            results = [self._eval_node(c, context) for c in children]
            return all(results) if op == "AND" else any(results)
        elif op == "NOT":
            children = node.get("children", [])
            if not children:
                return True
            return not self._eval_node(children[0], context)
        else:
            return self._eval_leaf(node, context)

    def _eval_leaf(self, node: dict[str, Any], context: dict[str, Any]) -> bool:
        field = node.get("field", "")
        op = node.get("op", "=")
        expected = node.get("value")
        actual = context.get(field)
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
            self._rules.clear()
            self._records.clear()


# ─────────────── 单例 ───────────────

_webhook_engine: WebhookEngine | None = None
_section_engine: SectionEngine | None = None
_revert_engine: RevertEngine | None = None
_lock = threading.Lock()


def get_webhook_engine() -> WebhookEngine:
    global _webhook_engine
    if _webhook_engine is None:
        with _lock:
            if _webhook_engine is None:
                _webhook_engine = WebhookEngine()
    return _webhook_engine


def get_section_engine() -> SectionEngine:
    global _section_engine
    if _section_engine is None:
        with _lock:
            if _section_engine is None:
                _section_engine = SectionEngine()
    return _section_engine


def get_revert_engine() -> RevertEngine:
    global _revert_engine
    if _revert_engine is None:
        with _lock:
            if _revert_engine is None:
                _revert_engine = RevertEngine()
    return _revert_engine
