"""Legacy Phase 3 Draft router compatibility marker.

The public Draft authority is split between ``routers.drafts`` (read/create/
reject) and ``routers.runtime_write`` (approved production write).  The former
Phase 3 in-memory handlers intentionally register no routes: keeping this
module importable avoids breaking internal imports while preventing a second
public Draft state machine or the unsafe generic ``transition`` endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix="/v1/aip", tags=["aip-drafts-legacy"])
