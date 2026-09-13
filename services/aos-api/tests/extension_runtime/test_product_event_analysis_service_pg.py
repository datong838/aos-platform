"""Real claim/control storage; source and installed runtime remain explicit doubles."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from test_product_event_consumer_pg import consumer_case,host_case,control_governed,governed,service_case,stored,pair
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory,_strict_analysis_start_command
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService


@pytest.fixture
def body():
    from test_product_event_schedule import body as template, seal
    value=template.__wrapped__()
    now=datetime.now(UTC).replace(microsecond=0)
    value.update(effectiveFrom=(now-timedelta(minutes=1)).isoformat(),
                 effectiveUntil=(now+timedelta(minutes=30)).isoformat())
    return seal(value)


@pytest.fixture
def analysis_case(consumer_case):
    conn,source,control_command,result=consumer_case
    source._phase(conn,control_command['policyRef']['resourceId'],lambda snap,request,binding:source._write(conn,binding,result))
    original=source.reader.run_candidates
    source.reader.run_event=lambda *args,**kw:original(*args,execute=lambda rows:kw['execute'](rows[0]))
    factory=TransactionBoundConnectFactory(HostTransaction(conn),source.scope)
    claimed=AutomationOccurrenceStore(factory).claim_next(source.scope,owner='fixture-analysis',
             now=datetime.now(UTC).replace(microsecond=0)+timedelta(seconds=1))
    assert claimed is not None, conn.execute('SELECT effective_from,effective_until,enabled,approved FROM automation_schedule_binding').fetchall()
    service=object.__new__(ProductEventAnalysisService)
    service.scope=source.scope;service.source=source;service.invoker=source.invoker
    return conn,service,claimed


def test_current_original_event_prepares_exact_analysis_command(analysis_case):
    conn,service,claimed=analysis_case
    snapshot,request=service._phase(conn,claimed,lambda snap,request,dispatch:(snap,request))
    assert request['idempotencyKey']==claimed.target_idempotency_key
    assert request['occurrenceRef']['resourceId']==str(claimed.occurrence_id)
    assert snapshot['source']['events'][0]['event_key']=='c'*64
    from test_product_event_analysis_port import command
    _strict_analysis_start_command(command(request))
    assert conn.execute("SELECT status FROM automation_occurrence").fetchone()['status']=='claimed'


def test_withdrawn_current_control_blocks_analysis_preparation(analysis_case):
    conn,service,claimed=analysis_case
    conn.execute('RESET ROLE')
    conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(PermissionError):
        service._phase(conn,claimed,lambda *args:pytest.fail('revoked control reached analysis'))


@pytest.mark.parametrize('fault',['run','actor'])
def test_analysis_cannot_substitute_another_original_batch(analysis_case,fault):
    conn,service,claimed=analysis_case
    if fault=='run':service.source.reader._journal._run_id='another-run'
    else:service.source.actor='another-actor'
    with pytest.raises(ValueError,match='original event batch'):
        service._phase(conn,claimed,lambda *args:pytest.fail('different batch admitted'))
