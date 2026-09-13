import importlib.util
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from test_ui_read_store_pg import admission, queue, attempt_case, database, SCOPE, pytestmark
from aos_api.asset_registry.canonical_json import canonical_sha256


@pytest.fixture
def api_role(admission):
    owner,request=admission
    schema=owner.execute('SELECT current_schema()').fetchone()[0]
    owner.execute('CREATE TABLE authz_tuple(org_id text,project_id text,user_key text,relation text,object_key text)')
    owner.execute("INSERT INTO authz_tuple VALUES('org-org','dev-project','user:reader','bearer','marking:public')")
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_032_runtime_ui_read_admission.py'
    spec=importlib.util.spec_from_file_location('ui_api_role',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=lambda q:owner.execute(q.replace('public.',schema+'.').replace('pg_catalog,public,pg_temp',f'pg_catalog,{schema},pg_temp')))
    migration.upgrade()
    login='ui_read_'+uuid4().hex
    owner.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(login)))
    owner.execute(sql.SQL('GRANT aos_ui_read_api TO {}').format(sql.Identifier(login)))
    owner.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_ui_read_api').format(sql.Identifier(schema)))
    try:yield owner,request,schema,login
    finally:owner.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(login)))


@contextmanager
def caller(case,*,subject='reader',org='org-org',privileged=False,repeatable=False):
    _,_,schema,login=case
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres' if privileged else login,dbname='postgres') as conn:
        if repeatable:conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        conn.execute('SET LOCAL ROLE aos_ui_read_api')
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id','dev-project',true),set_config('aos.subject',%s,true)",(org,subject))
        yield conn


def submit(conn,request,key='key'):
    return conn.execute('SELECT extension_ui_read_enqueue_a0v_032(%s,%s,%s)',('reader',key,Jsonb(request.model_dump(mode='json')))).fetchone()[0]


def test_restricted_role_enqueues_and_replays_with_canonical_digest(api_role):
    _,request,*_=api_role
    with caller(api_role) as conn:
        first=submit(conn,request)
        assert submit(conn,request)==first
        assert first['requestHash']==canonical_sha256(dict(tenant=dict(orgId=SCOPE.org_id,projectId=SCOPE.project_id),subject='reader',request=request.model_dump(mode='json')))
    assert api_role[0].execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone()==(1,)


@pytest.mark.parametrize('statement',[
    'SELECT * FROM meta_membership FOR SHARE',
    "UPDATE meta_membership SET role='admin' WHERE false",
    'SELECT * FROM extension_runtime_execution_attempt',
    'UPDATE extension_runtime_ui_read_request SET state=state WHERE false',
    'DELETE FROM extension_runtime_ui_read_request WHERE false',
    'SELECT * FROM extension_runtime_ui_read_request',
])
def test_delivery_role_has_no_direct_authority_access(api_role,statement):
    with caller(api_role) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute(statement)


@pytest.mark.parametrize('kind',['subject','canary','superuser','repeatable'])
def test_wrong_identity_or_transaction_rejected(api_role,kind):
    kwargs={}
    if kind=='subject':kwargs['subject']='other'
    if kind=='canary':kwargs['org']='dev-org'
    if kind=='superuser':kwargs['privileged']=True
    if kind=='repeatable':kwargs['repeatable']=True
    with caller(api_role,**kwargs) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):submit(conn,api_role[1])


def test_principal_marking_lock_blocks_revocation_without_update_grant(api_role):
    owner,*_=api_role
    with caller(api_role) as conn:
        assert conn.execute("SELECT extension_ui_read_principal_a0v_032('reader',ARRAY['public'])").fetchone()==('reader',)
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with owner.transaction():
                owner.execute("SET LOCAL lock_timeout='100ms'")
                owner.execute('DELETE FROM authz_tuple')
    owner.execute('DELETE FROM authz_tuple')
    with caller(api_role) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute("SELECT extension_ui_read_principal_a0v_032('reader',ARRAY['public'])")


def test_fixed_function_rejects_arbitrary_payload_and_key_conflict(api_role):
    _,request,*_=api_role
    with caller(api_role) as conn:submit(conn,request)
    with caller(api_role) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):submit(conn,request.model_copy(update={'caseLimit':10}))
    with caller(api_role) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute('SELECT extension_ui_read_enqueue_a0v_032(%s,%s,%s)',('reader','extra',Jsonb(request.model_dump(mode='json')|{'sql':'SELECT secret'})))


def test_fixed_function_enforces_pending_capacity(api_role):
    _,request,*_=api_role
    with caller(api_role) as conn:
        for i in range(8):submit(conn,request,key=str(i))
    with caller(api_role) as conn:
        with pytest.raises(psycopg.errors.CheckViolation,match='capacity'):submit(conn,request,key='overflow')
    with caller(api_role) as conn:assert submit(conn,request,key='0')['state']=='requested'


def test_revoked_member_cannot_replay_fixed_function(api_role):
    owner,request,*_=api_role
    with caller(api_role) as conn:submit(conn,request)
    owner.execute("DELETE FROM meta_membership WHERE subject='reader'")
    with caller(api_role) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='membership'):submit(conn,request)
