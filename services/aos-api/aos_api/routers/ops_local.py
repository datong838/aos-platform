"""165 — Local-First ops: dependency probe / ensure."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api import local_deps as deps
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["ops-local"])
log = get_logger("aos-api.ops-local")


@router.get("/v1/ops/local/deps")
def get_local_deps(principal: Principal = Depends(require_principal)) -> dict:
    out = deps.probe_deps()
    log.info(
        "local_deps_probe subject=%s ok=%s",
        principal.subject,
        out.get("ok"),
    )
    return out


@router.post("/v1/ops/local/deps/ensure")
def ensure_local_deps(principal: Principal = Depends(require_principal)) -> dict:
    if not deps.ensure_allowed():
        raise ApiError(
            code="FORBIDDEN",
            message="local dependency ensure disabled in this environment",
            status_code=403,
        )
    out = deps.ensure_deps()
    log.info(
        "local_deps_ensure subject=%s action=%s ok=%s",
        principal.subject,
        out.get("action"),
        out.get("ok"),
    )
    return out


@router.get("/v1/ops/local/hub")
def get_local_hub(principal: Principal = Depends(require_principal)) -> dict:
    """165 v1.1 — active Docker Hub reachability probe (read-only)."""
    out = deps.probe_docker_hub()
    log.info(
        "local_hub_probe subject=%s ok=%s latencyMs=%s",
        principal.subject,
        out.get("ok"),
        out.get("latencyMs"),
    )
    return out
