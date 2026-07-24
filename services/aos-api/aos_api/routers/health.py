from __future__ import annotations

from fastapi import APIRouter

from aos_api.logging_facade import get_logger

router = APIRouter(tags=["health"])
log = get_logger("aos-api.health")


@router.get("/v1/health")
def health() -> dict[str, str]:
    log.debug("health_probe")
    return {"status": "ok"}


@router.get("/v1/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}
