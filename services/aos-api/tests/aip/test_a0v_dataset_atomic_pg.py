import os
import pytest
import psycopg
from test_aip_budget_reservation_pg import database, runtime_connection
from aos_api import data_os_store as store
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PG opt-in')


def test_dataset_history_failure_rolls_back_and_retry_recovers(database, monkeypatch):
    database.owner.execute('CREATE TABLE meta_dataset (LIKE public.meta_dataset INCLUDING ALL)')
    database.owner.execute('CREATE TABLE meta_dataset_history (LIKE public.meta_dataset_history INCLUDING ALL)')
    # Never use the copied default's public sequence.
    database.owner.execute('CREATE SEQUENCE local_history_id')
    database.owner.execute("ALTER TABLE meta_dataset_history ALTER COLUMN id SET DEFAULT nextval('local_history_id')")
    database.owner.execute('GRANT USAGE ON SEQUENCE local_history_id TO aos_runtime')
    for table in ('meta_dataset', 'meta_dataset_history'):
        database.owner.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO aos_runtime')
        database.owner.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        database.owner.execute(f"CREATE POLICY scope ON {table} TO aos_runtime USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
    database.owner.execute("ALTER TABLE meta_dataset_history ADD CONSTRAINT test_reject CHECK (payload->>'status' <> 'REJECT')")
    monkeypatch.setattr(store, 'connect', runtime_connection(database))
    monkeypatch.setattr(store, 'ensure_data_os_schema', lambda: None)
    scope = TenantScope('org-org', 'dev-project')
    item = {'rid': 'atomic-test', 'name': 'old'}
    store.persist_dataset(scope, item, history_entries=[{'status': 'OLD'}])
    with pytest.raises(psycopg.errors.CheckViolation):
        store.persist_dataset(scope, dict(item, name='new'), history_entries=[{'status': 'REJECT'}])
    assert database.owner.execute('SELECT name FROM meta_dataset').fetchone()['name'] == 'old'
    assert database.owner.execute('SELECT payload FROM meta_dataset_history').fetchone()['payload'] == {'status': 'OLD'}
    store.persist_dataset(scope, dict(item, name='new'), history_entries=[{'status': 'NEW'}])
    assert database.owner.execute('SELECT name FROM meta_dataset').fetchone()['name'] == 'new'
    assert database.owner.execute('SELECT payload FROM meta_dataset_history').fetchone()['payload'] == {'status': 'NEW'}
