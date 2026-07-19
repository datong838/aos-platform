"""TWB.6 — SaaS tenant provisioning + quotas (ops control plane; in-memory)."""
from __future__ import annotations

import re
import time
from typing import Any

from aos_api import membership as mem
from aos_api import orgs as org_store
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.provisioning")

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")

# org_id -> tenant record
_TENANTS: dict[str, dict[str, Any]] = {}

DEFAULT_QUOTA = {
    "maxWorkspaces": 5,
    "maxMembers": 20,
    "maxStorageGb": 50,
}


def reset_provisioning_store() -> None:
    _TENANTS.clear()


def require_ops(roles: list[str]) -> None:
    allowed = {"platform_admin", "admin", "developer", "dev"}
    if not any(r.lower() in allowed for r in (roles or [])):
        raise ApiError(
            code="FORBIDDEN",
            message="SaaS provisioning requires platform admin",
            status_code=403,
        )


def list_tenants() -> list[dict[str, Any]]:
    return [dict(v) for _, v in sorted(_TENANTS.items())]


def get_tenant(org_id: str) -> dict[str, Any] | None:
    row = _TENANTS.get(org_id)
    return dict(row) if row else None


def provision_tenant(
    *,
    org_id: str,
    org_name: str,
    owner_subject: str,
    plan: str = "starter",
    quota: dict[str, Any] | None = None,
    actor_id: str,
) -> dict[str, Any]:
    oid = (org_id or "").strip()
    if not _SAFE.match(oid):
        raise ApiError(
            code="VALIDATION",
            message="orgId must be 2-64 chars [A-Za-z0-9._-]",
            status_code=400,
        )
    if oid in _TENANTS:
        raise ApiError(code="CONFLICT", message="tenant already provisioned", status_code=409)
    q = {**DEFAULT_QUOTA, **(quota or {})}
    for k in ("maxWorkspaces", "maxMembers", "maxStorageGb"):
        try:
            q[k] = max(0, int(q[k]))
        except (TypeError, ValueError) as exc:
            raise ApiError(
                code="VALIDATION",
                message=f"invalid quota.{k}",
                status_code=400,
            ) from exc

    org_store.ensure_org(oid, name=(org_name or oid).strip() or oid, kind="saas")

    default_project = "dev-project"
    mem.upsert_member(
        oid,
        default_project,
        owner_subject,
        "owner",
        actor_id=actor_id,
    )

    row = {
        "orgId": oid,
        "orgName": org_store.org_name(oid),
        "plan": plan or "starter",
        "status": "active",
        "ownerSubject": owner_subject,
        "defaultProjectId": default_project,
        "quota": q,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "createdBy": actor_id,
    }
    _TENANTS[oid] = row
    mem.append_audit(
        org_id=oid,
        project_id=default_project,
        actor_id=actor_id,
        action="saas.provision",
        detail={"plan": row["plan"], "quota": q},
    )
    log.info(
        "saas_provisioned org=%s owner=%s plan=%s actor=%s",
        oid,
        owner_subject,
        row["plan"],
        actor_id,
    )
    return dict(row)


def patch_quota(
    org_id: str,
    quota_patch: dict[str, Any],
    *,
    actor_id: str,
) -> dict[str, Any]:
    row = _TENANTS.get(org_id)
    if not row:
        raise ApiError(code="NOT_FOUND", message="tenant not found", status_code=404)
    q = dict(row["quota"])
    for k in ("maxWorkspaces", "maxMembers", "maxStorageGb"):
        if k in quota_patch:
            try:
                q[k] = max(0, int(quota_patch[k]))
            except (TypeError, ValueError) as exc:
                raise ApiError(
                    code="VALIDATION",
                    message=f"invalid quota.{k}",
                    status_code=400,
                ) from exc
    row["quota"] = q
    mem.append_audit(
        org_id=org_id,
        project_id=row.get("defaultProjectId") or "-",
        actor_id=actor_id,
        action="saas.quota_patch",
        detail={"quota": q},
    )
    log.info("saas_quota_patch org=%s actor=%s", org_id, actor_id)
    return dict(row)


def assert_workspace_quota(org_id: str, current_workspace_count: int) -> None:
    row = _TENANTS.get(org_id)
    if not row:
        return  # non-SaaS / private orgs unconstrained here
    limit = int(row["quota"].get("maxWorkspaces") or 0)
    if current_workspace_count >= limit:
        raise ApiError(
            code="QUOTA_EXCEEDED",
            message=f"workspace quota exceeded (max {limit})",
            status_code=409,
            details={"quota": "maxWorkspaces", "limit": limit},
        )
