"W4 · 通知链接配置（220w L2956） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.at_notification_link import (
    NotificationLink,
    NotificationLinkEngine,
    NotificationLinkError,
    get_engine,
)

router = APIRouter(prefix="/api/at/notification-link", tags=["AT Notification Link"])


def _eng() -> NotificationLinkEngine:
    return get_engine()


@router.post("")
def create(item: NotificationLink):
    try:
        return _eng().register(item)
    except NotificationLinkError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except NotificationLinkError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except NotificationLinkError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except NotificationLinkError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
