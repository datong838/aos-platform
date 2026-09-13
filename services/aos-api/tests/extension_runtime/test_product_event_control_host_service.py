"""Real isolated storage/approval composition; source qualification is a named double."""
from types import SimpleNamespace
from datetime import datetime,timezone
import pytest
from test_product_event_control_approval_pg import control_governed,governed,service_case,stored,pair,body
from test_automation_occurrences_pg import _seed
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_event_control_qualified_owner import ProductEventControlQualifiedOwner
from aos_api.ecommerce_product_event_control_host_service import ProductEventControlHostService
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project')


@pytest.fixture
def host_case(control_governed,stored,monkeypatch):
    from aos_api.ecommerce_product_event_store import ProductEventPolicyStore
    from test_product_event_store_pg import write
    conn,command,_=control_governed
    write(ProductEventPolicyStore(HostTransaction(conn),SCOPE),stored[1])
    conn.execute('RESET ROLE')
    class Seed:
        def execute(self,query,params=()):
            if isinstance(query,str) and query.startswith('INSERT INTO bundle_installation('):
                return conn.execute('''INSERT INTO bundle_installation(org_id,project_id,installation_pk,
                    installation_id,display_name,current_revision,etag_version,created_by)
                    VALUES(%s,%s,%s,%s,'control Host fixture',1,1,'fixture')''',(*params[:2],params[2],params[2]))
            return conn.execute(query,params)
    runtime=_seed(SimpleNamespace(owner=Seed(),schema='public'),SCOPE)
    for operation in ['ecommerce_growth_event_control','ecommerce_growth_analysis_advance']:
        conn.execute('''INSERT INTO extension_operation_dispatch_binding
            SELECT (jsonb_populate_record(NULL::extension_operation_dispatch_binding,
                to_jsonb(d)||jsonb_build_object('operation_id',%s::text))).*
            FROM extension_operation_dispatch_binding d WHERE operation_id='ecommerce_growth_schedule_trigger' ''',(operation,))
    group=conn.execute("SELECT cutover_group_id,cutover_group_revision FROM extension_operation_dispatch_binding WHERE operation_id='ecommerce_growth_event_control'").fetchone()
    conn.execute('SET LOCAL ROLE aos_runtime')
    dispatch=SimpleNamespace(operation_id='ecommerce_growth_event_control',installation_id=runtime.installation_id,
        generation=runtime.generation,execution_epoch=runtime.execution_epoch,**group)
    monkeypatch.setattr(ProductEventControlQualifiedOwner,'run_without_source',lambda self,*a,**kw:kw['execute']())
    service=ProductEventControlHostService(object.__new__(ProductEventControlQualifiedOwner),actor='fixture-host')
    return conn,service,HostTransaction(conn),dispatch,command


def call(data,command=None):
    conn,service,transaction,dispatch,original=data
    return service.execute(transaction=transaction,scope=SCOPE,dispatch_ref=dispatch,
        command=original if command is None else command,checked_at=datetime.now(timezone.utc),occurred_at=None)


def test_control_host_enable_and_disable(host_case):
    conn,service,transaction,dispatch,command=host_case
    result=call(host_case)
    assert result['authority']['binding']['operation_id']=='ecommerce_growth_analysis_advance'
    assert result['authority']['binding']['enabled'] is True
    from ecommerce_growth.ecommerce_product_event_control import verify_event_control_receipt
    from types import SimpleNamespace
    assert verify_event_control_receipt(result,command=command,dispatch_ref=SimpleNamespace(
        org_id=SCOPE.org_id,project_id=SCOPE.project_id))==result
    assert service.verify_receipt(transaction=transaction,scope=SCOPE,dispatch=dispatch,command=command,receipt=result)==result
    stop=dict(command,intent='disable',approvalRef=None,idempotencyKey='stop',expectedBindingRevision=1)
    assert call(host_case,stop)['authority']['binding']['enabled'] is False
    assert call(host_case)['replayed'] is True
    assert conn.execute('SELECT enabled FROM automation_schedule_binding').fetchone()['enabled'] is False


def test_control_host_rejects_analysis_target_drift(host_case):
    conn,_,_,_,_=host_case
    conn.execute('RESET ROLE')
    conn.execute("UPDATE extension_operation_dispatch_binding SET operation_fence=true WHERE operation_id='ecommerce_growth_analysis_advance'")
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(ValueError,match='target'):call(host_case)
    assert conn.execute('SELECT count(*) AS n FROM automation_schedule_binding').fetchone()['n']==0


def test_stop_checks_current_controller(host_case):
    conn,_,_,_,command=host_case;call(host_case)
    conn.execute('RESET ROLE');conn.execute("UPDATE meta_membership SET role='viewer' WHERE subject='fixture-host'");conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(PermissionError):call(host_case,dict(command,intent='disable',approvalRef=None,idempotencyKey='stop',expectedBindingRevision=1))
    assert conn.execute('SELECT enabled FROM automation_schedule_binding').fetchone()['enabled'] is True


def test_approval_revocation_after_write_rolls_back_everything(host_case,monkeypatch):
    from aos_api.ecommerce_product_event_control_receipt import ProductEventControlReceiptStore
    conn,_,_,_,_=host_case
    original=ProductEventControlReceiptStore.put
    def revoke(self,*args,**kwargs):
        result=original(self,*args,**kwargs)
        conn.execute('RESET ROLE');conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'");conn.execute('SET LOCAL ROLE aos_runtime')
        return result
    monkeypatch.setattr(ProductEventControlReceiptStore,'put',revoke)
    with pytest.raises(PermissionError),conn.transaction():call(host_case)
    assert conn.execute('SELECT count(*) AS n FROM automation_schedule_binding').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_product_event_control_receipt').fetchone()['n']==0


def test_stopping_does_not_reopen_failed_source(host_case,monkeypatch):
    from aos_api.ecommerce_product_event_guard import ProductEventPolicyGuard
    _,_,_,_,command=host_case;call(host_case)
    monkeypatch.setattr(ProductEventPolicyGuard,'run_policy',lambda *a,**kw:pytest.fail('stop reopened source'))
    result=call(host_case,dict(command,intent='disable',approvalRef=None,idempotencyKey='stop',expectedBindingRevision=1))
    assert result['authority']['binding']['enabled'] is False


def test_event_authority_keeps_null_schedule_time(host_case):
    from datetime import timedelta
    from aos_api.automation_occurrence_store import AutomationOccurrenceStore
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory,_occurrence_payload
    from test_product_event_control_cas_pg import current_binding
    conn,_,transaction,_,_=host_case;call(host_case)
    store=AutomationOccurrenceStore(TransactionBoundConnectFactory(transaction,SCOPE))
    event=store.record_event(SCOPE,current_binding(conn),source_event_id='source-null-time',
        deadline=(datetime.now(timezone.utc)+timedelta(hours=1)).replace(microsecond=0))
    authority=_occurrence_payload(transaction,SCOPE,event.occurrence_id)
    assert authority['scheduledAt'] is None and authority['triggerSource']=='event'
    assert authority['sourceEventId']=='source-null-time'
