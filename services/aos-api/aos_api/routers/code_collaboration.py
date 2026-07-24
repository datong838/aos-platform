"""W2-AC · 代码仓库与 PR 工作流组路由：#101 分支 + #102 PR + #103 变换预览."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.code_collaboration import (
    Branch,
    CodeCollaborationError,
    PullRequest,
    TransformPreview,
    get_branch_engine,
    get_pr_engine,
    get_preview_engine,
)
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["code-collaboration"])
log = get_logger("aos-api.code-collaboration")


def _map_err(err: CodeCollaborationError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND" or err.code in ("TARGET_NOT_FOUND",):
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #101 Branch ════════════════════

class BranchIn(BaseModel):
    repo_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    base_branch: str = "main"
    protected: bool = False


class BranchUpdateIn(BaseModel):
    name: str | None = None
    base_branch: str | None = None
    protected: bool | None = None


class MergeIn(BaseModel):
    target_branch: str = Field(min_length=1)
    strategy: str = "merge"


class ProtectIn(BaseModel):
    protected: bool = True


@router.post("/v1/code-collaboration/branches")
def register_branch(
    body: BranchIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#101 · 注册分支。"""
    _ = principal
    try:
        b = get_branch_engine().register(Branch(**body.model_dump()))
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": b.model_dump()}


@router.get("/v1/code-collaboration/branches")
def list_branches(
    repo_id: str | None = None, status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#101 · 分支列表。"""
    _ = principal
    items = get_branch_engine().list(repo_id=repo_id, status=status)
    return {"items": [b.model_dump() for b in items], "count": len(items)}


@router.get("/v1/code-collaboration/branches/{branch_id}")
def get_branch(
    branch_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#101 · 单条分支。"""
    _ = principal
    try:
        return {"item": get_branch_engine().get(branch_id).model_dump()}
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/code-collaboration/branches/{branch_id}")
def update_branch(
    branch_id: str, body: BranchUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#101 · 更新分支。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        b = get_branch_engine().update(branch_id, updates)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": b.model_dump()}


@router.delete("/v1/code-collaboration/branches/{branch_id}")
def delete_branch(
    branch_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#101 · 删除分支。"""
    _ = principal
    ok = get_branch_engine().delete(branch_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"分支 {branch_id} 不存在", status_code=404)
    return {"id": branch_id, "deleted": True}


@router.post("/v1/code-collaboration/branches/{branch_id}/merge")
def merge_branch(
    branch_id: str, body: MergeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#101 · 合并分支。"""
    _ = principal
    try:
        result = get_branch_engine().merge(branch_id, body.target_branch, body.strategy)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": result.model_dump()}


@router.post("/v1/code-collaboration/branches/{branch_id}/protect")
def protect_branch(
    branch_id: str, body: ProtectIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#101 · 保护/取消保护分支。"""
    _ = principal
    try:
        b = get_branch_engine().protect(branch_id, body.protected)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": b.model_dump()}


# ════════════════════ #102 PullRequest ════════════════════

class PRIn(BaseModel):
    repo_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    source_branch: str = Field(min_length=1)
    target_branch: str = Field(min_length=1)
    author: str = Field(min_length=1)
    reviewers: list[str] = Field(default_factory=list)


class PRUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None


class TransitionIn(BaseModel):
    new_status: str = Field(min_length=1)


class ReviewerIn(BaseModel):
    reviewer: str = Field(min_length=1)


class CIStatusIn(BaseModel):
    ci_status: str = Field(min_length=1)


@router.post("/v1/code-collaboration/pull-requests")
def register_pr(
    body: PRIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#102 · 注册 PR。"""
    _ = principal
    try:
        p = get_pr_engine().register(PullRequest(**body.model_dump()))
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.get("/v1/code-collaboration/pull-requests")
def list_prs(
    repo_id: str | None = None, status: str | None = None, author: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#102 · PR 列表。"""
    _ = principal
    items = get_pr_engine().list(repo_id=repo_id, status=status, author=author)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.get("/v1/code-collaboration/pull-requests/{pr_id}")
def get_pr(
    pr_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#102 · 单条 PR。"""
    _ = principal
    try:
        return {"item": get_pr_engine().get(pr_id).model_dump()}
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/code-collaboration/pull-requests/{pr_id}")
def update_pr(
    pr_id: str, body: PRUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#102 · 更新 PR。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        p = get_pr_engine().update(pr_id, updates)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.post("/v1/code-collaboration/pull-requests/{pr_id}/transition")
def transition_pr(
    pr_id: str, body: TransitionIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#102 · PR 状态转换。"""
    _ = principal
    try:
        p = get_pr_engine().transition(pr_id, body.new_status)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.post("/v1/code-collaboration/pull-requests/{pr_id}/reviewers")
def add_reviewer(
    pr_id: str, body: ReviewerIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#102 · 添加审查者。"""
    _ = principal
    try:
        p = get_pr_engine().add_reviewer(pr_id, body.reviewer)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.post("/v1/code-collaboration/pull-requests/{pr_id}/ci-status")
def set_ci_status(
    pr_id: str, body: CIStatusIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#102 · 设置 CI 状态。"""
    _ = principal
    try:
        p = get_pr_engine().set_ci_status(pr_id, body.ci_status)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.post("/v1/code-collaboration/pull-requests/{pr_id}/merge")
def merge_pr(
    pr_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#102 · 合并 PR。"""
    _ = principal
    try:
        p = get_pr_engine().merge(pr_id)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


# ════════════════════ #103 Transform Preview ════════════════════

class PreviewIn(BaseModel):
    name: str = Field(min_length=1)
    repo_id: str = ""
    branch: str = "main"
    transform_code: str = Field(min_length=1)
    language: str = "python"
    input_schema: dict[str, str] = Field(default_factory=dict)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class PreviewUpdateIn(BaseModel):
    name: str | None = None
    transform_code: str | None = None
    language: str | None = None
    input_schema: dict[str, str] | None = None
    sample_rows: list[dict[str, Any]] | None = None


@router.post("/v1/code-collaboration/previews")
def register_preview(
    body: PreviewIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#103 · 注册变换预览。"""
    _ = principal
    try:
        p = get_preview_engine().register(TransformPreview(**body.model_dump()))
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.get("/v1/code-collaboration/previews")
def list_previews(
    repo_id: str | None = None, language: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#103 · 预览列表。"""
    _ = principal
    items = get_preview_engine().list(repo_id=repo_id, language=language)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.get("/v1/code-collaboration/previews/{preview_id}")
def get_preview(
    preview_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#103 · 单条预览。"""
    _ = principal
    try:
        return {"item": get_preview_engine().get(preview_id).model_dump()}
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/code-collaboration/previews/{preview_id}")
def update_preview(
    preview_id: str, body: PreviewUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#103 · 更新预览。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        p = get_preview_engine().update(preview_id, updates)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.delete("/v1/code-collaboration/previews/{preview_id}")
def delete_preview(
    preview_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#103 · 删除预览。"""
    _ = principal
    ok = get_preview_engine().delete(preview_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"预览 {preview_id} 不存在", status_code=404)
    return {"id": preview_id, "deleted": True}


@router.post("/v1/code-collaboration/previews/{preview_id}/run")
def run_preview(
    preview_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#103 · 执行预览。"""
    _ = principal
    try:
        r = get_preview_engine().run(preview_id)
    except CodeCollaborationError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.get("/v1/code-collaboration/preview-results")
def list_preview_results(
    preview_id: str | None = None, limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#103 · 预览结果列表。"""
    _ = principal
    items = get_preview_engine().list_results(preview_id=preview_id, limit=limit)
    return {"items": [r.model_dump() for r in items], "count": len(items)}
