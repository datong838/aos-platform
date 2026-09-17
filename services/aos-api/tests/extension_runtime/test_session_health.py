import asyncio
import re

import pytest

from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.session_supervisor import RuntimeSession
from aos_api.extension_runtime.ipc import ProtocolError


@pytest.mark.parametrize('case', ['valid','nonce','status','extra'])
def test_health_response_is_exact_and_not_a_business_grant(case):
    async def run():
        closed=[]
        async def close():closed.append(True)
        session=RuntimeSession(None,None,RegistrationDescription(contributions=[]),close)
        async def exchange(kind,method,payload,timeout):
            assert kind==method=='heartbeat' and timeout==3
            assert re.fullmatch(r'[0-9a-f]{32}',payload['nonce'])
            result={**payload,'protocol':'aos-extension/1','status':'alive'}
            if case=='nonce':result['nonce']='wrong'
            if case=='status':result['status']='ready'
            if case=='extra':result['enabled']=True
            return result
        session._exchange=exchange
        if case=='valid':
            assert await session.check_health() is None
            assert not closed
        else:
            with pytest.raises(ProtocolError):await session.check_health()
            assert session.failed and closed==[True]
    asyncio.run(run())


def test_health_budget_starts_after_bounded_request_lock_wait(monkeypatch):
    async def run():
        closed=[]
        async def close():closed.append(True)
        session=RuntimeSession(None,None,RegistrationDescription(contributions=[]),close)
        timeout=asyncio.timeout
        budgets=[]
        def short_budget(seconds):
            assert seconds==3
            budgets.append(seconds)
            return timeout(.01)
        monkeypatch.setattr(asyncio,'timeout',short_budget)
        exchanged=asyncio.Event()
        async def exchange(kind,method,payload,seconds):
            assert kind==method=='heartbeat' and seconds==3
            exchanged.set()
            return {**payload,'protocol':'aos-extension/1','status':'alive'}
        session._exchange=exchange
        await session.lock.acquire()
        task=asyncio.create_task(session.check_health())
        try:
            await asyncio.sleep(.02)
            assert not task.done() and not exchanged.is_set()
            assert budgets==[] and not session.failed and closed==[]
        finally:
            session.lock.release()
        assert await asyncio.wait_for(task,.1) is None
        assert exchanged.is_set() and budgets==[3]
        assert not session.failed and closed==[]
    asyncio.run(run())


def test_actual_health_exchange_timeout_still_closes(monkeypatch):
    async def run():
        closed=[]
        async def close():closed.append(True)
        session=RuntimeSession(None,None,RegistrationDescription(contributions=[]),close)
        timeout=asyncio.timeout
        monkeypatch.setattr(asyncio,'timeout',lambda seconds: timeout(.01))
        async def exchange(*args):await asyncio.Event().wait()
        session._exchange=exchange
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(session.check_health(),.1)
        assert session.failed and closed==[True]
    asyncio.run(run())
