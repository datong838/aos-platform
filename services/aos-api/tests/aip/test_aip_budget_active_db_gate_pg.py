"""Direct runtime INSERT cannot turn a Draft budget active."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest

from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevisionCreate
from aos_api.aip_budget_store import AipBudgetAuthorityStore, materialize_revision
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def test_runtime_direct_active_insert_requires_formal_consumer_without_mutation() -> None:
    now = datetime.now(UTC)
    budget_id = f"test:active-db-gate:{uuid4().hex}"
    draft = BudgetRevisionCreate(
        budgetId=budget_id, revision=1, environment="development", currency="CNY",
        dailyLimitMinor=500, monthlyLimitMinor=5000, alertThresholdPct=80,
        hardStop=True, unknownUsageBehavior="block",
        effectiveFrom=now - timedelta(minutes=1),
        effectiveUntil=now + timedelta(days=30), owner="test:owner",
        overBudgetApprover="test:checker", lifecycle="draft",
    )
    AipBudgetAuthorityStore().publish(SCOPE, "test:maker", f"draft:{budget_id}", draft)
    active = materialize_revision(
        SCOPE, "test:maker",
        draft.model_copy(update={"revision": 2, "lifecycle": BudgetLifecycle.ACTIVE}),
    )
    with connect(SCOPE) as conn:
        with pytest.raises(psycopg.Error, match="BUDGET_ACTIVATION_CONSUMPTION_REQUIRED"):
            conn.execute(
                """INSERT INTO aip_budget_revision
                   (org_id,project_id,budget_id,revision,content_hash,lifecycle,
                    environment,currency,daily_limit_minor,monthly_limit_minor,
                    alert_threshold_pct,hard_stop,unknown_usage_behavior,
                    effective_from,effective_until,owner,over_budget_approver,
                    payload,created_by,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (*SCOPE.key, active.budget_id, active.revision, active.content_hash,
                 active.lifecycle.value, active.environment, active.currency,
                 active.daily_limit_minor, active.monthly_limit_minor,
                 active.alert_threshold_pct, active.hard_stop,
                 active.unknown_usage_behavior, active.effective_from,
                 active.effective_until, active.owner, active.over_budget_approver,
                 json.dumps(active.model_dump(mode="json", by_alias=True)),
                 "test:maker", active.created_at),
            )
        conn.rollback()
    with connect(SCOPE) as conn:
        head = conn.execute(
            "SELECT current_revision,version FROM aip_budget_head WHERE org_id=%s AND project_id=%s AND budget_id=%s",
            (*SCOPE.key, budget_id),
        ).fetchone()
        assert (head["current_revision"], head["version"]) == (1, 1)
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_budget_revision WHERE org_id=%s AND project_id=%s AND budget_id=%s AND lifecycle='active'",
            (*SCOPE.key, budget_id),
        ).fetchone()["n"] == 0
