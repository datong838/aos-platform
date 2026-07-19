"""T3.4 Action Runtime — approve draft → merge proposed into obj_instance.
G-ALIGN-02: POST /v1/actions/execute is the T-API write entry (still via Draft).
"""
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
from aos_api.marking import ensure_markings
from aos_api.routers.actions import ensure_action_schema
from aos_api.routers.drafts import ensure_draft_schema
from aos_api.submission import evaluate_criteria

router = APIRouter(tags=["action-runtime"])
log = get_logger("aos-api.action_runtime")


class ExecuteIn(BaseModel):
    draftId: str | None = None
    actionTypeId: str | None = None
    objectType: str | None = None
    objectId: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    # alias: proposed edits for draft create
    proposed: dict[str, Any] | None = None
    autoApprove: bool = False


def ensure_lineage_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_lineage (
              id TEXT PRIMARY KEY,
              draft_id TEXT,
              action_type_id TEXT,
              object_type TEXT,
              object_id TEXT,
              steps JSONB NOT NULL DEFAULT '[]'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()


def apply_draft_approval(
    *,
    draft_id: str,
    principal: Principal,
    allow_conflicts: bool,
) -> dict[str, Any]:
    """Shared write core — only path that mutates obj_instance from Draft."""
    from aos_api.marking import ensure_field_writes

    ensure_draft_schema()
    ensure_lineage_schema()
    with connect() as conn:
        draft = conn.execute(
            """
            SELECT id, action_type_id, object_type, object_id, proposed, status
            FROM draft_dataset
            WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (draft_id, principal.org_id, principal.project_id),
        ).fetchone()
        if not draft:
            raise ApiError(code="NOT_FOUND", message="draft not found", status_code=404)
        if draft["status"] != "proposed":
            raise ApiError(
                code="VALIDATION",
                message=f"draft status is {draft['status']}",
                status_code=400,
            )
        object_id = draft["object_id"] or f"auto-{draft_id[-8:]}"
        object_type = draft["object_type"]
        proposed_raw = dict(draft["proposed"] or {})
        action_type_id = str(draft["action_type_id"] or "")
        wiki_body = proposed_raw.pop("wikiBody", None)
        proposed = proposed_raw
        wiki_written = False

        if isinstance(wiki_body, dict):
            prev = conn.execute(
                """
                SELECT body FROM wiki_page
                WHERE object_type=%s AND object_id=%s
                  AND org_id=%s AND project_id=%s
                """,
                (object_type, object_id, principal.org_id, principal.project_id),
            ).fetchone()
            if prev and prev.get("body") is not None:
                conn.execute(
                    """
                    INSERT INTO wiki_page_version
                      (object_type, object_id, body, draft_id, org_id, project_id)
                    VALUES (%s,%s,%s::jsonb,%s,%s,%s)
                    """,
                    (
                        object_type,
                        object_id,
                        json.dumps(prev["body"]),
                        draft_id,
                        principal.org_id,
                        principal.project_id,
                    ),
                )
            conn.execute(
                """
                INSERT INTO wiki_page (object_type, object_id, body, org_id, project_id)
                VALUES (%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT (object_type, object_id)
                DO UPDATE SET body = EXCLUDED.body,
                  org_id = EXCLUDED.org_id,
                  project_id = EXCLUDED.project_id
                """,
                (
                    object_type,
                    object_id,
                    json.dumps(wiki_body),
                    principal.org_id,
                    principal.project_id,
                ),
            )
            wiki_written = True
        elif action_type_id == "UpdateWikiCard":
            raise ApiError(
                code="VALIDATION",
                message="UpdateWikiCard requires proposed.wikiBody object",
                status_code=400,
            )

        props_row = conn.execute(
            "SELECT properties FROM meta_object_type WHERE id=%s",
            (object_type,),
        ).fetchone()
        props = props_row["properties"] if props_row else None
        if isinstance(props, list) and proposed:
            ensure_field_writes(principal, proposed, props, conn=conn)

        existing = conn.execute(
            "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
        base = dict(existing["props"]) if existing else {}
        conflicts = [
            k for k in proposed.keys() if k in base and base[k] != proposed[k]
        ]
        if conflicts and not allow_conflicts:
            raise ApiError(
                code="FIELD_CONFLICT",
                message=f"field conflicts: {conflicts}; send X-Allow-Conflicts: true to force",
                status_code=409,
            )
        merged = {**base, **proposed} if proposed else base
        # Wiki-only drafts may leave obj_instance untouched when proposed empty
        if proposed or not wiki_written:
            if existing:
                if proposed:
                    conn.execute(
                        """
                        UPDATE obj_instance SET props=%s::jsonb
                        WHERE object_type=%s AND object_id=%s
                        """,
                        (json.dumps(merged), object_type, object_id),
                    )
            else:
                conn.execute(
                    """
                    INSERT INTO obj_instance (object_type, object_id, props)
                    VALUES (%s,%s,%s::jsonb)
                    """,
                    (object_type, object_id, json.dumps(merged)),
                )
        conn.execute(
            """
            UPDATE draft_dataset SET status='approved', updated_at=NOW()
            WHERE id=%s
            """,
            (draft_id,),
        )
        lineage_id = f"lin-{draft_id}"
        steps = [
            {"step": "read", "objectType": object_type, "objectId": object_id},
            {"step": "draft", "draftId": draft_id},
            {"step": "approve", "actor": principal.subject},
            {
                "step": "write",
                "mergedKeys": list(proposed.keys()),
                "conflicts": conflicts,
                "wikiWritten": wiki_written,
            },
        ]
        conn.execute(
            """
            INSERT INTO decision_lineage (id, draft_id, action_type_id, object_type, object_id, steps)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                lineage_id,
                draft_id,
                draft["action_type_id"],
                object_type,
                object_id,
                json.dumps(steps),
            ),
        )
        conn.commit()

    body: dict[str, Any] = {
        "id": draft_id,
        "status": "approved",
        "productionWritten": True,
        "objectType": object_type,
        "objectId": object_id,
        "merged": merged,
        "conflicts": conflicts,
        "lineageId": lineage_id,
        "wikiWritten": wiki_written,
    }
    log.info(
        "draft_approved id=%s object=%s/%s conflicts=%s wiki=%s",
        draft_id,
        object_type,
        object_id,
        len(conflicts),
        wiki_written,
    )
    return body


def _create_draft_from_execute(
    *,
    principal: Principal,
    action_type_id: str,
    object_type: str | None,
    object_id: str | None,
    proposed: dict[str, Any],
) -> dict[str, Any]:
    ensure_action_schema()
    ensure_draft_schema()
    with connect() as conn:
        action = conn.execute(
            """
            SELECT id, object_type, submission_criteria
            FROM meta_action_type WHERE id=%s
            """,
            (action_type_id,),
        ).fetchone()
        if not action:
            raise ApiError(code="NOT_FOUND", message="action type not found", status_code=404)
        result = evaluate_criteria(action["submission_criteria"], proposed)
        if not result["ok"]:
            raise ApiError(
                code="VALIDATION",
                message="submission criteria not met; draft rejected",
                status_code=400,
                details=result,
            )
        draft_id = f"draft-{uuid.uuid4().hex[:12]}"
        ot = object_type or action["object_type"]
        title = f"{action_type_id} on {ot}"
        conn.execute(
            """
            INSERT INTO draft_dataset
              (id, action_type_id, object_type, object_id, title, proposed, status,
               created_by, org_id, project_id)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,'proposed',%s,%s,%s)
            """,
            (
                draft_id,
                action_type_id,
                ot,
                object_id,
                title,
                json.dumps(proposed),
                principal.subject,
                principal.org_id,
                principal.project_id,
            ),
        )
        conn.commit()
    return {
        "id": draft_id,
        "status": "proposed",
        "productionWritten": False,
        "actionTypeId": action_type_id,
        "objectType": ot,
        "objectId": object_id,
        "title": title,
        "proposed": proposed,
    }


@router.post("/v1/aip/drafts/{draft_id}/approve")
def approve_draft(
    draft_id: str,
    principal: Principal = Depends(require_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    allow_conflicts: str | None = Header(default=None, alias="X-Allow-Conflicts"),
) -> JSONResponse:
    """T3.4 — only path that writes production objects from Draft."""
    if idempotency_key:
        cached = idempotency_store.get(
            principal.org_id, principal.project_id, idempotency_key
        )
        if cached:
            return JSONResponse(
                status_code=cached["status_code"],
                content={**cached["body"], "idempotentReplay": True},
            )

    body = apply_draft_approval(
        draft_id=draft_id,
        principal=principal,
        allow_conflicts=(allow_conflicts or "").lower() in {"1", "true", "yes"},
    )
    if idempotency_key:
        idempotency_store.put(
            principal.org_id,
            principal.project_id,
            idempotency_key,
            status_code=200,
            body=body,
        )
    return JSONResponse(status_code=200, content=body)


@router.post("/v1/actions/execute")
def execute_action(
    body: ExecuteIn,
    principal: Principal = Depends(require_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    allow_conflicts: str | None = Header(default=None, alias="X-Allow-Conflicts"),
) -> JSONResponse:
    """T-API write entry — Idempotency-Key required; production write only via Draft approve."""
    if not idempotency_key or not str(idempotency_key).strip():
        raise ApiError(
            code="MISSING_IDEMPOTENCY_KEY",
            message="Idempotency-Key header is required for POST /v1/actions/execute",
            status_code=400,
        )
    cached = idempotency_store.get(
        principal.org_id, principal.project_id, idempotency_key
    )
    if cached:
        return JSONResponse(
            status_code=cached["status_code"],
            content={**cached["body"], "idempotentReplay": True},
        )

    allow = (allow_conflicts or "").lower() in {"1", "true", "yes"}
    proposed = body.proposed if body.proposed is not None else body.payload

    if body.actionTypeId:
        # TX.4 — enforce Action Type requiredMarkings before draft path
        try:
            ensure_action_schema()
            with connect() as conn:
                row = conn.execute(
                    "SELECT required_markings, object_type FROM meta_action_type WHERE id=%s",
                    (body.actionTypeId,),
                ).fetchone()
                if row:
                    ensure_markings(principal, row["required_markings"] or [], conn=conn)
                    ot = body.objectType or row["object_type"]
                    props_row = conn.execute(
                        "SELECT properties FROM meta_object_type WHERE id=%s",
                        (ot,),
                    ).fetchone()
                    props = props_row["properties"] if props_row else None
                    if isinstance(props, list):
                        from aos_api.marking import ensure_field_writes

                        ensure_field_writes(
                            principal, proposed or {}, props, conn=conn
                        )
        except ApiError:
            raise
        except Exception:  # noqa: BLE001
            pass

    if body.draftId:
        out = apply_draft_approval(
            draft_id=body.draftId,
            principal=principal,
            allow_conflicts=allow,
        )
        out["route"] = "actions.execute"
        out["via"] = "draftId"
    elif body.actionTypeId:
        created = _create_draft_from_execute(
            principal=principal,
            action_type_id=body.actionTypeId,
            object_type=body.objectType,
            object_id=body.objectId,
            proposed=proposed,
        )
        if body.autoApprove:
            out = apply_draft_approval(
                draft_id=created["id"],
                principal=principal,
                allow_conflicts=allow,
            )
            out["route"] = "actions.execute"
            out["via"] = "autoApprove"
        else:
            out = {**created, "route": "actions.execute", "via": "hitl-draft"}
    else:
        raise ApiError(
            code="BAD_REQUEST",
            message="draftId or actionTypeId required",
            status_code=400,
        )

    idempotency_store.put(
        principal.org_id,
        principal.project_id,
        idempotency_key,
        status_code=200,
        body=out,
    )
    log.info(
        "actions_execute via=%s draft=%s written=%s",
        out.get("via"),
        out.get("id"),
        out.get("productionWritten"),
    )
    return JSONResponse(status_code=200, content=out)


@router.get("/v1/aip/lineage/{lineage_id}")
def get_lineage(
    lineage_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    ensure_lineage_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT id, draft_id, action_type_id, object_type, object_id, steps FROM decision_lineage WHERE id=%s",
            (lineage_id,),
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="lineage not found", status_code=404)
    return {
        "id": row["id"],
        "draftId": row["draft_id"],
        "actionTypeId": row["action_type_id"],
        "objectType": row["object_type"],
        "objectId": row["object_id"],
        "steps": row["steps"],
    }
