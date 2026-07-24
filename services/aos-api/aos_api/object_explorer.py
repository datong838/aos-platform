"""W2-#12 · OE 探索图表可视化。

7 种图表 + group_by 聚合 + filters + 撤销重做 + 保存设计。
图表数据来源为外部传入的 rows（调用方负责权限过滤）。

详见 docs/palantier/20_tech/220tech_w2-c-ontology-manager.md §2.2。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .function_engine import evaluate, parse


ChartKind = Literal[
    "bar",
    "line",
    "pie",
    "scatter",
    "heatmap",
    "histogram",
    "table",
]

CHART_CATALOG: list[dict[str, Any]] = [
    {"kind": "bar", "name": "柱状图", "description": "分类聚合对比"},
    {"kind": "line", "name": "折线图", "description": "时间/顺序趋势"},
    {"kind": "pie", "name": "饼图", "description": "占比分布"},
    {"kind": "scatter", "name": "散点图", "description": "二维相关性"},
    {"kind": "heatmap", "name": "热力图", "description": "密度矩阵"},
    {"kind": "histogram", "name": "直方图", "description": "数值分布"},
    {"kind": "table", "name": "表格", "description": "明细列表"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExplorerMetric(BaseModel):
    field: str
    agg: Literal["count", "sum", "avg", "min", "max"] = "count"


class ExplorerFilter(BaseModel):
    field: str
    expr: str  # DSL 表达式，复用 function_engine


class ExplorerDesign(BaseModel):
    id: str = Field(default_factory=lambda: "design-" + uuid.uuid4().hex[:8])
    name: str
    otd_id: str
    chart_kind: ChartKind
    group_by: str = ""
    metrics: list[ExplorerMetric] = Field(default_factory=list)
    filters: list[ExplorerFilter] = Field(default_factory=list)
    sort_order: int = 0
    saved_at: str = Field(default_factory=_now)


class ExplorerError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_CHART_KINDS = {item["kind"] for item in CHART_CATALOG}


def _apply_filter(rows: list[dict[str, Any]], filters: list[ExplorerFilter]) -> list[dict[str, Any]]:
    if not filters:
        return rows
    result: list[dict[str, Any]] = []
    for row in rows:
        keep = True
        for f in filters:
            try:
                ok = bool(evaluate(parse(f.expr), row))
            except Exception:
                ok = False
            if not ok:
                keep = False
                break
        if keep:
            result.append(row)
    return result


def _aggregate(values: list[Any], agg: str) -> float | None:
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if agg == "count":
        return float(len(values))
    if not nums:
        return None
    if agg == "sum":
        return float(sum(nums))
    if agg == "avg":
        return float(sum(nums)) / len(nums)
    if agg == "min":
        return float(min(nums))
    if agg == "max":
        return float(max(nums))
    return None


class ObjectExplorerStore:
    """探索图表设计注册表 + 撤销重做 + 渲染。"""

    def __init__(self) -> None:
        self._designs: dict[str, ExplorerDesign] = {}
        self._undo: dict[str, list[ExplorerDesign]] = {}
        self._redo: dict[str, list[ExplorerDesign]] = {}

    def create(self, design: ExplorerDesign) -> ExplorerDesign:
        if not design.name:
            raise ExplorerError("MISSING_NAME", "设计缺少 name")
        if not design.otd_id:
            raise ExplorerError("MISSING_OTD", "设计缺少 otd_id")
        if design.chart_kind not in _CHART_KINDS:
            raise ExplorerError("UNKNOWN_CHART", f"未知图表 {design.chart_kind!r}")
        self._designs[design.id] = design
        return design

    def get(self, design_id: str) -> ExplorerDesign | None:
        return self._designs.get(design_id)

    def list_by_otd(self, otd_id: str) -> list[ExplorerDesign]:
        return [d for d in self._designs.values() if d.otd_id == otd_id]

    def list_all(self) -> list[ExplorerDesign]:
        return list(self._designs.values())

    def _push_undo(self, design_id: str, snapshot: ExplorerDesign) -> None:
        self._undo.setdefault(design_id, []).append(snapshot)
        self._undo[design_id] = self._undo[design_id][-50:]
        self._redo.pop(design_id, None)

    def update(self, design_id: str, **fields: Any) -> ExplorerDesign:
        design = self._designs.get(design_id)
        if design is None:
            raise ExplorerError("NOT_FOUND", f"设计 {design_id!r} 不存在")
        if "chart_kind" in fields and fields["chart_kind"] not in _CHART_KINDS:
            raise ExplorerError("UNKNOWN_CHART", f"未知图表 {fields['chart_kind']!r}")
        self._push_undo(design_id, design.model_copy())
        updated = design.model_copy(update=fields)
        updated.saved_at = _now()
        self._designs[design_id] = updated
        return updated

    def save_design(self, design_id: str, snapshot: ExplorerDesign) -> ExplorerDesign:
        return self.update(design_id, **snapshot.model_dump(exclude={"id", "otd_id"}))

    def undo(self, design_id: str) -> ExplorerDesign:
        stack = self._undo.get(design_id, [])
        if not stack:
            raise ExplorerError("UNDO_EMPTY", "无可撤销操作")
        current = self._designs[design_id]
        self._redo.setdefault(design_id, []).append(current.model_copy())
        previous = stack.pop()
        self._designs[design_id] = previous
        return previous

    def redo(self, design_id: str) -> ExplorerDesign:
        stack = self._redo.get(design_id, [])
        if not stack:
            raise ExplorerError("REDO_EMPTY", "无可重做操作")
        current = self._designs[design_id]
        self._undo.setdefault(design_id, []).append(current.model_copy())
        nxt = stack.pop()
        self._designs[design_id] = nxt
        return nxt

    def delete(self, design_id: str) -> bool:
        existed = design_id in self._designs
        self._designs.pop(design_id, None)
        self._undo.pop(design_id, None)
        self._redo.pop(design_id, None)
        return existed

    def render(self, design_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        design = self._designs.get(design_id)
        if design is None:
            raise ExplorerError("NOT_FOUND", f"设计 {design_id!r} 不存在")
        filtered = _apply_filter(rows, design.filters)
        if design.group_by:
            buckets: dict[Any, list[dict[str, Any]]] = {}
            for row in filtered:
                key = row.get(design.group_by)
                buckets.setdefault(key, []).append(row)
            series = []
            for key, group_rows in buckets.items():
                point: dict[str, Any] = {design.group_by: key}
                for metric in design.metrics:
                    values = [r.get(metric.field) for r in group_rows]
                    point[f"{metric.field}_{metric.agg}"] = _aggregate(values, metric.agg)
                series.append(point)
            return {
                "chart_kind": design.chart_kind,
                "group_by": design.group_by,
                "series": series,
                "total": len(filtered),
            }
        return {
            "chart_kind": design.chart_kind,
            "series": filtered,
            "total": len(filtered),
        }


_store = ObjectExplorerStore()


def get_store() -> ObjectExplorerStore:
    return _store


def list_chart_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in CHART_CATALOG]
