"""Original AIP budget contract in an explicitly disposable signed test schema."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
import importlib.util

from psycopg import sql
from psycopg.types.json import Jsonb
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import materialize_revision
from aos_api.tenant_scope import TenantScope


def install_signed_test_budget(conn,scope):
    schema=conn.execute('SELECT current_schema() AS name').fetchone()['name']
    if conn.info.port!=18432 or not schema.startswith('ar1c_'):
        raise AssertionError('budget fixture requires dedicated disposable database')
    conn.execute("""CREATE FUNCTION guard_aip4_append_only() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'AIP4_APPEND_ONLY' USING ERRCODE='55000'; END; $$ LANGUAGE plpgsql""")
    path=Path(__file__).resolve().parents[2]/'alembic/versions/aip10_001_budget_authority.py'
    spec=importlib.util.spec_from_file_location('signed_budget_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=conn.execute);migration.upgrade()
    now=datetime.now(timezone.utc)
    item=BudgetRevisionCreate(budgetId='isolated-signed-runtime-budget',revision=1,
        dailyLimitMinor=100,monthlyLimitMinor=1000,alertThresholdPct=80,
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(minutes=5),
        owner='隔离测试负责人',overBudgetApprover='隔离测试审批人',lifecycle='active')
    record=materialize_revision(TenantScope(**scope),'test-author',item)
    values=record.model_dump(mode='python');values.pop('tenant')
    values.update(**scope,payload=Jsonb(record.model_dump(mode='json',by_alias=True)))
    conn.execute('INSERT INTO aip_budget_head(org_id,project_id,budget_id,current_revision) VALUES(%s,%s,%s,1)',
        (scope['org_id'],scope['project_id'],record.budget_id))
    conn.execute(sql.SQL('INSERT INTO aip_budget_revision ({}) VALUES ({})').format(
        sql.SQL(',').join(map(sql.Identifier,values)),sql.SQL(',').join(sql.Placeholder() for _ in values)),tuple(values.values()))
    return dict(authority='aip.budget_revision',id=record.budget_id,revision=record.revision,hash='sha256:'+record.content_hash)
