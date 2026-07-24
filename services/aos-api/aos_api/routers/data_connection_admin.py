"""W2-AG · Data Connection 管理组路由：#114 AgentAdmin + #115 SourceExplorer."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.data_connection_admin import (
    AgentAdmin,
    AgentCertificate,
    AgentDriver,
    AgentLogEntry,
    DataConnectionAdminError,
    ERRelation,
    ResourceNode,
    SourceSchema,
    get_admin_engine,
    get_explorer_engine,
)
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["data-connection-admin"])
log = get_logger("aos-api.data-connection-admin")


def _map_err(err: DataConnectionAdminError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #114 AgentAdmin ════════════════════

class AgentDriverIn(BaseModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    type: str = Field(min_length=1)


class AgentCertificateIn(BaseModel):
    name: str = Field(min_length=1)
    issuer: str = ""
    expires_at: float = 0.0


class AgentAdminIn(BaseModel):
    agent_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = "1.0.0"
    status: str = "registered"
    download_url: str = ""
    drivers: list[AgentDriverIn] = Field(default_factory=list)
    certificates: list[AgentCertificateIn] = Field(default_factory=list)
    auto_upgrade: bool = False


class AgentAdminUpdateIn(BaseModel):
    name: str | None = None
    version: str | None = None
    status: str | None = None
    download_url: str | None = None
    drivers: list[AgentDriverIn] | None = None
    certificates: list[AgentCertificateIn] | None = None
    auto_upgrade: bool | None = None


class PushLogIn(BaseModel):
    level: str = Field(min_length=1)
    message: str = Field(min_length=1)


class UpgradeIn(BaseModel):
    new_version: str = Field(min_length=1)


@router.post("/v1/agent-admins")
def register_admin(
    body: AgentAdminIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · 注册 Agent 管理。"""
    _ = principal
    try:
        drivers = [AgentDriver(**d.model_dump()) for d in body.drivers]
        certs = [AgentCertificate(**c.model_dump()) for c in body.certificates]
        admin = AgentAdmin(
            agent_id=body.agent_id, name=body.name, version=body.version,
            status=body.status, download_url=body.download_url,
            drivers=drivers, certificates=certs, auto_upgrade=body.auto_upgrade,
        )
        a = get_admin_engine().register(admin)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"item": a.model_dump()}


@router.get("/v1/agent-admins")
def list_admins(
    agent_id: str | None = None, status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · Agent 管理列表。"""
    _ = principal
    items = get_admin_engine().list(agent_id=agent_id, status=status)
    return {"items": [a.model_dump() for a in items], "count": len(items)}


@router.get("/v1/agent-admins/{admin_id}")
def get_admin(
    admin_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · 单条 Agent 管理。"""
    _ = principal
    try:
        return {"item": get_admin_engine().get(admin_id).model_dump()}
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/agent-admins/{admin_id}")
def update_admin(
    admin_id: str, body: AgentAdminUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · 更新 Agent 管理。"""
    _ = principal
    updates: dict[str, Any] = {}
    for k, v in body.model_dump().items():
        if v is None:
            continue
        if k == "drivers":
            updates[k] = [AgentDriver(**d.model_dump()) for d in v]
        elif k == "certificates":
            updates[k] = [AgentCertificate(**c.model_dump()) for c in v]
        else:
            updates[k] = v
    try:
        a = get_admin_engine().update(admin_id, updates)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"item": a.model_dump()}


@router.delete("/v1/agent-admins/{admin_id}")
def delete_admin(
    admin_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · 删除 Agent 管理。"""
    _ = principal
    ok = get_admin_engine().delete(admin_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"Agent 管理 {admin_id} 不存在", status_code=404)
    return {"id": admin_id, "deleted": True}


@router.post("/v1/agent-admins/{admin_id}/heartbeat")
def heartbeat_admin(
    admin_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · Agent 心跳。"""
    _ = principal
    try:
        a = get_admin_engine().heartbeat(admin_id)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"item": a.model_dump()}


@router.post("/v1/agent-admins/{admin_id}/logs")
def push_log(
    admin_id: str, body: PushLogIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · 推送 Agent 日志。"""
    _ = principal
    try:
        a = get_admin_engine().push_log(admin_id, body.level, body.message)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"item": a.model_dump()}


@router.post("/v1/agent-admins/{admin_id}/upgrade")
def upgrade_admin(
    admin_id: str, body: UpgradeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · Agent 升级。"""
    _ = principal
    try:
        a = get_admin_engine().upgrade(admin_id, body.new_version)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"item": a.model_dump()}


@router.get("/v1/agent-admins/{admin_id}/drivers")
def list_drivers(
    admin_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · Agent 驱动列表。"""
    _ = principal
    try:
        items = get_admin_engine().list_drivers(admin_id)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"items": [d.model_dump() for d in items], "count": len(items)}


@router.get("/v1/agent-admins/{admin_id}/certificates")
def list_certificates(
    admin_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · Agent 证书列表。"""
    _ = principal
    try:
        items = get_admin_engine().list_certificates(admin_id)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.get("/v1/agent-admins/{admin_id}/download-url")
def get_download_url(
    admin_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#114 · Agent 下载链接。"""
    _ = principal
    try:
        url = get_admin_engine().get_download_url(admin_id)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"download_url": url}


# ════════════════════ #115 SourceExplorer ════════════════════

class ERRelationIn(BaseModel):
    from_table: str = Field(min_length=1)
    to_table: str = Field(min_length=1)
    from_column: str = Field(min_length=1)
    to_column: str = Field(min_length=1)
    relation_type: str = "many_to_one"


class ResourceNodeIn(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    children: list[str] = Field(default_factory=list)


class SourceSchemaIn(BaseModel):
    source_id: str = Field(min_length=1)
    dataset_name: str = Field(min_length=1)
    er_diagram: list[ERRelationIn] = Field(default_factory=list)
    resource_tree: list[ResourceNodeIn] = Field(default_factory=list)
    sample_preview: list[dict[str, Any]] = Field(default_factory=list)


class SourceSchemaUpdateIn(BaseModel):
    dataset_name: str | None = None
    er_diagram: list[ERRelationIn] | None = None
    resource_tree: list[ResourceNodeIn] | None = None
    sample_preview: list[dict[str, Any]] | None = None


@router.post("/v1/source-explorer/schemas")
def register_schema(
    body: SourceSchemaIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#115 · 注册 schema。"""
    _ = principal
    try:
        er = [ERRelation(**r.model_dump()) for r in body.er_diagram]
        tree = [ResourceNode(**n.model_dump()) for n in body.resource_tree]
        schema = SourceSchema(
            source_id=body.source_id, dataset_name=body.dataset_name,
            er_diagram=er, resource_tree=tree,
            sample_preview=body.sample_preview,
        )
        s = get_explorer_engine().register(schema)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.get("/v1/source-explorer/schemas")
def list_schemas(
    source_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#115 · schema 列表。"""
    _ = principal
    items = get_explorer_engine().list(source_id=source_id)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/source-explorer/schemas/{schema_id}")
def get_schema(
    schema_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#115 · 单条 schema。"""
    _ = principal
    try:
        return {"item": get_explorer_engine().get(schema_id).model_dump()}
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/source-explorer/schemas/{schema_id}")
def update_schema(
    schema_id: str, body: SourceSchemaUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#115 · 更新 schema。"""
    _ = principal
    updates: dict[str, Any] = {}
    for k, v in body.model_dump().items():
        if v is None:
            continue
        if k == "er_diagram":
            updates[k] = [ERRelation(**r.model_dump()) for r in v]
        elif k == "resource_tree":
            updates[k] = [ResourceNode(**n.model_dump()) for n in v]
        else:
            updates[k] = v
    try:
        s = get_explorer_engine().update(schema_id, updates)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.delete("/v1/source-explorer/schemas/{schema_id}")
def delete_schema(
    schema_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#115 · 删除 schema。"""
    _ = principal
    ok = get_explorer_engine().delete(schema_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"schema {schema_id} 不存在", status_code=404)
    return {"id": schema_id, "deleted": True}


@router.get("/v1/source-explorer/schemas/{schema_id}/er")
def explore_er(
    schema_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#115 · ER 关系图。"""
    _ = principal
    try:
        items = get_explorer_engine().explore_er(schema_id)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/source-explorer/schemas/{schema_id}/resource-tree")
def explore_resource_tree(
    schema_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#115 · 资源树。"""
    _ = principal
    try:
        items = get_explorer_engine().explore_resource_tree(schema_id)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"items": [n.model_dump() for n in items], "count": len(items)}


@router.get("/v1/source-explorer/schemas/{schema_id}/sample")
def preview_sample(
    schema_id: str, limit: int = 10,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#115 · 样本预览。"""
    _ = principal
    try:
        items = get_explorer_engine().preview_sample(schema_id, limit=limit)
    except DataConnectionAdminError as exc:
        raise _map_err(exc) from exc
    return {"items": items, "count": len(items)}
