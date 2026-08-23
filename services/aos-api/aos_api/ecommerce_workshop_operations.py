"""Tenant-bound, read-only W2-01A Operations view shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_data_authority import EcommerceDataAuthority
from aos_api.ecommerce_data_authority_contracts import (
    EcommerceDataAuthorityDescriptor,
)
from aos_api.ecommerce_workshop_operations_contracts import (
    OperationsAuthorityRef,
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
        "INVENTORY_READER_NOT_WIRED",
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
        "AFTERSALE_EVENTS_READER_NOT_WIRED",
    ),
    OperationsSliceId.OPERATION_CASES: (
        "workshop.w3-12a-operation-case-authority",
        "OPERATION_CASES_AUTHORITY_NOT_READY",
    ),
}


class EcommerceWorkshopOperations:
    """Expose the honest seven-slice shape without inventing business facts."""

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        data_authority: EcommerceDataAuthority | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._data_authority = data_authority or EcommerceDataAuthority()

    def read(self, *, org_id: str, project_id: str) -> WorkshopOperationsViewEnvelope:
        evaluated_at = self._clock()
        if evaluated_at.utcoffset() is None:
            raise ValueError("Operations clock must return a timezone-aware timestamp")
        authorities = {
            item.authority_id: item
            for item in self._data_authority.read_all(
                org_id=org_id,
                project_id=project_id,
            )
        }
        slices = []
        for slice_id in OperationsSliceId:
            dependency, code = _DEPENDENCIES[slice_id]
            authority_refs = self._authority_refs(slice_id, authorities)
            slices.append(
                OperationsSliceReadiness(
                    slice_id=slice_id,
                    status=OperationsSliceStatus.BLOCKED,
                    data_cutoff=evaluated_at,
                    authority_refs=authority_refs,
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

    @staticmethod
    def _authority_refs(
        slice_id: OperationsSliceId,
        authorities: dict[str, EcommerceDataAuthorityDescriptor],
    ) -> list[OperationsAuthorityRef]:
        authority_id = {
            OperationsSliceId.INVENTORY: "inventory.product-sku",
            OperationsSliceId.AFTERSALE_EVENTS: "aftersale.event",
        }.get(slice_id)
        if authority_id is None:
            return []
        authority = authorities[authority_id]
        return [
            OperationsAuthorityRef(
                resource_type=authority.resource_type,
                resource_id=authority.authority_id,
                revision=authority.semantic_revision,
                content_hash=authority.content_hash,
                receipt_id=authority.receipt_id,
            )
        ]


__all__ = ["EcommerceWorkshopOperations"]
