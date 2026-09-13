import asyncio

import pytest

from test_ui_read_consumer_pg import consumer_case,host_snapshot,host_role,api_role,admission,queue,attempt_case,database,snapshot,projector,SCOPE,pytestmark
from aos_api.extension_runtime.runtime_host import RuntimeHost,RuntimeTenantAssignment
from aos_api.tenant_scope import TenantScope


def setup(case):
    consumer=case[0]
    assignment=RuntimeTenantAssignment(scope=SCOPE,consumers=(consumer,))
    current=[assignment]
    runtime=RuntimeHost(assignments=lambda:tuple(current))
    return runtime,current


def test_host_runs_ui_delivery_through_original_tick(consumer_case):
    runtime,_=setup(consumer_case)
    async def run():
        tick=await runtime.run_once()
        await runtime.stop()
        return tick
    tick=asyncio.run(run())
    assert tick.tenants[0].deliveries[0].state=='succeeded'
    assert len(consumer_case[3])==1


@pytest.mark.parametrize('phase',['prepared','invoked'])
def test_assignment_revocation_does_not_invoke_or_deliver_after_boundary(consumer_case,monkeypatch,phase):
    consumer,owner,_,calls,*_=consumer_case
    runtime,current=setup(consumer_case)
    if phase=='prepared':
        original=consumer.prepare_once
        def prepare(**kwargs):
            value=original(**kwargs);current.clear();return value
        monkeypatch.setattr(consumer,'prepare_once',prepare)
    else:
        original=consumer.invoke_prepared
        async def invoke(prepared):
            value=await original(prepared);current.clear();return value
        monkeypatch.setattr(consumer,'invoke_prepared',invoke)
    async def run():
        tick=await runtime.run_once();await runtime.stop();return tick
    tick=asyncio.run(run())
    assert tick.tenants[0].deliveries==(None,)
    assert len(calls)==(0 if phase=='prepared' else 1)
    assert owner.execute('SELECT state,result_json FROM extension_runtime_ui_read_request').fetchone()==('claimed',None)
    assert owner.execute('SELECT state FROM extension_runtime_execution_attempt').fetchone()==('running',)
    assert consumer._issued=={}


def test_stop_waits_for_started_read_and_completion(consumer_case):
    consumer,owner,_,calls,*_=consumer_case
    runtime,_=setup(consumer_case)
    async def run():
        entered=asyncio.Event();release=asyncio.Event()
        job=consumer.directory.jobs_for_scope(SCOPE)[0]
        original=job.invoke_selected_once
        async def pending(**kwargs):
            entered.set();await release.wait();return await original(**kwargs)
        job.invoke_selected_once=pending
        running=asyncio.create_task(runtime.run_once())
        await asyncio.wait_for(entered.wait(),5)
        stopping=asyncio.create_task(runtime.stop())
        await asyncio.sleep(0)
        assert not stopping.done()
        release.set()
        tick=await running;await stopping
        return tick
    tick=asyncio.run(run())
    assert tick.tenants[0].deliveries[0].state=='succeeded' and len(calls)==1
    assert owner.execute('SELECT state FROM extension_runtime_execution_attempt').fetchone()==('succeeded',)


def test_assignment_requires_same_scope_and_one_read_consumer(consumer_case):
    consumer=consumer_case[0]
    with pytest.raises(TypeError,match='scope'):
        RuntimeTenantAssignment(scope=TenantScope('dev-org','dev-project'),consumers=(consumer,))
    with pytest.raises(ValueError,match='duplicate'):
        RuntimeTenantAssignment(scope=SCOPE,consumers=(consumer,consumer))
