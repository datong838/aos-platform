from __future__ import annotations

import uuid

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.db import get_dsn
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


def test_killed_runtime_policy_is_not_counted_in_disposable_postgres():
    conn = psycopg.connect(get_dsn(), row_factory=dict_row)
    try:
        baseline = read_candidates(conn, SCOPE).counts["runtime_policies"]
        for killed in (True, False):
            policy_id = f"bg00ef-test-{uuid.uuid4().hex}"
            conn.execute(
                "INSERT INTO aip_runtime_policy_head(org_id,project_id,runtime_policy_id,current_revision,version) "
                "VALUES(%s,%s,%s,1,1)", (*SCOPE.key, policy_id),
            )
            conn.execute(
                "INSERT INTO aip_runtime_policy_revision(org_id,project_id,runtime_policy_id,revision,"
                "content_hash,lifecycle,payload,created_by,created_at) "
                "VALUES(%s,%s,%s,1,%s,'active',%s,'bg00ef-test',NOW())",
                (*SCOPE.key, policy_id, "a" * 64, Jsonb({"killSwitchEnabled": killed})),
            )
            expected = baseline if killed else baseline + 1
            assert read_candidates(conn, SCOPE).counts["runtime_policies"] == expected
    finally:
        conn.rollback()
        conn.close()
