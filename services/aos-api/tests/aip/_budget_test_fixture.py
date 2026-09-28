"""Legacy governance fixture, confined to pytest's disposable PostgreSQL database.

This seeds a historical active row for downstream reader tests. It is not an
activation workflow and must never target the current AOS database.
"""

import json

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevisionCreate
from aos_api.aip_budget_store import materialize_revision
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope


def insert_isolated_active_budget_revision(scope: TenantScope, query: str, params: tuple) -> None:
    """Seed legacy reader coverage only in pytest's disposable full database."""
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        database = conn.execute("SELECT current_database() AS name").fetchone()["name"]
        if not (database.startswith("aos_test_") and database.endswith("_ti4_test")):
            raise RuntimeError("legacy active fixture is isolated-test-database only")
        if conn.execute(
            """SELECT count(*) AS n FROM pg_trigger
               WHERE tgrelid='public.aip_budget_revision'::regclass
                 AND tgname='aip_budget_active_insert_guard'"""
        ).fetchone()["n"] != 1:
            raise RuntimeError("database active gate must exist before legacy fixture")
        conn.execute("ALTER TABLE public.aip_budget_revision DISABLE TRIGGER aip_budget_active_insert_guard")
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
        conn.execute(query, params)
        conn.execute("RESET ROLE")
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.execute("ALTER TABLE public.aip_budget_revision ENABLE TRIGGER aip_budget_active_insert_guard")
        conn.commit()


def seed_isolated_active_budget(
    scope: TenantScope, actor: str, item: BudgetRevisionCreate,
):
    if item.lifecycle is not BudgetLifecycle.ACTIVE or item.revision != 1:
        raise ValueError("legacy fixture requires a first active revision")
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        database = conn.execute("SELECT current_database() AS name").fetchone()["name"]
        if not (database.startswith("aos_test_") and database.endswith("_ti4_test")):
            raise RuntimeError("legacy active fixture is isolated-test-database only")
        if conn.execute(
            """SELECT count(*) AS n FROM pg_trigger
               WHERE tgrelid='public.aip_budget_revision'::regclass
                 AND tgname='aip_budget_active_insert_guard'"""
        ).fetchone()["n"] != 1:
            raise RuntimeError("database active gate must exist before legacy fixture")
        result = materialize_revision(scope, actor, item)
        # This DDL is transactional and confined to a disposable test database.
        # Any error rolls the disabled-trigger state back with the connection.
        conn.execute(
            "ALTER TABLE public.aip_budget_revision DISABLE TRIGGER aip_budget_active_insert_guard"
        )
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
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
        conn.execute("RESET ROLE")
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.execute(
            "ALTER TABLE public.aip_budget_revision ENABLE TRIGGER aip_budget_active_insert_guard"
        )
        conn.commit()
        return result
