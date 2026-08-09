"""Authoritative organization/workspace scope validation."""

from __future__ import annotations

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


def require_workspace(scope: TenantScope) -> None:
    """Reject scopes absent from the control-plane directory.

    The lookup intentionally runs before tenant role binding because its job is
    to validate whether that tenant boundary exists at all.
    """
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM twa_workspace WHERE org_id=%s AND project_id=%s",
                scope.key,
            ).fetchone()
    except Exception as exc:
        raise ApiError(
            code="AUTH_TENANT_DIRECTORY_UNAVAILABLE",
            message="tenant directory is unavailable",
            status_code=503,
        ) from exc
    if row is None:
        raise ApiError(
            code="AUTH_TENANT_UNKNOWN",
            message="organization/workspace scope is not registered",
            status_code=403,
        )
