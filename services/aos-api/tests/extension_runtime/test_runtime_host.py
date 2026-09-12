from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from aos_api.extension_runtime.configuration_consumer import ConfigurationConsumer
from aos_api.extension_runtime.disable_consumer import RuntimeDisableConsumer
from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, DisableDeliveryResult
from aos_api.extension_runtime.generation_attempts import ExpiredSignedReadAttemptRecovery
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery, RecoveryPage
from aos_api.extension_runtime.runtime_host import RuntimeHost, RuntimeTenantAssignment
from aos_api.extension_runtime.live_installation_owner import LiveInstallationLifecycleOwner
from aos_api.extension_runtime.live_installation_scheduler import (
    LiveInstallationScheduler,
    LiveInstallationSchedulerTick,
)
from aos_api.extension_runtime.outbox_store import OutboxLease
from aos_api.tenant_scope import TenantScope


def recovery(pages, calls, *, after_call=None):
    worker = object.__new__(ExpiredResourceRecovery)
    pages = iter(pages)

    def run_batch(**kwargs):
        calls.append(("recovery", kwargs))
        result = next(pages)
        if after_call is not None:
            after_call()
        return result

    worker.run_batch = run_batch
    return worker


def configuration(calls, *, result=None, action=None):
    consumer = object.__new__(ConfigurationConsumer)

    def run_once(**scope):
        calls.append(("configuration", scope))
        if action is not None:
            action()
        return result

    consumer.run_once = run_once
    return consumer


def disable(calls):
    consumer = object.__new__(RuntimeDisableConsumer)
    consumer.run_once = lambda **scope: calls.append(("disable", scope))
    return consumer


def lifecycle(calls, tenant, *, installation=None, action=None, failure=None,
              revoke_failure=None):
    scheduler = object.__new__(LiveInstallationScheduler)
    scheduler.directory = SimpleNamespace(scope=tenant)
    owner = object.__new__(LiveInstallationLifecycleOwner) if installation else None

    async def run_once():
        calls.append(("lifecycle", tenant.key))
        if action is not None:
            action()
        if failure is not None:
            raise failure
        return LiveInstallationSchedulerTick(())

    async def revoke(target, expected):
        assert target == installation and expected is owner
        calls.append(("revoke", target))
        if revoke_failure is not None:
            raise revoke_failure

    async def stop():
        calls.append(("lifecycle-stop", tenant.key))

    scheduler.run_once = run_once
    scheduler.find_owner = lambda target: owner if target == installation else None
    scheduler.revoke = revoke
    scheduler.stop = stop
    return scheduler


def coordinated_disable(calls, tenant, installation, *, status='succeeded'):
    consumer = object.__new__(RuntimeDisableConsumer)
    lease = OutboxLease(
        UUID(int=80), UUID(int=81), 1, "operation-accepted", 1,
        datetime.now(timezone.utc),
    )
    claimed = ClaimedDisableDelivery(tenant, lease, installation)

    def claim_once(**scope):
        calls.append(("disable-claim", scope))
        return claimed

    def finish_claimed(value):
        assert value is claimed
        calls.append(("disable-finish", installation))
        return DisableDeliveryResult(lease.operation_id,status,'acknowledged' if status=='succeeded' else 'deferred')

    consumer.claim_once = claim_once
    consumer.finish_claimed = finish_claimed
    return consumer


def attempt_recovery(calls, *, result=(), action=None):
    worker = object.__new__(ExpiredSignedReadAttemptRecovery)

    def run_once(**scope):
        calls.append(("attempt-recovery", scope))
        if action is not None:
            action()
        return result

    worker.run_once = run_once
    return worker


def scope(org, project):
    return TenantScope(org, project)


async def wait_for_thread_event(event, timeout=2):
    deadline = time.monotonic() + timeout
    while not event.is_set():
        assert time.monotonic() < deadline, "worker thread did not enter"
        await asyncio.sleep(0.005)


def test_assignment_rejects_untrusted_and_empty_workers():
    with pytest.raises(TypeError):
        RuntimeTenantAssignment(scope("a", "b"), recovery=object())
    with pytest.raises(TypeError):
        RuntimeTenantAssignment(scope("a", "b"), attempt_recovery=object())
    with pytest.raises(TypeError):
        RuntimeTenantAssignment(scope("a", "b"), consumers=(object(),))
    with pytest.raises(ValueError):
        RuntimeTenantAssignment(scope("a", "b"))
    with pytest.raises(ValueError, match="duplicate"):
        RuntimeTenantAssignment(
            scope("a", "b"), consumers=(configuration([]), configuration([]))
        )


def test_consumer_order_is_fixed_independent_of_input_order():
    calls = []
    assignment = RuntimeTenantAssignment(
        scope("org", "project"), consumers=(disable(calls), configuration(calls))
    )
    asyncio.run(RuntimeHost(assignments=lambda: (assignment,)).run_once())
    assert [call[0] for call in calls] == ["configuration", "disable"]


def test_lifecycle_runs_after_recovery_before_configure_and_claimed_disable_revoke():
    calls = []
    tenant = scope("org", "project")
    installation = UUID(int=90)
    scheduler = lifecycle(calls, tenant, installation=installation)
    assignment = RuntimeTenantAssignment(
        tenant,
        recovery=recovery((RecoveryPage((), None),), calls),
        attempt_recovery=attempt_recovery(calls),
        lifecycle=scheduler,
        consumers=(configuration(calls), coordinated_disable(calls, tenant, installation)),
    )
    result = asyncio.run(RuntimeHost(assignments=lambda: (assignment,)).run_once())
    assert [item[0] for item in calls] == [
        "recovery", "attempt-recovery", "lifecycle", "configuration",
        "disable-claim", "disable-finish", "revoke",
    ]
    assert type(result.tenants[0].lifecycle) is LiveInstallationSchedulerTick
    assert result.tenants[0].deliveries[0] is None
    assert result.tenants[0].deliveries[1].operation_status=='succeeded'


def test_assignment_replacement_after_lifecycle_stops_old_before_consumer():
    calls = []
    current = None

    def replace():
        nonlocal current
        current = RuntimeTenantAssignment(
            scope("org", "project"), consumers=(configuration(calls),)
        )

    original = RuntimeTenantAssignment(
        scope("org", "project"),
        lifecycle=lifecycle(calls, scope("org", "project"), action=replace),
    )
    current = original
    result = asyncio.run(RuntimeHost(assignments=lambda: (current,)).run_once())
    assert [item[0] for item in calls] == ["lifecycle", "lifecycle-stop"]
    assert result.tenants[0].deliveries == ()


def test_failed_lifecycle_tick_still_cleans_scheduler_on_host_stop():
    calls = []
    assignment = RuntimeTenantAssignment(
        scope("org", "project"),
        lifecycle=lifecycle(calls, scope("org", "project"), failure=RuntimeError("tick failed")),
    )

    async def exercise():
        host = RuntimeHost(assignments=lambda: (assignment,))
        with pytest.raises(RuntimeError, match="tick failed"):
            await host.run_once()
        with pytest.raises(RuntimeError, match="tick failed"):
            await host.stop()

    asyncio.run(exercise())
    assert [item[0] for item in calls] == ["lifecycle", "lifecycle-stop"]


def test_disable_cleanup_failure_occurs_after_committed_disable():
    calls = []
    tenant = scope("org", "project")
    installation = UUID(int=91)
    assignment = RuntimeTenantAssignment(
        tenant,
        lifecycle=lifecycle(
            calls, tenant, installation=installation,
            revoke_failure=RuntimeError("cleanup uncertain"),
        ),
        consumers=(coordinated_disable(calls, tenant, installation),),
    )
    with pytest.raises(RuntimeError, match="cleanup uncertain"):
        asyncio.run(RuntimeHost(assignments=lambda: (assignment,)).run_once())
    assert [item[0] for item in calls] == [
        "lifecycle", "disable-claim", "disable-finish", "revoke",
    ]


@pytest.mark.parametrize('status',['running','failed','cancelled'])
def test_unfinished_or_failed_disable_does_not_release_owner(status):
    calls=[];tenant=scope('org','project');installation=UUID(int=92)
    assignment=RuntimeTenantAssignment(tenant,
        lifecycle=lifecycle(calls,tenant,installation=installation),
        consumers=(coordinated_disable(calls,tenant,installation,status=status),))
    result=asyncio.run(RuntimeHost(assignments=lambda:(assignment,)).run_once())
    assert result.tenants[0].deliveries[0].operation_status==status
    assert 'revoke' not in [item[0] for item in calls]


def test_tick_sorts_tenants_and_runs_recoveries_before_concrete_consumers():
    calls = []
    recovered = UUID("00000000-0000-0000-0000-000000000008")
    one = RuntimeTenantAssignment(
        scope("org-b", "project"),
        consumers=(configuration(calls, result="b"),),
    )
    two = RuntimeTenantAssignment(
        scope("org-a", "project"),
        recovery=recovery((RecoveryPage((), None),), calls),
        attempt_recovery=attempt_recovery(calls, result=(recovered,)),
        consumers=(configuration(calls, result="a"),),
    )
    result = asyncio.run(RuntimeHost(assignments=lambda: (one, two)).run_once())
    assert [item.scope.org_id for item in result.tenants] == ["org-a", "org-b"]
    assert [item[0] for item in calls] == [
        "recovery",
        "attempt-recovery",
        "configuration",
        "configuration",
    ]
    assert result.tenants[0].recovered_attempts == (recovered,)
    assert result.tenants[0].deliveries == ("a",)


def test_recovery_cursor_returns_to_origin_after_empty_page():
    calls = []
    marker = UUID("00000000-0000-0000-0000-000000000007")
    worker = recovery(
        (
            RecoveryPage(((marker, "busy"),), marker),
            RecoveryPage((), marker),
            RecoveryPage(((marker, "released"),), marker),
        ),
        calls,
    )
    host = RuntimeHost(
        assignments=lambda: (RuntimeTenantAssignment(scope("org", "project"), worker),)
    )

    async def exercise():
        await host.run_once()
        await host.run_once()
        await host.run_once()

    asyncio.run(exercise())
    assert [call[1]["after"] for call in calls] == [None, marker, None]


@pytest.mark.parametrize("value", [[], iter(()), (object(),)])
def test_assignment_source_must_return_typed_bounded_tuple(value):
    with pytest.raises(TypeError):
        asyncio.run(RuntimeHost(assignments=lambda: value).run_once())


def test_assignment_source_rejects_runtime_assignment_subclass():
    class ForgedAssignment(RuntimeTenantAssignment):
        pass

    forged = ForgedAssignment(
        scope("org", "project"), consumers=(configuration([]),)
    )
    with pytest.raises(TypeError, match="invalid runtime assignment"):
        asyncio.run(RuntimeHost(assignments=lambda: (forged,)).run_once())


def test_async_assignment_source_is_rejected_without_starting_it():
    async def assignments():
        return ()

    with pytest.raises(ValueError):
        RuntimeHost(assignments=assignments)


def test_duplicate_tenant_assignments_are_rejected_before_work():
    calls = []
    first = RuntimeTenantAssignment(scope("org", "project"), consumers=(configuration(calls),))
    second = RuntimeTenantAssignment(scope("org", "project"), consumers=(configuration(calls),))
    with pytest.raises(ValueError, match="duplicate"):
        asyncio.run(RuntimeHost(assignments=lambda: (first, second)).run_once())
    assert calls == []


def test_failed_tenant_stops_tick_without_running_later_tenants():
    calls = []

    def fail():
        raise RuntimeError("fixed failure")

    first = RuntimeTenantAssignment(scope("org-a", "project"), consumers=(configuration(calls, action=fail),))
    second = RuntimeTenantAssignment(scope("org-b", "project"), consumers=(configuration(calls),))
    with pytest.raises(RuntimeError, match="fixed failure"):
        asyncio.run(RuntimeHost(assignments=lambda: (second, first)).run_once())
    assert calls == [("configuration", {"org_id": "org-a", "project_id": "project"})]


def test_only_one_tick_and_cancellation_waits_for_sync_worker_to_settle():
    entered = threading.Event()
    release = threading.Event()

    def block():
        entered.set()
        release.wait(timeout=2)

    assignment = RuntimeTenantAssignment(
        scope("org", "project"),
        consumers=(configuration([], result="settled", action=block),),
    )
    host = RuntimeHost(assignments=lambda: (assignment,))

    async def exercise():
        first = asyncio.create_task(host.run_once())
        try:
            await wait_for_thread_event(entered)
            with pytest.raises(RuntimeError, match="already in progress"):
                await host.run_once()
            first.cancel()
            await asyncio.sleep(0)
            assert first.cancelled()
            closing = asyncio.create_task(host.stop())
            await asyncio.sleep(0)
            assert not closing.done()
            with pytest.raises(RuntimeError, match="closing"):
                await host.run_once()
            release.set()
            await closing
        finally:
            release.set()

    asyncio.run(exercise())


def test_serve_stops_without_starting_another_tick():
    calls = []
    stop = asyncio.Event()

    def stops():
        stop.set()

    assignment = RuntimeTenantAssignment(
        scope("org", "project"), consumers=(configuration([], action=stops),)
    )
    host = RuntimeHost(assignments=lambda: (assignment,))
    asyncio.run(host.serve(stop, interval_seconds=1))
    assert stop.is_set()


def test_revoked_assignment_after_recovery_does_not_enter_consumer():
    calls = []
    current = True

    def revoke():
        nonlocal current
        current = False

    assignment = RuntimeTenantAssignment(
        scope("org", "project"),
        recovery=recovery((RecoveryPage((), None),), calls, after_call=revoke),
        consumers=(configuration(calls),),
    )
    host = RuntimeHost(assignments=lambda: (assignment,) if current else ())
    result = asyncio.run(host.run_once())
    assert [call[0] for call in calls] == ["recovery"]
    assert result.tenants[0].deliveries == ()


def test_revoked_assignment_after_attempt_recovery_does_not_enter_consumer():
    calls = []
    current = True

    def revoke():
        nonlocal current
        current = False

    assignment = RuntimeTenantAssignment(
        scope("org", "project"),
        attempt_recovery=attempt_recovery(calls, action=revoke),
        consumers=(configuration(calls),),
    )
    host = RuntimeHost(assignments=lambda: (assignment,) if current else ())
    result = asyncio.run(host.run_once())
    assert [call[0] for call in calls] == ["attempt-recovery"]
    assert result.tenants[0].deliveries == ()


def test_replaced_assignment_for_same_scope_revokes_old_worker():
    calls = []
    current = None

    def replace():
        nonlocal current
        current = RuntimeTenantAssignment(
            scope("org", "project"), consumers=(configuration(calls),)
        )

    original = RuntimeTenantAssignment(
        scope("org", "project"),
        recovery=recovery((RecoveryPage((), None),), calls, after_call=replace),
        consumers=(configuration(calls),),
    )
    current = original
    result = asyncio.run(RuntimeHost(assignments=lambda: (current,)).run_once())
    assert [call[0] for call in calls] == ["recovery"]
    assert result.tenants[0].deliveries == ()


def test_cancelled_caller_does_not_leave_unretrieved_tick_exception():
    entered = threading.Event()
    release = threading.Event()
    observed = []

    def fail_after_release():
        entered.set()
        release.wait(timeout=2)
        raise RuntimeError("background failure")

    assignment = RuntimeTenantAssignment(
        scope("org", "project"),
        consumers=(configuration([], action=fail_after_release),),
    )
    host = RuntimeHost(assignments=lambda: (assignment,))

    async def exercise():
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda _loop, context: observed.append(context))
        caller = asyncio.create_task(host.run_once())
        try:
            await wait_for_thread_event(entered)
            caller.cancel()
            with pytest.raises(asyncio.CancelledError):
                await caller
            release.set()
            await asyncio.sleep(0.05)
        finally:
            release.set()

    asyncio.run(exercise())
    assert observed == []
