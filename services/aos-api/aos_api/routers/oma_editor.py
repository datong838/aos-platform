"""W2-J · OMA 编辑器增强路由：Property Editor + Proposals."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.oma_editor import (
    PropertyEditor,
    PropertyEditorError,
    Proposal,
    ProposalComment,
    ProposalError,
    ProposalStatus,
    get_property_engine,
    get_proposal_engine,
)

router = APIRouter(tags=["oma-editor"])
log = get_logger("aos-api.oma-editor")


def _map_prop_error(err: PropertyEditorError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_proposal_error(err: ProposalError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #28+#34 Property Editor ───────────────

class PropertyCreateIn(BaseModel):
    object_type: str
    name: str
    display_name: str = ""
    description: str = ""
    data_type: str = "string"
    backing_column: str = ""
    backing_dataset: str = ""
    title_key: bool = False
    is_tsp: bool = False
    tsp_config: dict[str, Any] = Field(default_factory=dict)
    origin: str = "manual"
    origin_mapping: dict[str, Any] = Field(default_factory=dict)
    nullable: bool = True
    indexed: bool = False
    unique: bool = False
    default_value: Any = None
    validation_rules: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class PropertyUpdateIn(BaseModel):
    display_name: str | None = None
    description: str | None = None
    data_type: str | None = None
    backing_column: str | None = None
    backing_dataset: str | None = None
    title_key: bool | None = None
    is_tsp: bool | None = None
    tsp_config: dict[str, Any] | None = None
    origin: str | None = None
    origin_mapping: dict[str, Any] | None = None
    nullable: bool | None = None
    indexed: bool | None = None
    unique: bool | None = None
    default_value: Any = None
    validation_rules: list[dict[str, Any]] | None = None
    tags: list[str] | None = None


@router.get("/v1/oma/property-types")
def list_properties(
    object_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#28+#34 · 列出属性（可按 object_type 过滤）。"""
    _ = principal
    eng = get_property_engine()
    props = eng.list(object_type=object_type)
    return {"properties": [p.model_dump() for p in props], "count": len(props)}


@router.get("/v1/oma/property-types/{prop_id}")
def get_property(
    prop_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#28+#34 · 获取属性详情。"""
    _ = principal
    eng = get_property_engine()
    try:
        return eng.get(prop_id).model_dump()
    except PropertyEditorError as err:
        raise _map_prop_error(err) from err


@router.post("/v1/oma/property-types")
def create_property(
    body: PropertyCreateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#28+#34 · 创建属性。"""
    _ = principal
    eng = get_property_engine()
    prop = PropertyEditor(**body.model_dump())
    try:
        created = eng.create(prop)
    except PropertyEditorError as err:
        raise _map_prop_error(err) from err
    log.info("property_created id=%s otype=%s name=%s", created.id, created.object_type, created.name)
    return created.model_dump()


@router.put("/v1/oma/property-types/{prop_id}")
def update_property(
    prop_id: str,
    body: PropertyUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#28+#34 · 更新属性。"""
    _ = principal
    eng = get_property_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = eng.update(prop_id, updates)
    except PropertyEditorError as err:
        raise _map_prop_error(err) from err
    log.info("property_updated id=%s", prop_id)
    return updated.model_dump()


@router.delete("/v1/oma/property-types/{prop_id}")
def delete_property(
    prop_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#28+#34 · 删除属性。"""
    _ = principal
    eng = get_property_engine()
    try:
        eng.delete(prop_id)
    except PropertyEditorError as err:
        raise _map_prop_error(err) from err
    log.info("property_deleted id=%s", prop_id)
    return {"ok": True}


@router.post("/v1/oma/property-types/{prop_id}/promote-title-key")
def promote_title_key(
    prop_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#28 · 设为 title key（同一 OT 仅一个）。"""
    _ = principal
    eng = get_property_engine()
    try:
        prop = eng.promote_title_key(prop_id)
    except PropertyEditorError as err:
        raise _map_prop_error(err) from err
    log.info("title_key_promoted id=%s otype=%s", prop_id, prop.object_type)
    return prop.model_dump()


@router.get("/v1/oma/object-types/{object_type}/title-key")
def get_title_key(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#28 · 获取 Object Type 的当前 title key。"""
    _ = principal
    eng = get_property_engine()
    prop = eng.get_title_key(object_type)
    if prop:
        return prop.model_dump()
    return {"objectType": object_type, "titleKey": None}


# ─────────────── #35 Proposals 审查工作流 ───────────────

class ProposalCreateIn(BaseModel):
    title: str
    branch_id: str
    author: str = ""
    description: str = ""


class CommentIn(BaseModel):
    author: str
    body: str
    action: str = "comment"


class ReviewerIn(BaseModel):
    reviewer: str


@router.get("/v1/ontology/proposals")
def list_proposals(
    status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 列出提案（可按 status 过滤）。"""
    _ = principal
    eng = get_proposal_engine()
    props = eng.list(status=status)
    return {"proposals": [p.model_dump() for p in props], "count": len(props)}


@router.post("/v1/ontology/proposals")
def create_proposal(
    body: ProposalCreateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 创建提案（关联分支）。"""
    _ = principal
    eng = get_proposal_engine()
    proposal = eng.create(body.title, body.branch_id, author=body.author, description=body.description)
    log.info("proposal_created id=%s title=%s branch=%s", proposal.id, proposal.title, proposal.branch_id)
    return proposal.model_dump()


@router.get("/v1/ontology/proposals/{proposal_id}")
def get_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 获取提案详情。"""
    _ = principal
    eng = get_proposal_engine()
    try:
        return eng.get(proposal_id).model_dump()
    except ProposalError as err:
        raise _map_proposal_error(err) from err


@router.post("/v1/ontology/proposals/{proposal_id}/submit")
def submit_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 提交审查（DRAFT/WITHDRAWN/REJECTED → PENDING_REVIEW）。"""
    _ = principal
    eng = get_proposal_engine()
    try:
        return eng.submit(proposal_id).model_dump()
    except ProposalError as err:
        raise _map_proposal_error(err) from err


@router.post("/v1/ontology/proposals/{proposal_id}/start-review")
def start_review_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 开始审查（PENDING_REVIEW → IN_REVIEW）。"""
    _ = principal
    eng = get_proposal_engine()
    try:
        return eng.start_review(proposal_id).model_dump()
    except ProposalError as err:
        raise _map_proposal_error(err) from err


@router.post("/v1/ontology/proposals/{proposal_id}/approve")
def approve_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 批准（IN_REVIEW → APPROVED）。"""
    _ = principal
    eng = get_proposal_engine()
    try:
        return eng.approve(proposal_id).model_dump()
    except ProposalError as err:
        raise _map_proposal_error(err) from err


@router.post("/v1/ontology/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 拒绝（IN_REVIEW → REJECTED）。"""
    _ = principal
    eng = get_proposal_engine()
    try:
        return eng.reject(proposal_id).model_dump()
    except ProposalError as err:
        raise _map_proposal_error(err) from err


@router.post("/v1/ontology/proposals/{proposal_id}/withdraw")
def withdraw_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 撤回（→ WITHDRAWN）。"""
    _ = principal
    eng = get_proposal_engine()
    try:
        return eng.withdraw(proposal_id).model_dump()
    except ProposalError as err:
        raise _map_proposal_error(err) from err


@router.post("/v1/ontology/proposals/{proposal_id}/publish")
def publish_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 发布（APPROVED → PUBLISHED）。"""
    _ = principal
    eng = get_proposal_engine()
    try:
        return eng.publish(proposal_id).model_dump()
    except ProposalError as err:
        raise _map_proposal_error(err) from err


@router.post("/v1/ontology/proposals/{proposal_id}/comments")
def add_comment(
    proposal_id: str,
    body: CommentIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 添加评论。"""
    _ = principal
    eng = get_proposal_engine()
    comment = ProposalComment(author=body.author, body=body.body, action=body.action)
    try:
        proposal = eng.add_comment(proposal_id, comment)
    except ProposalError as err:
        raise _map_proposal_error(err) from err
    log.info("comment_added proposal=%s author=%s", proposal_id, body.author)
    return proposal.model_dump()


@router.post("/v1/ontology/proposals/{proposal_id}/reviewers")
def add_reviewer(
    proposal_id: str,
    body: ReviewerIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#35 · 添加审查者。"""
    _ = principal
    eng = get_proposal_engine()
    try:
        return eng.add_reviewer(proposal_id, body.reviewer).model_dump()
    except ProposalError as err:
        raise _map_proposal_error(err) from err
