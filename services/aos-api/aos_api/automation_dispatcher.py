"""Generic fail-closed dispatcher for persistent automation occurrences."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ClaimedOccurrence, ClaimTarget
from aos_api.tenant_scope import TenantScope


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
    except Exception:
        authority.mark_needs_attention(
            scope,
            occurrence_id=claimed.occurrence_id,
            owner=owner,
            occurred_at=occurred_at,
        )
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
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
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
    except Exception:
        store.mark_needs_attention(
            scope, occurrence_id=claimed.occurrence_id, owner=owner, occurred_at=clock()
        )
        return False
    # Cancellation propagates; a failed commit leaves the original claim for reconciliation.
    store.record_target_receipt(
        scope, occurrence_id=claimed.occurrence_id, owner=owner,
        receipt_ref=receipt, occurred_at=clock(),
    )
    return True


__all__ = ["dispatch_one_occurrence", "dispatch_one_occurrence_async"]
