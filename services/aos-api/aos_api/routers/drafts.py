"""Wave-3 T3.3 — Draft Dataset (isolated from production objects)."""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.idempotency import idempotency_store
from aos_api.logging_facade import get_logger
from aos_api.routers.actions import ensure_action_schema
from aos_api.submission import evaluate_criteria

router = APIRouter(tags=["drafts"])
log = get_logger("aos-api.drafts")


class DraftIn(BaseModel):
    actionTypeId: str
    objectType: str
    objectId: str | None = None
    proposed: dict[str, Any] = Field(default_factory=dict)
    title: str = ""


def ensure_draft_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS draft_dataset (
              id TEXT PRIMARY KEY,
              action_type_id TEXT NOT NULL,
              object_type TEXT NOT NULL,
              object_id TEXT,
              title TEXT NOT NULL DEFAULT '',
              proposed JSONB NOT NULL DEFAULT '{}'::jsonb,
              status TEXT NOT NULL DEFAULT 'proposed',
              created_by TEXT NOT NULL,
              org_id TEXT NOT NULL,
              project_id TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              CONSTRAINT draft_status_chk CHECK (status IN ('proposed','approved','rejected'))
            )
            """
        )
        conn.commit()
    log.info("draft_schema_ready")


@router.get("/v1/aip/drafts")
def list_drafts(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    ensure_draft_schema()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, action_type_id, object_type, object_id, title, proposed, status, created_by
            FROM draft_dataset
            WHERE org_id=%s AND project_id=%s
            ORDER BY created_at DESC
            """,
            (principal.org_id, principal.project_id),
        ).fetchall()
    items = [
        {
            "id": r["id"],
            "actionTypeId": r["action_type_id"],
            "objectType": r["object_type"],
            "objectId": r["object_id"],
            "title": r["title"],
            "proposed": r["proposed"],
            "status": r["status"],
            "createdBy": r["created_by"],
        }
        for r in rows
    ]
    return {"items": items}


@router.post("/v1/aip/drafts")
def create_draft(
    body: DraftIn,
    principal: Principal = Depends(require_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    """Create draft only if submission criteria pass — never writes obj_instance."""
    from aos_api.marking import ensure_field_writes

    ensure_draft_schema()
    ensure_action_schema()
    if idempotency_key:
        cached = idempotency_store.get(
            principal.org_id, principal.project_id, idempotency_key
        )
        if cached:
            return JSONResponse(
                status_code=cached["status_code"],
                content={**cached["body"], "idempotentReplay": True},
            )

    with connect() as conn:
        action = conn.execute(
            "SELECT submission_criteria FROM meta_action_type WHERE id=%s",
            (body.actionTypeId,),
        ).fetchone()
        if not action:
            raise ApiError(code="NOT_FOUND", message="action type not found", status_code=404)
        props_row = conn.execute(
            "SELECT properties FROM meta_object_type WHERE id=%s",
            (body.objectType,),
        ).fetchone()
        props = props_row["properties"] if props_row else None
        if isinstance(props, list):
            ensure_field_writes(principal, body.proposed, props, conn=conn)
        gate = evaluate_criteria(action["submission_criteria"], body.proposed)
        if not gate["ok"]:
            raise ApiError(
                code="VALIDATION",
                message="submission criteria not met; draft rejected",
                status_code=400,
                details=gate,
            )
        draft_id = f"draft-{uuid.uuid4().hex[:12]}"
        title = body.title or f"{body.actionTypeId} on {body.objectType}"
        conn.execute(
            """
            INSERT INTO draft_dataset
              (id, action_type_id, object_type, object_id, title, proposed, status,
               created_by, org_id, project_id)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,'proposed',%s,%s,%s)
            """,
            (
                draft_id,
                body.actionTypeId,
                body.objectType,
                body.objectId,
                title,
                json.dumps(body.proposed),
                principal.subject,
                principal.org_id,
                principal.project_id,
            ),
        )
        conn.commit()

    payload = {
        "id": draft_id,
        "actionTypeId": body.actionTypeId,
        "objectType": body.objectType,
        "objectId": body.objectId,
        "title": title,
        "proposed": body.proposed,
        "status": "proposed",
        "productionWritten": False,
    }
    log.info("draft_created id=%s action=%s", draft_id, body.actionTypeId)
    if idempotency_key:
        idempotency_store.put(
            principal.org_id,
            principal.project_id,
            idempotency_key,
            status_code=201,
            body=payload,
        )
    return JSONResponse(status_code=201, content=payload)


@router.get("/v1/aip/drafts/{draft_id}")
def get_draft(
    draft_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    ensure_draft_schema()
    with connect() as conn:
        r = conn.execute(
            """
            SELECT id, action_type_id, object_type, object_id, title, proposed, status, created_by
            FROM draft_dataset WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (draft_id, principal.org_id, principal.project_id),
        ).fetchone()
    if not r:
        raise ApiError(code="NOT_FOUND", message="draft not found", status_code=404)
    return {
        "id": r["id"],
        "actionTypeId": r["action_type_id"],
        "objectType": r["object_type"],
        "objectId": r["object_id"],
        "title": r["title"],
        "proposed": r["proposed"],
        "status": r["status"],
        "createdBy": r["created_by"],
        "productionWritten": False,
    }


@router.post("/v1/aip/drafts/{draft_id}/reject")
def reject_draft(
    draft_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    ensure_draft_schema()
    with connect() as conn:
        r = conn.execute(
            """
            UPDATE draft_dataset SET status='rejected', updated_at=NOW()
            WHERE id=%s AND org_id=%s AND project_id=%s AND status='proposed'
            RETURNING id, status
            """,
            (draft_id, principal.org_id, principal.project_id),
        ).fetchone()
        conn.commit()
    if not r:
        raise ApiError(code="VALIDATION", message="draft not rejectable", status_code=400)
    log.info("draft_rejected id=%s by=%s", draft_id, principal.subject)
    return {"id": r["id"], "status": r["status"], "productionWritten": False}
