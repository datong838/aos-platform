"""Private no-effect issuer inquiry; decision waits for durable attempt authority."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from aos_api.aip_network_issuer_auth import authenticate_issuer_request
from aos_api.aip_network_issuer_attempt import reserve_decision_attempt
from aos_api.aip_network_issuer_contracts import (
    NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry,
)
from aos_api.aip_network_issuer_reconcile import (
    ReconcileResult, ReconcileStatus, reconcile_approval_event_read_only,
)
from aos_api.aip_network_policy_action_producer import decide_network_activation


class IssuerServiceBlocked(RuntimeError):
    pass


def dispatch_issuer_request(
    request: NetworkIssuerDecisionCommand | NetworkIssuerDecisionInquiry,
    *,
    read_connect_factory: Callable[[], AbstractContextManager[Any]],
    expected_database: str,
) -> ReconcileResult:
    if type(request) is NetworkIssuerDecisionCommand:
        raise IssuerServiceBlocked("ISSUER_ATTEMPT_RECEIPT_REQUIRED")
    if (type(request) is not NetworkIssuerDecisionInquiry
            or not callable(read_connect_factory)
            or type(expected_database) is not str or not expected_database):
        raise IssuerServiceBlocked("ISSUER_READ_INTERFACE_INVALID")
    principal = authenticate_issuer_request(request)
    with read_connect_factory() as conn:
        return reconcile_approval_event_read_only(
            conn, request, expected_actor=principal.subject,
            expected_database=expected_database,
        )


def issue_decision_once(
    command: NetworkIssuerDecisionCommand,
    *,
    attempt_directory: str | Path,
    decision_connect_factory: Callable[..., AbstractContextManager[Any]],
    read_connect_factory: Callable[[], AbstractContextManager[Any]],
    expected_database: str,
) -> ReconcileResult:
    """Reserve durably, call decide at most once, then trust only exact Event readback."""
    if (type(command) is not NetworkIssuerDecisionCommand
            or not callable(decision_connect_factory)
            or not callable(read_connect_factory)
            or type(expected_database) is not str or not expected_database):
        raise IssuerServiceBlocked("ISSUER_DECISION_INTERFACE_INVALID")
    principal = authenticate_issuer_request(command)
    reserve_decision_attempt(attempt_directory, command, principal)
    try:
        decide_network_activation(
            principal, command.proposal_id, command.idempotency_key,
            command.decision, connect_factory=decision_connect_factory,
        )
    except Exception:
        # A DB commit may have succeeded before a disconnect. Never call decide again.
        pass
    try:
        with read_connect_factory() as conn:
            return reconcile_approval_event_read_only(
                conn, command.inquiry(), expected_actor=principal.subject,
                expected_database=expected_database,
            )
    except Exception:
        return ReconcileResult(ReconcileStatus.UNRESOLVED)
