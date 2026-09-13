import importlib.util
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import psycopg
from psycopg import sql
import pytest

from test_ui_read_api_role_pg import api_role,admission,queue,attempt_case,database,caller,pytestmark
from test_ui_read_worker_store_pg import claim,complete
from test_ui_read_request_pg import insert


@pytest.fixture
def host_role(api_role):
    owner,request,schema,login=api_role
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_033_runtime_ui_read_worker.py'
    spec=importlib.util.spec_from_file_location('ui_host_role',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=lambda q:owner.execute(q.replace('public.',schema+'.').replace('pg_catalog,public,pg_temp',f'pg_catalog,{schema},pg_temp')))
    migration.upgrade()
    owner.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
    owner.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(login)))
    return api_role


@contextmanager
def host(case,*,repeatable=True):
    _,_,schema,login=case
    with psycopg.connect(host='127.0.0.1',port=18432,user=login,dbname='postgres') as conn:
        if repeatable:conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true),set_config('aos.subject','reader',true)")
        yield conn


def test_runtime_can_lock_principal_claim_and_complete(host_role,queue):
    owner,*_=host_role;request_id=insert(queue)
    with host(host_role) as conn:
        assert conn.execute("SELECT extension_ui_read_host_principal_a0v_033('reader',ARRAY['public'])").fetchone()==('reader',)
        value=claim(conn,request_id)
    with host(host_role) as conn:assert complete(conn,value,result={})=='succeeded'
    assert owner.execute('SELECT state FROM extension_runtime_execution_attempt').fetchone()==('succeeded',)


@pytest.mark.parametrize('statement',[
    "UPDATE meta_membership SET role='admin' WHERE false",
    "UPDATE extension_runtime_ui_read_request SET subject='reader' WHERE false",
    'UPDATE extension_runtime_ui_read_request SET target_json=target_json WHERE false',
    'UPDATE extension_runtime_ui_read_request SET deadline=deadline WHERE false',
    'DELETE FROM extension_runtime_ui_read_request WHERE false',
    'INSERT INTO extension_runtime_ui_read_request SELECT * FROM extension_runtime_ui_read_request WHERE false',
])
def test_runtime_cannot_change_request_identity_or_membership(host_role,statement):
    with host(host_role) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute(statement)


def test_api_cannot_call_host_principal_and_host_requires_repeatable(host_role):
    with caller(host_role) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute("SELECT extension_ui_read_host_principal_a0v_033('reader',ARRAY[]::text[])")
    with host(host_role,repeatable=False) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute("SELECT extension_ui_read_host_principal_a0v_033('reader',ARRAY[]::text[])")


def test_current_member_lock_holds_without_member_update_privilege(host_role):
    owner,*_=host_role
    with host(host_role) as conn:
        conn.execute("SELECT extension_ui_read_host_principal_a0v_033('reader',ARRAY[]::text[])")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with owner.transaction():
                owner.execute("SET LOCAL lock_timeout='100ms'")
                owner.execute("DELETE FROM meta_membership WHERE subject='reader'")
    owner.execute("DELETE FROM meta_membership WHERE subject='reader'")
    with host(host_role) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute("SELECT extension_ui_read_host_principal_a0v_033('reader',ARRAY[]::text[])")
