"""Auth — T0.5 Dev Bearer + TX.3 OIDC JWT + TWA.1 tenant header harden (R-ISO-01)."""
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


def claim_org_raw(claims: dict) -> str | None:
    for key in ("org_id", "orgId", "organization_id"):
        val = claims.get(key)
        if val:
            return str(val)
    return None


def claim_project_raw(claims: dict) -> str | None:
    for key in ("project_id", "projectId"):
        val = claims.get(key)
        if val:
            return str(val)
    return None


def org_from_claims(claims: dict, fallback: str) -> str:
    return claim_org_raw(claims) or fallback


def project_from_claims(claims: dict, fallback: str) -> str:
    return claim_project_raw(claims) or fallback


def bind_tenant_ids(
    *,
    claim_org: str | None,
    claim_project: str | None,
    header_org: str | None,
    header_project: str | None,
    allow_header_fallback: bool,
) -> tuple[str, str]:
    """TWA.1 / R-ISO-01: claims win; header mismatch → 403; prod forbids header-only tenant."""
    if header_org and claim_org and header_org != claim_org:
        log.warning(
            "tenant_header_mismatch field=org claim=%s header=%s",
            claim_org,
            header_org,
        )
        raise ApiError(
            code="AUTH_TENANT_MISMATCH",
            message="X-Org-Id does not match token claim",
            status_code=403,
        )
    if header_project and claim_project and header_project != claim_project:
        log.warning(
            "tenant_header_mismatch field=project claim=%s header=%s",
            claim_project,
            header_project,
        )
        raise ApiError(
            code="AUTH_TENANT_MISMATCH",
            message="X-Project-Id does not match token claim",
            status_code=403,
        )

    if claim_org and claim_project:
        if header_org or header_project:
            log.info(
                "tenant_bound source=claim org=%s project=%s header_ignored_or_matched=1",
                claim_org,
                claim_project,
            )
        return claim_org, claim_project

    if allow_header_fallback:
        org = claim_org or header_org or "dev-org"
        project = claim_project or header_project or "dev-project"
        log.info(
            "tenant_bound source=header_fallback org=%s project=%s allow_dev=1",
            org,
            project,
        )
        return org, project

    log.warning(
        "tenant_claim_required claim_org=%s claim_project=%s header_org=%s header_project=%s",
        claim_org,
        claim_project,
        header_org,
        header_project,
    )
    raise ApiError(
        code="AUTH_TENANT_CLAIM_REQUIRED",
        message="token must include org_id and project_id claims (production)",
        status_code=401,
    )


def resolve_principal(
    *,
    token: str,
    header_org: str | None = None,
    header_project: str | None = None,
    # backward-compat for older call sites
    org_id: str | None = None,
    project_id: str | None = None,
) -> Principal:
    header_org = header_org if header_org is not None else org_id
    header_project = header_project if header_project is not None else project_id

    if looks_like_jwt(token):
        try:
            claims = verify_access_token(token)
        except Exception as exc:  # noqa: BLE001
            raise ApiError(
                code="AUTH_INVALID",
                message=f"invalid JWT: {exc}",
                status_code=401,
            ) from exc
        org, project = bind_tenant_ids(
            claim_org=claim_org_raw(claims),
            claim_project=claim_project_raw(claims),
            header_org=header_org,
            header_project=header_project,
            allow_header_fallback=allow_dev(),
        )
        return Principal(
            subject=str(claims.get("sub") or "unknown"),
            org_id=org,
            project_id=project,
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
        org = header_org or "dev-org"
        project = header_project or "dev-project"
        log.info(
            "tenant_bound source=dev_bearer org=%s project=%s",
            org,
            project,
        )
        return Principal(
            subject="user:dev",
            org_id=org,
            project_id=project,
            roles=["developer", "admin"],
            markings=["public", "restricted"],
            token_kind="dev",
        )

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
    x_aos_desktop_version: str | None = Header(
        default=None, alias="X-AOS-Desktop-Version"
    ),
) -> Principal:
    token = parse_bearer(authorization)
    # TWA.1: only *explicit* X-Org-Id / X-Project-Id count for mismatch.
    # Middleware may default request.state to dev-org — must NOT treat that as a client header.
    principal = resolve_principal(
        token=token,
        header_org=x_org_id,
        header_project=x_project_id,
    )
    # 188m — optional force-reject old desktop (skip matrix endpoints)
    path = request.url.path or ""
    if x_aos_desktop_version and not path.startswith("/v1/ops/version-matrix"):
        from aos_api.version_matrix import assert_desktop_header_allowed

        assert_desktop_header_allowed(x_aos_desktop_version)
    request.state.principal = principal
    request.state.org_id = principal.org_id
    request.state.project_id = principal.project_id
    try:
        from aos_api.logging_facade import set_context

        set_context(
            org_id=principal.org_id,
            project_id=principal.project_id,
        )
    except Exception:  # noqa: BLE001
        pass
    log.info(
        "principal_resolved kind=%s subject=%s org=%s project=%s",
        principal.token_kind,
        principal.subject,
        principal.org_id,
        principal.project_id,
    )
    return principal
