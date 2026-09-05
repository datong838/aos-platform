import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

from aos_api.extension_runtime.preparation_owner import PreparationOwner


@pytest.mark.parametrize('mode', ['duplicate', 'health_failure', 'commit_failure'])
def test_verification_admission_and_failure_are_supervised(mode):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        closed=[]
        @asynccontextmanager
        async def resource():
            class Session:
                process=type('Process', (), {'wait': lambda self: asyncio.Event().wait()})()
                async def check_health(self):
                    if mode=='health_failure':raise ValueError('health')
            try:yield Session()
            finally:closed.append(True)
        async def prepare():return 'prepared'
        async def commit(observed):
            entered.set()
            if mode=='commit_failure':raise ValueError('commit')
            await release.wait()
            return 'verified'
        owner=PreparationOwner([resource],prepare,lease_seconds=5)
        await owner.prepared()
        task=asyncio.create_task(owner.verify(commit))
        if mode=='duplicate':
            await entered.wait()
            with pytest.raises(RuntimeError,match='exclusive'):await owner.verify(commit)
            release.set()
            assert await task=='verified'
            await owner.stop()
            with pytest.raises(RuntimeError):await owner.verify(commit)
        else:
            with pytest.raises(ValueError):await task
            with pytest.raises(ValueError):await owner.wait_closed()
        assert closed==[True]
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())


@pytest.mark.parametrize('reason', ['stop', 'lease', 'exit', 'request_cancel'])
def test_owned_verification_settles_before_resource_cleanup(reason):
    async def run():
        entered, release, exited = asyncio.Event(), asyncio.Event(), asyncio.Event()
        events = []
        @asynccontextmanager
        async def resource():
            class Session:
                process = type('Process', (), {'wait': lambda self: exited.wait()})()
                async def check_health(self):events.append('health')
            try:yield Session()
            finally:events.append('closed')
        async def prepare():return 'prepared'
        async def commit(observed):
            assert 0 <= (datetime.now(timezone.utc)-observed).total_seconds() < 1
            entered.set()
            try:await release.wait()
            except asyncio.CancelledError:await release.wait()
            events.append('committed')
            return 'verified'
        owner = PreparationOwner([resource], prepare, lease_seconds=.05 if reason=='lease' else 5)
        await owner.prepared()
        waiter = asyncio.create_task(owner.verify(commit))
        await entered.wait()
        if reason=='stop':closing=asyncio.create_task(owner.stop())
        elif reason=='exit':exited.set(); closing=asyncio.create_task(owner.wait_closed())
        elif reason=='lease':closing=asyncio.create_task(owner.wait_closed())
        else:waiter.cancel(); closing=None
        await asyncio.sleep(.08)
        assert events == ['health']
        release.set()
        if reason=='request_cancel':
            with pytest.raises(asyncio.CancelledError):await waiter
            await owner.stop()
        else:
            await asyncio.gather(waiter,closing,return_exceptions=True)
        assert events == ['health','committed','closed']
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())
