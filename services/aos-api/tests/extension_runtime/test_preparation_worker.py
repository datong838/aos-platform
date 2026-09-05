import asyncio
import threading
from types import SimpleNamespace

import pytest

from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.oci_driver import CleanupUncertainError
from aos_api.extension_runtime.preparation_worker import PreparedJob, PreparationWorker


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
