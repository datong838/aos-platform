"""Module deployments router — Phase 1 Workshop backend.

GET /v1/modules/:id/deployments — deployment history.
POST /v1/modules/:id/deploy — deploy to environment.
POST /v1/modules/:id/rollback — rollback to a previous deployment.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.module_deployments import deploy, list_deployments, rollback

router = APIRouter(
    prefix="/v1/modules",
    tags=["modules-deployments"],
    dependencies=[Depends(require_principal)],
)


class DeployBody(BaseModel):
    environment: str = "dev"
    version: str = "1.0.0"
    configSnapshot: dict[str, Any] = {}


class RollbackBody(BaseModel):
    targetDeploymentId: str


@router.get("/{module_id}/deployments")
def list_module_deployments(module_id: str) -> dict[str, Any]:
    items = list_deployments(module_id)
    return {"moduleId": module_id, "items": items, "count": len(items)}


@router.post("/{module_id}/deploy")
def deploy_module(module_id: str, body: DeployBody) -> dict[str, Any]:
    item = deploy(
        module_id,
        body.environment,
        version=body.version,
        config_snapshot=body.configSnapshot,
    )
    return {"ok": True, "item": item}


@router.post("/{module_id}/rollback")
def rollback_module(
    module_id: str, body: RollbackBody
) -> dict[str, Any]:
    item = rollback(module_id, body.targetDeploymentId)
    if not item:
        raise HTTPException(
            status_code=404, detail="Target deployment not found"
        )
    return {"ok": True, "item": item}
