"""TI-1 E2 feature-gated tenant dual-write evidence helpers."""
from __future__ import annotations

import hashlib
import os
from enum import StrEnum
from typing import Any

from aos_api.tenant_scope import TenantScope

AUTHZ_DUAL_WRITE_ENV = "AOS_TENANT_DUAL_WRITE_AUTHZ"


class DualWriteMode(StrEnum):
    OFF = "off"
    SHADOW = "shadow"
    ENFORCE = "enforce"


def authz_dual_write_mode(raw: str | None = None) -> DualWriteMode:
    value = (raw if raw is not None else os.getenv(AUTHZ_DUAL_WRITE_ENV, "off"))
    try:
        return DualWriteMode(value.strip().lower())
    except ValueError as exc:
        raise RuntimeError(
            f"{AUTHZ_DUAL_WRITE_ENV} must be off, shadow, or enforce"
        ) from exc


def stable_key_hash(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def record_dual_write_evidence(
    conn: Any,
    *,
    scope: TenantScope,
    resource: str,
    operation: str,
    key_hash: str,
    status: str,
    observed_scope: TenantScope | None,
) -> None:
    conn.execute(
        """
        INSERT INTO tenant_dual_write_ledger (
          org_id, project_id, resource, operation, key_hash,
          observed_org_id, observed_project_id, status
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            scope.org_id,
            scope.project_id,
            resource,
            operation,
            key_hash,
            observed_scope.org_id if observed_scope else None,
            observed_scope.project_id if observed_scope else None,
            status,
        ),
    )
