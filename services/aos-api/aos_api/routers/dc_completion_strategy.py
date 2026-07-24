"""W3 Task 1.1 · Completion Strategy Router（220w L156）."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from aos_api.dc_completion_strategy import (
    CompletionStrategy,
    CompletionStrategyEngine,
    CompletionStrategyError,
    get_engine,
)

router = APIRouter(prefix="/api/dc/completion-strategies", tags=["DC Completion Strategy"])


def _eng() -> CompletionStrategyEngine:
    return get_engine()


@router.post("")
def create_strategy(strategy: CompletionStrategy):
    try:
        return _eng().register(strategy)
    except CompletionStrategyError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_strategies(
    trigger: Optional[str] = None,
    enabled: Optional[bool] = None,
):
    return _eng().list(trigger=trigger, enabled=enabled)


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str):
    try:
        return _eng().get(strategy_id)
    except CompletionStrategyError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{strategy_id}")
def update_strategy(strategy_id: str, patch: dict):
    try:
        return _eng().update(strategy_id, patch)
    except CompletionStrategyError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: str):
    try:
        _eng().delete(strategy_id)
        return {"ok": True}
    except CompletionStrategyError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.post("/evaluate")
def evaluate(task_id: str, task_result: str):
    try:
        triggered = _eng().evaluate(task_id, task_result)
        return {"triggered_task_ids": triggered}
    except CompletionStrategyError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
