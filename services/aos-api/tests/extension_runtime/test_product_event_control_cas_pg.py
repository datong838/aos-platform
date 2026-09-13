"""CAS transport tests only. All authorities are isolated test fixtures."""
from dataclasses import replace
import pytest
from test_product_event_control_receipt_pg import receipt_store
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_event_control_store import ProductEventBindingControlStore
from aos_api.tenant_scope import TenantScope


def test_disable_then_original_enable_replay_stays_disabled(receipt_store):
    conn,receipts,original=receipt_store
    receipts.put(original,actor='fixture-operator')
    store=ProductEventBindingControlStore(HostTransaction(conn),TenantScope('org-org','dev-project'))
    disable=dict(original,intent='disable',approvalRef=None,idempotencyKey='stop',expectedBindingRevision=1)
    stopped=store.apply(disable,actor='fixture-operator')
    assert stopped['authority']['binding']['enabled'] is False
    replay=store.apply(original,actor='fixture-operator')
    assert replay['replayed'] is True
    assert conn.execute('SELECT enabled,revision FROM automation_schedule_binding').fetchone()=={'enabled':False,'revision':2}
    with pytest.raises(ValueError,match='revision'):
        store.apply(dict(disable,idempotencyKey='stale-stop'),actor='fixture-operator')


def test_receipt_failure_rolls_back_binding_change(receipt_store,monkeypatch):
    from aos_api.ecommerce_product_event_control_receipt import ProductEventControlReceiptStore
    conn,_,original=receipt_store
    store=ProductEventBindingControlStore(HostTransaction(conn),TenantScope('org-org','dev-project'))
    def reject(*args,**kw):raise RuntimeError('receipt failed')
    monkeypatch.setattr(ProductEventControlReceiptStore,'put',reject)
    with pytest.raises(RuntimeError),conn.transaction():
        store.apply(dict(original,intent='disable',approvalRef=None,expectedBindingRevision=1),actor='fixture-operator')
    assert conn.execute('SELECT enabled,revision FROM automation_schedule_binding').fetchone()=={'enabled':True,'revision':1}


def test_cross_scope_does_not_change_binding(receipt_store):
    conn,_,original=receipt_store
    store=ProductEventBindingControlStore(HostTransaction(conn),TenantScope('dev-org','dev-project'))
    with pytest.raises(ValueError,match='scope'):
        store.apply(dict(original,intent='disable',approvalRef=None,expectedBindingRevision=1),actor='fixture-operator')
    assert conn.execute('SELECT revision FROM automation_schedule_binding').fetchone()['revision']==1


def current_binding(conn):
    from dataclasses import fields
    from aos_api.automation_occurrence_store import ScheduleBinding
    row=conn.execute('SELECT * FROM automation_schedule_binding').fetchone()
    return ScheduleBinding(**{field.name:row[field.name] for field in fields(ScheduleBinding)})


def test_fresh_enable_after_disable_requires_new_version_and_key(receipt_store):
    conn,_,original=receipt_store;binding=current_binding(conn)
    store=ProductEventBindingControlStore(HostTransaction(conn),TenantScope('org-org','dev-project'))
    store.apply(dict(original,intent='disable',approvalRef=None,expectedBindingRevision=1,idempotencyKey='stop'),actor='fixture')
    result=store.apply(dict(original,expectedBindingRevision=2,idempotencyKey='restart'),actor='fixture',binding=binding)
    assert result['authority']['binding']['revision']==3
    assert result['authority']['binding']['enabled'] is True


def test_initial_binding_and_receipt_are_same_transaction(receipt_store):
    conn,_,original=receipt_store;binding=current_binding(conn)
    conn.execute('RESET ROLE');conn.execute('DELETE FROM automation_schedule_binding');conn.execute('SET LOCAL ROLE aos_runtime')
    store=ProductEventBindingControlStore(HostTransaction(conn),TenantScope('org-org','dev-project'))
    result=store.apply(original,actor='fixture',binding=binding)
    assert result['authority']['binding']['revision']==1
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_product_event_control_receipt').fetchone()['n']==1


def test_current_dispatch_drift_prevents_enable(receipt_store):
    conn,_,original=receipt_store;binding=current_binding(conn)
    conn.execute('RESET ROLE')
    conn.execute('UPDATE extension_operation_dispatch_binding SET execution_epoch=execution_epoch+1')
    conn.execute('SET LOCAL ROLE aos_runtime')
    store=ProductEventBindingControlStore(HostTransaction(conn),TenantScope('org-org','dev-project'))
    with pytest.raises(ValueError,match='dispatch'):
        store.apply(dict(original,expectedBindingRevision=1),actor='fixture',binding=binding)
    assert conn.execute('SELECT revision FROM automation_schedule_binding').fetchone()['revision']==1
