"""W1-8 + W2-#5 · Transform 算子库。

15 个数据变换算子（W1-8 原始 9 个 + W2-#5 新增 6 个）：
  - 原始：Filter/Join/Aggregate/Explode/Cast/Union/Sort/Distinct/Expression
  - 新增：Window/Pivot/Unpivot/Fillna/Normalize/StringOps

每个算子统一签名 (rows, config) -> rows，支持链式组合。
集成 scalar_functions 标量函数库（50+ 函数）用于表达式计算。

详见 docs/palantier/20_tech/220tech_transform-ops.md。
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from aos_api.function_engine import evaluate, parse
from aos_api.scalar_functions import SCALAR_FN_REGISTRY, call_scalar


TransformOp = Callable[[list[dict[str, Any]], dict[str, Any]], list[dict[str, Any]]]


def op_filter(rows: list[dict], config: dict) -> list[dict]:
    expr_text = config.get("expression", "true")
    expr = parse(expr_text)
    return [r for r in rows if evaluate(expr, r)]


def op_join(rows: list[dict], config: dict) -> list[dict]:
    right: list[dict] = config.get("right", [])
    left_key = config.get("left_key", "id")
    right_key = config.get("right_key", "id")
    how = config.get("how", "inner")
    right_map = {r.get(right_key): r for r in right}
    result: list[dict] = []
    for left_row in rows:
        match = right_map.get(left_row.get(left_key))
        if match is not None:
            merged = {**left_row}
            for k, v in match.items():
                if k not in merged:
                    merged[k] = v
            result.append(merged)
        elif how == "left":
            result.append(dict(left_row))
    if how == "right":
        left_keys = {r.get(left_key) for r in rows}
        for rk, rv in right_map.items():
            if rk not in left_keys:
                result.append(dict(rv))
    return result


def op_aggregate(rows: list[dict], config: dict) -> list[dict]:
    group_by = config.get("group_by", [])
    aggregations = config.get("aggregations", {})
    if not group_by:
        return rows
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        key = tuple(r.get(g) for g in group_by)
        groups.setdefault(key, []).append(r)
    result: list[dict] = []
    for key, group_rows in groups.items():
        row: dict[str, Any] = {g: k for g, k in zip(group_by, key)}
        for field, agg_func in aggregations.items():
            values = [r.get(field) for r in group_rows if r.get(field) is not None]
            if agg_func == "count":
                row[f"{field}_{agg_func}"] = len(values)
            elif agg_func == "sum" and values:
                row[f"{field}_{agg_func}"] = sum(values)
            elif agg_func == "avg" and values:
                row[f"{field}_{agg_func}"] = sum(values) / len(values)
            elif agg_func == "min" and values:
                row[f"{field}_{agg_func}"] = min(values)
            elif agg_func == "max" and values:
                row[f"{field}_{agg_func}"] = max(values)
            else:
                row[f"{field}_{agg_func}"] = None
        result.append(row)
    return result


def op_explode(rows: list[dict], config: dict) -> list[dict]:
    field = config.get("field", "")
    result: list[dict] = []
    for r in rows:
        val = r.get(field)
        if isinstance(val, list):
            for item in val:
                new_row = {**r, field: item}
                result.append(new_row)
        else:
            result.append(dict(r))
    return result


def op_cast(rows: list[dict], config: dict) -> list[dict]:
    field = config.get("field", "")
    target_type = config.get("type", "string")
    casters = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": lambda x: str(x).lower() in ("true", "1", "yes"),
    }
    caster = casters.get(target_type, str)
    result: list[dict] = []
    for r in rows:
        new_row = {**r}
        if field in new_row and new_row[field] is not None:
            try:
                new_row[field] = caster(new_row[field])
            except (ValueError, TypeError):
                pass
        result.append(new_row)
    return result


def op_union(rows: list[dict], config: dict) -> list[dict]:
    other: list[dict] = config.get("other", [])
    return [*rows, *other]


def op_sort(rows: list[dict], config: dict) -> list[dict]:
    field = config.get("field", "")
    descending = config.get("descending", False)
    try:
        return sorted(rows, key=lambda r: (r.get(field) is None, r.get(field)), reverse=descending)
    except TypeError:
        return sorted(rows, key=lambda r: str(r.get(field, "")), reverse=descending)


def op_distinct(rows: list[dict], config: dict) -> list[dict]:
    fields = config.get("fields", [])
    if not fields:
        fields = list(rows[0].keys()) if rows else []
    seen: set[tuple] = set()
    result: list[dict] = []
    for r in rows:
        key = tuple(str(r.get(f)) for f in fields)
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def op_expression(rows: list[dict], config: dict) -> list[dict]:
    output_field = config.get("output_field", "computed")
    expr_text = config.get("expression", "null")
    expr = parse(expr_text)
    result: list[dict] = []
    for r in rows:
        new_row = {**r}
        new_row[output_field] = evaluate(expr, r)
        result.append(new_row)
    return result


# ──────────────────────────────────────────────────────────────
# W2-#5 · 新增算子
# ──────────────────────────────────────────────────────────────


def op_window(rows: list[dict], config: dict) -> list[dict]:
    """窗口函数算子。

    支持 row_number / rank / lag / lead / running_sum / moving_avg。
    config:
      - partition_by: list[str]  分组键
      - order_by: str            排序列
      - functions: list[dict]    窗口函数定义
          [{type, field, output, N, order_desc}]
    """
    partition_by = config.get("partition_by", [])
    order_by = config.get("order_by", "")
    functions: list[dict] = config.get("functions", [])
    descending = config.get("order_desc", False)

    if not partition_by:
        groups: dict[tuple, list[dict]] = {(): list(rows)}
    else:
        groups = {}
        for r in rows:
            key = tuple(r.get(g) for g in partition_by)
            groups.setdefault(key, []).append(r)

    # 排序每个 group
    for key in groups:
        groups[key] = sorted(
            groups[key],
            key=lambda r: (r.get(order_by) is None, r.get(order_by)),
            reverse=descending,
        )

    result: list[dict] = []
    for key, group_rows in groups.items():
        # 计算 running sums
        running_sums: dict[str, float] = {}
        for wf in functions:
            if wf.get("type") == "running_sum":
                running_sums[wf.get("field", "")] = 0.0

        for i, row in enumerate(group_rows):
            new_row = {**row}
            for wf in functions:
                fn_type = wf.get("type", "")
                field = wf.get("field", "")
                output = wf.get("output", f"{field}_{fn_type}")
                N = wf.get("N", 1)

                if fn_type == "row_number":
                    new_row[output] = i + 1
                elif fn_type == "rank":
                    # dense_rank: same values get same rank
                    if i > 0 and row.get(order_by) == group_rows[i - 1].get(order_by):
                        new_row.setdefault(output, new_row.get(output, i))
                    else:
                        new_row[output] = i + 1
                elif fn_type == "lag":
                    src_idx = i - N
                    if src_idx >= 0:
                        new_row[output] = group_rows[src_idx].get(field)
                    else:
                        new_row[output] = None
                elif fn_type == "lead":
                    src_idx = i + N
                    if src_idx < len(group_rows):
                        new_row[output] = group_rows[src_idx].get(field)
                    else:
                        new_row[output] = None
                elif fn_type == "running_sum":
                    val = row.get(field, 0) or 0
                    running_sums[field] += val
                    new_row[output] = running_sums[field]
                elif fn_type == "moving_avg":
                    start = max(0, i - N + 1)
                    window = group_rows[start:i + 1]
                    vals = [r.get(field) for r in window if r.get(field) is not None]
                    new_row[output] = sum(vals) / len(vals) if vals else None
            result.append(new_row)
    return result


def op_pivot(rows: list[dict], config: dict) -> list[dict]:
    """透视表算子：行转列。

    config:
      - group_by: list[str]       分组键
      - pivot_column: str         透视列（取值作为新列名）
      - value_column: str         值列
      - aggregation: str          聚合函数（sum/count/avg/min/max）
    """
    group_by = config.get("group_by", [])
    pivot_column = config.get("pivot_column", "")
    value_column = config.get("value_column", "")
    agg = config.get("aggregation", "sum")

    # 收集所有透视值
    pivot_values = sorted(set(r.get(pivot_column) for r in rows if r.get(pivot_column) is not None))

    # 分组
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        key = tuple(r.get(g) for g in group_by)
        groups.setdefault(key, []).append(r)

    agg_fns = {
        "sum": lambda vals: sum(v for v in vals if v is not None) if vals else None,
        "count": lambda vals: len(vals),
        "avg": lambda vals: sum(v for v in vals if v is not None) / len([v for v in vals if v is not None]) if vals else None,
        "min": lambda vals: min(v for v in vals if v is not None) if vals else None,
        "max": lambda vals: max(v for v in vals if v is not None) if vals else None,
    }
    agg_fn = agg_fns.get(agg, agg_fns["sum"])

    result: list[dict] = []
    for key, group_rows in groups.items():
        row = {g: k for g, k in zip(group_by, key)}
        for pv in pivot_values:
            pv_rows = [r for r in group_rows if r.get(pivot_column) == pv]
            vals = [r.get(value_column) for r in pv_rows]
            row[str(pv)] = agg_fn(vals)
        result.append(row)
    return result


def op_unpivot(rows: list[dict], config: dict) -> list[dict]:
    """逆透视算子：列转行。

    config:
      - id_columns: list[str]     保留的标识列
      - value_columns: list[str]  要逆透视的列
      - variable_column: str      新列名（存储原列名，默认 "variable"）
      - value_column: str         新列名（存储原值，默认 "value"）
    """
    id_columns = config.get("id_columns", [])
    value_columns = config.get("value_columns", [])
    var_col = config.get("variable_column", "variable")
    val_col = config.get("value_column", "value")

    result: list[dict] = []
    for r in rows:
        for vc in value_columns:
            new_row = {c: r.get(c) for c in id_columns}
            new_row[var_col] = vc
            new_row[val_col] = r.get(vc)
            result.append(new_row)
    return result


def op_fillna(rows: list[dict], config: dict) -> list[dict]:
    """空值填充算子。

    config:
      - columns: list[str]          要填充的列（空=所有列）
      - method: str                 填充方法（constant/ffill/bfill/mean/median）
      - value: Any                  constant 方法的填充值
    """
    columns = config.get("columns", [])
    method = config.get("method", "constant")
    fill_value = config.get("value")

    result_rows = [dict(r) for r in rows]
    if not columns:
        columns = list(result_rows[0].keys()) if result_rows else []

    if method == "constant":
        val = fill_value
        for r in result_rows:
            for c in columns:
                if r.get(c) is None:
                    r[c] = val

    elif method == "ffill":
        last_vals: dict[str, Any] = {}
        for r in result_rows:
            for c in columns:
                if r.get(c) is not None:
                    last_vals[c] = r[c]
                elif c in last_vals:
                    r[c] = last_vals[c]

    elif method == "bfill":
        next_vals: dict[str, Any] = {}
        for i in reversed(range(len(result_rows))):
            r = result_rows[i]
            for c in columns:
                if r.get(c) is not None:
                    next_vals[c] = r[c]
                elif c in next_vals:
                    r[c] = next_vals[c]

    elif method == "mean":
        for c in columns:
            vals = [r[c] for r in result_rows if r.get(c) is not None]
            mean_val = sum(vals) / len(vals) if vals else fill_value
            for r in result_rows:
                if r.get(c) is None:
                    r[c] = mean_val

    elif method == "median":
        for c in columns:
            vals = sorted(r[c] for r in result_rows if r.get(c) is not None)
            if vals:
                n = len(vals)
                median_val = vals[n // 2] if n % 2 == 1 else (vals[n // 2 - 1] + vals[n // 2]) / 2
            else:
                median_val = fill_value
            for r in result_rows:
                if r.get(c) is None:
                    r[c] = median_val

    return result_rows


def op_normalize(rows: list[dict], config: dict) -> list[dict]:
    """归一化算子。

    config:
      - columns: list[str]    要归一化的列
      - method: str           归一化方法（minmax/zscore）
      - output_suffix: str    输出列后缀（默认 "_norm"）
    """
    columns = config.get("columns", [])
    method = config.get("method", "minmax")
    suffix = config.get("output_suffix", "_norm")

    if not columns or not rows:
        return [dict(r) for r in rows]

    result = [dict(r) for r in rows]

    if method == "minmax":
        for c in columns:
            vals = [r[c] for r in result if r.get(c) is not None]
            if not vals:
                continue
            vmin, vmax = min(vals), max(vals)
            rng = vmax - vmin
            for r in result:
                if r.get(c) is not None:
                    r[c + suffix] = (r[c] - vmin) / rng if rng != 0 else 0.0

    elif method == "zscore":
        for c in columns:
            vals = [r[c] for r in result if r.get(c) is not None]
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            for r in result:
                if r.get(c) is not None and std != 0:
                    r[c + suffix] = (r[c] - mean) / std

    return result


def op_string_ops(rows: list[dict], config: dict) -> list[dict]:
    """批量字符串操作算子。

    config:
      - operations: list[dict]  操作列表
          [{column, function, args, output}]
        支持的 function: upper/lower/trim/ltrim/rtrim/replace/substring/concat/split/length/contains/extract
    """
    operations: list[dict] = config.get("operations", [])
    result = [dict(r) for r in rows]

    for r in result:
        for op_def in operations:
            col = op_def.get("column", "")
            fn_name = op_def.get("function", "")
            args = op_def.get("args", [])
            output_col = op_def.get("output", f"{col}_{fn_name}")

            fn = SCALAR_FN_REGISTRY.get(fn_name)
            if fn is None:
                continue

            val = r.get(col)
            try:
                if isinstance(args, list):
                    r[output_col] = fn(val, *args)
                else:
                    r[output_col] = fn(val, args)
            except Exception:
                r[output_col] = None

    return result


TRANSFORM_REGISTRY: dict[str, TransformOp] = {
    "filter": op_filter,
    "join": op_join,
    "aggregate": op_aggregate,
    "explode": op_explode,
    "cast": op_cast,
    "union": op_union,
    "sort": op_sort,
    "distinct": op_distinct,
    "expression": op_expression,
    # W2-#5 新增
    "window": op_window,
    "pivot": op_pivot,
    "unpivot": op_unpivot,
    "fillna": op_fillna,
    "normalize": op_normalize,
    "string_ops": op_string_ops,
}


class TransformOpMeta(BaseModel):
    name: str
    description: str = ""
    config_schema: dict[str, Any] = {}


_BUILTIN_OP_DESCRIPTIONS: dict[str, str] = {
    "filter": "按表达式筛选行，保留 evaluate(expr,row)==true 的行",
    "join": "按 key 关联右表（inner/left/right）",
    "aggregate": "按 group_by 分组聚合（count/sum/avg/min/max）",
    "explode": "将列表字段展开为多行",
    "cast": "字段类型转换（string/number/integer/boolean）",
    "union": "纵向拼接 other 行集",
    "sort": "按字段排序（支持 descending）",
    "distinct": "按字段去重",
    "expression": "新增计算列（DSL 表达式求值）",
    "window": "窗口函数（row_number/rank/lag/lead/running_sum/moving_avg）",
    "pivot": "行转列透视表（sum/count/avg/min/max 聚合）",
    "unpivot": "列转行逆透视",
    "fillna": "空值填充（constant/ffill/bfill/mean/median）",
    "normalize": "数据归一化（minmax/zscore）",
    "string_ops": "批量字符串操作（upper/lower/trim/replace/substring/extract 等）",
}

_OP_META: dict[str, TransformOpMeta] = {
    name: TransformOpMeta(name=name, description=desc)
    for name, desc in _BUILTIN_OP_DESCRIPTIONS.items()
}


def register_transform(
    name: str, description: str = "", config_schema: dict[str, Any] | None = None
) -> Callable[[TransformOp], TransformOp]:
    """W2-#21 · @transform 装饰器：注册算子到 TRANSFORM_REGISTRY + _OP_META。

    用法::

        @register_transform("my_op", description="自定义算子")
        def op_my(rows, config):
            return rows
    """

    def _deco(fn: TransformOp) -> TransformOp:
        TRANSFORM_REGISTRY[name] = fn
        _OP_META[name] = TransformOpMeta(
            name=name, description=description, config_schema=config_schema or {}
        )
        return fn

    return _deco


def list_op_catalog() -> list[TransformOpMeta]:
    """返回所有已注册算子的元信息（含内建 + 装饰器注册）。"""
    return [meta.model_copy() for meta in _OP_META.values()]


class TransformError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def apply_transform(op_name: str, rows: list[dict], config: dict) -> list[dict]:
    op = TRANSFORM_REGISTRY.get(op_name)
    if op is None:
        raise TransformError("UNKNOWN_OP", f"未知算子 {op_name!r}，可用：{list(TRANSFORM_REGISTRY.keys())}")
    return op(rows, config)


def apply_pipeline(rows: list[dict], steps: list[dict]) -> list[dict]:
    result = rows
    for step in steps:
        op_name = step.get("op", "")
        config = step.get("config", {})
        result = apply_transform(op_name, result, config)
    return result
