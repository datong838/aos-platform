import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from aos_api.extension_runtime.preparation_owner import PreparationOwner
from aos_api.extension_runtime.preparation_worker import PreparedJob


class _Process:
    def __init__(self):
        self.closed = asyncio.Event()

    async def wait(self):
        await self.closed.wait()


class _Session:
    def __init__(self, calls, *, block=None, failure=None):
        self.process = _Process()
        self.calls = calls
        self.block = block
        self.failure = failure

    async def invoke(self, operation, payload):
        self.calls.append((operation, payload))
        if self.block is not None:
            await self.block.wait()
        if self.failure is not None:
            raise self.failure
        return {"operation": operation, "payload": payload}


def _factory(session):
    @asynccontextmanager
    async def opened():
        try:
            yield session
        finally:
            session.process.closed.set()
    return opened


async def _owner(session):
    owner = PreparationOwner([_factory(session)], lambda: asyncio.sleep(0, result="ready"), lease_seconds=30)
    await owner.prepared()
    return owner


def test_live_owner_invokes_owned_session_without_exposing_it():
    async def run():
        calls = []
        owner = await _owner(_Session(calls))
        try:
            result = await owner.invoke_once(0, "ecommerce_growth_review_advance", {"kind": "validate_runtime"})
            assert result == {"operation": "ecommerce_growth_review_advance", "payload": {"kind": "validate_runtime"}}
            assert calls == [("ecommerce_growth_review_advance", {"kind": "validate_runtime"})]
        finally:
            await owner.stop()
    asyncio.run(run())


def test_live_owner_serializes_calls_and_never_retries_failure():
    async def run():
        calls = []
        release = asyncio.Event()
        session = _Session(calls, block=release)
        owner = await _owner(session)
        try:
            first = asyncio.create_task(owner.invoke_once(0, "one", {"n": 1}))
            await asyncio.sleep(0)
            second = asyncio.create_task(owner.invoke_once(0, "two", {"n": 2}))
            await asyncio.sleep(0)
            assert calls == [("one", {"n": 1})]
            release.set()
            await asyncio.gather(first, second)
            assert calls == [("one", {"n": 1}), ("two", {"n": 2})]
        finally:
            await owner.stop()

        failed_calls = []
        failed = await _owner(_Session(failed_calls, failure=PermissionError("undeclared operation")))
        try:
            with pytest.raises(PermissionError, match="undeclared"):
                await failed.invoke_once(0, "missing", {})
            assert failed_calls == [("missing", {})]
        finally:
            await failed.stop()
    asyncio.run(run())


def test_prepared_job_selects_exact_unique_package_before_owner_call():
    class Owner:
        def __init__(self):
            self.calls = []

        async def invoke_once(self, index, operation, payload):
            self.calls.append((index, operation, payload))
            return {"ok": True}

    async def run():
        job = object.__new__(PreparedJob)
        job.plan = SimpleNamespace(members=(
            SimpleNamespace(selected=SimpleNamespace(id="solution.ecommerce.growth", content_hash="sha256:" + "a" * 64)),
            SimpleNamespace(selected=SimpleNamespace(id="dependency", content_hash="sha256:" + "b" * 64)),
        ))
        job._owner = Owner()
        result = await job.invoke_selected_once(
            package_id="solution.ecommerce.growth",
            package_hash="sha256:" + "a" * 64,
            operation="ecommerce_growth_review_advance",
            payload={"kind": "validate_runtime"},
        )
        assert result == {"ok": True}
        assert job._owner.calls == [(0, "ecommerce_growth_review_advance", {"kind": "validate_runtime"})]
        for package_id, package_hash in (("missing", "sha256:" + "a" * 64),
                                         ("solution.ecommerce.growth", "sha256:" + "c" * 64)):
            with pytest.raises(PermissionError, match="package is not owned"):
                await job.invoke_selected_once(package_id=package_id, package_hash=package_hash,
                                               operation="ecommerce_growth_review_advance", payload={})
        assert len(job._owner.calls) == 1
    asyncio.run(run())


def test_stop_cancels_and_settles_inflight_invocation():
    async def run():
        calls = []
        owner = await _owner(_Session(calls, block=asyncio.Event()))
        invocation = asyncio.create_task(owner.invoke_once(0, "blocked", {}))
        await asyncio.sleep(0)
        await owner.stop()
        with pytest.raises(asyncio.CancelledError):
            await invocation
        assert calls == [("blocked", {})]
    asyncio.run(run())
