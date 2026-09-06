"""Formal budget contract on disposable PostgreSQL, never the default AIP DSN."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import uuid
import os

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import materialize_revision
from aos_api.tenant_scope import TenantScope

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='dedicated isolated PostgreSQL opt-in required')


@pytest.fixture
def budget_case():
    schema='ar1c_'+uuid.uuid4().hex
    conn=psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True)
    created=conn.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created:conn.execute('CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN')
    try:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        # Same prerequisite function as aip4_001, in this disposable schema only.
        conn.execute("""CREATE FUNCTION guard_aip4_append_only() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'AIP4_APPEND_ONLY' USING ERRCODE='55000'; END; $$ LANGUAGE plpgsql""")
        path=Path(__file__).resolve().parents[2]/'alembic/versions/aip10_001_budget_authority.py'
        spec=importlib.util.spec_from_file_location('isolated_budget_migration',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
        now=datetime.now(timezone.utc)
        item=BudgetRevisionCreate(budgetId='isolated-runtime-budget',revision=1,dailyLimitMinor=100,
            monthlyLimitMinor=1000,alertThresholdPct=80,effectiveFrom=now-timedelta(minutes=1),
            effectiveUntil=now+timedelta(minutes=5),owner='测试负责人',overBudgetApprover='测试审批人',lifecycle='active')
        record=materialize_revision(TenantScope('org-org','dev-project'),'test-author',item)
        values=record.model_dump(mode='python');values.pop('tenant')
        values.update(org_id='org-org',project_id='dev-project',payload=Jsonb(record.model_dump(mode='json',by_alias=True)))
        conn.execute("INSERT INTO aip_budget_head(org_id,project_id,budget_id,current_revision) VALUES('org-org','dev-project',%s,1)",(record.budget_id,))
        conn.execute(sql.SQL('INSERT INTO aip_budget_revision ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier,values)),sql.SQL(',').join(sql.Placeholder() for _ in values)),tuple(values.values()))
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
        conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
        conn.execute('SET ROLE aos_runtime')
        yield conn,record,schema
    finally:
        conn.execute('RESET ROLE')
        conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        if created:conn.execute('DROP ROLE aos_runtime')
        conn.close()


def reference(record):
    return dict(authority='aip.budget_revision',id=record.budget_id,revision=record.revision,hash='sha256:'+record.content_hash)


def test_current_budget_reference_reads_original_canonical_record(budget_case):
    from aos_api.aip_runtime_configuration_authority import read_current_budget_ref
    conn,record,_=budget_case
    with conn.transaction():
        result=read_current_budget_ref(conn,org_id='org-org',project_id='dev-project',ref=reference(record))
        assert result==record
    assert conn.execute('SELECT count(*) FROM aip_budget_receipt').fetchone()==(0,)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute('UPDATE aip_budget_revision SET lifecycle=lifecycle')


@pytest.mark.parametrize('failure',['authority','hash','head','revoked','suspended','expired','future','payload','column','canonical_hash','tenant','scope','canary','role'])
def test_budget_reference_rejects_stale_or_invalid_current_authority(budget_case,failure):
    from aos_api.aip_runtime_configuration_authority import read_current_budget_ref
    conn,record,_=budget_case
    ref=reference(record)
    if failure=='authority':ref['authority']='different.budget'
    elif failure=='hash':ref['hash']='sha256:'+'b'*64
    elif failure=='head':conn.execute('UPDATE aip_budget_head SET current_revision=2')
    elif failure=='tenant':ref['id']='another-tenant-budget'
    elif failure=='scope':conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    elif failure=='canary':conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    elif failure=='role':conn.execute('RESET ROLE')
    else:
        conn.execute('RESET ROLE');conn.execute('ALTER TABLE aip_budget_revision DISABLE TRIGGER trg_aip_budget_revision_append_only')
        if failure in {'revoked','suspended','expired','future'}:
            fields={name:getattr(record,name) for name in BudgetRevisionCreate.model_fields}
            now=datetime.now(timezone.utc)
            if failure in {'revoked','suspended'}:fields['lifecycle']=failure
            elif failure=='expired':fields.update(effective_from=now-timedelta(minutes=2),effective_until=now-timedelta(minutes=1))
            else:fields.update(effective_from=now+timedelta(minutes=1),effective_until=now+timedelta(minutes=2))
            replacement=materialize_revision(TenantScope('org-org','dev-project'),'test-author',
                BudgetRevisionCreate.model_validate(fields),created_at=record.created_at)
            updates=replacement.model_dump(mode='python');updates.pop('tenant')
            updates['payload']=Jsonb(replacement.model_dump(mode='json',by_alias=True))
            conn.execute(sql.SQL('UPDATE aip_budget_revision SET {}').format(sql.SQL(',').join(
                sql.SQL('{}=%s').format(sql.Identifier(name)) for name in updates)),tuple(updates.values()))
            ref=reference(replacement)
        elif failure=='payload':conn.execute("UPDATE aip_budget_revision SET payload=jsonb_set(payload,'{dailyLimitMinor}','99')")
        elif failure=='canonical_hash':
            digest='b'*64
            conn.execute("UPDATE aip_budget_revision SET content_hash=%s,payload=jsonb_set(payload,'{contentHash}',%s)",(digest,Jsonb(digest)))
            ref['hash']='sha256:'+digest
        else:conn.execute('UPDATE aip_budget_revision SET daily_limit_minor=99')
        conn.execute('SET ROLE aos_runtime')
    with pytest.raises((ValueError,PermissionError,LookupError)):
        with conn.transaction():read_current_budget_ref(conn,org_id='dev-org' if failure=='canary' else 'org-org',project_id='dev-project',ref=ref)


def test_budget_head_read_prevents_concurrent_authority_switch(budget_case):
    from aos_api.aip_runtime_configuration_authority import read_current_budget_ref
    conn,record,schema=budget_case
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as other:
        other.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        other.execute("SET lock_timeout='100ms'")
        with conn.transaction():
            read_current_budget_ref(conn,org_id='org-org',project_id='dev-project',ref=reference(record))
            with pytest.raises(psycopg.errors.LockNotAvailable):other.execute('UPDATE aip_budget_head SET current_revision=2')
        other.execute('UPDATE aip_budget_head SET current_revision=2')
        with pytest.raises(ValueError):
            with conn.transaction():read_current_budget_ref(conn,org_id='org-org',project_id='dev-project',ref=reference(record))
