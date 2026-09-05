import asyncio
from contextlib import asynccontextmanager

import pytest
from test_admission import fixture
from aos_api.extension_runtime import signed_session as module


def test_signature_and_declared_package_are_joined(monkeypatch):
    args,_=fixture()
    expected=list(args["record"].manifest.spec.contributions)
    calls=[]
    @asynccontextmanager
    async def journal(driver,**kwargs):
        calls.append(kwargs)
        yield "verified-session"
    monkeypatch.setattr(module,"open_journaled_session",journal)
    observations=[]
    monkeypatch.setattr(module,"_record_registration",lambda *values:observations.append(values[-1]))
    original=args["driver"]._run
    def inspect(*values):
        # Caller mutation while async validation runs cannot change declarations.
        args["record"].manifest.spec.contributions.clear()
        return original(*values)
    args["driver"]._run=inspect
    async def run():
        async with module.open_signed_session(**args,connect=None,org_id="org-org",project_id="dev-project",resource_id="test") as session:
            assert session=="verified-session"
    asyncio.run(run())
    assert calls[0]["declared"].contributions==expected
    assert observations[0].contributions==expected
    assert calls[0]["image_id"]=="sha256:"+"b"*64
    assert calls[0]["expected_package"]==(args["selected"].id,args["selected"].content_hash)


def test_invalid_signature_never_claims_resource(monkeypatch):
    args,_=fixture()
    args["record"].signature=None
    def forbidden(*args,**kwargs):
        raise AssertionError("must not claim")
    monkeypatch.setattr(module,"open_journaled_session",forbidden)
    async def run():
        async with module.open_signed_session(**args,connect=None,org_id="org-org",project_id="dev-project",resource_id="test"):
            raise AssertionError("must not enter")
    with pytest.raises(Exception) as failure:
        asyncio.run(run())
    assert not isinstance(failure.value,AssertionError)
    assert args["driver"].calls==0


def test_cancel_during_image_check_never_claims(monkeypatch):
    import threading
    args,_=fixture()
    started,finish=threading.Event(),threading.Event()
    original=args["driver"]._run
    def inspect(*values):
        started.set()
        assert finish.wait(5)
        return original(*values)
    args["driver"]._run=inspect
    calls=[]
    def forbidden(*values,**kwargs):
        calls.append("claim")
        raise AssertionError("must not claim")
    monkeypatch.setattr(module,"open_journaled_session",forbidden)
    async def enter():
        async with module.open_signed_session(**args,connect=None,org_id="org-org",project_id="dev-project",resource_id="test"):
            raise AssertionError("must not enter")
    async def run():
        task=asyncio.create_task(enter())
        try:
            assert await asyncio.to_thread(started.wait,3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
        finally:
            finish.set()
    asyncio.run(run())
    assert calls==[]


def test_cancel_waits_for_registration_commit_then_closes(monkeypatch):
    import threading
    args,_=fixture()
    started,finish=threading.Event(),threading.Event()
    events=[]
    @asynccontextmanager
    async def journal(*values,**kwargs):
        try:yield 'session'
        finally:events.append('closed')
    def record(*values):
        started.set()
        assert finish.wait(5)
        events.append('committed')
    monkeypatch.setattr(module,'open_journaled_session',journal)
    monkeypatch.setattr(module,'_record_registration',record)
    async def enter():
        async with module.open_signed_session(**args,connect=None,org_id='org-org',project_id='dev-project',resource_id='test'):
            events.append('entered')
    async def run():
        task=asyncio.create_task(enter())
        assert await asyncio.to_thread(started.wait,3)
        task.cancel()
        finish.set()
        with pytest.raises(asyncio.CancelledError):await task
    asyncio.run(run())
    assert events==['committed','closed']
