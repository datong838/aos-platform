"""Phase 3 · AIP Tool quality compatibility route.

Tool/Eval/Circuit list and mutation authorities live in ``wave_ext`` until
their canonical stores are implemented.  This module retains only the unique
quality endpoint and therefore cannot shadow those public routes.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from aos_api.aip_tools_engine import get_engine

router = APIRouter(prefix="/v1/aip", tags=["aip-tools-evals"])


@router.get("/tools/{tool_id}/quality")
async def get_quality(tool_id: str) -> dict[str, Any]:
    eng = get_engine()
    quality = eng.get_quality(tool_id)
    if quality is None:
        raise HTTPException(404, f"Quality score for tool {tool_id} not found")
    return quality.model_dump()
