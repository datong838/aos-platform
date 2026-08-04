"""Wave-3 T3.1/T3.2 — Action Type metadata + Submission Criteria."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.submission import evaluate_criteria
from aos_api.tenant_scope import TenantScope, bind_tenant_scope, require_tenant_scope

router = APIRouter(tags=["actions"])
log = get_logger("aos-api.actions")


class ActionTypeIn(BaseModel):
    id: str = Field(min_length=1)
    name: str
    objectType: str
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    requiredMarkings: list[str] = Field(default_factory=list)
    submissionCriteria: list[dict[str, Any]] = Field(default_factory=list)


class ValidateActionIn(BaseModel):
    actionTypeId: str
    payload: dict[str, Any] = Field(default_factory=dict)


def ensure_action_schema(scope: TenantScope | None = None) -> None:
    effective_scope = scope or require_tenant_scope()
    # Bootstrap DDL belongs to db.init_schema(); request paths only seed data.
    from aos_api.action_template_registry import seed_installed_action_types

    with bind_tenant_scope(effective_scope):
        seed_installed_action_types()
    log.info("action_schema_ready")


def _row_to_item(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "name": r["name"],
        "objectType": r["object_type"],
        "parameters": r["parameters"],
        "requiredMarkings": r["required_markings"],
        "submissionCriteria": r.get("submission_criteria") or [],
    }


@router.get("/v1/actions/types")
def list_action_types(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    ensure_action_schema(scope)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, object_type, parameters, required_markings, submission_criteria
            FROM meta_action_type ORDER BY id
            """
        ).fetchall()
    return {"items": [_row_to_item(r) for r in rows]}


@router.post("/v1/actions/types")
def create_action_type(
    body: ActionTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    ensure_action_schema(scope)
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM meta_action_type WHERE id=%s", (body.id,)
        ).fetchone()
        if exists:
            raise ApiError(code="VALIDATION", message="action type exists", status_code=400)
        conn.execute(
            """
            INSERT INTO meta_action_type
              (id, name, object_type, parameters, required_markings, submission_criteria)
            VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
            """,
            (
                body.id,
                body.name,
                body.objectType,
                json.dumps(body.parameters),
                json.dumps(body.requiredMarkings),
                json.dumps(body.submissionCriteria),
            ),
        )
        conn.commit()
    log.info("create_action_type id=%s", body.id)
    return body.model_dump()


@router.get("/v1/actions/types/{action_id}")
def get_action_type(
    action_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    ensure_action_schema(scope)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, name, object_type, parameters, required_markings, submission_criteria
            FROM meta_action_type WHERE id=%s
            """,
            (action_id,),
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="action type not found", status_code=404)
    return _row_to_item(row)


@router.put("/v1/actions/types/{action_id}")
def update_action_type(
    action_id: str,
    body: ActionTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """95 · 更新 Action Type 元数据。"""
    scope = TenantScope(principal.org_id, principal.project_id)
    if body.id != action_id:
        raise ApiError(code="VALIDATION", message="id mismatch", status_code=400)
    ensure_action_schema(scope)
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM meta_action_type WHERE id=%s", (action_id,)
        ).fetchone()
        if not exists:
            raise ApiError(code="NOT_FOUND", message="action type not found", status_code=404)
        conn.execute(
            """
            UPDATE meta_action_type SET
              name=%s, object_type=%s, parameters=%s::jsonb,
              required_markings=%s::jsonb, submission_criteria=%s::jsonb
            WHERE id=%s
            """,
            (
                body.name,
                body.objectType,
                json.dumps(body.parameters),
                json.dumps(body.requiredMarkings),
                json.dumps(body.submissionCriteria),
                action_id,
            ),
        )
        conn.commit()
    log.info("update_action_type id=%s", action_id)
    return body.model_dump()


@router.post("/v1/actions/validate")
def validate_action(
    body: ValidateActionIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """T3.2 — reject when submission criteria fail · TX.4 markings."""
    from aos_api.marking import ensure_field_writes, ensure_markings

    ensure_action_schema(TenantScope(principal.org_id, principal.project_id))
    with connect() as conn:
        row = conn.execute(
            """
            SELECT submission_criteria, required_markings, object_type
            FROM meta_action_type WHERE id=%s
            """,
            (body.actionTypeId,),
        ).fetchone()
        props_row = None
        if row:
            props_row = conn.execute(
                "SELECT properties FROM meta_object_type WHERE id=%s",
                (row["object_type"],),
            ).fetchone()
        if not row:
            raise ApiError(code="NOT_FOUND", message="action type not found", status_code=404)
        ensure_markings(principal, row["required_markings"] or [], conn=conn)
        props = (props_row or {}).get("properties") if props_row else None
        if isinstance(props, list):
            ensure_field_writes(principal, body.payload, props, conn=conn)
        result = evaluate_criteria(row["submission_criteria"], body.payload)
        if not result["ok"]:
            raise ApiError(
                code="VALIDATION",
                message="submission criteria not met",
                status_code=400,
                details=result,
            )
        return {"ok": True, "actionTypeId": body.actionTypeId}
