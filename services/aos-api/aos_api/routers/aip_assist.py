"""W2-AE · AIP 辅助与仓库配置组路由：#107 AIP Assist + #108 repoSettings + #110 推荐结构."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.aip_assist import (
    AIPAssistError,
    AIPAssistRequest,
    ProjectStructure,
    RepoSettings,
    StructureComponent,
    get_assist_engine,
    get_settings_engine,
    get_structure_engine,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["aip-assist"])
log = get_logger("aos-api.aip-assist")


def _map_err(err: AIPAssistError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #107 AIP Assist ════════════════════

class AssistRequestIn(BaseModel):
    kind: str = Field(min_length=1)
    code: str = Field(min_length=1)
    language: str = "python"
    context: str = ""


class AssistUpdateIn(BaseModel):
    code: str | None = None
    context: str | None = None
    status: str | None = None


@router.post("/v1/aip-assist/requests")
def register_request(
    body: AssistRequestIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#107 · 注册辅助请求。"""
    _ = principal
    try:
        r = get_assist_engine().register(AIPAssistRequest(**body.model_dump()))
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.get("/v1/aip-assist/requests")
def list_requests(
    kind: str | None = None, status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#107 · 辅助请求列表。"""
    _ = principal
    items = get_assist_engine().list(kind=kind, status=status)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/aip-assist/requests/{req_id}")
def get_request(
    req_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#107 · 单条辅助请求。"""
    _ = principal
    try:
        return {"item": get_assist_engine().get(req_id).model_dump()}
    except AIPAssistError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/aip-assist/requests/{req_id}")
def update_request(
    req_id: str, body: AssistUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#107 · 更新辅助请求。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        r = get_assist_engine().update(req_id, updates)
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.delete("/v1/aip-assist/requests/{req_id}")
def delete_request(
    req_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#107 · 删除辅助请求。"""
    _ = principal
    ok = get_assist_engine().delete(req_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"请求 {req_id} 不存在", status_code=404)
    return {"id": req_id, "deleted": True}


@router.post("/v1/aip-assist/requests/{req_id}/run")
def run_request(
    req_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#107 · 执行辅助。"""
    _ = principal
    try:
        r = get_assist_engine().run(req_id)
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.get("/v1/aip-assist/results")
def list_results(
    kind: str | None = None, limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#107 · 结果列表。"""
    _ = principal
    items = get_assist_engine().list_results(kind=kind, limit=limit)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


# ════════════════════ #108 repoSettings.json ════════════════════

class RepoSettingsIn(BaseModel):
    repo_id: str = Field(min_length=1)
    label_validation: dict[str, Any] = Field(default_factory=dict)
    pr_template: str = ""
    validation_rules: list[dict[str, Any]] = Field(default_factory=list)
    enforce_branch_protection: bool = False


class RepoSettingsUpdateIn(BaseModel):
    label_validation: dict[str, Any] | None = None
    pr_template: str | None = None
    validation_rules: list[dict[str, Any]] | None = None
    enforce_branch_protection: bool | None = None


class ValidateLabelIn(BaseModel):
    label: str = Field(min_length=1)


class RenderTemplateIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/aip-assist/repo-settings")
def register_settings(
    body: RepoSettingsIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#108 · 注册仓库配置。"""
    _ = principal
    try:
        s = get_settings_engine().register(RepoSettings(**body.model_dump()))
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.get("/v1/aip-assist/repo-settings")
def list_settings(
    repo_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#108 · 仓库配置列表。"""
    _ = principal
    items = get_settings_engine().list(repo_id=repo_id)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/aip-assist/repo-settings/{settings_id}")
def get_settings(
    settings_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#108 · 单条仓库配置。"""
    _ = principal
    try:
        return {"item": get_settings_engine().get(settings_id).model_dump()}
    except AIPAssistError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/aip-assist/repo-settings/{settings_id}")
def update_settings(
    settings_id: str, body: RepoSettingsUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#108 · 更新仓库配置。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        s = get_settings_engine().update(settings_id, updates)
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.delete("/v1/aip-assist/repo-settings/{settings_id}")
def delete_settings(
    settings_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#108 · 删除仓库配置。"""
    _ = principal
    ok = get_settings_engine().delete(settings_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"配置 {settings_id} 不存在", status_code=404)
    return {"id": settings_id, "deleted": True}


@router.post("/v1/aip-assist/repo-settings/{settings_id}/validate-label")
def validate_label(
    settings_id: str, body: ValidateLabelIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#108 · 标签验证。"""
    _ = principal
    try:
        result = get_settings_engine().validate_label(settings_id, body.label)
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"result": result}


@router.post("/v1/aip-assist/repo-settings/{settings_id}/render-pr-template")
def render_pr_template(
    settings_id: str, body: RenderTemplateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#108 · 渲染 PR 模板。"""
    _ = principal
    try:
        rendered = get_settings_engine().render_pr_template(settings_id, body.context)
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"rendered": rendered}


# ════════════════════ #110 推荐项目结构 ════════════════════

class ComponentIn(BaseModel):
    layer: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    rid_prefix: str = ""
    required: bool = False


class ProjectStructureIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    layers: list[str] = Field(default_factory=list)
    components: list[ComponentIn] = Field(default_factory=list)


class ProjectStructureUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    layers: list[str] | None = None
    components: list[ComponentIn] | None = None


class ValidateProjectIn(BaseModel):
    components: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/v1/aip-assist/project-structures")
def register_structure(
    body: ProjectStructureIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#110 · 注册项目结构。"""
    _ = principal
    try:
        comps = [
            StructureComponent(**c.model_dump()) for c in body.components
        ]
        s = get_structure_engine().register(ProjectStructure(
            name=body.name, description=body.description,
            layers=body.layers, components=comps,
        ))
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.get("/v1/aip-assist/project-structures")
def list_structures(
    name: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#110 · 项目结构列表。"""
    _ = principal
    items = get_structure_engine().list(name=name)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/aip-assist/project-structures/{struct_id}")
def get_structure(
    struct_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#110 · 单条项目结构。"""
    _ = principal
    try:
        return {"item": get_structure_engine().get(struct_id).model_dump()}
    except AIPAssistError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/aip-assist/project-structures/{struct_id}")
def update_structure(
    struct_id: str, body: ProjectStructureUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#110 · 更新项目结构。"""
    _ = principal
    updates: dict[str, Any] = {}
    for k, v in body.model_dump().items():
        if v is None:
            continue
        if k == "components":
            updates[k] = [
                StructureComponent(**c.model_dump()) if hasattr(c, "model_dump") else c
                for c in v
            ]
        else:
            updates[k] = v
    try:
        s = get_structure_engine().update(struct_id, updates)
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.delete("/v1/aip-assist/project-structures/{struct_id}")
def delete_structure(
    struct_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#110 · 删除项目结构。"""
    _ = principal
    ok = get_structure_engine().delete(struct_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"结构 {struct_id} 不存在", status_code=404)
    return {"id": struct_id, "deleted": True}


@router.get("/v1/aip-assist/project-structures/{struct_id}/render")
def render_template(
    struct_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#110 · 渲染模板。"""
    _ = principal
    try:
        return {"template": get_structure_engine().render_template(struct_id)}
    except AIPAssistError as exc:
        raise _map_err(exc) from exc


@router.post("/v1/aip-assist/project-structures/{struct_id}/validate-project")
def validate_project(
    struct_id: str, body: ValidateProjectIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#110 · 校验项目。"""
    _ = principal
    try:
        result = get_structure_engine().validate_project(struct_id, body.components)
    except AIPAssistError as exc:
        raise _map_err(exc) from exc
    return {"result": result}
