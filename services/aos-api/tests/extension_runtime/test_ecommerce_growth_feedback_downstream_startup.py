"""Downstream feedback consumers require independent, default-off Host gates."""

import asyncio
from types import SimpleNamespace

import pytest

from aos_api.main import _start_feedback_downstream_workers


FLAGS = (
    "AOS_ECOM_IMPROVEMENT_WORKER_ENABLED",
    "AOS_ECOM_EFFECT_REVIEW_WORKER_ENABLED",
    "AOS_ECOM_MEMORY_CANDIDATE_WORKER_ENABLED",
)
STATES = (
    "ecommerce_improvement_worker_status",
    "ecommerce_effect_review_worker_status",
    "ecommerce_memory_candidate_worker_status",
)
TASKS = (
    "ecommerce_improvement_worker_task",
    "ecommerce_effect_review_worker_task",
    "ecommerce_memory_candidate_worker_task",
)


def app(host=None):
    return SimpleNamespace(state=SimpleNamespace(
        extension_runtime_host_task=host,
        extension_runtime_host_status="ACTIVE" if host is not None else "DISABLED",
        runtime_background_tasks=[],
    ))


def clear_flags(monkeypatch):
    for flag in FLAGS:
        monkeypatch.delenv(flag, raising=False)


def test_all_downstream_workers_are_off_by_default(monkeypatch):
    clear_flags(monkeypatch)
    application = app()
    asyncio.run(_start_feedback_downstream_workers(application, asyncio.Event()))
    assert [getattr(application.state, name) for name in STATES] == ["DISABLED"] * 3
    assert [getattr(application.state, name) for name in TASKS] == [None] * 3
    assert application.state.runtime_background_tasks == []


@pytest.mark.parametrize("index", range(3))
def test_invalid_flag_and_missing_host_fail_before_any_task(monkeypatch, index):
    clear_flags(monkeypatch)
    monkeypatch.setenv(FLAGS[index], "maybe")
    application = app()
    with pytest.raises(RuntimeError, match="flag is invalid"):
        asyncio.run(_start_feedback_downstream_workers(application, asyncio.Event()))
    assert getattr(application.state, STATES[index]) == "FAILED_CLOSED"
    assert application.state.runtime_background_tasks == []

    monkeypatch.setenv(FLAGS[index], "true")
    application = app()
    with pytest.raises(RuntimeError, match="active Runtime Host"):
        asyncio.run(_start_feedback_downstream_workers(application, asyncio.Event()))
    assert getattr(application.state, STATES[index]) == "FAILED_CLOSED"
    assert application.state.runtime_background_tasks == []


@pytest.mark.parametrize("index", range(3))
def test_each_worker_uses_distinct_runtime_identity_and_host_stop(monkeypatch, index):
    clear_flags(monkeypatch)
    monkeypatch.setenv(FLAGS[index], "true")
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main

    def missing_identity():
        raise RuntimeError("runtime identity missing")

    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", missing_identity)

    async def exercise_missing():
        host = asyncio.create_task(asyncio.sleep(10))
        application = app(host)
        try:
            with pytest.raises(RuntimeError, match="runtime identity missing"):
                await _start_feedback_downstream_workers(application, asyncio.Event())
            assert application.state.runtime_background_tasks == []
            assert getattr(application.state, STATES[index]) == "FAILED_CLOSED"
        finally:
            host.cancel()
            with pytest.raises(asyncio.CancelledError):
                await host

    asyncio.run(exercise_missing())

    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", lambda: "isolated-test-dsn")
    calls = []

    class Runner:
        async def serve(self, stop, *, host_ready):
            calls.append(host_ready())
            await stop.wait()

    builders = (
        "_build_ecommerce_improvement_consumer",
        "_build_ecommerce_effect_review_consumer",
        "_build_ecommerce_memory_candidate_consumer",
    )
    monkeypatch.setattr(main, builders[index], lambda: Runner())

    async def exercise_active():
        stop = asyncio.Event()
        host = asyncio.create_task(asyncio.sleep(10))
        application = app(host)
        try:
            await _start_feedback_downstream_workers(application, stop)
            assert getattr(application.state, STATES[index]) == "RUNNING"
            assert calls == [True]
            assert len(application.state.runtime_background_tasks) == 1
            stop.set()
            await getattr(application.state, TASKS[index])
            assert getattr(application.state, STATES[index]) == "STOPPED"
        finally:
            host.cancel()
            with pytest.raises(asyncio.CancelledError):
                await host

    asyncio.run(exercise_active())


@pytest.mark.parametrize("index", range(3))
def test_later_unknown_result_fails_worker_closed_without_restarting(monkeypatch, index):
    clear_flags(monkeypatch)
    monkeypatch.setenv(FLAGS[index], "true")
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main

    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", lambda: "isolated-test-dsn")
    builders = (
        "_build_ecommerce_improvement_consumer",
        "_build_ecommerce_effect_review_consumer",
        "_build_ecommerce_memory_candidate_consumer",
    )
    trigger = asyncio.Event()
    calls = []

    class Runner:
        async def serve(self, stop, *, host_ready):
            calls.append(host_ready())
            await trigger.wait()
            raise RuntimeError("unknown commit boundary")

    monkeypatch.setattr(main, builders[index], lambda: Runner())

    async def exercise():
        host = asyncio.create_task(asyncio.sleep(10))
        application = app(host)
        try:
            await _start_feedback_downstream_workers(application, asyncio.Event())
            assert getattr(application.state, STATES[index]) == "RUNNING"
            trigger.set()
            with pytest.raises(RuntimeError, match="unknown commit boundary"):
                await getattr(application.state, TASKS[index])
            assert getattr(application.state, STATES[index]) == "FAILED_CLOSED"
            assert calls == [True]
        finally:
            host.cancel()
            with pytest.raises(asyncio.CancelledError):
                await host

    asyncio.run(exercise())


def test_immediate_unexpected_worker_return_fails_startup(monkeypatch):
    clear_flags(monkeypatch)
    monkeypatch.setenv(FLAGS[2], "true")
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main

    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", lambda: "isolated-test-dsn")

    class Runner:
        async def serve(self, stop, *, host_ready):
            assert host_ready()

    monkeypatch.setattr(main, "_build_ecommerce_memory_candidate_consumer", lambda: Runner())

    async def exercise():
        host = asyncio.create_task(asyncio.sleep(10))
        application = app(host)
        try:
            with pytest.raises(RuntimeError, match="failed during startup"):
                await _start_feedback_downstream_workers(application, asyncio.Event())
            assert application.state.ecommerce_memory_candidate_worker_status == "FAILED_CLOSED"
            assert application.state.runtime_background_tasks == []
        finally:
            host.cancel()
            with pytest.raises(asyncio.CancelledError):
                await host

    asyncio.run(exercise())
