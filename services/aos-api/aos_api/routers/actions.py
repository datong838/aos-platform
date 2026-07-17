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


def ensure_action_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_action_type (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              object_type TEXT NOT NULL,
              parameters JSONB NOT NULL DEFAULT '[]'::jsonb,
              required_markings JSONB NOT NULL DEFAULT '[]'::jsonb,
              submission_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        # migrate older installs
        conn.execute(
            """
            ALTER TABLE meta_action_type
            ADD COLUMN IF NOT EXISTS submission_criteria JSONB NOT NULL DEFAULT '[]'::jsonb
            """
        )
        row = conn.execute("SELECT COUNT(*) AS c FROM meta_action_type").fetchone()
        if row and int(row["c"]) == 0:
            conn.execute(
                """
                INSERT INTO meta_action_type
                  (id, name, object_type, parameters, required_markings, submission_criteria)
                VALUES (
                  'CloseWorkOrder',
                  '关闭工单',
                  'WorkOrder',
                  '[{"name":"reason","type":"string","required":true}]'::jsonb,
                  '["public"]'::jsonb,
                  '[{"field":"reason","op":"required"}]'::jsonb
                )
                """
            )
        else:
            conn.execute(
                """
                UPDATE meta_action_type
                SET submission_criteria = '[{"field":"reason","op":"required"}]'::jsonb
                WHERE id='CloseWorkOrder'
                  AND (submission_criteria IS NULL OR submission_criteria = '[]'::jsonb)
                """
            )
        conn.commit()
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
    _ = principal
    ensure_action_schema()
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
    _ = principal
    ensure_action_schema()
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


@router.post("/v1/actions/validate")
def validate_action(
    body: ValidateActionIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """T3.2 — reject when submission criteria fail · TX.4 markings."""
    from aos_api.marking import ensure_field_writes, ensure_markings

    ensure_action_schema()
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
