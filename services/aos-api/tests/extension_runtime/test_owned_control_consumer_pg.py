import asyncio
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_lifecycle_pg import database,pytestmark
from test_resource_recovery_pg import setup,SCOPE
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.preparation_worker import PreparedJob


def named_job(installation):
    # Explicit consumer-only fixture; actual signed ownership is tested separately.
    job=object.__new__(PreparedJob)
    job._tenant_scope=TenantScope(**SCOPE)
    job.plan=SimpleNamespace(installation_id=installation,generation=uuid4())
    return job


@pytest.mark.parametrize('kind',['runtime-verify','enable'])
@pytest.mark.parametrize('case',['terminal','wrong_installation','wrong_kind','deferred','execute','wrong_generation'])
def test_owned_consumer_routes_current_installation(database,monkeypatch,kind,case):
    from aos_api.extension_runtime.owned_control_consumer import OwnedControlConsumer
    conn,_,connect=setup(database)
    installation=conn.execute('SELECT installation_id FROM extension_runtime_operation').fetchone()[0]
    conn.execute('UPDATE extension_runtime_operation SET kind=%s,status=%s,phase=%s',
        ('disable' if case=='wrong_kind' else kind,'succeeded' if case=='terminal' else 'running' if case=='deferred' else 'accepted',
         'succeeded' if case=='terminal' else 'committing' if case=='deferred' else 'accepted'))
    job=named_job(uuid4() if case=='wrong_installation' else installation)
    if kind=='enable':
        monkeypatch.setattr('aos_api.extension_runtime.owned_control_consumer.load_enable_target',
            lambda *a,**k:SimpleNamespace(generation=str(uuid4() if case=='wrong_generation' else job.plan.generation)))
    calls=[]
    async def execute(**kwargs):
        calls.append(kwargs)
        raise RuntimeError('named executor failure')
    job.verify=execute
    job.enable=execute
    async def run():
        consumer=OwnedControlConsumer(connect=connect,job=job,kind=kind,**SCOPE)
        if case=='execute' or (case=='wrong_generation' and kind=='runtime-verify'):
            with pytest.raises(RuntimeError,match='named executor'):await consumer.run_once()
            assert len(calls)==1
        else:
            result=await consumer.run_once()
            assert not calls
            if case in ('wrong_installation','wrong_kind'):assert result is None
            else:assert result.delivery_status==('acknowledged' if case=='terminal' else 'deferred')
    asyncio.run(run())
    if case!='terminal':
        assert conn.execute('SELECT count(*) FROM extension_runtime_outbox WHERE delivered_at IS NOT NULL').fetchone()==(0,)


@pytest.mark.parametrize('phase',['claim','read','command','finish'])
def test_internal_cancellation_waits_for_database_thread(phase):
    from aos_api.extension_runtime.owned_control_consumer import OwnedControlConsumer
    async def run():
        consumer=OwnedControlConsumer(connect=lambda:None,job=named_job(uuid4()),kind='enable',**SCOPE)
        entered,release=threading.Event(),threading.Event()
        completed=[]
        def blocked(*args):
            entered.set()
            assert release.wait(5)
            completed.append(True)
            return None
        consumer._claim=blocked if phase=='claim' else lambda:SimpleNamespace(operation_id=uuid4())
        consumer._read=blocked if phase=='read' else lambda lease:('accepted' if phase=='command' else 'succeeded','accepted' if phase=='command' else 'succeeded',1,True)
        async def command(**kwargs):return await asyncio.to_thread(blocked)
        consumer.job.enable=command
        consumer._finish=blocked
        waiter=asyncio.create_task(consumer.run_once())
        try:
            assert await asyncio.to_thread(entered.wait,5)
            consumer._task.cancel()
            await asyncio.sleep(0)
            consumer._task.cancel()
            await asyncio.sleep(0)
            assert not consumer._task.done() and not completed
        finally:release.set()
        with pytest.raises(asyncio.CancelledError):await waiter
        assert completed==[True]
        with pytest.raises(asyncio.CancelledError):await consumer.wait_idle()
    asyncio.run(run())


def test_owned_consumer_rejects_foreign_scope_before_database():
    from aos_api.extension_runtime.owned_control_consumer import OwnedControlConsumer
    with pytest.raises(ValueError,match='scope'):
        OwnedControlConsumer(connect=lambda:None,job=named_job(uuid4()),kind='enable',org_id='dev-org',project_id='dev-project')


def test_cancelled_wait_keeps_registered_work_and_idle_wait_observes_it():
    from aos_api.extension_runtime.owned_control_consumer import OwnedControlConsumer
    async def run():
        consumer=OwnedControlConsumer(connect=lambda:None,job=named_job(uuid4()),kind='enable',**SCOPE)
        entered,release=asyncio.Event(),asyncio.Event()
        async def work():
            entered.set()
            await release.wait()
            return 'settled'
        consumer._run=work
        waiter=asyncio.create_task(consumer.run_once())
        await entered.wait()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):await waiter
        with pytest.raises(RuntimeError,match='in progress'):await consumer.run_once()
        release.set()
        assert await consumer.wait_idle()=='settled'
    asyncio.run(run())
