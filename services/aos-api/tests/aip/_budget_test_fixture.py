"""Legacy governance fixture, confined to pytest's disposable PostgreSQL database.

This seeds a historical active row for downstream reader tests. It is not an
activation workflow and must never target the current AOS database.
"""

import json

from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevisionCreate
from aos_api.aip_budget_store import materialize_revision
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


def seed_isolated_active_budget(
    scope: TenantScope, actor: str, item: BudgetRevisionCreate,
):
    if item.lifecycle is not BudgetLifecycle.ACTIVE or item.revision != 1:
        raise ValueError("legacy fixture requires a first active revision")
    with connect(scope) as conn:
        database = conn.execute("SELECT current_database() AS name").fetchone()["name"]
        if not (database.startswith("aos_test_") and database.endswith("_ti4_test")):
            raise RuntimeError("legacy active fixture is isolated-test-database only")
        result = materialize_revision(scope, actor, item)
        conn.execute(
            """INSERT INTO aip_budget_head
               (org_id,project_id,budget_id,current_revision,version)
               VALUES(%s,%s,%s,1,1)""",
            (*scope.key, result.budget_id),
        )
        conn.execute(
            """INSERT INTO aip_budget_revision
               (org_id,project_id,budget_id,revision,content_hash,lifecycle,
                environment,currency,daily_limit_minor,monthly_limit_minor,
                alert_threshold_pct,hard_stop,unknown_usage_behavior,
                effective_from,effective_until,owner,over_budget_approver,
                payload,created_by,created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (*scope.key, result.budget_id, result.revision, result.content_hash,
             result.lifecycle.value, result.environment, result.currency,
             result.daily_limit_minor, result.monthly_limit_minor,
             result.alert_threshold_pct, result.hard_stop,
             result.unknown_usage_behavior, result.effective_from,
             result.effective_until, result.owner, result.over_budget_approver,
             json.dumps(result.model_dump(mode="json", by_alias=True)),
             actor, result.created_at),
        )
        conn.commit()
        return result
