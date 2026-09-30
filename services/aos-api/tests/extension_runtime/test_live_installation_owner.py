from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import aos_api.extension_runtime.live_installation_owner as module
from aos_api.extension_runtime.live_installation_owner import (
    LiveInstallationLifecycleOwner,
)
from aos_api.extension_runtime.preparation_consumer import PreparationConsumer


def preparation(calls, *, job=None, run=None):
    consumer = object.__new__(PreparationConsumer)
    consumer.connect = object()
    consumer.scope = {"org_id": "org", "project_id": "project"}
    consumer._job = job

    async def run_once():
        calls.append("runtime-apply")
        if run is not None:
            await run()
        return "prepared"

    async def stop():
        calls.append("stop")

    consumer.run_once = run_once
    consumer.stop = stop
    return consumer


def install_owned(monkeypatch, calls, results=None, *, fail_kind=None):
    results = results or {}

    class Owned:
        def __init__(self, *, connect, job, kind, org_id, project_id):
            assert connect is expected_connect
            assert job is expected_job
            assert (org_id, project_id) == ("org", "project")
            self.kind = kind

        async def run_once(self):
            calls.append(self.kind)
            if self.kind == fail_kind:
                raise RuntimeError(f"{self.kind} failed")
            return results.get(self.kind)

    monkeypatch.setattr(module, "OwnedControlConsumer", Owned)


class HealthyJob:
    async def check_health(self):
        return None
    async def renew_if_due(self):
        return None


expected_job = HealthyJob()
expected_connect = None


def test_requires_exact_preparation_consumer():
    with pytest.raises(TypeError, match="exact preparation"):
        LiveInstallationLifecycleOwner(preparation=object())


def test_without_job_only_runs_preparation(monkeypatch):
    calls = []
    consumer = preparation(calls)
    owner = LiveInstallationLifecycleOwner(preparation=consumer)
    result = asyncio.run(owner.run_once())
    assert result.preparation == "prepared"
    assert result.verification is None and result.enablement is None
    assert calls == ["runtime-apply"]


def test_idle_tick_detects_lost_resource_before_any_control(monkeypatch):
    calls = []
    class LostJob:
        async def check_health(self):
            raise RuntimeError("preparation is no longer owned")
    owner = LiveInstallationLifecycleOwner(preparation=preparation(calls, job=LostJob()))
    with pytest.raises(RuntimeError, match="no longer owned"):
        asyncio.run(owner.run_once())
    assert calls == ["runtime-apply"]


def test_fixed_order_reuses_exact_job_scope_and_connection(monkeypatch):
    global expected_connect
    calls = []
    consumer = preparation(calls, job=expected_job)
    expected_connect = consumer.connect
    verified = SimpleNamespace(operation_status="succeeded")
    install_owned(monkeypatch, calls, {"runtime-verify": verified, "enable": "enabled"})
    result = asyncio.run(LiveInstallationLifecycleOwner(preparation=consumer).run_once())
    assert calls == ["runtime-apply", "runtime-verify", "enable"]
    assert result.verification is verified and result.enablement == "enabled"


def test_preparation_only_never_constructs_enable_consumer(monkeypatch):
    global expected_connect
    calls = []
    consumer = preparation(calls, job=expected_job)
    expected_connect = consumer.connect
    verified = SimpleNamespace(operation_status="succeeded")
    install_owned(monkeypatch, calls, {"runtime-verify": verified})
    owner = LiveInstallationLifecycleOwner(preparation=consumer, enable_allowed=False)
    result = asyncio.run(owner.run_once())
    assert calls == ["runtime-apply", "runtime-verify"]
    assert result.verification is verified and result.enablement is None


def test_failed_verification_result_does_not_enter_enable(monkeypatch):
    global expected_connect
    calls = []
    consumer = preparation(calls, job=expected_job)
    expected_connect = consumer.connect
    failed = SimpleNamespace(operation_status="failed")
    install_owned(monkeypatch, calls, {"runtime-verify": failed})
    result = asyncio.run(LiveInstallationLifecycleOwner(preparation=consumer).run_once())
    assert calls == ["runtime-apply", "runtime-verify"]
    assert result.verification is failed and result.enablement is None


def test_verification_exception_does_not_enter_enable_and_stop_cleans_up(monkeypatch):
    global expected_connect
    calls = []
    consumer = preparation(calls, job=expected_job)
    expected_connect = consumer.connect
    install_owned(monkeypatch, calls, fail_kind="runtime-verify")

    async def exercise():
        owner = LiveInstallationLifecycleOwner(preparation=consumer)
        with pytest.raises(RuntimeError, match="runtime-verify failed"):
            await owner.run_once()
        with pytest.raises(RuntimeError, match="runtime-verify failed"):
            await owner.stop()

    asyncio.run(exercise())
    assert calls == ["runtime-apply", "runtime-verify", "stop"]


def test_cancellation_and_stop_wait_for_tick_then_close(monkeypatch):
    global expected_connect
    calls = []
    entered = asyncio.Event()
    release = asyncio.Event()

    async def block():
        entered.set()
        await release.wait()

    async def exercise():
        global expected_connect
        consumer = preparation(calls, job=expected_job, run=block)
        expected_connect = consumer.connect
        install_owned(monkeypatch, calls)
        owner = LiveInstallationLifecycleOwner(preparation=consumer)
        request = asyncio.create_task(owner.run_once())
        await entered.wait()
        with pytest.raises(RuntimeError, match="already in progress"):
            await owner.run_once()
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        closing = asyncio.create_task(owner.stop())
        await asyncio.sleep(0)
        assert not closing.done() and "stop" not in calls
        with pytest.raises(RuntimeError, match="closing"):
            await owner.run_once()
        release.set()
        await closing

    asyncio.run(exercise())
    assert calls == ["runtime-apply", "runtime-verify", "enable", "stop"]
