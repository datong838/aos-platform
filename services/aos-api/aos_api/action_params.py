"""W2-P · Action 参数增强：参数约束 + 默认值 + 条件覆盖."""
from __future__ import annotations

import os
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


# ─────────────── #58 Action 参数约束 ───────────────

class ParameterConstraint(BaseModel):
    id: str = Field(default_factory=lambda: _uid("pc"))
    action_id: str
    param_name: str
    constraint_type: str  # user_input / multiple_choice / object_set
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class ConstraintError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_CONSTRAINT_TYPES = {"user_input", "multiple_choice", "object_set"}


class ConstraintEngine:
    """Action 参数约束引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._constraints: dict[str, ParameterConstraint] = {}
        # Object Set 缓存: object_set_id -> list[dict]
        self._object_sets: dict[str, list[dict[str, Any]]] = {}

    def register_object_set(self, set_id: str, objects: list[dict[str, Any]]) -> None:
        with self._lock:
            self._object_sets[set_id] = list(objects)

    def create(self, constraint: ParameterConstraint) -> ParameterConstraint:
        if constraint.constraint_type not in _VALID_CONSTRAINT_TYPES:
            raise ConstraintError(
                "INVALID_TYPE",
                f"未知约束类型: {constraint.constraint_type}",
            )
        with self._lock:
            self._constraints[constraint.id] = constraint
        return constraint

    def get(self, constraint_id: str) -> ParameterConstraint:
        c = self._constraints.get(constraint_id)
        if not c:
            raise ConstraintError("NOT_FOUND", f"约束 {constraint_id} 不存在")
        return c

    def list(self, *, action_id: str | None = None) -> list[ParameterConstraint]:
        with self._lock:
            items = list(self._constraints.values())
        if action_id:
            items = [c for c in items if c.action_id == action_id]
        return items

    def update(self, constraint_id: str, updates: dict[str, Any]) -> ParameterConstraint:
        with self._lock:
            c = self._constraints.get(constraint_id)
            if not c:
                raise ConstraintError("NOT_FOUND", f"约束 {constraint_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(c, k, v)
            return c

    def delete(self, constraint_id: str) -> bool:
        with self._lock:
            if constraint_id not in self._constraints:
                raise ConstraintError("NOT_FOUND", f"约束 {constraint_id} 不存在")
            del self._constraints[constraint_id]
            return True

    def validate_value(self, constraint_id: str, value: Any) -> dict[str, Any]:
        """验证值是否符合约束。"""
        c = self.get(constraint_id)
        if c.constraint_type == "user_input":
            return self._validate_user_input(c, value)
        elif c.constraint_type == "multiple_choice":
            return self._validate_multiple_choice(c, value)
        elif c.constraint_type == "object_set":
            return self._validate_object_set(c, value)
        return {"valid": True}

    def _validate_user_input(self, c: ParameterConstraint, value: Any) -> dict[str, Any]:
        config = c.config
        errors: list[str] = []
        # min/max for numeric
        if "min" in config and isinstance(value, (int, float)):
            if value < config["min"]:
                errors.append(f"值 {value} 小于最小值 {config['min']}")
        if "max" in config and isinstance(value, (int, float)):
            if value > config["max"]:
                errors.append(f"值 {value} 大于最大值 {config['max']}")
        # pattern for string
        if "pattern" in config and isinstance(value, str):
            if not re.match(config["pattern"], value):
                errors.append(f"值 '{value}' 不匹配模式 {config['pattern']}")
        # required
        if config.get("required", False) and (value is None or value == ""):
            errors.append("值不能为空")
        return {"valid": len(errors) == 0, "errors": errors}

    def _validate_multiple_choice(self, c: ParameterConstraint, value: Any) -> dict[str, Any]:
        options = c.config.get("options", [])
        if isinstance(value, list):
            invalid = [v for v in value if v not in options]
            return {"valid": len(invalid) == 0, "errors": [f"无效选项: {v}" for v in invalid]}
        if value not in options:
            return {"valid": False, "errors": [f"值 {value} 不在选项中"]}
        return {"valid": True, "errors": []}

    def _validate_object_set(self, c: ParameterConstraint, value: Any) -> dict[str, Any]:
        set_id = c.config.get("object_set_id", "")
        objects = self._object_sets.get(set_id, [])
        key_field = c.config.get("key_field", "id")
        valid_keys = {o.get(key_field) for o in objects}
        if isinstance(value, list):
            invalid = [v for v in value if v not in valid_keys]
            return {"valid": len(invalid) == 0, "errors": [f"无效对象 ID: {v}" for v in invalid]}
        if value not in valid_keys:
            return {"valid": False, "errors": [f"对象 {value} 不在 Object Set 中"]}
        return {"valid": True, "errors": []}

    def get_options(self, constraint_id: str) -> list[Any]:
        """获取约束的选项列表。"""
        c = self.get(constraint_id)
        if c.constraint_type == "multiple_choice":
            return c.config.get("options", [])
        elif c.constraint_type == "object_set":
            set_id = c.config.get("object_set_id", "")
            key_field = c.config.get("key_field", "id")
            return [o.get(key_field) for o in self._object_sets.get(set_id, [])]
        return []

    def reset(self) -> None:
        with self._lock:
            self._constraints.clear()
            self._object_sets.clear()


# ─────────────── #59 Action 参数默认值 ───────────────

class ParameterDefault(BaseModel):
    id: str = Field(default_factory=lambda: _uid("pd"))
    action_id: str
    param_name: str
    source: str           # static / object_property / type_class / environment
    value: Any = None     # 静态值或引用键
    fallback: Any = None
    created_at: str = Field(default_factory=_now)


class DefaultError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_SOURCES = {"static", "object_property", "type_class", "environment"}

# 类型类默认值
_TYPE_CLASS_DEFAULTS: dict[str, Any] = {
    "String": "",
    "Integer": 0,
    "Float": 0.0,
    "Boolean": False,
    "currency": 0,
    "percentage": 0,
}


class DefaultEngine:
    """Action 参数默认值引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._defaults: dict[str, ParameterDefault] = {}
        # 对象缓存: object_type -> {id -> obj}
        self._objects: dict[str, dict[str, dict[str, Any]]] = {}

    def register_object(self, object_type: str, obj: dict[str, Any]) -> None:
        with self._lock:
            self._objects.setdefault(object_type, {})[obj.get("id", "")] = obj

    def create(self, default: ParameterDefault) -> ParameterDefault:
        if default.source not in _VALID_SOURCES:
            raise DefaultError("INVALID_SOURCE", f"未知来源: {default.source}")
        with self._lock:
            self._defaults[default.id] = default
        return default

    def get(self, default_id: str) -> ParameterDefault:
        d = self._defaults.get(default_id)
        if not d:
            raise DefaultError("NOT_FOUND", f"默认值 {default_id} 不存在")
        return d

    def list(self, *, action_id: str | None = None) -> list[ParameterDefault]:
        with self._lock:
            items = list(self._defaults.values())
        if action_id:
            items = [d for d in items if d.action_id == action_id]
        return items

    def update(self, default_id: str, updates: dict[str, Any]) -> ParameterDefault:
        with self._lock:
            d = self._defaults.get(default_id)
            if not d:
                raise DefaultError("NOT_FOUND", f"默认值 {default_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(d, k, v)
            return d

    def delete(self, default_id: str) -> bool:
        with self._lock:
            if default_id not in self._defaults:
                raise DefaultError("NOT_FOUND", f"默认值 {default_id} 不存在")
            del self._defaults[default_id]
            return True

    def resolve(self, default_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """解析默认值。"""
        d = self.get(default_id)
        context = context or {}
        value: Any = None
        resolved = True

        if d.source == "static":
            value = d.value
        elif d.source == "object_property":
            # value 格式: "object_type.object_id.field"
            parts = str(d.value).split(".")
            if len(parts) == 3:
                otype, oid, field = parts
                obj = self._objects.get(otype, {}).get(oid)
                if obj:
                    value = obj.get(field)
                else:
                    resolved = False
            else:
                resolved = False
        elif d.source == "type_class":
            value = _TYPE_CLASS_DEFAULTS.get(str(d.value), d.fallback)
        elif d.source == "environment":
            env_key = str(d.value)
            value = os.environ.get(env_key)
            if value is None:
                resolved = False

        if not resolved or value is None:
            value = d.fallback

        return {
            "default_id": default_id,
            "source": d.source,
            "value": value,
            "resolved": resolved,
        }

    def reset(self) -> None:
        with self._lock:
            self._defaults.clear()
            self._objects.clear()


# ─────────────── #60 Action 参数覆盖 ───────────────

class ParameterOverride(BaseModel):
    id: str = Field(default_factory=lambda: _uid("po"))
    action_id: str
    param_name: str
    condition: str        # 触发条件表达式
    overrides: dict[str, Any] = Field(default_factory=dict)  # {visible, disabled, required}
    created_at: str = Field(default_factory=_now)


class OverrideError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class OverrideEngine:
    """Action 参数条件覆盖引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._overrides: dict[str, ParameterOverride] = {}

    def create(self, override: ParameterOverride) -> ParameterOverride:
        with self._lock:
            self._overrides[override.id] = override
        return override

    def get(self, override_id: str) -> ParameterOverride:
        o = self._overrides.get(override_id)
        if not o:
            raise OverrideError("NOT_FOUND", f"覆盖 {override_id} 不存在")
        return o

    def list(self, *, action_id: str | None = None, param_name: str | None = None) -> list[ParameterOverride]:
        with self._lock:
            items = list(self._overrides.values())
        if action_id:
            items = [o for o in items if o.action_id == action_id]
        if param_name:
            items = [o for o in items if o.param_name == param_name]
        return items

    def update(self, override_id: str, updates: dict[str, Any]) -> ParameterOverride:
        with self._lock:
            o = self._overrides.get(override_id)
            if not o:
                raise OverrideError("NOT_FOUND", f"覆盖 {override_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(o, k, v)
            return o

    def delete(self, override_id: str) -> bool:
        with self._lock:
            if override_id not in self._overrides:
                raise OverrideError("NOT_FOUND", f"覆盖 {override_id} 不存在")
            del self._overrides[override_id]
            return True

    def evaluate(
        self,
        action_id: str,
        param_name: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """评估所有匹配的覆盖块，返回合并后的状态。"""
        with self._lock:
            overrides = [
                o for o in self._overrides.values()
                if o.action_id == action_id and o.param_name == param_name
            ]

        result: dict[str, Any] = {
            "visible": True,
            "disabled": False,
            "required": False,
            "applied_overrides": [],
        }

        for o in overrides:
            if self._evaluate_condition(o.condition, context):
                for k, v in o.overrides.items():
                    result[k] = v
                result["applied_overrides"].append(o.id)

        return result

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """简单条件评估器。"""
        condition = condition.strip()
        if not condition:
            return True

        # 支持: field = value, field != value, field > value, field < value
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
                elif op == ">":
                    try:
                        return float(actual) > float(target)
                    except (ValueError, TypeError):
                        return False
                elif op == "<":
                    try:
                        return float(actual) < float(target)
                    except (ValueError, TypeError):
                        return False
                elif op == ">=":
                    try:
                        return float(actual) >= float(target)
                    except (ValueError, TypeError):
                        return False
                elif op == "<=":
                    try:
                        return float(actual) <= float(target)
                    except (ValueError, TypeError):
                        return False

        return False

    def reset(self) -> None:
        with self._lock:
            self._overrides.clear()


# ─────────────── 单例 ───────────────

_constraint_engine: ConstraintEngine | None = None
_default_engine: DefaultEngine | None = None
_override_engine: OverrideEngine | None = None
_lock = threading.Lock()


def get_constraint_engine() -> ConstraintEngine:
    global _constraint_engine
    if _constraint_engine is None:
        with _lock:
            if _constraint_engine is None:
                _constraint_engine = ConstraintEngine()
    return _constraint_engine


def get_default_engine() -> DefaultEngine:
    global _default_engine
    if _default_engine is None:
        with _lock:
            if _default_engine is None:
                _default_engine = DefaultEngine()
    return _default_engine


def get_override_engine() -> OverrideEngine:
    global _override_engine
    if _override_engine is None:
        with _lock:
            if _override_engine is None:
                _override_engine = OverrideEngine()
    return _override_engine
