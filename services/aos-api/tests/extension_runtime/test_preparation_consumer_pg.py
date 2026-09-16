import asyncio
from types import SimpleNamespace
from uuid import uuid4
import pytest
from test_lifecycle_pg import database,pytestmark
from test_resource_recovery_pg import setup,SCOPE
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.preparation_worker import PreparationWorker,PreparedJob


def named_worker(start):
    worker=object.__new__(PreparationWorker)
    worker.start=start
    return worker


def test_rehydration_never_claims_outbox_and_registers_exact_live_job():
    from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
    async def run():
        installation,operation=uuid4(),uuid4()
        calls=[]
        job=named_job(installation,operation)
        async def prepared():calls.append('prepared')
        async def stop():calls.append('stop')
        job.prepared,job.stop=prepared,stop
        worker=object.__new__(PreparationWorker)
        async def resume_current(**kwargs):
            calls.append(('resume',kwargs));return job
        worker.resume_current=resume_current
        consumer=PreparationConsumer(connect=lambda:None,worker=worker,
            installation_id=installation,rehydrate=True,**SCOPE)
        consumer._claim=lambda:pytest.fail('rehydration consumed an outbox')
        assert await consumer.run_once() is None
        assert await consumer.run_once() is None
        assert calls[:2]==[('resume',{'org_id':'org-org','project_id':'dev-project',
            'installation_id':installation}),'prepared']
        assert len([item for item in calls if isinstance(item,tuple)])==1
        await consumer.stop()
        assert calls[-1]=='stop'
    asyncio.run(run())


def named_job(installation,operation):
    job=object.__new__(PreparedJob)
    job._tenant_scope=TenantScope(**SCOPE)
    job.plan=SimpleNamespace(installation_id=installation,operation_id=operation,generation=uuid4())
    return job


@pytest.mark.parametrize('case',['terminal','wrong_kind','wrong_installation','preparing','existing_job','ack_failure'])
def test_preparation_delivery_retains_one_owner(database,case):
    from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
    conn,_,connect=setup(database)
    operation,installation=conn.execute('SELECT operation_id,installation_id FROM extension_runtime_operation').fetchone()
    status='succeeded' if case=='terminal' else 'running' if case=='preparing' else 'accepted'
    conn.execute('UPDATE extension_runtime_operation SET kind=%s,status=%s,phase=%s',
        ('disable' if case=='wrong_kind' else 'runtime-apply',status,'preparing' if case=='preparing' else status))
    calls=[]
    job=named_job(installation,operation)
    async def prepared():
        conn.execute("UPDATE extension_runtime_operation SET status='succeeded',phase='succeeded'")
        return 'prepared'
    async def stop():calls.append('stop')
    job.prepared,job.stop=prepared,stop
    async def start(**kwargs):calls.append('start');return job
    async def run():
        consumer=PreparationConsumer(connect=connect,worker=named_worker(start),
            installation_id=uuid4() if case=='wrong_installation' else installation,**SCOPE)
        if case=='existing_job':consumer._job=job
        if case=='ack_failure':
            original=consumer.outbox.ack
            def failed(c,**kw):original(c,**kw);raise RuntimeError('named ACK failure')
            consumer.outbox.ack=failed
            with pytest.raises(RuntimeError,match='named ACK'):await consumer.run_once()
            assert consumer.job is job and calls==['start']
        else:
            result=await consumer.run_once()
            assert not calls
            if case in ('wrong_kind','wrong_installation'):assert result is None
            else:assert result.delivery_status==('acknowledged' if case=='terminal' else 'deferred')
        try:await consumer.stop()
        except RuntimeError as exc:assert str(exc)=='named ACK failure'
        if case in ('existing_job','ack_failure'):assert calls[-1]=='stop'
        with pytest.raises(RuntimeError,match='closed'):await consumer.run_once()
    asyncio.run(run())


def test_cancellation_during_start_registers_returned_job_before_closing():
    from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
    async def run():
        installation,operation=uuid4(),uuid4()
        entered,release=asyncio.Event(),asyncio.Event()
        calls=[]
        job=named_job(installation,operation)
        async def start(**kwargs):
            entered.set()
            await release.wait()
            return job
        async def stop():calls.append('stop')
        job.stop=stop
        consumer=PreparationConsumer(connect=lambda:None,worker=named_worker(start),installation_id=installation,**SCOPE)
        consumer._claim=lambda:SimpleNamespace(operation_id=operation)
        consumer._read=lambda lease:('accepted','accepted',1)
        waiter=asyncio.create_task(consumer.run_once())
        await entered.wait()
        consumer._task.cancel()
        await asyncio.sleep(0)
        assert not consumer._task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):await waiter
        assert consumer.job is job
        try:await consumer.stop()
        except asyncio.CancelledError:pass
        assert calls==['stop']
    asyncio.run(run())


@pytest.mark.parametrize('cleanup_fails',[False,True])
def test_stop_waits_before_cleanup_and_preserves_cleanup_uncertainty(cleanup_fails):
    from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
    from aos_api.extension_runtime.oci_driver import CleanupUncertainError
    async def run():
        installation,operation=uuid4(),uuid4()
        entered,release=asyncio.Event(),asyncio.Event()
        calls=[]
        async def never(**kwargs):raise AssertionError('unexpected start')
        consumer=PreparationConsumer(connect=lambda:None,worker=named_worker(never),installation_id=installation,**SCOPE)
        job=named_job(installation,operation)
        async def cleanup():
            calls.append('cleanup')
            if cleanup_fails:raise CleanupUncertainError('named-engine','named-resource','named-owner')
        job.stop=cleanup
        consumer._job=job
        async def consume():
            entered.set()
            await release.wait()
            calls.append('consume-settled')
            raise RuntimeError('named consume failure')
        consumer._run=consume
        waiter=asyncio.create_task(consumer.run_once())
        await entered.wait()
        closing=asyncio.create_task(consumer.stop())
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError,match='closed'):await consumer.run_once()
        assert not calls
        release.set()
        with pytest.raises(RuntimeError,match='named consume failure'):await waiter
        with pytest.raises(CleanupUncertainError if cleanup_fails else RuntimeError):await closing
        assert calls==['consume-settled','cleanup']
        with pytest.raises(CleanupUncertainError if cleanup_fails else RuntimeError):await consumer.stop()
        assert calls==['consume-settled','cleanup']
    asyncio.run(run())


@pytest.mark.parametrize('mismatch',['scope','installation','operation'])
def test_returned_owner_mismatch_is_cleaned_before_rejection(mismatch):
    from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    async def run():
        installation,operation=uuid4(),uuid4()
        job=named_job(installation,operation)
        if mismatch=='scope':job._tenant_scope=TenantScope('dev-org','dev-project')
        if mismatch=='installation':job.plan.installation_id=uuid4()
        if mismatch=='operation':job.plan.operation_id=uuid4()
        calls=[]
        async def start(**kwargs):return job
        async def stop():calls.append('cleaned')
        job.stop=stop
        consumer=PreparationConsumer(connect=lambda:None,worker=named_worker(start),installation_id=installation,**SCOPE)
        consumer._claim=lambda:SimpleNamespace(operation_id=operation)
        consumer._read=lambda lease:('accepted','accepted',1)
        with pytest.raises(RuntimeConflict,match='routing mismatch'):await consumer.run_once()
        assert calls==['cleaned'] and consumer.job is job
    asyncio.run(run())
