import os
import pytest
import psycopg
from psycopg import sql
from test_lifecycle_pg import database
from aos_api.extension_runtime.ui_current_principal import read_current_ui_principal
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PG opt-in')


def test_current_ui_membership_is_locked_until_transaction_finishes(database, monkeypatch):
    conn, _, schema = database
    monkeypatch.delenv('AOS_OPENFGA_API_URL', raising=False)
    conn.execute('CREATE TABLE meta_membership(org_id text,project_id text,subject text,role text)')
    conn.execute('CREATE TABLE authz_tuple(org_id text,project_id text,user_key text,relation text,object_key text)')
    conn.execute("INSERT INTO meta_membership VALUES('org-org','dev-project','reader','operator')")
    conn.execute("INSERT INTO authz_tuple VALUES('org-org','dev-project','user:reader','bearer','marking:public')")
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as other:
        other.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        other.execute("SET lock_timeout='100ms'")
        with conn.transaction():
            conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
            current=read_current_ui_principal(conn=conn,scope=TenantScope('org-org','dev-project'),subject='reader',required_markings=('public',))
            assert current.roles == ('operator',)
            for table in ('meta_membership','authz_tuple'):
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    other.execute(sql.SQL('DELETE FROM {}').format(sql.Identifier(table)))
        other.execute('DELETE FROM meta_membership')
        with conn.transaction():
            conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
            with pytest.raises(RuntimeConflict):
                read_current_ui_principal(conn=conn,scope=TenantScope('org-org','dev-project'),subject='reader',required_markings=('public',))
