import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, UTC, timedelta
import pytest
from aos_api.extension_runtime.preparation_owner import PreparationOwner


def test_only_verified_owner_may_extend_a_live_lease():
    async def run():
        @asynccontextmanager
        async def factory():
            class Process:
                async def wait(self):
                    await asyncio.Event().wait()
            class Session:
                process = Process()
                async def check_health(self):
                    return True
            yield Session()
        async def prepared(): return "prepared"
        async def verified(_): return "verified"
        calls = []
        async def renew(_):
            calls.append("renew")
            return datetime.now(UTC) + timedelta(seconds=1)
        owner = PreparationOwner([factory], prepared, lease_seconds=.2)
        await owner.prepared()
        with pytest.raises(RuntimeError):
            await owner.renew(renew)
        assert calls == []
        await owner.verify(verified)
        await owner.renew(renew)
        await asyncio.sleep(.3)
        await owner.check_health()
        assert calls == ["renew"]
        await owner.stop()
        with pytest.raises(RuntimeError):
            await owner.renew(renew)
    asyncio.run(run())


def test_failed_renewal_closes_resources():
    async def run():
        closed = asyncio.Event()
        @asynccontextmanager
        async def factory():
            class Process:
                async def wait(self): await asyncio.Event().wait()
            class Session:
                process = Process()
                async def check_health(self): pass
            try: yield Session()
            finally: closed.set()
        async def commit(): return "prepared"
        async def verify(_): return "verified"
        async def denied(_): raise PermissionError("revoked")
        owner = PreparationOwner([factory], commit, lease_seconds=1)
        await owner.prepared(); await owner.verify(verify)
        with pytest.raises(PermissionError): await owner.renew(denied)
        with pytest.raises(PermissionError): await owner.wait_closed()
        assert closed.is_set()
    asyncio.run(run())
