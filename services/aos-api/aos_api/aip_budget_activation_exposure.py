"""Scoped read of the existing ledger before a first budget activation.

An empty AOS ledger is only a necessary fact. It does not prove external usage
or produce an activation preview, approval, or runtime permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.pq import TransactionStatus

from aos_api.tenant_scope import TenantScope


class BudgetActivationLedgerBlocked(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class InitialBudgetLedgerSnapshot:
    budget_id: str
    current_revision: int
    head_version: int
    checked_at: datetime
    recorded_invocations: int
    recorded_reservations: int
    recorded_buckets: int
    external_usage_proven: bool = False


def read_initial_budget_ledger(
    conn, scope: TenantScope, budget_id: str, *, expected_head_version: int
) -> InitialBudgetLedgerSnapshot:
    """Require a current draft and no internal usage under one scoped transaction."""
    if (type(scope) is not TenantScope or type(budget_id) is not str
            or not budget_id or budget_id != budget_id.strip()
            or type(expected_head_version) is not int or expected_head_version < 1):
        raise BudgetActivationLedgerBlocked("BUDGET_ACTIVATION_ARGUMENT_INVALID")
    if conn.info.transaction_status != TransactionStatus.INTRANS:
        raise BudgetActivationLedgerBlocked("BUDGET_ACTIVATION_TRANSACTION_REQUIRED")
    identity = conn.execute(
        "SELECT current_setting('aos.org_id',true) AS org_id, "
        "current_setting('aos.project_id',true) AS project_id"
    ).fetchone()
    if (identity is None or identity["org_id"] != scope.org_id
            or identity["project_id"] != scope.project_id):
        raise BudgetActivationLedgerBlocked("BUDGET_ACTIVATION_SCOPE_MISMATCH")
    head = conn.execute(
        """SELECT h.current_revision,h.version,r.lifecycle
           FROM aip_budget_head h JOIN aip_budget_revision r
             ON r.org_id=h.org_id AND r.project_id=h.project_id
            AND r.budget_id=h.budget_id AND r.revision=h.current_revision
           WHERE h.org_id=%s AND h.project_id=%s AND h.budget_id=%s
           FOR SHARE OF h""",
        (*scope.key, budget_id),
    ).fetchone()
    if (head is None or head["version"] != expected_head_version
            or head["lifecycle"] != "draft"):
        raise BudgetActivationLedgerBlocked("BUDGET_ACTIVATION_HEAD_DRIFT")
    row = conn.execute(
        """SELECT
          (SELECT count(*) FROM aip_capability_invocation
             WHERE org_id=%s AND project_id=%s
               AND policy_ref->>'resourceType'='BudgetRevision'
               AND policy_ref->>'resourceId'=%s) AS invocations,
          (SELECT count(*) FROM aip_budget_reservation
             WHERE org_id=%s AND project_id=%s
               AND policy_ref->>'resourceType'='BudgetRevision'
               AND policy_ref->>'resourceId'=%s) AS reservations,
          (SELECT count(*) FROM aip_budget_bucket
             WHERE org_id=%s AND project_id=%s
               AND ((bucket_kind='daily' AND account_id=%s)
                 OR (bucket_kind='pilot' AND account_id=%s))) AS buckets,
          clock_timestamp() AS checked_at""",
        (*scope.key, budget_id, *scope.key, budget_id,
         *scope.key, f"{budget_id}:daily", f"{budget_id}:pilot"),
    ).fetchone()
    if (row is None or any(type(row[name]) is not int or row[name] != 0
                           for name in ("invocations", "reservations", "buckets"))):
        raise BudgetActivationLedgerBlocked("BUDGET_ACTIVATION_LEDGER_NOT_EMPTY")
    return InitialBudgetLedgerSnapshot(
        budget_id=budget_id, current_revision=head["current_revision"],
        head_version=head["version"], checked_at=row["checked_at"],
        recorded_invocations=row["invocations"],
        recorded_reservations=row["reservations"],
        recorded_buckets=row["buckets"],
    )
