from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from aos_api.extension_runtime.live_installation_owner import (
    LiveInstallationLifecycleOwner,
    LiveInstallationTick,
)
from aos_api.extension_runtime.live_installation_scheduler import (
    LiveInstallationScheduler,
)
from aos_api.extension_runtime.pending_preparation_directory import (
    LiveInstallationOwnerFactory,
    PendingPreparationDescriptor,
    PostgresPendingPreparationDirectory,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def descriptor(value):
    return PendingPreparationDescriptor(SCOPE, UUID(int=value))


def dependencies(monkeypatch, pages, calls, *, fail=None, block=None, stop_fail=()):
    directory = object.__new__(PostgresPendingPreparationDirectory)
    directory.scope = SCOPE
    pages = iter(pages)
    directory.read_descriptors = lambda: next(pages)
    factory = object.__new__(LiveInstallationOwnerFactory)
    factory.scope = SCOPE
    owners = {}

    def create(_factory, item):
        calls.append(("create", item.installation_id.int))
        owner = object.__new__(LiveInstallationLifecycleOwner)

        async def run_once():
            calls.append(("run", item.installation_id.int))
            if block is not None and item.installation_id.int == block[0]:
                block[1].set()
                await block[2].wait()
            if item.installation_id.int == fail:
                raise RuntimeError("named owner failure")
            return LiveInstallationTick(None, None, None)

        async def stop():
            calls.append(("stop", item.installation_id.int))
            if item.installation_id.int in stop_fail:
                raise RuntimeError(f"stop {item.installation_id.int} failed")

        owner.run_once = run_once
        owner.stop = stop
        owners[item.installation_id] = owner
        return owner

    monkeypatch.setattr(LiveInstallationOwnerFactory, "__call__", create)
    return directory, factory, owners


def test_requires_exact_same_scope_dependencies():
    with pytest.raises(TypeError, match="same-scope"):
        LiveInstallationScheduler(directory=object(), factory=object())
    directory = object.__new__(PostgresPendingPreparationDirectory)
    directory.scope = SCOPE
    factory = object.__new__(LiveInstallationOwnerFactory)
    factory.scope = TenantScope("other", "project")
    with pytest.raises(TypeError, match="same-scope"):
        LiveInstallationScheduler(directory=directory, factory=factory)


def test_creates_in_uuid_order_and_retains_after_descriptor_disappears(monkeypatch):
    calls = []
    directory, factory, owners = dependencies(
        monkeypatch,
        ((descriptor(1), descriptor(2)), ()),
        calls,
    )

    async def exercise():
        scheduler = LiveInstallationScheduler(directory=directory, factory=factory)
        first = await scheduler.run_once()
        second = await scheduler.run_once()
        assert tuple(key.int for key, _ in scheduler.owners) == (1, 2)
        assert len(first.deliveries) == len(second.deliveries) == 2
        await scheduler.stop()

    asyncio.run(exercise())
    assert calls == [
        ("create", 1), ("create", 2), ("run", 1), ("run", 2),
        ("run", 1), ("run", 2), ("stop", 1), ("stop", 2),
    ]
    assert len(owners) == 2


def test_owner_failure_stops_tick_before_later_owner_and_stop_cleans_all(monkeypatch):
    calls = []
    directory, factory, _ = dependencies(
        monkeypatch, ((descriptor(1), descriptor(2)),), calls, fail=1
    )

    async def exercise():
        scheduler = LiveInstallationScheduler(directory=directory, factory=factory)
        with pytest.raises(RuntimeError, match="named owner failure"):
            await scheduler.run_once()
        with pytest.raises(RuntimeError, match="named owner failure"):
            await scheduler.stop()

    asyncio.run(exercise())
    assert calls == [
        ("create", 1), ("create", 2), ("run", 1), ("stop", 1), ("stop", 2)
    ]


def test_revoke_requires_identity_then_stops_only_exact_owner(monkeypatch):
    calls = []
    directory, factory, owners = dependencies(monkeypatch, ((descriptor(1),),), calls)

    async def exercise():
        scheduler = LiveInstallationScheduler(directory=directory, factory=factory)
        await scheduler.run_once()
        wrong = object.__new__(LiveInstallationLifecycleOwner)
        with pytest.raises(LookupError, match="identity changed"):
            await scheduler.revoke(UUID(int=1), wrong)
        await scheduler.revoke(UUID(int=1), owners[UUID(int=1)])
        assert scheduler.owners == ()
        await scheduler.stop()

    asyncio.run(exercise())
    assert calls == [("create", 1), ("run", 1), ("stop", 1)]


def test_cancelled_request_and_stop_wait_for_owned_tick(monkeypatch):
    calls = []

    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        directory, factory, _ = dependencies(
            monkeypatch, ((descriptor(1),),), calls, block=(1, entered, release)
        )
        scheduler = LiveInstallationScheduler(directory=directory, factory=factory)
        request = asyncio.create_task(scheduler.run_once())
        await entered.wait()
        with pytest.raises(RuntimeError, match="already in progress"):
            await scheduler.run_once()
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        closing = asyncio.create_task(scheduler.stop())
        await asyncio.sleep(0)
        assert not closing.done() and ("stop", 1) not in calls
        release.set()
        await closing

    asyncio.run(exercise())
    assert calls == [("create", 1), ("run", 1), ("stop", 1)]


def test_stop_attempts_every_owner_after_cleanup_failure(monkeypatch):
    calls = []
    directory, factory, _ = dependencies(
        monkeypatch, ((descriptor(1), descriptor(2)),), calls, stop_fail=(1,)
    )

    async def exercise():
        scheduler = LiveInstallationScheduler(directory=directory, factory=factory)
        await scheduler.run_once()
        with pytest.raises(RuntimeError, match="stop 1 failed"):
            await scheduler.stop()
        assert scheduler.owners == ()

    asyncio.run(exercise())
    assert calls[-2:] == [("stop", 1), ("stop", 2)]


def test_rejects_unbounded_or_invalid_directory_result(monkeypatch):
    calls = []
    for page in ((descriptor(1),) * 101, (object(),)):
        directory, factory, _ = dependencies(monkeypatch, (page,), calls)
        with pytest.raises(TypeError, match="bounded"):
            asyncio.run(LiveInstallationScheduler(directory=directory, factory=factory).run_once())
