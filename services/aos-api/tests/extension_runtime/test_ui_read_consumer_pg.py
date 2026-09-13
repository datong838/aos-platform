import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus
import pytest

from test_host_analyst_snapshot_pg import host_snapshot,host_role,api_role,admission,queue,attempt_case,database,snapshot,projector,SCOPE,TABLES,pytestmark
from test_ui_read_api_role_pg import caller,submit
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.extension_runtime.preparation_worker import PreparedJob
from aos_api.extension_runtime.ui_read_consumer import RuntimeUiReadConsumer,PreparedUiRead,UiReadConsumerResult,UiReadInvocation
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


@pytest.fixture
def consumer_case(host_snapshot,projector,monkeypatch):
    role_case,_=host_snapshot
    owner,request,schema,login=role_case
    for table in TABLES:
        owner.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        owner.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        owner.execute(sql.SQL("CREATE POLICY tenant_scope ON {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier(table)))
    connections=[];calls=[];mode={'result':'valid'}
    class ScopedConnection(psycopg.Connection):
        def execute(self,query,params=None,**kwargs):
            if isinstance(query,str):query=query.replace('public.extension_ui_read_',schema+'.extension_ui_read_')
            return super().execute(query,params,**kwargs)
    @contextmanager
    def connect():
        with ScopedConnection.connect(host='127.0.0.1',port=18432,user=login,dbname='postgres',autocommit=True,row_factory=dict_row) as conn:
            conn.execute('SET ROLE aos_runtime')
            conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            connections.append(conn)
            yield conn
    target=request.target
    entry=SimpleNamespace(installationId=target.installationId,installationRevision=target.installationRevision,
        generation=target.generation,executionEpoch=target.executionEpoch,bindingRevision=target.bindingRevision,
        module=SimpleNamespace(module_id=request.moduleId,route=target.route,permissions=SimpleNamespace(roles=('reader',),markings=('public',),data_scopes=('ecommerce.workshop.read',))),
        moduleRef=SimpleNamespace(bundleId='solution.ecommerce.growth',bundleContentHash=target.resourceHash),
        ui=SimpleNamespace(initialRoute=target.route,resourceHash=target.resourceHash,routeClaims=(target.route,),
                           readOperationClaims=(request.operationId,),commandOperationClaims=()))
    catalog=RuntimeWorkshopCatalog(source=None,loader=None,view_reader=None)
    monkeypatch.setattr(catalog,'list_modules',lambda **_:SimpleNamespace(tenant=SimpleNamespace(orgId=SCOPE.org_id,projectId=SCOPE.project_id),count=1,items=[entry]))
    store=object.__new__(PostgresInstallationStore)
    # Installed-baseline/hash verification has separate invoker tests. Here the
    # transaction/role/source/Attempt path is real PG, and package execution is a
    # protocol substitute invoking the actual pure package projector.
    monkeypatch.setattr(CurrentInstalledPackageInvoker,'read_current_in_transaction',lambda *a,**k:{'package':{'contentHash':target.resourceHash}})
    job=object.__new__(PreparedJob);job._tenant_scope=SCOPE
    job.plan=SimpleNamespace(installation_id=target.installationId,generation=target.generation)
    async def invoke_selected_once(**kwargs):
        assert not any(not c.closed and c.info.transaction_status==TransactionStatus.INTRANS for c in connections)
        assert kwargs['operation']=='analyst_workspace_view_v1'
        calls.append(kwargs)
        if mode['result']=='unknown':raise TimeoutError('protocol response unavailable')
        result=projector(kwargs['payload']['snapshot'])
        if mode['result']=='foreign':result['tenant']={'orgId':'dev-org','projectId':'dev-project'}
        return result
    job.invoke_selected_once=invoke_selected_once
    directory=LivePreparedJobDirectory();directory.register(job)
    consumer=RuntimeUiReadConsumer(scope=SCOPE,connect=connect,catalog=catalog,installation_store=store,
                                   live_directory=directory,markings=('public',))
    with caller(role_case) as conn:delivery=submit(conn,request)
    return consumer,owner,entry,calls,mode,delivery


def prepare(case):return case[0].prepare_once(org_id=SCOPE.org_id,project_id=SCOPE.project_id)


def test_consumer_once_through_real_role_snapshot_attempt_and_result(consumer_case):
    consumer,owner,_,calls,_,_=consumer_case
    prepared=prepare(consumer_case);assert type(prepared) is PreparedUiRead
    invocation=asyncio.run(consumer.invoke_prepared(prepared))
    assert invocation.result['caseCount']==1 and invocation.result['runCount']==1
    with pytest.raises(RuntimeConflict):asyncio.run(consumer.invoke_prepared(prepared))
    assert consumer.finish_prepared(prepared,invocation).state=='succeeded'
    assert prepare(consumer_case) is None
    with pytest.raises(RuntimeConflict):asyncio.run(consumer.invoke_prepared(prepared))
    assert len(calls)==1
    assert owner.execute('SELECT state FROM extension_runtime_execution_attempt').fetchone()==('succeeded',)


@pytest.mark.parametrize('failure',['claim','package-hash'])
def test_gate_rejection_has_no_attempt_or_invocation(consumer_case,failure):
    _,owner,entry,calls,*_=consumer_case
    if failure=='claim':entry.ui.readOperationClaims=()
    else:entry.moduleRef.bundleContentHash='sha256:'+'b'*64
    result=prepare(consumer_case)
    assert type(result) is UiReadConsumerResult and result.state=='denied'
    assert calls==[] and owner.execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone()==(0,)


@pytest.mark.parametrize('failure',['revoked','foreign','unknown','snapshot'])
def test_result_is_not_delivered_after_failure(consumer_case,failure):
    consumer,owner,_,calls,mode,_=consumer_case
    prepared=prepare(consumer_case)
    if failure in ('foreign','unknown'):mode['result']=failure
    if failure=='snapshot':prepared.snapshot['truncated']=not prepared.snapshot['truncated']
    invocation=asyncio.run(consumer.invoke_prepared(prepared))
    if failure=='revoked':owner.execute("DELETE FROM meta_membership WHERE subject='reader'")
    result=consumer.finish_prepared(prepared,invocation)
    assert result.state=='failed'
    assert owner.execute('SELECT result_json FROM extension_runtime_ui_read_request').fetchone()==(None,)
    assert len(calls)==(0 if failure=='snapshot' else 1)
    assert prepare(consumer_case) is None


def test_completion_cannot_precede_invocation(consumer_case):
    consumer,*_=consumer_case;prepared=prepare(consumer_case)
    with pytest.raises(RuntimeConflict,match='not consumed'):
        consumer.finish_prepared(prepared,UiReadInvocation(result={}))


def test_second_invocation_is_rejected_while_first_is_pending(consumer_case):
    consumer,_,_,calls,_,_=consumer_case;prepared=prepare(consumer_case)
    async def run():
        entered=asyncio.Event();release=asyncio.Event()
        job=prepared.invoker.expected_job;original=job.invoke_selected_once
        async def pending(**kwargs):
            entered.set();await release.wait();return await original(**kwargs)
        job.invoke_selected_once=pending
        first=asyncio.create_task(consumer.invoke_prepared(prepared))
        await asyncio.wait_for(entered.wait(),2)
        try:
            with pytest.raises(RuntimeConflict,match='already consumed'):await consumer.invoke_prepared(prepared)
        finally:release.set()
        return await first
    result=asyncio.run(run())
    assert consumer.finish_prepared(prepared,result).state=='succeeded' and len(calls)==1


def test_other_consumer_cannot_use_prepared_identity(consumer_case):
    consumer,_,_,calls,_,_=consumer_case;prepared=prepare(consumer_case)
    other=RuntimeUiReadConsumer(scope=SCOPE,connect=consumer.connect,catalog=consumer.catalog,
        installation_store=consumer.store,live_directory=consumer.directory,markings=consumer.markings)
    with pytest.raises(RuntimeConflict,match='not issued'):asyncio.run(other.invoke_prepared(prepared))
    assert calls==[]


def test_lost_source_rls_stops_consumer_before_claim(consumer_case):
    _,owner,_,calls,*_=consumer_case
    owner.execute('ALTER TABLE ecommerce_investigation_case_head NO FORCE ROW LEVEL SECURITY')
    with pytest.raises(PermissionError,match='isolation'):prepare(consumer_case)
    assert calls==[] and owner.execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone()==(0,)


def test_missing_current_scope_denies_before_business_snapshot(consumer_case, monkeypatch):
    _, owner, _, calls, *_ = consumer_case
    reads = []
    def reject(invoker, transaction):
        assert invoker.required_data_scopes == ('ecommerce.workshop.read',)
        raise PermissionError('current installed package data scopes are not admitted')
    monkeypatch.setattr(CurrentInstalledPackageInvoker, 'read_current_in_transaction', reject)
    monkeypatch.setattr('aos_api.extension_runtime.ui_read_consumer.read_host_analyst_workspace_snapshot',
                        lambda **kwargs: reads.append(kwargs))
    assert prepare(consumer_case).state == 'denied'
    assert reads == [] and calls == []
    assert owner.execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone() == (0,)
