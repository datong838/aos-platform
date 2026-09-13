"""Disposable PG receipt transport; fixture binding is not an authorization."""
import os
from dataclasses import replace
from types import SimpleNamespace
import psycopg
from psycopg.rows import dict_row
import pytest
from test_automation_occurrences_pg import _seed
from test_product_event_control_contracts import payload
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_event_control_receipt import ProductEventControlReceiptStore
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def receipt_store():
    scope=TenantScope('org-org','dev-project')
    with psycopg.connect(os.environ['AOS_DATABASE_URL'],row_factory=dict_row) as conn:
        assert conn.execute('SELECT current_database() AS db').fetchone()['db'].endswith('_ti4_test')
        class FullSchemaSeed:
            def execute(self,query,params=()):
                if isinstance(query,str) and query.startswith('INSERT INTO bundle_installation('):
                    return conn.execute('''INSERT INTO bundle_installation(org_id,project_id,installation_pk,
                        installation_id,display_name,current_revision,etag_version,created_by)
                        VALUES(%s,%s,%s,%s,'control receipt fixture',1,1,'fixture')''',
                        (*params[:2],params[2],params[2]))
                return conn.execute(query,params)
        binding=replace(_seed(SimpleNamespace(owner=FullSchemaSeed(),schema='public'),scope),
                        cadence='event',weekly_day=None,local_time=None)
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
        conn.execute('SET LOCAL ROLE aos_runtime')
        tx=HostTransaction(conn)
        AutomationOccurrenceStore(TransactionBoundConnectFactory(tx,scope)).put_binding(scope,binding)
        command=payload();command['policyRef'].update(resourceId=binding.policy_id,contentHash=binding.policy_hash)
        yield conn,ProductEventControlReceiptStore(tx,scope),command
        conn.rollback()


def test_receipt_replay_and_conflicting_key(receipt_store):
    conn,store,command=receipt_store
    first=store.put(command,actor='fixture-operator')
    again=store.put(command,actor='fixture-operator')
    assert first['replayed'] is False and again['replayed'] is True
    assert first['receiptRef']==again['receiptRef']
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_product_event_control_receipt').fetchone()['n']==1
    command=dict(command,intent='disable',approvalRef=None)
    with pytest.raises(ValueError,match='conflict'):store.put(command,actor='fixture-operator')


def test_outer_failure_rolls_back_receipt(receipt_store):
    conn,store,command=receipt_store
    with pytest.raises(RuntimeError),conn.transaction():
        store.put(command,actor='fixture-operator')
        raise RuntimeError('owner rejected')
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_product_event_control_receipt').fetchone()['n']==0


def test_receipt_scope_and_immutability(receipt_store):
    conn,store,command=receipt_store;store.put(command,actor='fixture-operator')
    assert conn.execute("SELECT has_table_privilege(current_user,'ecommerce_product_event_control_receipt','DELETE') AS allowed").fetchone()['allowed'] is False
    with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
        conn.execute('DELETE FROM ecommerce_product_event_control_receipt')
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert conn.execute('SELECT count(*) AS n FROM ecommerce_product_event_control_receipt').fetchone()['n']==0
        with pytest.raises(ValueError,match='scope'):store.put(command,actor='fixture-operator')


def test_wrong_binding_revision_cannot_create_receipt(receipt_store):
    conn,store,command=receipt_store;command['expectedBindingRevision']=1
    with pytest.raises(ValueError,match='binding'):store.put(command,actor='fixture-operator')
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_product_event_control_receipt').fetchone()['n']==0


def test_old_enable_receipt_does_not_reenable_disabled_binding(receipt_store):
    conn,store,command=receipt_store
    first=store.put(command,actor='fixture-operator')
    conn.execute('UPDATE automation_schedule_binding SET enabled=false,revision=revision+1')
    replay=store.put(command,actor='fixture-operator')
    assert replay['replayed'] is True and replay['authority']==first['authority']
    assert conn.execute('SELECT enabled FROM automation_schedule_binding').fetchone()['enabled'] is False


def test_receipt_is_immutable_even_for_table_owner(receipt_store):
    conn,store,command=receipt_store;store.put(command,actor='fixture-operator')
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState),conn.transaction():
        conn.execute('RESET ROLE')
        conn.execute("UPDATE ecommerce_product_event_control_receipt SET actor='different'")


def test_migration_empty_roundtrip_and_nonempty_retention(receipt_store):
    import importlib.util
    from pathlib import Path
    conn,store,command=receipt_store
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_042_product_event_control_receipt.py'
    spec=importlib.util.spec_from_file_location('event_control_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=conn.execute)
    with conn.transaction():
        conn.execute('RESET ROLE')
        migration.downgrade();migration.upgrade()
        conn.execute('SET LOCAL ROLE aos_runtime')
    store.put(command,actor='fixture-operator')
    with pytest.raises(psycopg.errors.RaiseException,match='retain'),conn.transaction():
        conn.execute('RESET ROLE')
        migration.downgrade()
