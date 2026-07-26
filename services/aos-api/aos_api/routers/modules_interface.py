"""Module interface router — Phase 1 Workshop backend.

GET/PUT /v1/modules/:id/interface — module API/interface definition.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.module_interfaces import get_interface, put_interface

router = APIRouter(prefix="/v1/modules", tags=["modules-interface"])


class InterfaceBody(BaseModel):
    name: str = ""
    description: str = ""
    entryParams: list[dict[str, Any]] = []
    expose: dict[str, Any] = {}
    version: str = "1.0.0"


@router.get("/{module_id}/interface")
def get_module_interface(module_id: str) -> dict[str, Any]:
    iface = get_interface(module_id)
    if not iface:
        return {
            "moduleId": module_id,
            "name": "",
            "description": "",
            "entryParams": [],
            "expose": {},
            "version": "1.0.0",
        }
    return iface


@router.put("/{module_id}/interface")
def put_module_interface(
    module_id: str, body: InterfaceBody
) -> dict[str, Any]:
    return put_interface(module_id, body.model_dump())
