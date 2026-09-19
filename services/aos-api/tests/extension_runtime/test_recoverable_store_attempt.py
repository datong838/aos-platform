from threading import Event

import pytest

from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.recoverable_store_attempt import (
    MAX_RECOVERABLE_STORE_EXECUTION_SECONDS,
    RecoverableStoreAttempt,
    RecoverableStoreAttemptOwner,
    _terminal_failure,
)


def _attempt_for_cancellation():
    attempt = object.__new__(RecoverableStoreAttempt)
    attempt._stop = Event()
    return attempt


def test_attempt_cancellation_combines_heartbeat_and_caller_stop():
    caller = Event()
    attempt = _attempt_for_cancellation()
    combined = attempt.cancellation(caller)

    assert combined.is_set() is False
    assert combined.wait(0.01) is False

    caller.set()
    assert combined.is_set() is True
    assert combined.wait(0) is True

    caller.clear()
    attempt._stop.set()
    assert combined.is_set() is True
    assert combined.wait(0) is True


@pytest.mark.parametrize(
    ("exc", "heartbeat", "stopped", "expected"),
    [
        (IngressJournalConflict("INGRESS_CANCELLED"), None, True,
         ("RECOVERABLE_INGRESS_CANCELLED", "IngressJournalConflict")),
        (IngressJournalConflict("INGRESS_DEADLINE_EXCEEDED"), None, True,
         ("RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict")),
        (ValueError("raw provider response must not persist"), None, True,
         ("RECOVERABLE_EXECUTION_EXCEPTION", "ValueError")),
        (ValueError("business"), RuntimeConflict("renewal"), True,
         ("RECOVERABLE_HEARTBEAT_FAILED", "RuntimeConflict")),
        (ValueError("business"), RuntimeConflict("stop"), False,
         ("RECOVERABLE_HEARTBEAT_STOP_TIMEOUT", "RuntimeConflict")),
    ],
)
def test_terminal_failure_is_fixed_and_never_contains_raw_message(
    exc, heartbeat, stopped, expected,
):
    assert _terminal_failure(exc, heartbeat, stopped) == expected


def test_terminal_failure_replaces_unsafe_exception_type():
    unsafe = type("坏异常", (Exception,), {})
    assert _terminal_failure(unsafe("secret"), None, True) == (
        "RECOVERABLE_EXECUTION_EXCEPTION", "Exception",
    )


def test_heartbeat_deadline_uses_execution_deadline_reason():
    deadline = IngressJournalConflict("INGRESS_DEADLINE_EXCEEDED")
    assert _terminal_failure(None, deadline, True) == (
        "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict",
    )


@pytest.mark.parametrize(
    "seconds", (0.05, MAX_RECOVERABLE_STORE_EXECUTION_SECONDS + 1, float("inf")),
)
def test_attempt_owner_requires_bounded_execution_lifetime(seconds):
    with pytest.raises(ValueError, match="bounded recoverable Store heartbeat"):
        RecoverableStoreAttemptOwner(
            connect=lambda: None, heartbeat_seconds=.05,
            lease_seconds=.2, max_execution_seconds=seconds,
        )


def test_real_saved_group_budget_remains_finite_and_bounded():
    owner = RecoverableStoreAttemptOwner(connect=lambda: None)
    assert MAX_RECOVERABLE_STORE_EXECUTION_SECONDS == 1800.0
    assert owner._max_execution_seconds == MAX_RECOVERABLE_STORE_EXECUTION_SECONDS
