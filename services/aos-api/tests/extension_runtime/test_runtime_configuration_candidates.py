from __future__ import annotations

import pytest

from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.runtime_configuration_candidates import read_candidates


SCOPE = TenantScope("org-org", "dev-project")
FIELDS = (
    "responsibility_plans", "runtime_policies", "data_policies", "egress_policies",
    "network_policies", "quota_policies", "budget_policies", "budgets",
)


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows


class Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return Result(self.row)


def test_current_candidates_are_only_scoped_counts_not_installation_readiness():
    conn = Connection({name: 0 for name in FIELDS})
    result = read_candidates(conn, SCOPE)
    assert result.counts == {name: 0 for name in FIELDS}
    assert result.missing == FIELDS
    assert result.all_present is False
    assert len(conn.calls) == 1
    assert conn.calls[0][1] == SCOPE.key * 8


def test_partial_candidates_remain_blocked_and_unknown_is_not_zero():
    conn = Connection({name: 1 for name in FIELDS} | {"budgets": 0})
    result = read_candidates(conn, SCOPE)
    assert result.missing == ("budgets",)
    assert result.all_present is False
    with pytest.raises(ValueError, match="candidate authority query incomplete"):
        read_candidates(Connection({"budgets": 0}), SCOPE)


def test_all_candidates_present_does_not_claim_runtime_binding():
    result = read_candidates(Connection({name: 1 for name in FIELDS}), SCOPE)
    assert result.all_present is True
    assert not hasattr(result, "runtime_ready")
