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
