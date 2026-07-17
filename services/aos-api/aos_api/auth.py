"""Auth — T0.5 Dev Bearer + TX.3 OIDC JWT."""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Header, Request

from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.oidc import allow_dev, looks_like_jwt, verify_access_token

log = get_logger("aos-api.auth")

DEV_TOKEN = "dev"
DEV_BEARER = f"Bearer {DEV_TOKEN}"


@dataclass
class Principal:
    subject: str
    org_id: str
    project_id: str
    roles: list[str] = field(default_factory=list)
    markings: list[str] = field(default_factory=list)
    token_kind: str = "dev"


def parse_bearer(authorization: str | None) -> str:
    if not authorization:
        raise ApiError(
            code="AUTH_REQUIRED",
            message="Bearer token required",
            status_code=401,
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise ApiError(
            code="AUTH_REQUIRED",
            message="Authorization must be Bearer <token>",
            status_code=401,
        )
    return parts[1].strip()


def _as_str_list(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    return []


def roles_from_claims(claims: dict) -> list[str]:
    """Prefer roles; Keycloak realm_access.roles as fallback (scheme 60)."""
    roles = _as_str_list(claims.get("roles"))
    if roles:
        return roles
    ra = claims.get("realm_access")
    if isinstance(ra, dict):
        roles = _as_str_list(ra.get("roles"))
        if roles:
            return roles
    return ["developer"]


def markings_from_claims(claims: dict) -> list[str]:
    markings = _as_str_list(claims.get("markings"))
    return markings if markings else ["public"]


def org_from_claims(claims: dict, fallback: str) -> str:
    for key in ("org_id", "orgId", "organization_id"):
        val = claims.get(key)
        if val:
            return str(val)
    return fallback


def project_from_claims(claims: dict, fallback: str) -> str:
    for key in ("project_id", "projectId"):
        val = claims.get(key)
        if val:
            return str(val)
    return fallback


def resolve_principal(
    *,
    token: str,
    org_id: str,
    project_id: str,
) -> Principal:
    if looks_like_jwt(token):
        try:
            claims = verify_access_token(token)
        except Exception as exc:  # noqa: BLE001
            raise ApiError(
                code="AUTH_INVALID",
                message=f"invalid JWT: {exc}",
                status_code=401,
            ) from exc
        return Principal(
            subject=str(claims.get("sub") or "unknown"),
            org_id=org_from_claims(claims, org_id),
            project_id=project_from_claims(claims, project_id),
            roles=roles_from_claims(claims),
            markings=markings_from_claims(claims),
            token_kind="oidc",
        )

    if token == DEV_TOKEN:
        if not allow_dev():
            raise ApiError(
                code="AUTH_DEV_DISABLED",
                message="Bearer dev disabled (AOS_AUTH_ALLOW_DEV=0)",
                status_code=401,
            )
        return Principal(
            subject="user:dev",
            org_id=org_id,
            project_id=project_id,
            roles=["developer", "admin"],
            markings=["public", "restricted"],
            token_kind="dev",
        )

    # opaque non-dev: reject unless allow_dev (legacy Wave-0 any-token) — tighten: reject
    raise ApiError(
        code="AUTH_INVALID",
        message="use Bearer JWT (OIDC) or Bearer dev (if allowed)",
        status_code=401,
    )


async def require_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
    x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
) -> Principal:
    token = parse_bearer(authorization)
    org_id = x_org_id or getattr(request.state, "org_id", None) or "dev-org"
    project_id = x_project_id or getattr(request.state, "project_id", None) or "dev-project"
    principal = resolve_principal(token=token, org_id=org_id, project_id=project_id)
    request.state.principal = principal
    log.debug(
        "principal_resolved kind=%s subject=%s org=%s",
        principal.token_kind,
        principal.subject,
        principal.org_id,
    )
    return principal
