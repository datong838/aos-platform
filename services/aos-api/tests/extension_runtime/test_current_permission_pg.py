import os
from types import SimpleNamespace

import pytest
import psycopg
from psycopg import sql

from test_lifecycle_pg import database

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG opt-in')


@pytest.mark.parametrize('case', ['allowed','revoked','viewer','owner','no_marking','wrong_tenant','no_scope','remote','revoke_locked'])
def test_current_permission_reads_persisted_exact_tenant(database,monkeypatch,case):
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.asset_registry.control_policy import VERIFY_INSTALLATION_OPERATION
    from aos_api.asset_registry.errors import AssetRegistryError
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    conn,_,schema=database
    conn.execute('CREATE TABLE meta_membership(org_id text,project_id text,subject text,role text)')
    conn.execute('CREATE TABLE authz_tuple(org_id text,project_id text,user_key text,relation text,object_key text)')
    role=case if case in {'viewer','owner'} else 'admin'
    conn.execute("INSERT INTO meta_membership VALUES('org-org','dev-project','tester',%s)",(role,))
    if case!='no_marking':
        conn.execute("INSERT INTO authz_tuple VALUES('org-org','dev-project','user:tester','bearer','marking:public')")
    if case=='revoked':conn.execute('DELETE FROM meta_membership')
    locked=SimpleNamespace(org_id='org-org',project_id='dev-project')
    lock=SimpleNamespace(payload=SimpleNamespace(permission_diff=SimpleNamespace(target=SimpleNamespace(markings=['public']))))
    monkeypatch.setattr('aos_api.extension_runtime.current_permission._load_current_lock',lambda *a,**kw:lock)
    monkeypatch.delenv('AOS_OPENFGA_API_URL',raising=False)
    if case=='remote':monkeypatch.setenv('AOS_OPENFGA_API_URL','http://not-contacted.invalid')
    with conn.transaction():
        if case!='no_scope':
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id','dev-project',true)",
                         ('dev-org' if case=='wrong_tenant' else 'org-org',))
        reader=CurrentControlPermission(operation=VERIFY_INSTALLATION_OPERATION)
        if case in {'allowed','revoke_locked'}:
            assert reader(conn=conn,locked=locked,actor='tester') is True
            if case=='revoke_locked':
                with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as other:
                    other.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
                    other.execute("SET lock_timeout='100ms'")
                    for table in ('meta_membership','authz_tuple'):
                        with pytest.raises(psycopg.errors.LockNotAvailable):
                            other.execute(sql.SQL('DELETE FROM {}').format(sql.Identifier(table)))
        else:
            with pytest.raises((AssetRegistryError,RuntimeConflict)):
                reader(conn=conn,locked=locked,actor='tester')
