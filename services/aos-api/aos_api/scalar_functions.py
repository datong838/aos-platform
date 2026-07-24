"""W2-#5 · 标量函数库（Scalar Functions）。

提供 50+ 行级标量函数，涵盖数值、字符串、日期时间、数组、条件、类型六大类别。
每个函数统一签名 (value, *args) -> value，可通过 DSL 表达式引用或在 Pipeline Builder 中使用。

函数类别（对标 Foundry Pipeline Builder 函数索引）：
  - 数值（12）：abs, ceil, floor, round, sqrt, pow, log, exp, mod, sign, radians, degrees
  - 字符串（14）：upper, lower, trim, ltrim, rtrim, replace, substring, concat, length,
                split, contains, starts_with, ends_with, regex_extract
  - 日期时间（10）：year, month, day, hour, minute, second, date_diff, date_add,
                  date_trunc, current_timestamp
  - 数组（6）：size, array_contains, first, last, element_at, explode_array
  - 条件（5）：coalesce, if_null, case_when, greatest, least
  - 类型转换（6）：is_null, is_not_null, to_string, to_number, to_integer, to_boolean

详见 docs/palantier/20_tech/220w-与目标系统差距对照分析.md §5.1 表达式函数索引。
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Callable

ScalarFn = Callable[..., Any]


# ──────────────────────────────────────────────────────────────
# 数值函数
# ──────────────────────────────────────────────────────────────


def fn_abs(v: Any) -> Any:
    return abs(v) if v is not None else None


def fn_ceil(v: Any) -> Any:
    return math.ceil(v) if v is not None else None


def fn_floor(v: Any) -> Any:
    return math.floor(v) if v is not None else None


def fn_round(v: Any, decimals: int = 0) -> Any:
    return round(v, decimals) if v is not None else None


def fn_sqrt(v: Any) -> Any:
    return math.sqrt(v) if v is not None and v >= 0 else None


def fn_pow(v: Any, exp: float) -> Any:
    return math.pow(v, exp) if v is not None else None


def fn_log(v: Any) -> Any:
    return math.log(v) if v is not None and v > 0 else None


def fn_exp(v: Any) -> Any:
    return math.exp(v) if v is not None else None


def fn_mod(a: Any, b: Any) -> Any:
    return a % b if a is not None and b is not None else None


def fn_sign(v: Any) -> Any:
    return (1 if v > 0 else -1 if v < 0 else 0) if v is not None else None


def fn_radians(v: Any) -> Any:
    return math.radians(v) if v is not None else None


def fn_degrees(v: Any) -> Any:
    return math.degrees(v) if v is not None else None


# ──────────────────────────────────────────────────────────────
# 字符串函数
# ──────────────────────────────────────────────────────────────


def fn_upper(s: Any) -> Any:
    return str(s).upper() if s is not None else None


def fn_lower(s: Any) -> Any:
    return str(s).lower() if s is not None else None


def fn_trim(s: Any) -> Any:
    return str(s).strip() if s is not None else None


def fn_ltrim(s: Any) -> Any:
    return str(s).lstrip() if s is not None else None


def fn_rtrim(s: Any) -> Any:
    return str(s).rstrip() if s is not None else None


def fn_replace(s: Any, old: str, new: str) -> Any:
    return str(s).replace(old, new) if s is not None else None


def fn_substring(s: Any, start: int, length: int | None = None) -> Any:
    if s is None:
        return None
    s = str(s)
    if length is None:
        return s[start:]
    return s[start:start + length]


def fn_concat(*args: Any) -> str:
    return ''.join(str(a) for a in args if a is not None)


def fn_length(s: Any) -> int | None:
    return len(str(s)) if s is not None else None


def fn_split(s: Any, delimiter: str) -> list[str] | None:
    return str(s).split(delimiter) if s is not None else None


def fn_contains(s: Any, substr: str) -> bool:
    return substr in str(s) if s is not None else False


def fn_starts_with(s: Any, prefix: str) -> bool:
    return str(s).startswith(prefix) if s is not None else False


def fn_ends_with(s: Any, suffix: str) -> bool:
    return str(s).endswith(suffix) if s is not None else False


def fn_regex_extract(s: Any, pattern: str, group: int = 0) -> str | None:
    if s is None:
        return None
    m = re.search(pattern, str(s))
    return m.group(group) if m else None


# ──────────────────────────────────────────────────────────────
# 日期时间函数
# ──────────────────────────────────────────────────────────────


def _parse_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def fn_year(v: Any) -> int | None:
    dt = _parse_dt(v)
    return dt.year if dt else None


def fn_month(v: Any) -> int | None:
    dt = _parse_dt(v)
    return dt.month if dt else None


def fn_day(v: Any) -> int | None:
    dt = _parse_dt(v)
    return dt.day if dt else None


def fn_hour(v: Any) -> int | None:
    dt = _parse_dt(v)
    return dt.hour if dt else None


def fn_minute(v: Any) -> int | None:
    dt = _parse_dt(v)
    return dt.minute if dt else None


def fn_second(v: Any) -> int | None:
    dt = _parse_dt(v)
    return dt.second if dt else None


def fn_date_diff(v1: Any, v2: Any, unit: str = "day") -> int | None:
    dt1, dt2 = _parse_dt(v1), _parse_dt(v2)
    if not dt1 or not dt2:
        return None
    delta = dt1 - dt2
    units = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
    divisor = units.get(unit, 86400)
    return int(delta.total_seconds() / divisor)


def fn_date_add(v: Any, days: int) -> datetime | None:
    from datetime import timedelta
    dt = _parse_dt(v)
    return dt + timedelta(days=days) if dt else None


def fn_date_trunc(v: Any, unit: str = "day") -> datetime | None:
    dt = _parse_dt(v)
    if not dt:
        return None
    truncations = {
        "year": datetime(dt.year, 1, 1, tzinfo=dt.tzinfo),
        "month": datetime(dt.year, dt.month, 1, tzinfo=dt.tzinfo),
        "day": datetime(dt.year, dt.month, dt.day, tzinfo=dt.tzinfo),
        "hour": datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=dt.tzinfo),
    }
    return truncations.get(unit, dt)


def fn_current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────
# 数组函数
# ──────────────────────────────────────────────────────────────


def fn_array_size(arr: Any) -> int | None:
    return len(arr) if isinstance(arr, (list, tuple)) else None


def fn_array_contains(arr: Any, item: Any) -> bool:
    return item in arr if isinstance(arr, (list, tuple)) else False


def fn_array_first(arr: Any) -> Any:
    if isinstance(arr, (list, tuple)) and arr:
        return arr[0]
    return None


def fn_array_last(arr: Any) -> Any:
    if isinstance(arr, (list, tuple)) and arr:
        return arr[-1]
    return None


def fn_array_element_at(arr: Any, index: int) -> Any:
    if isinstance(arr, (list, tuple)) and 0 <= index < len(arr):
        return arr[index]
    return None


def fn_explode_array(arr: Any) -> list[dict[str, Any]]:
    """将数组列展开为多行（返回 dict 列表，供 transform 层使用）"""
    if not isinstance(arr, list):
        return [{"_value": arr}]
    return [{"_value": item} for item in arr]


# ──────────────────────────────────────────────────────────────
# 条件函数
# ──────────────────────────────────────────────────────────────


def fn_coalesce(*args: Any) -> Any:
    for a in args:
        if a is not None:
            return a
    return None


def fn_if_null(v: Any, default: Any) -> Any:
    return v if v is not None else default


def fn_case_when(condition: bool, true_val: Any, false_val: Any) -> Any:
    return true_val if condition else false_val


def fn_greatest(*args: Any) -> Any:
    filtered = [a for a in args if a is not None]
    return max(filtered) if filtered else None


def fn_least(*args: Any) -> Any:
    filtered = [a for a in args if a is not None]
    return min(filtered) if filtered else None


# ──────────────────────────────────────────────────────────────
# 类型函数
# ──────────────────────────────────────────────────────────────


def fn_is_null(v: Any) -> bool:
    return v is None


def fn_is_not_null(v: Any) -> bool:
    return v is not None


def fn_to_string(v: Any) -> str | None:
    return str(v) if v is not None else None


def fn_to_number(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def fn_to_integer(v: Any) -> int | None:
    try:
        return int(float(v)) if v is not None else None
    except (ValueError, TypeError):
        return None


def fn_to_boolean(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes", "t")
    if isinstance(v, (int, float)):
        return v != 0
    return bool(v)


# ──────────────────────────────────────────────────────────────
# 函数注册表
# ──────────────────────────────────────────────────────────────

SCALAR_FN_REGISTRY: dict[str, ScalarFn] = {
    # 数值
    "abs": fn_abs, "ceil": fn_ceil, "floor": fn_floor, "round": fn_round,
    "sqrt": fn_sqrt, "pow": fn_pow, "log": fn_log, "exp": fn_exp,
    "mod": fn_mod, "sign": fn_sign, "radians": fn_radians, "degrees": fn_degrees,
    # 字符串
    "upper": fn_upper, "lower": fn_lower, "trim": fn_trim,
    "ltrim": fn_ltrim, "rtrim": fn_rtrim, "replace": fn_replace,
    "substring": fn_substring, "concat": fn_concat, "length": fn_length,
    "split": fn_split, "contains": fn_contains,
    "starts_with": fn_starts_with, "ends_with": fn_ends_with,
    "regex_extract": fn_regex_extract,
    # 日期时间
    "year": fn_year, "month": fn_month, "day": fn_day,
    "hour": fn_hour, "minute": fn_minute, "second": fn_second,
    "date_diff": fn_date_diff, "date_add": fn_date_add,
    "date_trunc": fn_date_trunc, "current_timestamp": fn_current_timestamp,
    # 数组
    "array_size": fn_array_size, "array_contains": fn_array_contains,
    "array_first": fn_array_first, "array_last": fn_array_last,
    "array_element_at": fn_array_element_at, "explode_array": fn_explode_array,
    # 条件
    "coalesce": fn_coalesce, "if_null": fn_if_null,
    "case_when": fn_case_when, "greatest": fn_greatest, "least": fn_least,
    # 类型
    "is_null": fn_is_null, "is_not_null": fn_is_not_null,
    "to_string": fn_to_string, "to_number": fn_to_number,
    "to_integer": fn_to_integer, "to_boolean": fn_to_boolean,
}


# 函数分类元数据（用于 Pipeline Builder UI 函数选择器）
SCALAR_FN_CATEGORIES: dict[str, list[str]] = {
    "数值": ["abs", "ceil", "floor", "round", "sqrt", "pow", "log", "exp", "mod", "sign", "radians", "degrees"],
    "字符串": ["upper", "lower", "trim", "ltrim", "rtrim", "replace", "substring", "concat", "length", "split", "contains", "starts_with", "ends_with", "regex_extract"],
    "日期时间": ["year", "month", "day", "hour", "minute", "second", "date_diff", "date_add", "date_trunc", "current_timestamp"],
    "数组": ["array_size", "array_contains", "array_first", "array_last", "array_element_at", "explode_array"],
    "条件": ["coalesce", "if_null", "case_when", "greatest", "least"],
    "类型转换": ["is_null", "is_not_null", "to_string", "to_number", "to_integer", "to_boolean"],
}


def call_scalar(name: str, *args: Any) -> Any:
    """调用标量函数。"""
    fn = SCALAR_FN_REGISTRY.get(name)
    if fn is None:
        raise ValueError(f"未知标量函数 {name!r}，可用：{sorted(SCALAR_FN_REGISTRY.keys())}")
    return fn(*args)


def list_scalar_functions() -> list[dict[str, Any]]:
    """返回所有标量函数目录（含分类信息）。"""
    result: list[dict[str, Any]] = []
    for category, names in SCALAR_FN_CATEGORIES.items():
        for name in names:
            result.append({
                "name": name,
                "category": category,
                "signature": _fn_signature(SCALAR_FN_REGISTRY[name]),
            })
    return result


def _fn_signature(fn: Callable) -> str:
    """提取函数签名字符串。"""
    import inspect
    try:
        sig = inspect.signature(fn)
        params = [f"{n}" for n, p in sig.parameters.items()]
        return f"({', '.join(params)})"
    except (ValueError, TypeError):
        return "(*args)"
