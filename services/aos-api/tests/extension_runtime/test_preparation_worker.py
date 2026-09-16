import asyncio
import threading
from types import SimpleNamespace

import pytest

from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.oci_driver import CleanupUncertainError
from aos_api.extension_runtime.preparation_worker import PreparedJob, PreparationWorker


def test_worker_binds_artifact_reader_to_each_member_and_preserves_legacy_reader():
    legacy_calls=[]
    member_calls=[]
    legacy=lambda path,limit:legacy_calls.append((path,limit)) or b'legacy'
    worker=PreparationWorker(connect=None,driver=None,installation_store=None,revalidator=None,
        check_current_permission=None,load_record=None,read_artifact=legacy,policy=None,platform=None,
        read_member_artifact=lambda selected,path,limit:
            member_calls.append((selected,path,limit)) or selected.encode())
    first=SimpleNamespace(selected='bundle-a')
    second=SimpleNamespace(selected='bundle-b')
    assert worker._artifact_reader(first)('artifacts/backend-runtime.json',65536)==b'bundle-a'
    assert worker._artifact_reader(second)('artifacts/backend-runtime.json',65536)==b'bundle-b'
    assert member_calls==[
        ('bundle-a','artifacts/backend-runtime.json',65536),
        ('bundle-b','artifacts/backend-runtime.json',65536),
    ]
    assert legacy_calls==[]

    compatible=PreparationWorker(connect=None,driver=None,installation_store=None,revalidator=None,
        check_current_permission=None,load_record=None,read_artifact=legacy,policy=None,platform=None)
    assert compatible._artifact_reader(first) is legacy
    assert compatible._artifact_reader(first)('artifact.json',17)==b'legacy'
    assert legacy_calls==[('artifact.json',17)]


def test_job_verification_settles_thread_on_owner_cancellation():
    async def run():
        started,release=threading.Event(),threading.Event()
        stopped=asyncio.Event()
        results=[]
        class Owner:
            async def verify(self,commit):
                self.task=asyncio.create_task(commit('trusted-observation'))
                return await asyncio.shield(self.task)
            async def wait_closed(self):await stopped.wait()
        owner=Owner()
        def verify(op,rev,observed):
            assert (op,rev,observed)==('op',7,'trusted-observation')
            started.set()
            assert release.wait(5)
            results.append('committed')
            return 'result'
        job=PreparedJob(None,owner,lambda code:None,verify)
        waiter=asyncio.create_task(job.verify(operation_id='op',expected_revision=7))
        try:
            assert await asyncio.to_thread(started.wait,5)
            owner.task.cancel()
            await asyncio.sleep(0)
            owner.task.cancel()
            await asyncio.sleep(0)
            assert not owner.task.done() and results==[]
        finally:release.set()
        with pytest.raises(asyncio.CancelledError):await waiter
        assert results==['committed']
        stopped.set()
        await job.wait_closed()
    asyncio.run(run())


def test_job_requires_host_conditions_before_verification():
    async def run():
        stopped=asyncio.Event()
        class Owner:
            async def wait_closed(self):await stopped.wait()
        job=PreparedJob(None,Owner(),lambda code:None)
        with pytest.raises(RuntimeError,match='conditions reader'):
            await job.verify(operation_id='op',expected_revision=1)
        stopped.set()
        await job.wait_closed()
    asyncio.run(run())


def test_rehydrated_job_renews_without_replaying_verification():
    async def run():
        stopped=asyncio.Event();calls=[]
        class Owner:
            async def wait_closed(self):await stopped.wait()
            async def renew(self,commit):return await commit('trusted-clock')
        def renew(observed):
            calls.append(observed)
            from datetime import datetime,timezone,timedelta
            return datetime.now(timezone.utc)+timedelta(seconds=180)
        job=PreparedJob(None,Owner(),lambda code:None,renew=renew,already_verified=True)
        assert await job.renew_if_due() is not None
        assert calls==['trusted-clock']
        stopped.set();await job.wait_closed()
    asyncio.run(run())


def test_job_health_preserves_uncertain_when_finalization_refuses():
    async def run():
        error = CleanupUncertainError('isolated', 'exact-name', 'exact-owner')
        stopped = asyncio.Event()
        class Owner:
            async def check_health(self):raise error
            async def stop(self):stopped.set()
            async def wait_closed(self):await stopped.wait()
        def finalize(code):raise RuntimeConflict('unresolved resource')
        job = PreparedJob(None, Owner(), finalize)
        with pytest.raises(CleanupUncertainError) as caught:
            await job.check_health()
        assert caught.value is error
        assert isinstance(error.__cause__, RuntimeConflict)
        assert job._closed.done()
    asyncio.run(run())


def test_job_retains_exact_cleanup_uncertain_when_finalization_refuses():
    async def run():
        error=CleanupUncertainError('isolated-engine','exact-name','exact-owner')
        class Owner:
            async def wait_closed(self):raise error
        def finalize(code):raise RuntimeConflict('resources remain unresolved')
        job=PreparedJob(None,Owner(),finalize)
        with pytest.raises(CleanupUncertainError) as caught:
            await job.wait_closed()
        assert caught.value is error
        assert isinstance(caught.value.__cause__,RuntimeConflict)
    asyncio.run(run())


def test_start_cancellation_settles_committed_claim_before_finalizing():
    async def run():
        started=threading.Event()
        release=threading.Event()
        plan=SimpleNamespace()
        finalized=[]
        worker=PreparationWorker(connect=None,driver=None,installation_store=None,revalidator=None,
            check_current_permission=None,load_record=None,read_artifact=None,policy=None,platform=None)
        def claim(*args):
            started.set()
            assert release.wait(timeout=5)
            return plan
        def finalize(scope,target,code):
            assert target is plan
            finalized.append(code)
        worker._claim=claim
        worker._finalize=finalize
        task=asyncio.create_task(worker.start(org_id='org-org',project_id='dev-project',
            operation_id='test-operation',expected_revision=1))
        try:
            assert await asyncio.to_thread(started.wait,5)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and finalized==[]
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):await task
        assert finalized==['PREPARATION_STOPPED']
    asyncio.run(run())
