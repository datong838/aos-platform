"""Initial budget ledger check in the disposable PostgreSQL test database."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aos_api.aip_budget_activation_exposure import (
    BudgetActivationLedgerBlocked,
    read_initial_budget_ledger,
)
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import AipBudgetAuthorityStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime.now(UTC)


def seed_draft() -> str:
    budget_id = f"test:initial-budget:{uuid4().hex}"
    AipBudgetAuthorityStore().publish(
        SCOPE, "test:maker", f"draft:{budget_id}",
        BudgetRevisionCreate(
            budgetId=budget_id, revision=1, environment="development",
            currency="CNY", dailyLimitMinor=500, monthlyLimitMinor=5000,
            alertThresholdPct=80, hardStop=True, unknownUsageBehavior="block",
            effectiveFrom=NOW - timedelta(minutes=1),
            effectiveUntil=NOW + timedelta(days=30),
            owner="test:owner", overBudgetApprover="test:checker",
            lifecycle="draft",
        ),
    )
    return budget_id


def test_initial_draft_with_no_recorded_invocation_reservation_or_bucket_is_read_only() -> None:
    budget_id = seed_draft()
    with connect(SCOPE) as conn:
        result = read_initial_budget_ledger(conn, SCOPE, budget_id, expected_head_version=1)
        assert result.budget_id == budget_id
        assert result.current_revision == 1
        assert result.head_version == 1
        assert result.recorded_invocations == 0
        assert result.recorded_reservations == 0
        assert result.recorded_buckets == 0
        assert result.external_usage_proven is False


def test_wrong_scope_stale_head_and_missing_budget_fail_closed() -> None:
    budget_id = seed_draft()
    with connect(SCOPE) as conn:
        with pytest.raises(BudgetActivationLedgerBlocked, match="SCOPE"):
            read_initial_budget_ledger(
                conn, TenantScope("other-org", "dev-project"), budget_id,
                expected_head_version=1,
            )
        with pytest.raises(BudgetActivationLedgerBlocked, match="HEAD"):
            read_initial_budget_ledger(conn, SCOPE, budget_id, expected_head_version=2)
        with pytest.raises(BudgetActivationLedgerBlocked, match="HEAD"):
            read_initial_budget_ledger(conn, SCOPE, "missing", expected_head_version=1)


def test_existing_budget_bucket_blocks_first_activation_without_mutation() -> None:
    budget_id = seed_draft()
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_budget_bucket(
                org_id,project_id,bucket_kind,account_id,period_start,period_end,
                currency,limit_minor,unknown_minor)
               VALUES(%s,%s,'daily',%s,%s,%s,'CNY',500,10)""",
            (*SCOPE.key, f"{budget_id}:daily", NOW, NOW + timedelta(days=1)),
        )
        with pytest.raises(BudgetActivationLedgerBlocked, match="NOT_EMPTY"):
            read_initial_budget_ledger(conn, SCOPE, budget_id, expected_head_version=1)
        row = conn.execute(
            "SELECT unknown_minor FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s AND account_id=%s",
            (*SCOPE.key, f"{budget_id}:daily"),
        ).fetchone()
        assert row["unknown_minor"] == 10
