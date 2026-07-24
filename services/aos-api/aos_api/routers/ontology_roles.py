"""W1-17 · Ontology 角色体系 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.ontology_roles import Permission, Role, OntologyRoleError, get_store

router = APIRouter(tags=["ontology-roles"])


class AssignRequest(BaseModel):
    object_type: str
    principal: str
    role: Role
    granted_by: str = ""


class CheckRequest(BaseModel):
    object_type: str
    principal: str
    permission: Permission


def _map_error(err: OntologyRoleError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/ontology/roles/assign")
def assign_role(req: AssignRequest):
    try:
        assignment = get_store().assign(req.object_type, req.principal, req.role, req.granted_by)
    except OntologyRoleError as err:
        raise _map_error(err) from err
    return assignment.model_dump()


@router.delete("/v1/ontology/roles/assign")
def revoke_role(object_type: str, principal: str):
    removed = get_store().revoke(object_type, principal)
    return {"revoked": removed, "object_type": object_type, "principal": principal}


@router.get("/v1/ontology/roles/{object_type}")
def list_roles(object_type: str):
    assignments = get_store().get_roles(object_type)
    return {"object_type": object_type, "assignments": [a.model_dump() for a in assignments]}


@router.post("/v1/ontology/roles/check")
def check_permission(req: CheckRequest):
    try:
        allowed = get_store().check_permission(req.object_type, req.principal, req.permission)
    except OntologyRoleError as err:
        raise _map_error(err) from err
    return {"allowed": allowed, "object_type": req.object_type, "principal": req.principal,
            "permission": req.permission.value}


@router.get("/v1/ontology/roles/permissions/list")
def list_permissions():
    return {"permissions": get_store().list_permissions()}


@router.get("/v1/ontology/roles/principals/{principal}")
def list_principal_assignments(principal: str):
    assignments = get_store().get_assignments_for(principal)
    return {"principal": principal, "assignments": [a.model_dump() for a in assignments]}
