"""Real origin rows and occurrence; source/installation remain named fixture doubles."""
import pytest
import psycopg
from test_product_event_consumer_pg import consumer_case,host_case,control_governed,governed,service_case,stored,pair,body
from aos_api.ecommerce_growth_host_ports import HostTransaction


def test_origin_is_atomic_immutable_and_preserves_first_run(consumer_case):
    from aos_api.ecommerce_product_event_origin import ProductEventOriginStore
    conn,source,command,result=consumer_case
    def write():
        return source._phase(conn,command['policyRef']['resourceId'],lambda snap,request,binding:source._write(conn,binding,result))
    writes=write();origin=ProductEventOriginStore(HostTransaction(conn),source.scope)
    first=origin.read(writes[0].occurrence_id)
    assert first['runId']=='fixture-original' and first['actor']=='fixture-host'
    source.reader._journal._run_id='later-batch'
    write()
    assert origin.read(writes[0].occurrence_id)==first
    conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
    assert conn.execute('SELECT * FROM ecommerce_product_event_origin').fetchall()==[]
    conn.execute("SELECT set_config('aos.org_id','org-org',true)")
    assert origin.read(writes[0].occurrence_id)==first
    for query in ['UPDATE ecommerce_product_event_origin SET run_id=run_id',
                  'DELETE FROM ecommerce_product_event_origin','TRUNCATE ecommerce_product_event_origin']:
        with pytest.raises(psycopg.Error),conn.transaction():conn.execute(query)
    assert origin.read(writes[0].occurrence_id)==first


def test_origin_failure_rolls_back_occurrence_and_outbox(consumer_case,monkeypatch):
    from aos_api.ecommerce_product_event_origin import ProductEventOriginStore
    conn,source,command,result=consumer_case
    monkeypatch.setattr(ProductEventOriginStore,'put',lambda *args,**kw:(_ for _ in ()).throw(ValueError('origin failure')))
    with pytest.raises(ValueError),conn.transaction():
        source._phase(conn,command['policyRef']['resourceId'],lambda snap,request,binding:source._write(conn,binding,result))
    assert conn.execute('SELECT count(*) AS n FROM automation_occurrence').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM automation_occurrence_outbox').fetchone()['n']==0


def test_origin_scope_isolation_and_missing_origin_are_fail_closed(consumer_case):
    from aos_api.ecommerce_product_event_origin import ProductEventOriginStore
    from aos_api.automation_occurrence_store import AutomationOccurrenceStore
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from aos_api.tenant_scope import TenantScope
    from datetime import datetime
    conn,source,command,result=consumer_case
    origin=ProductEventOriginStore(HostTransaction(conn),source.scope)
    def old_writer(snapshot,request,binding):
        return AutomationOccurrenceStore(TransactionBoundConnectFactory(HostTransaction(conn),source.scope)).record_event_batch(
            source.scope,binding,events=[(item['eventKey'],datetime.fromisoformat(item['deadline'])) for item in result['events']])
    writes=source._phase(conn,command['policyRef']['resourceId'],old_writer)
    with pytest.raises(ValueError,match='no original'):
        origin.put(writes[0].occurrence_id,event_key=result['events'][0]['eventKey'],run_id='unknown',actor='fixture-host',replayed=True)
    assert origin.read(writes[0].occurrence_id) is None
    with pytest.raises(PermissionError):
        ProductEventOriginStore(HostTransaction(conn),TenantScope('dev-org','dev-project')).read(writes[0].occurrence_id)
