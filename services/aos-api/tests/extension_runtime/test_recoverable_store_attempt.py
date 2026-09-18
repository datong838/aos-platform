import pytest

from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.recoverable_store_attempt import _terminal_failure


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
