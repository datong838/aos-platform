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


def test_health_budget_includes_request_lock_wait(monkeypatch):
    async def run():
        closed=[]
        async def close():closed.append(True)
        session=RuntimeSession(None,None,RegistrationDescription(contributions=[]),close)
        timeout=asyncio.timeout
        def short_budget(seconds):
            assert seconds==3
            return timeout(.01)
        monkeypatch.setattr(asyncio,'timeout',short_budget)
        async def exchange(*args):raise AssertionError('must not exchange before lock')
        session._exchange=exchange
        await session.lock.acquire()
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(session.check_health(),.1)
            assert session.failed and closed==[True]
        finally:
            session.lock.release()
    asyncio.run(run())
