"""TX.3 auth/OIDC surface + Dev JWKS + optional Keycloak password proxy."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.oidc import (
    allow_dev,
    issue_dev_token,
    issue_password_token,
    local_jwks,
    public_config,
    token_url,
)

router = APIRouter(tags=["auth"])


class TokenIn(BaseModel):
    grantType: str = "dev"
    subject: str = "alice"
    orgId: str = "dev-org"
    projectId: str = "dev-project"
    roles: list[str] = Field(default_factory=lambda: ["developer"])
    markings: list[str] = Field(default_factory=lambda: ["public", "restricted"])
    alg: str = "HS256"
    username: str = ""
    password: str = ""


@router.get("/v1/auth/oidc")
def oidc_public_config() -> dict[str, Any]:
    return public_config()


@router.get("/v1/auth/jwks")
def oidc_jwks() -> dict[str, Any]:
    """Dev-shaped JWKS — point AOS_OIDC_JWKS_URL here, or to real Keycloak."""
    return local_jwks()


@router.post("/v1/auth/token")
def issue_token(body: TokenIn) -> dict[str, Any]:
    gt = (body.grantType or "dev").lower()
    if gt == "password":
        if not token_url():
            raise ApiError(
                code="UNSUPPORTED_GRANT",
                message="grantType=password requires AOS_OIDC_TOKEN_URL (Dev Keycloak)",
                status_code=400,
            )
        if not body.username or not body.password:
            raise ApiError(
                code="VALIDATION",
                message="username and password required for password grant",
                status_code=400,
            )
        try:
            return issue_password_token(username=body.username, password=body.password)
        except ValueError as exc:
            raise ApiError(
                code="OIDC_TOKEN_FAILED",
                message=str(exc),
                status_code=401,
            ) from exc

    if gt != "dev":
        raise ApiError(
            code="UNSUPPORTED_GRANT",
            message="supported grantType: dev | password (when TOKEN_URL set)",
            status_code=400,
        )
    if not allow_dev():
        raise ApiError(
            code="AUTH_DEV_DISABLED",
            message="dev token endpoint disabled",
            status_code=403,
        )
    return issue_dev_token(
        subject=body.subject,
        org_id=body.orgId,
        project_id=body.projectId,
        roles=body.roles,
        markings=body.markings,
        alg=body.alg,
    )
