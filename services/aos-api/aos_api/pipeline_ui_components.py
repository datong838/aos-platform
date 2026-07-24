"""W2-BH · Pipeline UI 组件引擎组。

- PipelineLayoutEngine：Pipeline界面四区域引擎（顶部工具栏/详细侧栏/提案/历史视图）

详见 docs/palantier/20_tech/220tech_w2-bh-pipeline-ui-components.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_VALID_REGIONS = {"toolbar", "sidebar", "proposal", "history"}

_VALID_TOOLBAR_ITEM_TYPES = {"button", "dropdown", "separator", "search", "toggle"}
_VALID_SIDEBAR_ITEM_TYPES = {"section", "field", "action"}
_VALID_PROPOSAL_STATUSES = {"draft", "reviewing", "approved", "rejected"}
_VALID_HISTORY_TYPES = {"create", "update", "delete", "execute", "publish"}

_MAX_LAYOUTS = 200
_MAX_PROPOSALS = 200
_MAX_HISTORY = 200

# ════════════════════ 数据模型 ════════════════════


class ToolbarItem(BaseModel):
    id: str = Field(default_factory=lambda: "toolbar-" + uuid.uuid4().hex[:8])
    type: str
    label: str = ""
    icon: str = ""
    action: str = ""
    enabled: bool = True
    visible: bool = True
    options: list[dict[str, Any]] = Field(default_factory=list)
    tooltip: str = ""


class SidebarItem(BaseModel):
    id: str = Field(default_factory=lambda: "sidebar-" + uuid.uuid4().hex[:8])
    type: str
    label: str = ""
    field_type: str = ""
    value: Any = None
    required: bool = False
    options: list[dict[str, Any]] = Field(default_factory=list)
    visible: bool = True


class PipelineProposal(BaseModel):
    id: str = Field(default_factory=lambda: "prop-" + uuid.uuid4().hex[:10])
    pipeline_id: str
    title: str
    description: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"
    reviewer_id: str = ""
    reviewed_at: float = 0.0
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class PipelineHistoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: "hist-" + uuid.uuid4().hex[:10])
    pipeline_id: str
    type: str
    actor_id: str = ""
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())


class PipelineLayout(BaseModel):
    id: str = Field(default_factory=lambda: "layout-" + uuid.uuid4().hex[:10])
    pipeline_id: str
    name: str
    description: str = ""
    toolbar: list[ToolbarItem] = Field(default_factory=list)
    sidebar: list[SidebarItem] = Field(default_factory=list)
    proposal_config: dict[str, Any] = Field(default_factory=dict)
    history_config: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


# ════════════════════ 错误 ════════════════════


class PipelineUIComponentsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ PipelineLayoutEngine ════════════════════


class PipelineLayoutEngine:
    def __init__(self) -> None:
        self._layouts: dict[str, PipelineLayout] = {}
        self._proposals: list[PipelineProposal] = []
        self._history: list[PipelineHistoryEntry] = []
        self._lock = threading.Lock()

    # ─── 布局管理 ───

    def create_layout(self, layout: PipelineLayout) -> PipelineLayout:
        if not layout.pipeline_id:
            raise PipelineUIComponentsError("MISSING_PIPELINE_ID", "pipeline_id 不能为空")
        if not layout.name:
            raise PipelineUIComponentsError("MISSING_NAME", "布局名称不能为空")
        for item in layout.toolbar:
            if item.type not in _VALID_TOOLBAR_ITEM_TYPES:
                raise PipelineUIComponentsError("INVALID_TOOLBAR_TYPE", f"未知工具栏项类型：{item.type}")
        for item in layout.sidebar:
            if item.type not in _VALID_SIDEBAR_ITEM_TYPES:
                raise PipelineUIComponentsError("INVALID_SIDEBAR_TYPE", f"未知侧栏项类型：{item.type}")
        with self._lock:
            if len(self._layouts) >= _MAX_LAYOUTS:
                oldest_id = next(iter(self._layouts))
                self._layouts.pop(oldest_id, None)
            self._layouts[layout.id] = layout
        self._add_history(layout.pipeline_id, "create", "创建布局", {"layout_id": layout.id})
        return layout

    def get_layout(self, layout_id: str) -> PipelineLayout:
        layout = self._layouts.get(layout_id)
        if layout is None:
            raise PipelineUIComponentsError("NOT_FOUND", f"布局 {layout_id} 不存在")
        return layout

    def get_layout_by_pipeline(self, pipeline_id: str) -> list[PipelineLayout]:
        return [l for l in self._layouts.values() if l.pipeline_id == pipeline_id]

    def list_layouts(self) -> list[PipelineLayout]:
        return list(self._layouts.values())

    def update_layout(self, layout_id: str, updates: dict[str, Any]) -> PipelineLayout:
        layout = self.get_layout(layout_id)
        for k, v in updates.items():
            if k in ("id", "pipeline_id", "created_at"):
                continue
            if k == "toolbar" and isinstance(v, list):
                for item in v:
                    itype = item.type if hasattr(item, "type") else item.get("type", "")
                    if itype not in _VALID_TOOLBAR_ITEM_TYPES:
                        raise PipelineUIComponentsError("INVALID_TOOLBAR_TYPE", f"未知工具栏项类型：{itype}")
            if k == "sidebar" and isinstance(v, list):
                for item in v:
                    itype = item.type if hasattr(item, "type") else item.get("type", "")
                    if itype not in _VALID_SIDEBAR_ITEM_TYPES:
                        raise PipelineUIComponentsError("INVALID_SIDEBAR_TYPE", f"未知侧栏项类型：{itype}")
            if hasattr(layout, k):
                setattr(layout, k, v)
        layout.updated_at = time.time()
        self._add_history(layout.pipeline_id, "update", "更新布局", {"layout_id": layout_id})
        return layout

    def delete_layout(self, layout_id: str) -> bool:
        layout = self._layouts.get(layout_id)
        if layout is None:
            return False
        pipeline_id = layout.pipeline_id
        with self._lock:
            self._layouts.pop(layout_id, None)
        self._add_history(pipeline_id, "delete", "删除布局", {"layout_id": layout_id})
        return True

    # ─── 工具栏操作 ───

    def update_toolbar(self, layout_id: str, items: list[ToolbarItem]) -> PipelineLayout:
        layout = self.get_layout(layout_id)
        for item in items:
            if item.type not in _VALID_TOOLBAR_ITEM_TYPES:
                raise PipelineUIComponentsError("INVALID_TOOLBAR_TYPE", f"未知工具栏项类型：{item.type}")
        layout.toolbar = items
        layout.updated_at = time.time()
        self._add_history(layout.pipeline_id, "update", "更新工具栏", {"layout_id": layout_id})
        return layout

    def get_toolbar(self, layout_id: str) -> list[ToolbarItem]:
        layout = self.get_layout(layout_id)
        return layout.toolbar

    # ─── 侧栏操作 ───

    def update_sidebar(self, layout_id: str, items: list[SidebarItem]) -> PipelineLayout:
        layout = self.get_layout(layout_id)
        for item in items:
            if item.type not in _VALID_SIDEBAR_ITEM_TYPES:
                raise PipelineUIComponentsError("INVALID_SIDEBAR_TYPE", f"未知侧栏项类型：{item.type}")
        layout.sidebar = items
        layout.updated_at = time.time()
        self._add_history(layout.pipeline_id, "update", "更新侧栏", {"layout_id": layout_id})
        return layout

    def get_sidebar(self, layout_id: str) -> list[SidebarItem]:
        layout = self.get_layout(layout_id)
        return layout.sidebar

    # ─── 提案管理 ───

    def create_proposal(self, proposal: PipelineProposal) -> PipelineProposal:
        if not proposal.pipeline_id:
            raise PipelineUIComponentsError("MISSING_PIPELINE_ID", "pipeline_id 不能为空")
        if not proposal.title:
            raise PipelineUIComponentsError("MISSING_TITLE", "提案标题不能为空")
        if proposal.status not in _VALID_PROPOSAL_STATUSES:
            raise PipelineUIComponentsError("INVALID_STATUS", f"未知提案状态：{proposal.status}")
        with self._lock:
            if len(self._proposals) >= _MAX_PROPOSALS:
                self._proposals.pop(0)
            self._proposals.append(proposal)
        self._add_history(proposal.pipeline_id, "create", "创建提案", {"proposal_id": proposal.id, "title": proposal.title})
        return proposal

    def get_proposal(self, proposal_id: str) -> PipelineProposal:
        for p in self._proposals:
            if p.id == proposal_id:
                return p
        raise PipelineUIComponentsError("NOT_FOUND", f"提案 {proposal_id} 不存在")

    def list_proposals(self, pipeline_id: str | None = None, status: str | None = None) -> list[PipelineProposal]:
        items = list(self._proposals)
        if pipeline_id:
            items = [p for p in items if p.pipeline_id == pipeline_id]
        if status:
            items = [p for p in items if p.status == status]
        return list(reversed(items))

    def update_proposal(self, proposal_id: str, updates: dict[str, Any]) -> PipelineProposal:
        proposal = self.get_proposal(proposal_id)
        for k, v in updates.items():
            if k in ("id", "pipeline_id", "created_at"):
                continue
            if k == "status" and v not in _VALID_PROPOSAL_STATUSES:
                raise PipelineUIComponentsError("INVALID_STATUS", f"未知提案状态：{v}")
            if hasattr(proposal, k):
                setattr(proposal, k, v)
        proposal.updated_at = time.time()
        self._add_history(proposal.pipeline_id, "update", "更新提案", {"proposal_id": proposal_id, "status": proposal.status})
        return proposal

    def delete_proposal(self, proposal_id: str) -> bool:
        for i, p in enumerate(self._proposals):
            if p.id == proposal_id:
                pipeline_id = p.pipeline_id
                with self._lock:
                    del self._proposals[i]
                self._add_history(pipeline_id, "delete", "删除提案", {"proposal_id": proposal_id})
                return True
        return False

    # ─── 历史记录 ───

    def _add_history(self, pipeline_id: str, type_: str, message: str, details: dict[str, Any]) -> None:
        if type_ not in _VALID_HISTORY_TYPES:
            raise PipelineUIComponentsError("INVALID_HISTORY_TYPE", f"未知历史记录类型：{type_}")
        entry = PipelineHistoryEntry(
            pipeline_id=pipeline_id,
            type=type_,
            message=message,
            details=details,
        )
        with self._lock:
            if len(self._history) >= _MAX_HISTORY:
                self._history.pop(0)
            self._history.append(entry)

    def list_history(self, pipeline_id: str | None = None, limit: int = 50) -> list[PipelineHistoryEntry]:
        items = list(self._history)
        if pipeline_id:
            items = [h for h in items if h.pipeline_id == pipeline_id]
        items = list(reversed(items))
        if limit > 0:
            items = items[:limit]
        return items


# ════════════════════ 单例 ════════════════════

_layout_engine: PipelineLayoutEngine | None = None
_singleton_lock = threading.Lock()


def get_layout_engine() -> PipelineLayoutEngine:
    global _layout_engine
    if _layout_engine is None:
        with _singleton_lock:
            if _layout_engine is None:
                _layout_engine = PipelineLayoutEngine()
    return _layout_engine
