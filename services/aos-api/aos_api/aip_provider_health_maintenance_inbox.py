"""Fail-closed discovery of one approved Provider Health execution Lease."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_provider_health_action import PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
from aos_api.aip_provider_health_action_authority import (
    provider_health_action_type_snapshot,
)
from aos_api.aip_provider_health_maintenance import SCOPE
from aos_api.aip_provider_health_maintenance_authority import (
    ProviderHealthActionLeaseConsumer,
    ProviderHealthLeaseExecution,
)
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class ProviderHealthLeaseInboxError(RuntimeError):
    """Stable selector failure that contains no sensitive row detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ProviderHealthMaintenanceLeaseInbox:
    """Select exactly one current, owned and unconsumed canonical Lease."""

    def __init__(self, principal: Principal) -> None:
        scope = TenantScope(principal.org_id, principal.project_id)
        if scope != SCOPE:
            raise ProviderHealthLeaseInboxError(
                "PROVIDER_HEALTH_MAINTENANCE_TENANT_FORBIDDEN"
            )
        if not {role.lower() for role in principal.roles}.intersection(
            {"admin", "executor", "aip_executor"}
        ):
            raise ProviderHealthLeaseInboxError(
                "PROVIDER_HEALTH_MAINTENANCE_EXECUTOR_REQUIRED"
            )
        self._principal = principal
        self._scope = scope

    def resolve(self, now: datetime) -> ProviderHealthLeaseExecution | None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ProviderHealthLeaseInboxError(
                "PROVIDER_HEALTH_MAINTENANCE_CUTOFF_TZ_REQUIRED"
            )
        expected_revision = provider_health_action_type_snapshot()["revisionHash"]
        with connect(self._scope) as conn:
            rows = conn.execute(
                """SELECT lease.lease_id, lease.proposal_hash
                   FROM aip_action_execution_lease lease
                   JOIN aip_action_proposal proposal
                     ON proposal.org_id=lease.org_id
                    AND proposal.project_id=lease.project_id
                    AND proposal.proposal_id=lease.proposal_id
                   WHERE lease.org_id=%s AND lease.project_id=%s
                     AND lease.owner_id=%s
                     AND lease.status='active' AND lease.expires_at>%s
                     AND proposal.status='leased'
                     AND proposal.action_type_id=%s
                     AND proposal.action_type_revision_hash=%s
                     AND proposal.proposal_hash=lease.proposal_hash
                     AND NOT EXISTS (
                       SELECT 1 FROM aip_action_receipt receipt
                        WHERE receipt.org_id=lease.org_id
                          AND receipt.project_id=lease.project_id
                          AND receipt.lease_id=lease.lease_id
                          AND receipt.receipt_kind='initial'
                     )
                   ORDER BY lease.expires_at,lease.created_at,lease.lease_id
                   LIMIT 2""",
                (
                    *self._scope.key,
                    self._principal.subject,
                    now,
                    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
                    expected_revision,
                ),
            ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise ProviderHealthLeaseInboxError(
                "MULTIPLE_EXACT_PROVIDER_HEALTH_LEASES_REQUIRE_SELECTION"
            )
        row: dict[str, Any] = rows[0]
        return ProviderHealthLeaseExecution(
            principal=self._principal,
            lease_id=row["lease_id"],
            expected_proposal_hash=row["proposal_hash"],
        )


class ProviderHealthMaintenanceLeaseRunner:
    """Resolve the current exact Lease and consume its canonical Receipt."""

    def __init__(
        self,
        inbox: ProviderHealthMaintenanceLeaseInbox,
        service: AipActionExecutionService,
    ) -> None:
        self._inbox = inbox
        self._service = service

    def __call__(self, now: datetime) -> dict[str, Any]:
        execution = self._inbox.resolve(now)
        if execution is None:
            raise ProviderHealthLeaseInboxError("EXACT_APPROVAL_LEASE_REQUIRED")
        return ProviderHealthActionLeaseConsumer(self._service, execution)(now)


__all__ = [
    "ProviderHealthLeaseInboxError",
    "ProviderHealthMaintenanceLeaseInbox",
    "ProviderHealthMaintenanceLeaseRunner",
]
