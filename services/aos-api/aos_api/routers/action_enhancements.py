"""W2-#54/#55/#56/#57/#76 · Action 增强组 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.action_enhancements import (
    ActionEffect,
    ActionEnhancementError,
    EffectType,
    MergeStrategy,
    get_engine,
)
from aos_api.errors import ApiError

router = APIRouter(tags=["action-enhancements"])


def _map_error(err: ActionEnhancementError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


# ── #54 Side Effects ──


class CreateEffectRequest(BaseModel):
    action_type_id: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    retry: int = 3
    enabled: bool = True


class TriggerEffectRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/actions/effects")
def create_effect(req: CreateEffectRequest):
    try:
        eff_type = EffectType(req.type)
    except ValueError:
        valid = [t.value for t in EffectType]
        raise ApiError(
            code="UNKNOWN_TYPE",
            message=f"未知副作用类型 {req.type!r}，可用：{valid}",
            status_code=400,
        ) from None
    effect = get_engine().create_effect(ActionEffect(
        action_type_id=req.action_type_id,
        type=eff_type,
        config=req.config,
        retry=req.retry,
        enabled=req.enabled,
    ))
    return effect.model_dump()


@router.get("/v1/actions/effects")
def list_effects(action_type_id: str | None = None):
    return {"effects": [e.model_dump() for e in get_engine().list_effects(action_type_id)]}


@router.post("/v1/actions/effects/{effect_id}/trigger")
def trigger_effect(effect_id: str, req: TriggerEffectRequest):
    try:
        result = get_engine().trigger_effect(effect_id, req.payload)
    except ActionEnhancementError as err:
        raise _map_error(err, 404) from err
    return result.model_dump()


# ── #55 Optimistic UI ──


class OptimisticSubmitRequest(BaseModel):
    action_type_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/actions/optimistic")
def optimistic_submit(req: OptimisticSubmitRequest):
    result = get_engine().optimistic_submit(req.action_type_id, req.payload)
    return result.model_dump()


@router.post("/v1/actions/optimistic/{token}/commit")
def optimistic_commit(token: str):
    try:
        result = get_engine().optimistic_commit(token)
    except ActionEnhancementError as err:
        raise _map_error(err, 404) from err
    return result.model_dump()


@router.post("/v1/actions/optimistic/{token}/rollback")
def optimistic_rollback(token: str):
    try:
        result = get_engine().optimistic_rollback(token)
    except ActionEnhancementError as err:
        raise _map_error(err, 404) from err
    return result.model_dump()


# ── #56 Soft Delete ──


class SoftDeleteRequest(BaseModel):
    dataset_rid: str
    pk: str


@router.post("/v1/actions/soft-delete")
def soft_delete(req: SoftDeleteRequest):
    return get_engine().soft_delete(req.dataset_rid, req.pk)


@router.post("/v1/actions/undelete")
def undelete(req: SoftDeleteRequest):
    return get_engine().undelete(req.dataset_rid, req.pk)


# ── #57 DLQ ──


@router.get("/v1/actions/dlq")
def list_dlq():
    return {"entries": [e.model_dump() for e in get_engine().list_dlq()]}


@router.post("/v1/actions/dlq/{entry_id}/retry")
def retry_dlq(entry_id: str):
    try:
        result = get_engine().retry_dlq(entry_id)
    except ActionEnhancementError as err:
        raise _map_error(err, 404) from err
    return result.model_dump()


@router.delete("/v1/actions/dlq")
def clear_dlq():
    count = get_engine().clear_dlq()
    return {"cleared": count}


# ── #76 Merge Strategy ──


class MergeRequest(BaseModel):
    current: dict[str, Any] = Field(default_factory=dict)
    incoming: dict[str, Any] = Field(default_factory=dict)
    strategy: str = "field_level"


@router.post("/v1/actions/merge")
def merge(req: MergeRequest):
    try:
        result = get_engine().merge(req.current, req.incoming, req.strategy)
    except ActionEnhancementError as err:
        raise _map_error(err) from err
    return result.model_dump()
