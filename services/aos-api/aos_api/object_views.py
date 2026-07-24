"""W2-#13 · Object Views 微件系统。

10+ 种微件 + 可视化编辑器数据模型 + 视图 CRUD + 拖拽排序。
视图独立 store，不修改 ObjectTypeDefinition（最小更改）。

详见 docs/palantier/20_tech/220tech_w2-c-ontology-manager.md §2.1。
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


WidgetKind = Literal[
    "property_table",
    "property_list",
    "object_card",
    "timeline",
    "bar_chart",
    "line_chart",
    "pie_chart",
    "scatter_plot",
    "map_view",
    "media_gallery",
    "link_list",
    "rich_text",
]

WIDGET_CATALOG: list[dict[str, Any]] = [
    {"kind": "property_table", "name": "属性表格", "description": "以表格展示对象所有属性"},
    {"kind": "property_list", "name": "属性列表", "description": "以键值对列表展示属性"},
    {"kind": "object_card", "name": "对象卡片", "description": "卡片式摘要展示"},
    {"kind": "timeline", "name": "时间线", "description": "按时间排序的事件流"},
    {"kind": "bar_chart", "name": "柱状图", "description": "分类聚合柱状图"},
    {"kind": "line_chart", "name": "折线图", "description": "趋势折线图"},
    {"kind": "pie_chart", "name": "饼图", "description": "占比饼图"},
    {"kind": "scatter_plot", "name": "散点图", "description": "二维分布散点图"},
    {"kind": "map_view", "name": "地图视图", "description": "地理坐标地图"},
    {"kind": "media_gallery", "name": "媒体画廊", "description": "图片/视频媒体集"},
    {"kind": "link_list", "name": "链接列表", "description": "关联对象链接列表"},
    {"kind": "rich_text", "name": "富文本", "description": "富文本说明区块"},
]


class ViewWidget(BaseModel):
    id: str = Field(default_factory=lambda: "wgt-" + uuid.uuid4().hex[:8])
    kind: WidgetKind
    title: str = ""
    bound_field: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class ObjectView(BaseModel):
    id: str = Field(default_factory=lambda: "view-" + uuid.uuid4().hex[:8])
    name: str
    otd_id: str
    widgets: list[ViewWidget] = Field(default_factory=list)
    is_default: bool = False


class ObjectViewError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_WIDGET_KINDS = {item["kind"] for item in WIDGET_CATALOG}


class ObjectViewStore:
    """对象视图注册表：CRUD + 拖拽排序 + 按 OTD 查询。"""

    def __init__(self) -> None:
        self._views: dict[str, ObjectView] = {}

    def create(self, view: ObjectView) -> ObjectView:
        if not view.name:
            raise ObjectViewError("MISSING_NAME", "视图缺少 name")
        if not view.otd_id:
            raise ObjectViewError("MISSING_OTD", "视图缺少 otd_id")
        for widget in view.widgets:
            self._validate_widget(widget)
        if view.is_default:
            self._clear_default(view.otd_id)
        self._views[view.id] = view
        return view

    def _validate_widget(self, widget: ViewWidget) -> None:
        if widget.kind not in _WIDGET_KINDS:
            raise ObjectViewError(
                "UNKNOWN_WIDGET", f"未知微件类型 {widget.kind!r}，可用：{sorted(_WIDGET_KINDS)}"
            )

    def _clear_default(self, otd_id: str) -> None:
        for view in self._views.values():
            if view.otd_id == otd_id and view.is_default:
                view.is_default = False

    def get(self, view_id: str) -> ObjectView | None:
        return self._views.get(view_id)

    def list_by_otd(self, otd_id: str) -> list[ObjectView]:
        return [v for v in self._views.values() if v.otd_id == otd_id]

    def list_all(self) -> list[ObjectView]:
        return list(self._views.values())

    def update(self, view_id: str, **fields: Any) -> ObjectView:
        view = self._views.get(view_id)
        if view is None:
            raise ObjectViewError("NOT_FOUND", f"视图 {view_id!r} 不存在")
        if "widgets" in fields:
            for widget in fields["widgets"]:
                self._validate_widget(widget)
        if fields.get("is_default"):
            self._clear_default(view.otd_id)
        updated = view.model_copy(update=fields)
        self._views[view_id] = updated
        return updated

    def delete(self, view_id: str) -> bool:
        existed = view_id in self._views
        self._views.pop(view_id, None)
        return existed

    def reorder_widgets(self, view_id: str, widget_ids: list[str]) -> ObjectView:
        view = self._views.get(view_id)
        if view is None:
            raise ObjectViewError("NOT_FOUND", f"视图 {view_id!r} 不存在")
        current_ids = {w.id for w in view.widgets}
        if set(widget_ids) != current_ids:
            raise ObjectViewError(
                "REORDER_MISMATCH",
                "widget_ids 必须与当前微件 id 集合完全一致",
            )
        widget_map = {w.id: w for w in view.widgets}
        reordered = [widget_map[wid] for wid in widget_ids]
        updated = view.model_copy(update={"widgets": reordered})
        self._views[view_id] = updated
        return updated

    def add_widget(self, view_id: str, widget: ViewWidget) -> ObjectView:
        self._validate_widget(widget)
        return self.update(view_id, widgets=[*self._views[view_id].widgets, widget])

    def remove_widget(self, view_id: str, widget_id: str) -> ObjectView:
        view = self._views.get(view_id)
        if view is None:
            raise ObjectViewError("NOT_FOUND", f"视图 {view_id!r} 不存在")
        new_widgets = [w for w in view.widgets if w.id != widget_id]
        updated = view.model_copy(update={"widgets": new_widgets})
        self._views[view_id] = updated
        return updated


_store = ObjectViewStore()


def get_store() -> ObjectViewStore:
    return _store


def list_widget_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in WIDGET_CATALOG]
