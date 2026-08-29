"""Governed, tenant-bound AIP FeatureActivation commands for Workshop."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, Literal

import psycopg

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.ecommerce_workshop_contracts import (
    WorkshopFeatureActivationCommandReceipt,
    WorkshopFeatureActivationCommandRequest,
    WorkshopFeatureActivationCommandResponse,
    WorkshopTenant,
)
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[[TenantScope], AbstractContextManager[Any]]
_WRITE_ROLES = frozenset({"admin", "platform-admin", "workshop-admin"})


class WorkshopFeatureActivationError(RuntimeError):
    code = "WORKSHOP_FEATURE_ACTIVATION_FAILED"


class WorkshopFeatureActivationForbidden(WorkshopFeatureActivationError):
    code = "WORKSHOP_FEATURE_ACTIVATION_FORBIDDEN"


class WorkshopFeatureActivationConflict(WorkshopFeatureActivationError):
    code = "WORKSHOP_FEATURE_ACTIVATION_CONFLICT"


class WorkshopFeatureActivationUnavailable(WorkshopFeatureActivationError):
    code = "WORKSHOP_FEATURE_ACTIVATION_AUTHORITY_UNAVAILABLE"


class EcommerceWorkshopFeatureActivationService:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or connect

    def execute(
        self,
        *,
        principal: Principal,
        feature_id: str,
        operation: Literal["activate", "revoke"],
        body: WorkshopFeatureActivationCommandRequest,
        idempotency_key: str,
    ) -> WorkshopFeatureActivationCommandResponse:
        if not _WRITE_ROLES.intersection(principal.roles):
            raise WorkshopFeatureActivationForbidden(
                "FeatureActivation requires an administrator role"
            )
        key = idempotency_key.strip()
        if not key or len(key) > 200:
            raise ValueError("Idempotency-Key must be 1..200 characters")
        if operation == "activate":
            if body.content_hash is None or body.expires_at is None:
                raise ValueError("activation requires contentHash and expiresAt")
            if body.expires_at <= datetime.now(UTC):
                raise ValueError("activation expiry must be in the future")
        elif body.content_hash is not None or body.expires_at is not None:
            raise ValueError("revoke does not accept contentHash or expiresAt")

        request_hash = canonical_sha256(
            {
                "featureId": feature_id,
                "operation": operation,
                "expectedRevision": body.expected_revision,
                "contentHash": body.content_hash,
                "expiresAt": body.expires_at.isoformat() if body.expires_at else None,
            }
        )
        scope = TenantScope(principal.org_id, principal.project_id)
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    "SELECT receipt_data,replayed FROM "
                    "ecommerce_workshop_feature_activation_command_wcat_001("
                    "%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        feature_id,
                        operation,
                        body.expected_revision,
                        body.content_hash,
                        body.expires_at,
                        key,
                        request_hash,
                        principal.subject,
                    ),
                ).fetchone()
        except psycopg.Error as exc:
            if exc.sqlstate == "WC002":
                raise WorkshopFeatureActivationConflict(str(exc)) from exc
            if exc.sqlstate in {"42883", "42P01", "42501"}:
                raise WorkshopFeatureActivationUnavailable(
                    "FeatureActivation authority is not installed"
                ) from exc
            raise WorkshopFeatureActivationError(
                "FeatureActivation command failed closed"
            ) from exc
        if row is None:
            raise WorkshopFeatureActivationError(
                "FeatureActivation command returned no receipt"
            )
        return WorkshopFeatureActivationCommandResponse(
            tenant=WorkshopTenant(orgId=principal.org_id, projectId=principal.project_id),
            receipt=WorkshopFeatureActivationCommandReceipt.model_validate(
                row["receipt_data"]
            ),
            replayed=bool(row["replayed"]),
        )


__all__ = [
    "EcommerceWorkshopFeatureActivationService",
    "WorkshopFeatureActivationConflict",
    "WorkshopFeatureActivationError",
    "WorkshopFeatureActivationForbidden",
    "WorkshopFeatureActivationUnavailable",
]
