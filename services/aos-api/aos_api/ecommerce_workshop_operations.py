"""Tenant-bound, read-only W2-01A Operations view shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import hashlib

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_aftersale_event_reader import (
    EcommerceAftersaleEventReader,
    EcommerceAftersaleEventReaderError,
)
from aos_api.ecommerce_data_authority import EcommerceDataAuthority
from aos_api.ecommerce_data_authority_contracts import (
    EcommerceDataAuthorityDescriptor,
)
from aos_api.ecommerce_inventory_reader import (
    EcommerceInventoryReader,
    EcommerceInventoryReaderError,
)
from aos_api.ecommerce_operation_case_store import (
    OperationAuthorityReadError,
    OperationAuthorityStore,
)
from aos_api.ecommerce_operations_object_reader import (
    EcommerceOperationsObjectReader,
    OperationsObjectReadError,
    OperationsObjectRef,
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
from aos_api.tenant_scope import TenantScope


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
_W3_12A_RECEIPT = "w3-12a3-operation-decision-append-code-20260824"
_W3_12A_SCHEMA_HASH = "sha256:" + hashlib.sha256(
    b"aos.ecommerce.operation-case-authority/w3-12a"
).hexdigest()
_W2_01B2_RECEIPT = "w2-01b2-transaction-slices-code-20260824"
_TRANSACTION_TYPES = {
    OperationsSliceId.ORDERS: "Order",
    OperationsSliceId.ORDER_LINES: "OrderLine",
    OperationsSliceId.SHIPMENTS: "Shipment",
    OperationsSliceId.PAYMENTS: "Payment",
}
_READ_FAILED_CODES = {
    OperationsSliceId.ORDERS: "ORDERS_READ_FAILED_CLOSED",
    OperationsSliceId.ORDER_LINES: "ORDER_LINES_READ_FAILED_CLOSED",
    OperationsSliceId.INVENTORY: "INVENTORY_READ_FAILED_CLOSED",
    OperationsSliceId.SHIPMENTS: "SHIPMENTS_READ_FAILED_CLOSED",
    OperationsSliceId.PAYMENTS: "PAYMENTS_READ_FAILED_CLOSED",
    OperationsSliceId.AFTERSALE_EVENTS: "AFTERSALE_EVENTS_READ_FAILED_CLOSED",
}


class EcommerceWorkshopOperations:
    """Compose bounded slice readiness without returning business payloads."""

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        data_authority: EcommerceDataAuthority | None = None,
        case_store: OperationAuthorityStore | None = None,
        object_reader: EcommerceOperationsObjectReader | None = None,
        inventory_reader: EcommerceInventoryReader | None = None,
        aftersale_reader: EcommerceAftersaleEventReader | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._data_authority = data_authority or EcommerceDataAuthority()
        self._case_store = case_store or OperationAuthorityStore()
        self._object_reader = object_reader or EcommerceOperationsObjectReader()
        self._inventory_reader = inventory_reader or EcommerceInventoryReader()
        self._aftersale_reader = aftersale_reader or EcommerceAftersaleEventReader()

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
        transaction_rows: dict[OperationsSliceId, list[OperationsObjectRef]] = {}
        transaction_errors: set[OperationsSliceId] = set()
        for slice_id, object_type in _TRANSACTION_TYPES.items():
            try:
                transaction_rows[slice_id] = self._object_reader.read(
                    org_id=org_id,
                    project_id=project_id,
                    object_type=object_type,
                    cutoff=evaluated_at,
                    limit=50,
                )
            except OperationsObjectReadError:
                transaction_errors.add(slice_id)
        inventory_error = False
        try:
            inventory = self._inventory_reader.read(
                org_id=org_id,
                project_id=project_id,
                cutoff=evaluated_at,
                limit=50,
            )
        except EcommerceInventoryReaderError:
            inventory = None
            inventory_error = True
        aftersale_error = False
        try:
            aftersale_events = self._aftersale_reader.read(
                org_id=org_id,
                project_id=project_id,
                cutoff=evaluated_at,
                limit=50,
            )
        except EcommerceAftersaleEventReaderError:
            aftersale_events = []
            aftersale_error = True
        case_error: OperationAuthorityReadError | None = None
        try:
            operation_cases = self._case_store.list_cases(
                scope=TenantScope(
                    org_id=org_id,
                    project_id=project_id,
                )
            )
        except OperationAuthorityReadError as exc:
            operation_cases = []
            case_error = exc
        slices = []
        for slice_id in OperationsSliceId:
            dependency, code = _DEPENDENCIES[slice_id]
            authority_refs = self._authority_refs(slice_id, authorities)
            if slice_id in _TRANSACTION_TYPES and slice_id not in transaction_errors:
                rows = transaction_rows[slice_id]
                slices.append(
                    self._ready_slice(
                        slice_id=slice_id,
                        evaluated_at=evaluated_at,
                        authority_refs=[self._transaction_authority_ref(slice_id)],
                        count=len(rows),
                    )
                )
                continue
            if slice_id is OperationsSliceId.INVENTORY and not inventory_error:
                slices.append(
                    self._ready_slice(
                        slice_id=slice_id,
                        evaluated_at=evaluated_at,
                        authority_refs=authority_refs,
                        count=len(inventory.items) if inventory is not None else 0,
                    )
                )
                continue
            if (
                slice_id is OperationsSliceId.AFTERSALE_EVENTS
                and not aftersale_error
            ):
                slices.append(
                    self._ready_slice(
                        slice_id=slice_id,
                        evaluated_at=evaluated_at,
                        authority_refs=authority_refs,
                        count=len(aftersale_events),
                    )
                )
                continue
            if slice_id is OperationsSliceId.OPERATION_CASES and case_error is None:
                refs = [
                    OperationsAuthorityRef(
                        resource_type="OperationCase",
                        resource_id=item.case_id,
                        revision=item.revision,
                        content_hash="sha256:" + item.content_hash,
                        receipt_id=_W3_12A_RECEIPT,
                    )
                    for item in operation_cases[:19]
                ]
                refs.insert(
                    0,
                    OperationsAuthorityRef(
                        resource_type="OperationCaseAuthority",
                        resource_id="w3-12a",
                        revision=1,
                        content_hash=_W3_12A_SCHEMA_HASH,
                        receipt_id=_W3_12A_RECEIPT,
                    ),
                )
                slices.append(
                    OperationsSliceReadiness(
                        slice_id=slice_id,
                        status=OperationsSliceStatus.READY,
                        data_cutoff=evaluated_at,
                        authority_refs=refs,
                        blockers=[],
                        count_ledger=OperationsCountLedger(
                            source_total=len(operation_cases),
                            attached=len(operation_cases),
                            unmatched=0,
                            conflicted=0,
                        ),
                    )
                )
                continue
            if slice_id in _READ_FAILED_CODES:
                code = _READ_FAILED_CODES[slice_id]
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
                count=sum(item.count_ledger.attached for item in slices),
                has_more=False,
                next_cursor=None,
            ),
        )

    @staticmethod
    def _ready_slice(
        *,
        slice_id: OperationsSliceId,
        evaluated_at: datetime,
        authority_refs: list[OperationsAuthorityRef],
        count: int,
    ) -> OperationsSliceReadiness:
        return OperationsSliceReadiness(
            slice_id=slice_id,
            status=OperationsSliceStatus.READY,
            data_cutoff=evaluated_at,
            authority_refs=authority_refs,
            blockers=[],
            count_ledger=OperationsCountLedger(
                source_total=count,
                attached=count,
                unmatched=0,
                conflicted=0,
            ),
        )

    @staticmethod
    def _transaction_authority_ref(
        slice_id: OperationsSliceId,
    ) -> OperationsAuthorityRef:
        object_type = _TRANSACTION_TYPES[slice_id]
        schema_id = f"aos.ecommerce.operations.{slice_id.value}-reader/v1"
        return OperationsAuthorityRef(
            resource_type=f"{object_type}ReadAuthority",
            resource_id=f"w2-01b2.{slice_id.value}",
            revision=1,
            content_hash="sha256:" + hashlib.sha256(schema_id.encode()).hexdigest(),
            receipt_id=_W2_01B2_RECEIPT,
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
