"""Stable TI-2 Module instance identity primitives."""
from __future__ import annotations

import uuid
from typing import Any

from aos_api.tenant_scope import TenantScope

MODULE_IDENTITY_NAMESPACE = uuid.UUID("02aa6d2e-3d7b-5b7c-8aca-723dbf489a82")


def stable_module_pk(org_id: str, project_id: str, module_id: str) -> uuid.UUID:
    identity = f"{org_id}/{project_id}/{module_id}"
    return uuid.uuid5(MODULE_IDENTITY_NAMESPACE, identity)


def resolve_module_pk(conn: Any, scope: TenantScope, module_id: str) -> uuid.UUID | None:
    row = conn.execute(
        "SELECT module_pk FROM meta_module "
        "WHERE id=%s AND org_id=%s AND project_id=%s",
        (module_id, *scope.key),
    ).fetchone()
    if not row or not row["module_pk"]:
        return None
    return uuid.UUID(str(row["module_pk"]))
