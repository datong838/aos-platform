"""TX.4 — OpenFGA-shaped authz API (schemes 55/58/61)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api import openfga as fga

router = APIRouter(tags=["authz"])
log = get_logger("aos-api.authz")


class CheckBody(BaseModel):
    user: str | None = None
    relation: str = "viewer"
    object: str = Field(min_length=1)


class TupleBody(BaseModel):
    user: str | None = None
    relation: str = "viewer"
    object: str = Field(min_length=1)


@router.get("/v1/authz/status")
def authz_status(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    _ = principal
    return fga.status_payload()


@router.get("/v1/authz/model")
def authz_model(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    """Production-shaped type/relation catalog (scheme 61)."""
    _ = principal
    return fga.model_payload()


@router.post("/v1/authz/check")
def authz_check(
    body: CheckBody,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    fga.validate_relation(body.relation)
    user = body.user or fga.user_key(principal.subject)
    with connect() as conn:
        allowed = fga.check(conn, user, body.relation, body.object)
    log.info(
        "authz_check user=%s rel=%s obj=%s allowed=%s",
        user,
        body.relation,
        body.object,
        allowed,
    )
    return {
        "allowed": allowed,
        "user": user,
        "relation": body.relation,
        "object": body.object,
        "mode": fga.status_payload()["mode"],
    }


@router.post("/v1/authz/tuples")
def authz_write_tuple(
    body: TupleBody,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    user = body.user or fga.user_key(principal.subject)
    with connect() as conn:
        fga.write_tuple(conn, user, body.relation, body.object)
        conn.commit()
    log.info(
        "authz_tuple_written by=%s user=%s rel=%s obj=%s",
        principal.subject,
        user,
        body.relation,
        body.object,
    )
    return {"ok": True, "user": user, "relation": body.relation, "object": body.object}


@router.get("/v1/authz/tuples")
def authz_list_tuples(
    object: str | None = None,
    user: str | None = None,
    limit: int = 100,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """207m — list local authz tuples (optional object/user filter)."""
    _ = principal
    with connect() as conn:
        items = fga.list_tuples_local(
            conn,
            object_key=(object or "").strip() or None,
            user_key=(user or "").strip() or None,
            limit=limit,
        )
    return {
        "items": items,
        "count": len(items),
        "mode": fga.status_payload()["mode"],
    }


@router.delete("/v1/authz/tuples")
def authz_delete_tuple(
    body: TupleBody,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """211m — revoke a local authz tuple."""
    from aos_api.errors import ApiError

    user = body.user or fga.user_key(principal.subject)
    with connect() as conn:
        ok = fga.delete_tuple(conn, user, body.relation, body.object)
        conn.commit()
    if not ok:
        raise ApiError(code="NOT_FOUND", message="authz tuple not found", status_code=404)
    log.info(
        "authz_tuple_deleted by=%s user=%s rel=%s obj=%s",
        principal.subject,
        user,
        body.relation,
        body.object,
    )
    return {"ok": True, "user": user, "relation": body.relation, "object": body.object}
