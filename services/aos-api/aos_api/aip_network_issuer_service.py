"""Private no-effect issuer inquiry; decision waits for durable attempt authority."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.aip_network_issuer_auth import authenticate_issuer_request
from aos_api.aip_network_issuer_contracts import (
    NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry,
)
from aos_api.aip_network_issuer_reconcile import (
    ReconcileResult, reconcile_approval_event_read_only,
)


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
