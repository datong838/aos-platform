"""Generic fail-closed dispatcher for persistent automation occurrences."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from pathlib import Path
from aos_api.logging_facade import get_logger

from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ClaimedOccurrence, ClaimTarget
from aos_api.tenant_scope import TenantScope


log = get_logger('aos-api.automation-dispatcher')


def _report_held_failure(scope, occurrence_id, error):
    """Metadata only: no exception text, source lines, locals, or payloads."""
    frames = []
    trace = error.__traceback__
    while trace is not None:
        code = trace.tb_frame.f_code
        frames.append((Path(code.co_filename).name, code.co_name, trace.tb_lineno))
        trace = trace.tb_next
    try:
        log.warning('automation_target_held scope=%s occurrence=%s error=%s locations=%s',
            scope.key, str(occurrence_id), type(error).__name__, frames[-6:])
    except Exception:
        # Diagnostic sinks must not undo the already persisted reconcile-only state.
        pass


TargetHandler = Callable[[ClaimedOccurrence], dict[str, Any]]


def dispatch_one_occurrence(
    scope: TenantScope,
    *,
    owner: str,
    occurred_at: datetime,
    handler: TargetHandler,
    store: AutomationOccurrenceStore | None = None,
) -> bool:
    """Dispatch once; an unknown handler outcome is held for Receipt reconciliation."""
    authority = store or AutomationOccurrenceStore()
    authority.reconcile_expired_claims(scope, now=occurred_at)
    claimed = authority.claim_next(scope, owner=owner, now=occurred_at)
    if claimed is None:
        return False
    try:
        receipt = handler(claimed)
        if not isinstance(receipt, dict) or not receipt:
            raise ValueError("handler returned no target Receipt")
    except Exception as error:
        authority.mark_needs_attention(
            scope,
            occurrence_id=claimed.occurrence_id,
            owner=owner,
            occurred_at=occurred_at,
        )
        _report_held_failure(scope, claimed.occurrence_id, error)
        return False
    authority.record_target_receipt(
        scope,
        occurrence_id=claimed.occurrence_id,
        owner=owner,
        receipt_ref=receipt,
        occurred_at=occurred_at,
    )
    return True


async def dispatch_one_occurrence_async(
    scope: TenantScope,
    *,
    owner: str,
    target: ClaimTarget,
    handler: Callable[[ClaimedOccurrence], Awaitable[dict[str, Any]]],
    store: AutomationOccurrenceStore,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC).replace(microsecond=0),
) -> bool:
    """Await one exact target; unknown outcomes remain reconcile-only."""
    if type(target) is not ClaimTarget:
        raise ValueError("async dispatch requires an exact claim target")
    started = clock()
    store.reconcile_expired_claims(scope, now=started)
    claimed = store.claim_next(scope, owner=owner, now=started, target=target)
    if claimed is None:
        return False
    try:
        receipt = await handler(claimed)
        if type(receipt) is not dict or not receipt:
            raise ValueError("handler returned no target Receipt")
    except Exception as error:
        store.mark_needs_attention(
            scope, occurrence_id=claimed.occurrence_id, owner=owner, occurred_at=clock()
        )
        _report_held_failure(scope, claimed.occurrence_id, error)
        return False
    # Cancellation propagates; a failed commit leaves the original claim for reconciliation.
    store.record_target_receipt(
        scope, occurrence_id=claimed.occurrence_id, owner=owner,
        receipt_ref=receipt, occurred_at=clock(),
    )
    return True


__all__ = ["dispatch_one_occurrence", "dispatch_one_occurrence_async"]
