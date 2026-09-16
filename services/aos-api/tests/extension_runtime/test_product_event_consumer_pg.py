"""Real control/occurrence storage; named source, runtime and group-lock doubles."""
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import pytest
from test_product_event_control_host_service import host_case,control_governed,governed,service_case,stored,pair,body,call,SCOPE
from aos_api.ecommerce_product_event_consumer import ProductEventConsumptionService
from aos_api.ecommerce_growth_host_ports import LockedEcommerceGrowthHostPort
from aos_api.ecommerce_product_event_control_approval import require_current_event_control_approval


@pytest.fixture
def consumer_case(host_case,monkeypatch):
    from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
    from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
    original_group = ProductEventAnalysisService._source_group
    def named_single_source(analysis, connection):
        # The old candidate fixture has no original claims. Composed native
        # tests install a real journal and must use the production locator.
        if type(analysis.source.reader._journal) is ControlledIngressJournal:
            return original_group(analysis, connection)
        return None
    monkeypatch.setattr(ProductEventAnalysisService, '_source_group', named_single_source)
    conn,control,tx,dispatch,command=host_case
    call(host_case)
    service=object.__new__(ProductEventConsumptionService)
    service.scope=SCOPE;service.actor='fixture-host';service.control=control
    service.guard=SimpleNamespace(run_policy_context=lambda **kw:kw['execute'](object()))
    now=datetime.now(timezone.utc).replace(microsecond=0)
    row=dict(event_key='c'*64,created_at=now,source_updated_at=now.isoformat(),outbox_id=1,input_revision=1)
    service.reader=SimpleNamespace(_journal=SimpleNamespace(_run_id='fixture-original'),
        run_candidates=lambda *args,**kw:kw['execute']((row,)))
    service.invoker=SimpleNamespace(installation_id=dispatch.installation_id,generation=dispatch.generation,
        read_current_in_transaction=lambda tx:{'fixtureInstalled':1})
    monkeypatch.setattr(LockedEcommerceGrowthHostPort,'_lock_and_revalidate',lambda *args:dispatch)
    result=dict(events=[dict(eventKey=row['event_key'],deadline=(now+timedelta(minutes=5)).isoformat())])
    return conn,service,command,result


def test_actual_current_enable_receipt_records_event_and_outbox(consumer_case):
    conn,service,command,result=consumer_case
    writes=service._phase(conn,command['policyRef']['resourceId'],lambda snap,request,binding:service._write(conn,binding,result))
    assert len(writes)==1
    assert conn.execute('SELECT count(*) AS n FROM automation_occurrence').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM automation_occurrence_outbox').fetchone()['n']==1


def test_stopped_binding_does_not_consume(consumer_case):
    conn,service,command,result=consumer_case
    conn.execute('UPDATE automation_schedule_binding SET enabled=false,revision=revision+1')
    with pytest.raises(PermissionError):service._phase(conn,command['policyRef']['resourceId'],lambda *a:pytest.fail('consumed'))
    assert conn.execute('SELECT count(*) AS n FROM automation_occurrence').fetchone()['n']==0


def test_withdrawn_approver_does_not_consume(consumer_case):
    conn,service,command,result=consumer_case
    conn.execute('RESET ROLE');conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'");conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(PermissionError):service._phase(conn,command['policyRef']['resourceId'],lambda *a:pytest.fail('consumed'))


def test_post_write_authority_failure_rolls_back_batch(consumer_case):
    conn,service,command,result=consumer_case
    def write_then_revoke(snapshot,request,binding):
        service._write(conn,binding,result)
        conn.execute('RESET ROLE');conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'");conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(PermissionError),conn.transaction():
        service._phase(conn,command['policyRef']['resourceId'],write_then_revoke)
    assert conn.execute('SELECT count(*) AS n FROM automation_occurrence').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM automation_occurrence_outbox').fetchone()['n']==0
