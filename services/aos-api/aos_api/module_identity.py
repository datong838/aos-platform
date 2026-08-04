"""Stable TI-2 Module instance identity primitives."""
from __future__ import annotations

import uuid
from typing import Any

from aos_api.tenant_scope import TenantScope

MODULE_IDENTITY_NAMESPACE = uuid.UUID("02aa6d2e-3d7b-5b7c-8aca-723dbf489a82")


class ModuleIdentityDriftError(RuntimeError):
    """The scoped legacy and stable Module identities no longer agree."""


def stable_module_pk(org_id: str, project_id: str, module_id: str) -> uuid.UUID:
    identity = f"{org_id}/{project_id}/{module_id}"
    return uuid.uuid5(MODULE_IDENTITY_NAMESPACE, identity)


def resolve_module_pk(conn: Any, scope: TenantScope, module_id: str) -> uuid.UUID | None:
    expected = stable_module_pk(scope.org_id, scope.project_id, module_id)
    rows = conn.execute(
        "SELECT id, module_id, module_pk FROM meta_module "
        "WHERE org_id=%s AND project_id=%s AND (module_pk=%s OR id=%s)",
        (*scope.key, expected, module_id),
    ).fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        raise ModuleIdentityDriftError(
            f"ambiguous module identity in scope {scope.org_id}/{scope.project_id}"
        )
    row = rows[0]
    actual = uuid.UUID(str(row["module_pk"])) if row["module_pk"] else None
    if (
        str(row["id"]) != module_id
        or str(row["module_id"]) != module_id
        or actual != expected
    ):
        raise ModuleIdentityDriftError(
            f"module identity drift in scope {scope.org_id}/{scope.project_id}"
        )
    return expected
