"""TWA.6 — shared plugin catalog + per-workspace configured instances."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["plugins"])
log = get_logger("aos-api.plugins")

# Shared catalog (not copied per workspace) — metadata only, no secrets.
_CATALOG: list[dict[str, Any]] = [
    {
        "id": "llm.openai",
        "kind": "llm",
        "name": "OpenAI 兼容大模型",
        "description": "可选 Provider；密钥在已配置实例中按工作区存放",
        "shared": True,
    },
    {
        "id": "llm.local",
        "kind": "llm",
        "name": "本机大模型",
        "description": "本地推理端点",
        "shared": True,
    },
    {
        "id": "connector.http",
        "kind": "connector",
        "name": "HTTP 采集连接器",
        "description": "通用 HTTP 拉取",
        "shared": True,
    },
]

# (org_id, project_id, config_id) -> config
_CONFIGS: dict[tuple[str, str, str], dict[str, Any]] = {}


def reset_plugin_store() -> None:
    _CONFIGS.clear()


@router.get("/v1/plugin-catalog")
def list_plugin_catalog(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Shared catalog — same items for every workspace in the org."""
    log.info(
        "plugin_catalog_list org=%s project=%s count=%s subject=%s",
        principal.org_id,
        principal.project_id,
        len(_CATALOG),
        principal.subject,
    )
    return {"items": list(_CATALOG), "scope": "shared"}


class PluginConfigIn(BaseModel):
    pluginId: str = Field(min_length=1)
    displayName: str = Field(min_length=1)
    # refs only — never store raw API keys in this lite store
    secretRef: str | None = None
    settings: dict[str, Any] | None = None
    id: str | None = None


@router.get("/v1/plugin-configs")
def list_plugin_configs(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    items = [
        v
        for (o, p, _), v in _CONFIGS.items()
        if o == principal.org_id and p == principal.project_id
    ]
    log.info(
        "plugin_config_list org=%s project=%s count=%s",
        principal.org_id,
        principal.project_id,
        len(items),
    )
    return {"items": items, "scope": "workspace"}


@router.post("/v1/plugin-configs")
def create_plugin_config(
    body: PluginConfigIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not any(c["id"] == body.pluginId for c in _CATALOG):
        raise ApiError(
            code="PLUGIN_UNKNOWN",
            message=f"plugin {body.pluginId} not in catalog",
            status_code=400,
        )
    cid = body.id or f"pcfg-{uuid.uuid4().hex[:8]}"
    item = {
        "id": cid,
        "pluginId": body.pluginId,
        "displayName": body.displayName,
        "secretRef": body.secretRef,
        "settings": body.settings or {},
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    _CONFIGS[(principal.org_id, principal.project_id, cid)] = item
    log.info(
        "plugin_config_create id=%s plugin=%s org=%s project=%s",
        cid,
        body.pluginId,
        principal.org_id,
        principal.project_id,
    )
    return item


@router.get("/v1/plugin-configs/{config_id}")
def get_plugin_config(
    config_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    key = (principal.org_id, principal.project_id, config_id)
    item = _CONFIGS.get(key)
    if not item:
        log.warning(
            "plugin_config_denied id=%s org=%s project=%s",
            config_id,
            principal.org_id,
            principal.project_id,
        )
        raise ApiError(
            code="NOT_FOUND",
            message=f"plugin config {config_id} not found",
            status_code=404,
        )
    return item
