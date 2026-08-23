"""Tenant-bound, read-only W2-01A Operations view shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_operations_contracts import (
    OperationsBlocker,
    OperationsCountLedger,
    OperationsPageInfo,
    OperationsSliceId,
    OperationsSliceReadiness,
    OperationsSliceStatus,
    WorkshopOperationsViewEnvelope,
)


Clock = Callable[[], datetime]

_DEPENDENCIES = {
    OperationsSliceId.ORDERS: ("ecommerce.orders", "ORDERS_READER_NOT_WIRED"),
    OperationsSliceId.ORDER_LINES: (
        "ecommerce.order-lines",
        "ORDER_LINES_READER_NOT_WIRED",
    ),
    OperationsSliceId.INVENTORY: (
        "data.inventory-authority",
        "INVENTORY_AUTHORITY_NOT_READY",
    ),
    OperationsSliceId.SHIPMENTS: (
        "ecommerce.shipments",
        "SHIPMENTS_READER_NOT_WIRED",
    ),
    OperationsSliceId.PAYMENTS: (
        "ecommerce.payments",
        "PAYMENTS_READER_NOT_WIRED",
    ),
    OperationsSliceId.AFTERSALE_EVENTS: (
        "data.aftersale-event-authority",
        "AFTERSALE_EVENTS_AUTHORITY_NOT_READY",
    ),
    OperationsSliceId.OPERATION_CASES: (
        "workshop.w3-12a-operation-case-authority",
        "OPERATION_CASES_AUTHORITY_NOT_READY",
    ),
}


class EcommerceWorkshopOperations:
    """Expose the honest seven-slice shape without inventing business facts."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopOperationsViewEnvelope:
        evaluated_at = self._clock()
        if evaluated_at.utcoffset() is None:
            raise ValueError("Operations clock must return a timezone-aware timestamp")
        slices = []
        for slice_id in OperationsSliceId:
            dependency, code = _DEPENDENCIES[slice_id]
            slices.append(
                OperationsSliceReadiness(
                    slice_id=slice_id,
                    status=OperationsSliceStatus.BLOCKED,
                    data_cutoff=evaluated_at,
                    authority_refs=[],
                    blockers=[
                        OperationsBlocker(
                            code=code,
                            dependency=dependency,
                            required_action=(
                                "接入同租户、同截止时间、带 exact Receipt "
                                "的只读 authority"
                            ),
                        )
                    ],
                    count_ledger=OperationsCountLedger(
                        source_total=0,
                        attached=0,
                        unmatched=0,
                        conflicted=0,
                    ),
                )
            )
        return WorkshopOperationsViewEnvelope(
            tenant=TenantContext(org_id=org_id, project_id=project_id),
            evaluated_at=evaluated_at,
            data_cutoff=evaluated_at,
            slices=slices,
            page=OperationsPageInfo(
                limit=50,
                count=0,
                has_more=False,
                next_cursor=None,
            ),
        )


__all__ = ["EcommerceWorkshopOperations"]
