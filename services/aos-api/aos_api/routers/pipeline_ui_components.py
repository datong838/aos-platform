"""W2-BH · Pipeline UI 组件路由：PipelineLayoutEngine 四区域接口（工具栏/侧栏/提案/历史）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.pipeline_ui_components import (
    PipelineLayout,
    PipelineProposal,
    PipelineUIComponentsError,
    SidebarItem,
    ToolbarItem,
    get_layout_engine,
)

router = APIRouter(prefix="/pipeline-ui-components", tags=["pipeline-ui-components"])
log = get_logger("aos-api.pipeline-ui-components")


def _map_err(err: PipelineUIComponentsError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ 布局管理 ════════════════════


class ToolbarItemIn(BaseModel):
    type: str = Field(min_length=1)
    label: str = ""
    icon: str = ""
    action: str = ""
    enabled: bool = True
    visible: bool = True
    options: list[dict[str, Any]] = Field(default_factory=list)
    tooltip: str = ""


class SidebarItemIn(BaseModel):
    type: str = Field(min_length=1)
    label: str = ""
    field_type: str = ""
    value: Any = None
    required: bool = False
    options: list[dict[str, Any]] = Field(default_factory=list)
    visible: bool = True


class PipelineLayoutIn(BaseModel):
    pipeline_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    toolbar: list[ToolbarItemIn] = Field(default_factory=list)
    sidebar: list[SidebarItemIn] = Field(default_factory=list)
    proposal_config: dict[str, Any] = Field(default_factory=dict)
    history_config: dict[str, Any] = Field(default_factory=dict)


class PipelineLayoutUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    toolbar: list[ToolbarItemIn] | None = None
    sidebar: list[SidebarItemIn] | None = None
    proposal_config: dict[str, Any] | None = None
    history_config: dict[str, Any] | None = None


@router.post("/v1/layouts")
def create_layout(
    body: PipelineLayoutIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """创建布局。"""
    _ = principal
    try:
        toolbar_items = [ToolbarItem(**t.model_dump()) for t in body.toolbar]
        sidebar_items = [SidebarItem(**s.model_dump()) for s in body.sidebar]
        layout = get_layout_engine().create_layout(PipelineLayout(
            pipeline_id=body.pipeline_id,
            name=body.name,
            description=body.description,
            toolbar=toolbar_items,
            sidebar=sidebar_items,
            proposal_config=body.proposal_config,
            history_config=body.history_config,
        ))
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc
    return {"item": layout.model_dump()}


@router.get("/v1/layouts")
def list_layouts(
    pipeline_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """布局列表。"""
    _ = principal
    if pipeline_id:
        items = get_layout_engine().get_layout_by_pipeline(pipeline_id)
    else:
        items = get_layout_engine().list_layouts()
    return {"items": [l.model_dump() for l in items], "count": len(items)}


@router.get("/v1/layouts/{layout_id}")
def get_layout(
    layout_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """单条布局。"""
    _ = principal
    try:
        return {"item": get_layout_engine().get_layout(layout_id).model_dump()}
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/layouts/{layout_id}")
def update_layout(
    layout_id: str, body: PipelineLayoutUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """更新布局。"""
    _ = principal
    updates: dict[str, Any] = {}
    for k, v in body.model_dump().items():
        if v is None:
            continue
        if k == "toolbar":
            updates[k] = [ToolbarItem(**t.model_dump()) for t in v]
        elif k == "sidebar":
            updates[k] = [SidebarItem(**s.model_dump()) for s in v]
        else:
            updates[k] = v
    try:
        layout = get_layout_engine().update_layout(layout_id, updates)
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc
    return {"item": layout.model_dump()}


@router.delete("/v1/layouts/{layout_id}")
def delete_layout(
    layout_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """删除布局。"""
    _ = principal
    ok = get_layout_engine().delete_layout(layout_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"布局 {layout_id} 不存在", status_code=404)
    return {"id": layout_id, "deleted": True}


# ════════════════════ 工具栏 ════════════════════


@router.get("/v1/layouts/{layout_id}/toolbar")
def get_toolbar(
    layout_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """获取工具栏配置。"""
    _ = principal
    try:
        items = get_layout_engine().get_toolbar(layout_id)
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.put("/v1/layouts/{layout_id}/toolbar")
def update_toolbar(
    layout_id: str, body: list[ToolbarItemIn],
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """更新工具栏配置。"""
    _ = principal
    items = [ToolbarItem(**t.model_dump()) for t in body]
    try:
        layout = get_layout_engine().update_toolbar(layout_id, items)
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc
    return {"item": layout.model_dump()}


# ════════════════════ 侧栏 ════════════════════


@router.get("/v1/layouts/{layout_id}/sidebar")
def get_sidebar(
    layout_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """获取侧栏配置。"""
    _ = principal
    try:
        items = get_layout_engine().get_sidebar(layout_id)
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.put("/v1/layouts/{layout_id}/sidebar")
def update_sidebar(
    layout_id: str, body: list[SidebarItemIn],
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """更新侧栏配置。"""
    _ = principal
    items = [SidebarItem(**s.model_dump()) for s in body]
    try:
        layout = get_layout_engine().update_sidebar(layout_id, items)
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc
    return {"item": layout.model_dump()}


# ════════════════════ 提案管理 ════════════════════


class PipelineProposalIn(BaseModel):
    pipeline_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"
    reviewer_id: str = ""


class PipelineProposalUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    content: dict[str, Any] | None = None
    status: str | None = None
    reviewer_id: str | None = None
    reviewed_at: float | None = None


@router.post("/v1/proposals")
def create_proposal(
    body: PipelineProposalIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """创建提案。"""
    _ = principal
    try:
        proposal = get_layout_engine().create_proposal(PipelineProposal(**body.model_dump()))
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc
    return {"item": proposal.model_dump()}


@router.get("/v1/proposals")
def list_proposals(
    pipeline_id: str | None = None, status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """提案列表。"""
    _ = principal
    items = get_layout_engine().list_proposals(pipeline_id=pipeline_id, status=status)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.get("/v1/proposals/{proposal_id}")
def get_proposal(
    proposal_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """单条提案。"""
    _ = principal
    try:
        return {"item": get_layout_engine().get_proposal(proposal_id).model_dump()}
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/proposals/{proposal_id}")
def update_proposal(
    proposal_id: str, body: PipelineProposalUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """更新提案。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        proposal = get_layout_engine().update_proposal(proposal_id, updates)
    except PipelineUIComponentsError as exc:
        raise _map_err(exc) from exc
    return {"item": proposal.model_dump()}


@router.delete("/v1/proposals/{proposal_id}")
def delete_proposal(
    proposal_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """删除提案。"""
    _ = principal
    ok = get_layout_engine().delete_proposal(proposal_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"提案 {proposal_id} 不存在", status_code=404)
    return {"id": proposal_id, "deleted": True}


# ════════════════════ 历史记录 ════════════════════


@router.get("/v1/history")
def list_history(
    pipeline_id: str | None = None, limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """历史记录列表。"""
    _ = principal
    items = get_layout_engine().list_history(pipeline_id=pipeline_id, limit=limit)
    return {"items": [h.model_dump() for h in items], "count": len(items)}
