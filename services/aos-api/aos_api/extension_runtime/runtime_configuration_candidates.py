"""Tenant-scoped read-only candidate counts for runtime configuration guidance.

Counts do not bind a source to an installation and never authorize runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect_read_only
from aos_api.tenant_scope import TenantScope


FIELDS = (
    "responsibility_plans", "runtime_policies", "data_policies", "egress_policies",
    "network_policies", "quota_policies", "budget_policies", "budgets",
)


@dataclass(frozen=True)
class RuntimeConfigurationCandidates:
    counts: dict[str, int]
    missing: tuple[str, ...]
    all_present: bool


def read_candidates(conn: Any, scope: TenantScope) -> RuntimeConfigurationCandidates:
    """Read current head/revision candidates; the caller owns visibility and scope."""
    if type(scope) is not TenantScope:
        raise TypeError("exact tenant scope required")
    row = conn.execute(
        """SELECT
          (SELECT count(*) FROM aip_responsibility_plan_head h
             JOIN aip_responsibility_plan_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.plan_id=h.plan_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND r.lifecycle='frozen') AS responsibility_plans,
          (SELECT count(*) FROM aip_runtime_policy_head h
             JOIN aip_runtime_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.runtime_policy_id=h.runtime_policy_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND r.lifecycle='active'
                AND r.payload->'killSwitchEnabled'='false'::jsonb) AS runtime_policies,
          (SELECT count(*) FROM aip_runtime_guard_policy_head h
             JOIN aip_runtime_guard_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='data_classification'
                AND r.lifecycle='active' AND r.effective_from<=clock_timestamp()
                AND r.effective_until>clock_timestamp()) AS data_policies,
          (SELECT count(*) FROM aip_runtime_guard_policy_head h
             JOIN aip_runtime_guard_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='egress'
                AND r.lifecycle='active' AND r.effective_from<=clock_timestamp()
                AND r.effective_until>clock_timestamp()) AS egress_policies,
          (SELECT count(*) FROM aip_network_policy_head h
             JOIN aip_network_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.policy_id=h.policy_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND r.lifecycle='active'
                AND r.effective_from<=clock_timestamp() AND r.effective_until>clock_timestamp()) AS network_policies,
          (SELECT count(*) FROM aip_model_governance_policy_head h
             JOIN aip_model_governance_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='quota'
                AND r.lifecycle='active' AND r.effective_from<=clock_timestamp()
                AND r.effective_until>clock_timestamp()) AS quota_policies,
          (SELECT count(*) FROM aip_model_governance_policy_head h
             JOIN aip_model_governance_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget'
                AND r.lifecycle='active' AND r.effective_from<=clock_timestamp()
                AND r.effective_until>clock_timestamp()) AS budget_policies,
          (SELECT count(*) FROM aip_budget_head h
             JOIN aip_budget_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.budget_id=h.budget_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND r.lifecycle='active'
                AND r.effective_from<=clock_timestamp() AND r.effective_until>clock_timestamp()) AS budgets""",
        scope.key * 8,
    ).fetchone()
    if not isinstance(row, dict) or set(row) != set(FIELDS):
        raise ValueError("candidate authority query incomplete")
    if any(type(row[name]) is not int or row[name] < 0 for name in FIELDS):
        raise ValueError("candidate authority count invalid")
    counts = {name: row[name] for name in FIELDS}
    missing = tuple(name for name in FIELDS if counts[name] == 0)
    return RuntimeConfigurationCandidates(counts, missing, not missing)


class RuntimeConfigurationCandidateReader:
    """Read candidates under the application's scoped read-only connection."""

    def __init__(self, connect_factory: Callable[[], AbstractContextManager[Any]] = connect_read_only) -> None:
        self._connect_factory = connect_factory

    def read(self, scope: TenantScope) -> RuntimeConfigurationCandidates:
        with self._connect_factory() as conn:
            apply_asset_transaction_scope(conn, org_id=scope.org_id, project_id=scope.project_id)
            result = read_candidates(conn, scope)
            conn.commit()
            return result
