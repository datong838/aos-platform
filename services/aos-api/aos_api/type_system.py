"""W2-O · 类型系统与视图配置：完整类型系统 + 视图配置 + 条件格式化."""
from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ─────────────── #52 完整类型系统 ───────────────

class TypeError_(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class TypeDefinition(BaseModel):
    name: str
    category: str           # scalar / temporal / binary / composite / security
    base_type: str          # 底层 Python 类型名
    description: str = ""
    validators: list[str] = Field(default_factory=list)  # 验证规则描述


class TypeSystem:
    """完整类型系统引擎：20+ 基础类型 + 验证 + 强制转换。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._types: dict[str, TypeDefinition] = {}
        self._validators: dict[str, Callable[[Any], bool]] = {}
        self._coercers: dict[str, Callable[[Any], Any]] = {}
        self._init_builtin_types()

    def _init_builtin_types(self) -> None:
        builtins: list[tuple[str, str, str, str]] = [
            # 标量
            ("String", "scalar", "str", "字符串"),
            ("Text", "scalar", "str", "长文本"),
            ("Integer", "scalar", "int", "32位整数"),
            ("Long", "scalar", "int", "64位整数"),
            ("Float", "scalar", "float", "单精度浮点"),
            ("Double", "scalar", "float", "双精度浮点"),
            ("Decimal", "scalar", "Decimal", "高精度十进制"),
            ("Boolean", "scalar", "bool", "布尔值"),
            # 时间
            ("Date", "temporal", "date", "日期"),
            ("Time", "temporal", "time", "时间"),
            ("Timestamp", "temporal", "datetime", "时间戳"),
            ("Interval", "temporal", "timedelta", "时间间隔"),
            # 二进制
            ("Byte", "binary", "int", "字节"),
            ("ByteArray", "binary", "bytes", "字节数组"),
            ("Attachment", "binary", "dict", "附件引用"),
            ("MediaReference", "binary", "dict", "媒体引用"),
            # 复合
            ("Vector", "composite", "list", "向量"),
            ("TimeSeries", "composite", "list", "时间序列"),
            ("JSON", "composite", "dict", "JSON 对象"),
            ("Geopoint", "composite", "tuple", "地理坐标点"),
            ("Geoshape", "composite", "dict", "地理形状"),
            # 安全
            ("Cipher", "security", "bytes", "加密数据"),
            ("Hash", "security", "bytes", "哈希值"),
        ]
        for name, category, base, desc in builtins:
            self.register_type(TypeDefinition(
                name=name, category=category, base_type=base, description=desc,
            ))
        # 注册内置验证器
        self._register_builtin_validators()

    def _register_builtin_validators(self) -> None:
        self._validators["String"] = lambda v: isinstance(v, str)
        self._validators["Text"] = lambda v: isinstance(v, str)
        self._validators["Integer"] = lambda v: isinstance(v, int) and not isinstance(v, bool)
        self._validators["Long"] = lambda v: isinstance(v, int) and not isinstance(v, bool)
        self._validators["Float"] = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
        self._validators["Double"] = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
        self._validators["Decimal"] = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
        self._validators["Boolean"] = lambda v: isinstance(v, bool)
        self._validators["Date"] = self._validate_date
        self._validators["Timestamp"] = self._validate_timestamp
        self._validators["Vector"] = lambda v: isinstance(v, list) and all(isinstance(x, (int, float)) for x in v)
        self._validators["JSON"] = lambda v: isinstance(v, (dict, list, str, int, float, bool, type(None)))
        self._validators["Geopoint"] = lambda v: isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)
        self._validators["Byte"] = lambda v: isinstance(v, int) and 0 <= v <= 255
        self._validators["ByteArray"] = lambda v: isinstance(v, (bytes, bytearray))
        self._validators["Cipher"] = lambda v: isinstance(v, (bytes, bytearray, str))
        self._validators["Hash"] = lambda v: isinstance(v, (bytes, bytearray, str))

        # Coercers
        self._coercers["String"] = lambda v: str(v) if v is not None else ""
        self._coercers["Integer"] = lambda v: int(v) if v is not None else 0
        self._coercers["Float"] = lambda v: float(v) if v is not None else 0.0
        self._coercers["Double"] = lambda v: float(v) if v is not None else 0.0
        self._coercers["Boolean"] = lambda v: bool(v) if v is not None else False

    def _validate_date(self, v: Any) -> bool:
        if isinstance(v, str):
            return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", v))
        return hasattr(v, "year") and hasattr(v, "month")

    def _validate_timestamp(self, v: Any) -> bool:
        if isinstance(v, str):
            try:
                datetime.fromisoformat(v)
                return True
            except (ValueError, TypeError):
                return False
        return hasattr(v, "timestamp")

    def register_type(self, td: TypeDefinition) -> TypeDefinition:
        with self._lock:
            self._types[td.name] = td
        return td

    def get_type(self, name: str) -> TypeDefinition:
        td = self._types.get(name)
        if not td:
            raise TypeError_("TYPE_NOT_FOUND", f"类型 {name} 不存在")
        return td

    def list_types(self, *, category: str | None = None) -> list[TypeDefinition]:
        with self._lock:
            types = list(self._types.values())
        if category:
            types = [t for t in types if t.category == category]
        return types

    def validate(self, type_name: str, value: Any) -> bool:
        """验证值是否符合类型。"""
        if type_name not in self._types:
            raise TypeError_("TYPE_NOT_FOUND", f"类型 {type_name} 不存在")
        validator = self._validators.get(type_name)
        if validator is None:
            return True  # 无验证器默认通过
        try:
            return validator(value)
        except Exception:
            return False

    def coerce(self, type_name: str, value: Any) -> Any:
        """强制转换值到类型。"""
        if type_name not in self._types:
            raise TypeError_("TYPE_NOT_FOUND", f"类型 {type_name} 不存在")
        coercer = self._coercers.get(type_name)
        if coercer is None:
            return value  # 无转换器原样返回
        try:
            return coercer(value)
        except (ValueError, TypeError):
            return value

    def reset(self) -> None:
        with self._lock:
            self._types.clear()
            self._validators.clear()
            self._coercers.clear()
        self._init_builtin_types()


# ─────────────── #51 Object Views 配置文件 ───────────────

class ViewTab(BaseModel):
    id: str = Field(default_factory=lambda: _uid("tab"))
    name: str
    widgets: list[str] = Field(default_factory=list)
    visible: bool = True


class ViewProfile(BaseModel):
    id: str = Field(default_factory=lambda: _uid("vp"))
    name: str
    object_type: str
    user_groups: list[str] = Field(default_factory=list)
    tabs: list[ViewTab] = Field(default_factory=list)
    is_default: bool = False
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ViewProfileError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ViewProfileEngine:
    """Object Views 配置文件引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: dict[str, ViewProfile] = {}
        # 激活状态: (object_type, user_group) -> profile_id
        self._active: dict[tuple[str, str], str] = {}

    def create(self, profile: ViewProfile) -> ViewProfile:
        with self._lock:
            self._profiles[profile.id] = profile
        return profile

    def get(self, profile_id: str) -> ViewProfile:
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ViewProfileError("NOT_FOUND", f"视图配置 {profile_id} 不存在")
        return profile

    def list(
        self,
        *,
        object_type: str | None = None,
        user_group: str | None = None,
    ) -> list[ViewProfile]:
        with self._lock:
            items = list(self._profiles.values())
        result: list[ViewProfile] = []
        for p in items:
            if object_type and p.object_type != object_type:
                continue
            if user_group and user_group not in p.user_groups:
                continue
            result.append(p)
        return result

    def update(self, profile_id: str, updates: dict[str, Any]) -> ViewProfile:
        with self._lock:
            profile = self._profiles.get(profile_id)
            if not profile:
                raise ViewProfileError("NOT_FOUND", f"视图配置 {profile_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(profile, k, v)
            profile.updated_at = _now()
            return profile

    def delete(self, profile_id: str) -> bool:
        with self._lock:
            if profile_id not in self._profiles:
                raise ViewProfileError("NOT_FOUND", f"视图配置 {profile_id} 不存在")
            del self._profiles[profile_id]
            # 清理激活映射
            to_remove = [k for k, v in self._active.items() if v == profile_id]
            for k in to_remove:
                del self._active[k]
            return True

    def activate(self, profile_id: str, user_group: str) -> ViewProfile:
        """为指定用户组激活配置。"""
        with self._lock:
            profile = self._profiles.get(profile_id)
            if not profile:
                raise ViewProfileError("NOT_FOUND", f"视图配置 {profile_id} 不存在")
            self._active[(profile.object_type, user_group)] = profile_id
            return profile

    def get_active(self, object_type: str, user_group: str) -> ViewProfile | None:
        """获取指定用户组的激活配置。"""
        with self._lock:
            pid = self._active.get((object_type, user_group))
            if pid:
                return self._profiles.get(pid)
            # 回退到默认
            for p in self._profiles.values():
                if p.object_type == object_type and p.is_default:
                    return p
            return None

    def reset(self) -> None:
        with self._lock:
            self._profiles.clear()
            self._active.clear()


# ─────────────── #53 值类型/条件格式化/类型类 ───────────────

class TypeClass(BaseModel):
    name: str                # e.g. currency, percentage, url, email
    base_type: str           # e.g. Decimal, Float, String
    description: str = ""
    render_hint: str = ""    # 渲染提示：symbol, percent, link, mailto, etc.
    validators: list[str] = Field(default_factory=list)


class ConditionalFormat(BaseModel):
    id: str = Field(default_factory=lambda: _uid("cf"))
    object_type: str
    field: str
    condition: str           # 表达式，如 "> 100" 或 "= 'high'"
    style: dict[str, Any] = Field(default_factory=dict)  # {color, background, icon, bold, ...}


class FormatError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class FormatEngine:
    """类型类 + 条件格式化引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._type_classes: dict[str, TypeClass] = {}
        self._conditional_formats: dict[str, ConditionalFormat] = {}
        self._init_builtin_type_classes()

    def _init_builtin_type_classes(self) -> None:
        builtins: list[tuple[str, str, str, str]] = [
            ("currency", "Decimal", "货币", "symbol:$"),
            ("percentage", "Float", "百分比", "percent"),
            ("url", "String", "URL 链接", "link"),
            ("email", "String", "邮箱", "mailto"),
            ("phone", "String", "电话", "tel"),
            ("id_code", "String", "ID 编号", "mono"),
            ("name", "String", "名称", "text"),
            ("description", "Text", "描述", "text"),
            ("color_hex", "String", "颜色值", "color"),
            ("image_url", "String", "图片 URL", "image"),
            ("file_size", "Long", "文件大小", "bytes"),
            ("duration", "Interval", "时长", "duration"),
            ("rating", "Integer", "评分", "stars"),
            ("status", "String", "状态", "badge"),
            ("priority", "Integer", "优先级", "priority"),
            ("latitude", "Float", "纬度", "geo"),
            ("longitude", "Float", "经度", "geo"),
            ("address", "Text", "地址", "text"),
            ("barcode", "String", "条形码", "barcode"),
            ("qr_code", "String", "二维码", "qrcode"),
            ("markdown", "Text", "Markdown", "markdown"),
            ("html", "Text", "HTML", "html"),
            ("json", "JSON", "JSON", "json"),
            ("code", "Text", "代码", "code"),
            ("tag", "String", "标签", "tag"),
            ("category", "String", "分类", "category"),
            ("ordinal", "Integer", "序号", "ordinal"),
            ("boolean_flag", "Boolean", "布尔标记", "flag"),
            ("timestamp_iso", "Timestamp", "ISO 时间戳", "datetime"),
            ("date_short", "Date", "短日期", "date"),
            ("time_short", "Time", "短时间", "time"),
        ]
        for name, base, desc, hint in builtins:
            self._type_classes[name] = TypeClass(
                name=name, base_type=base, description=desc, render_hint=hint,
            )

    def register_type_class(self, tc: TypeClass) -> TypeClass:
        with self._lock:
            self._type_classes[tc.name] = tc
        return tc

    def get_type_class(self, name: str) -> TypeClass:
        tc = self._type_classes.get(name)
        if not tc:
            raise FormatError("TYPE_CLASS_NOT_FOUND", f"类型类 {name} 不存在")
        return tc

    def list_type_classes(self) -> list[TypeClass]:
        with self._lock:
            return list(self._type_classes.values())

    def render(self, type_class_name: str, value: Any) -> dict[str, Any]:
        """渲染值。"""
        tc = self.get_type_class(type_class_name)
        rendered: str
        if tc.render_hint == "percent":
            rendered = f"{value}%"
        elif tc.render_hint == "symbol:$":
            rendered = f"${value}"
        elif tc.render_hint == "link":
            rendered = f'<a href="{value}">{value}</a>'
        elif tc.render_hint == "mailto":
            rendered = f'<a href="mailto:{value}">{value}</a>'
        elif tc.render_hint == "bytes":
            if isinstance(value, (int, float)):
                if value >= 1024 * 1024:
                    rendered = f"{value / (1024 * 1024):.1f} MB"
                elif value >= 1024:
                    rendered = f"{value / 1024:.1f} KB"
                else:
                    rendered = f"{value} B"
            else:
                rendered = str(value)
        else:
            rendered = str(value) if value is not None else ""
        return {
            "type_class": type_class_name,
            "raw_value": value,
            "rendered": rendered,
            "render_hint": tc.render_hint,
        }

    # 条件格式化
    def add_conditional_format(self, cf: ConditionalFormat) -> ConditionalFormat:
        with self._lock:
            self._conditional_formats[cf.id] = cf
        return cf

    def get_conditional_format(self, cf_id: str) -> ConditionalFormat:
        cf = self._conditional_formats.get(cf_id)
        if not cf:
            raise FormatError("NOT_FOUND", f"条件格式 {cf_id} 不存在")
        return cf

    def list_conditional_formats(
        self,
        *,
        object_type: str | None = None,
        field: str | None = None,
    ) -> list[ConditionalFormat]:
        with self._lock:
            items = list(self._conditional_formats.values())
        if object_type:
            items = [c for c in items if c.object_type == object_type]
        if field:
            items = [c for c in items if c.field == field]
        return items

    def delete_conditional_format(self, cf_id: str) -> bool:
        with self._lock:
            if cf_id not in self._conditional_formats:
                raise FormatError("NOT_FOUND", f"条件格式 {cf_id} 不存在")
            del self._conditional_formats[cf_id]
            return True

    def evaluate(self, cf_id: str, value: Any) -> dict[str, Any]:
        """评估条件格式是否匹配。"""
        cf = self.get_conditional_format(cf_id)
        condition = cf.condition.strip()
        matched = self._evaluate_condition(condition, value)
        return {
            "matched": matched,
            "style": cf.style if matched else {},
            "condition": condition,
        }

    def _evaluate_condition(self, condition: str, value: Any) -> bool:
        """简单条件评估器。"""
        # 支持: > N, < N, >= N, <= N, = X, != X, 'contains' X
        if condition.startswith(">"):
            try:
                return value is not None and float(value) > float(condition[1:].strip())
            except (ValueError, TypeError):
                return False
        if condition.startswith("<"):
            try:
                return value is not None and float(value) < float(condition[1:].strip())
            except (ValueError, TypeError):
                return False
        if condition.startswith(">="):
            try:
                return value is not None and float(value) >= float(condition[2:].strip())
            except (ValueError, TypeError):
                return False
        if condition.startswith("<="):
            try:
                return value is not None and float(value) <= float(condition[2:].strip())
            except (ValueError, TypeError):
                return False
        if condition.startswith("==") or condition.startswith("="):
            target = condition[2:].strip() if condition.startswith("==") else condition[1:].strip()
            target = target.strip("'\"")
            return str(value) == target
        if condition.startswith("!="):
            target = condition[2:].strip().strip("'\"")
            return str(value) != target
        if condition.lower().startswith("contains"):
            target = condition[8:].strip().strip("'\"")
            return target in str(value) if value is not None else False
        return False

    def reset(self) -> None:
        with self._lock:
            self._type_classes.clear()
            self._conditional_formats.clear()
        self._init_builtin_type_classes()


# ─────────────── 单例 ───────────────

_type_system: TypeSystem | None = None
_view_profile_engine: ViewProfileEngine | None = None
_format_engine: FormatEngine | None = None
_lock = threading.Lock()


def get_type_system() -> TypeSystem:
    global _type_system
    if _type_system is None:
        with _lock:
            if _type_system is None:
                _type_system = TypeSystem()
    return _type_system


def get_view_profile_engine() -> ViewProfileEngine:
    global _view_profile_engine
    if _view_profile_engine is None:
        with _lock:
            if _view_profile_engine is None:
                _view_profile_engine = ViewProfileEngine()
    return _view_profile_engine


def get_format_engine() -> FormatEngine:
    global _format_engine
    if _format_engine is None:
        with _lock:
            if _format_engine is None:
                _format_engine = FormatEngine()
    return _format_engine
