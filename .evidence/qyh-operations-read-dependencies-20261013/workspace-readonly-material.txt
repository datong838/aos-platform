"""Compose formal cross-domain facts into a read-only operation case workspace."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
from typing import Literal

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_aftersale_event_reader import (
    AftersaleEventOriginal,
    EcommerceAftersaleEventReader,
    EcommerceAftersaleEventReaderError,
)
from aos_api.ecommerce_inventory_reader import (
    EcommerceInventoryReader,
    EcommerceInventoryReaderError,
)
from aos_api.ecommerce_operation_case_contracts import (
    ExactAuthorityRevisionRef,
    ExactOriginalRef,
    OperationCaseRevision,
    OperationCaseStatus,
)
from aos_api.ecommerce_operation_case_store import (
    OperationAuthorityReadError,
    OperationAuthorityStore,
)
from aos_api.ecommerce_operation_case_workspace_contracts import (
    OperationCaseCandidateKind,
    OperationCaseMemberLedger,
    OperationCaseWorkspaceBlocker,
    OperationCaseWorkspaceCandidate,
    OperationCaseWorkspaceCase,
    OperationCaseWorkspaceEnvelope,
    OperationCaseWorkspaceLedger,
    OperationCaseWorkspaceSource,
    OperationCaseWorkspaceSourceId,
    OperationCaseWorkspaceSourceStatus,
    OperationCaseWorkspaceStatus,
)
from aos_api.ecommerce_operations_object_reader import (
    EcommerceOperationsObjectReader,
    OperationsObjectReadError,
    OperationsObjectRef,
)
from aos_api.tenant_scope import TenantScope


Clock = Callable[[], datetime]
_TRANSACTION_SOURCES = {
    OperationCaseWorkspaceSourceId.ORDERS: "Order",
    OperationCaseWorkspaceSourceId.SHIPMENTS: "Shipment",
    OperationCaseWorkspaceSourceId.PAYMENTS: "Payment",
}
_FAILURE_CODES = {
    OperationCaseWorkspaceSourceId.ORDERS: "OPERATION_CASE_ORDERS_READ_FAILED",
    OperationCaseWorkspaceSourceId.INVENTORY: "OPERATION_CASE_INVENTORY_READ_FAILED",
    OperationCaseWorkspaceSourceId.SHIPMENTS: "OPERATION_CASE_SHIPMENTS_READ_FAILED",
    OperationCaseWorkspaceSourceId.AFTERSALE_EVENTS: "OPERATION_CASE_AFTERSALES_READ_FAILED",
    OperationCaseWorkspaceSourceId.PAYMENTS: "OPERATION_CASE_PAYMENTS_READ_FAILED",
    OperationCaseWorkspaceSourceId.OPERATION_CASES: "OPERATION_CASE_AUTHORITY_READ_FAILED",
}
_MEMBER_FIELDS = {
    "Order": "orders",
    "OrderLine": "order_lines",
    "ProductSku": "inventory",
    "Shipment": "shipments",
    "Payment": "payments",
    "AfterSalesEvent": "aftersale_events",
}


def _bare_hash(value: str) -> str:
    return value.removeprefix("sha256:")


def _member_key(item: ExactOriginalRef) -> tuple[str, str, str, str, str]:
    return (
        item.tenant.org_id,
        item.tenant.project_id,
        item.resource_type,
        item.resource_id,
        item.content_hash,
    )


class EcommerceOperationCaseWorkspace:
    def __init__(
        self,
        *,
        clock: Clock | None = None,
        object_reader: EcommerceOperationsObjectReader | None = None,
        inventory_reader: EcommerceInventoryReader | None = None,
        aftersale_reader: EcommerceAftersaleEventReader | None = None,
        case_store: OperationAuthorityStore | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._object_reader = object_reader or EcommerceOperationsObjectReader()
        self._inventory_reader = inventory_reader or EcommerceInventoryReader()
        self._aftersale_reader = aftersale_reader or EcommerceAftersaleEventReader()
        self._case_store = case_store or OperationAuthorityStore()

    def read(self, *, org_id: str, project_id: str) -> OperationCaseWorkspaceEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("operation case workspace clock requires a timezone")
        tenant = TenantContext(org_id=org_id, project_id=project_id)
        scope = TenantScope(org_id=org_id, project_id=project_id)
        facts: list[ExactOriginalRef] = []
        source_rows: dict[OperationCaseWorkspaceSourceId, list[object]] = {}
        blocked: set[OperationCaseWorkspaceSourceId] = set()

        for source_id, object_type in _TRANSACTION_SOURCES.items():
            try:
                rows = self._object_reader.read(
                    org_id=org_id, project_id=project_id,
                    object_type=object_type, cutoff=cutoff, limit=50,
                )
                source_rows[source_id] = rows
                facts.extend(self._transaction_ref(item, tenant=tenant) for item in rows)
            except OperationsObjectReadError:
                source_rows[source_id] = []
                blocked.add(source_id)

        inventory_items: list[object] = []
        try:
            inventory = self._inventory_reader.read(
                org_id=org_id, project_id=project_id, cutoff=cutoff, limit=50,
            )
            inventory_items = list(inventory.items)
            source_rows[OperationCaseWorkspaceSourceId.INVENTORY] = inventory_items
            facts.extend(self._inventory_ref(item, tenant=tenant) for item in inventory_items)
        except EcommerceInventoryReaderError:
            source_rows[OperationCaseWorkspaceSourceId.INVENTORY] = []
            blocked.add(OperationCaseWorkspaceSourceId.INVENTORY)

        aftersale_items: list[AftersaleEventOriginal] = []
        try:
            aftersale_items = self._aftersale_reader.read(
                org_id=org_id, project_id=project_id, cutoff=cutoff, limit=50,
            )
            source_rows[OperationCaseWorkspaceSourceId.AFTERSALE_EVENTS] = aftersale_items
            facts.extend(self._aftersale_ref(item, tenant=tenant) for item in aftersale_items)
        except EcommerceAftersaleEventReaderError:
            source_rows[OperationCaseWorkspaceSourceId.AFTERSALE_EVENTS] = []
            blocked.add(OperationCaseWorkspaceSourceId.AFTERSALE_EVENTS)

        cases: list[OperationCaseRevision] = []
        try:
            cases = self._case_store.list_cases(scope, limit=50)
            if any(
                case.tenant.org_id != org_id
                or case.tenant.project_id != project_id
                or any(
                    member.tenant.org_id != org_id
                    or member.tenant.project_id != project_id
                    for member in case.member_refs
                )
                for case in cases
            ):
                raise OperationAuthorityReadError("operation case tenant drift")
            source_rows[OperationCaseWorkspaceSourceId.OPERATION_CASES] = cases
        except OperationAuthorityReadError:
            cases = []
            source_rows[OperationCaseWorkspaceSourceId.OPERATION_CASES] = []
            blocked.add(OperationCaseWorkspaceSourceId.OPERATION_CASES)

        fact_by_key = {_member_key(item): item for item in facts}
        assigned_keys = {
            _member_key(member)
            for case in cases
            for member in case.member_refs
            if _member_key(member) in fact_by_key
        }
        available = [item for key, item in fact_by_key.items() if key not in assigned_keys]
        available_keys = {_member_key(item) for item in available}
        candidates = self._candidates(
            inventory_items=inventory_items,
            aftersale_items=aftersale_items,
            tenant=tenant,
            available_keys=available_keys,
        )
        sources = [
            self._source(source_id, source_rows[source_id], source_id in blocked)
            for source_id in OperationCaseWorkspaceSourceId
        ]
        if not blocked:
            status = OperationCaseWorkspaceStatus.READY
        elif len(blocked) == len(OperationCaseWorkspaceSourceId):
            status = OperationCaseWorkspaceStatus.BLOCKED
        else:
            status = OperationCaseWorkspaceStatus.PARTIAL
        case_views = [self._case_view(item) for item in cases]
        return OperationCaseWorkspaceEnvelope(
            tenant=tenant,
            status=status,
            evaluated_at=cutoff,
            data_cutoff=cutoff,
            sources=sources,
            cases=case_views,
            candidates=candidates,
            available_refs=available,
            ledger=OperationCaseWorkspaceLedger(
                source_total=len(fact_by_key),
                assigned=len(assigned_keys),
                unassigned=len(available),
                candidates=len(candidates),
                open_cases=sum(item.status is OperationCaseStatus.OPEN for item in cases),
                paused_cases=sum(item.status is OperationCaseStatus.PAUSED for item in cases),
                closed_cases=sum(item.status is OperationCaseStatus.CLOSED for item in cases),
            ),
            external_effect_allowed=False,
        )

    @staticmethod
    def _source(
        source_id: OperationCaseWorkspaceSourceId,
        rows: list[object],
        failed: bool,
    ) -> OperationCaseWorkspaceSource:
        if failed:
            return OperationCaseWorkspaceSource(
                source_id=source_id,
                status=OperationCaseWorkspaceSourceStatus.BLOCKED,
                count=0,
                blocker=OperationCaseWorkspaceBlocker(
                    code=_FAILURE_CODES[source_id],
                    required_action="重新核对当前租户同一数据截止的正式来源",
                ),
            )
        return OperationCaseWorkspaceSource(
            source_id=source_id,
            status=OperationCaseWorkspaceSourceStatus.READY,
            count=len(rows),
            blocker=None,
        )

    @staticmethod
    def _transaction_ref(item: OperationsObjectRef, *, tenant: TenantContext) -> ExactOriginalRef:
        return ExactOriginalRef(
            tenant=tenant,
            resource_type=item.object_type,
            resource_id=item.object_id,
            content_hash=_bare_hash(item.content_hash),
            source_updated_at=item.source_updated_at,
        )

    @staticmethod
    def _inventory_ref(item: object, *, tenant: TenantContext) -> ExactOriginalRef:
        return ExactOriginalRef(
            tenant=tenant,
            resource_type="ProductSku",
            resource_id=getattr(item, "object_id"),
            content_hash=_bare_hash(getattr(getattr(item, "revision"), "content_hash")),
            source_updated_at=getattr(item, "source_updated_at"),
        )

    @staticmethod
    def _aftersale_ref(item: AftersaleEventOriginal, *, tenant: TenantContext) -> ExactOriginalRef:
        return ExactOriginalRef(
            tenant=tenant,
            resource_type="AfterSalesEvent",
            resource_id=item.event_id,
            content_hash=item.source_hash,
            source_updated_at=item.occurred_at,
        )

    @staticmethod
    def _member_ledger(members: list[ExactOriginalRef]) -> OperationCaseMemberLedger:
        counts = Counter(_MEMBER_FIELDS[item.resource_type] for item in members)
        return OperationCaseMemberLedger(
            orders=counts["orders"],
            order_lines=counts["order_lines"],
            inventory=counts["inventory"],
            shipments=counts["shipments"],
            payments=counts["payments"],
            aftersale_events=counts["aftersale_events"],
            total=len(members),
        )

    @classmethod
    def _case_view(cls, item: OperationCaseRevision) -> OperationCaseWorkspaceCase:
        return OperationCaseWorkspaceCase(
            case_ref=ExactAuthorityRevisionRef(
                resource_id=item.case_id,
                revision=item.revision,
                content_hash=item.content_hash,
            ),
            version=item.version,
            status=item.status,
            priority=item.priority,
            member_refs=item.member_refs,
            member_ledger=cls._member_ledger(item.member_refs),
        )

    @classmethod
    def _candidates(
        cls,
        *,
        inventory_items: list[object],
        aftersale_items: list[AftersaleEventOriginal],
        tenant: TenantContext,
        available_keys: set[tuple[str, str, str, str, str]],
    ) -> list[OperationCaseWorkspaceCandidate]:
        candidates: list[OperationCaseWorkspaceCandidate] = []
        for item in inventory_items:
            missing = [
                label
                for label, value in (
                    ("库存数量", getattr(item, "stock")),
                    ("告警阈值", getattr(item, "stock_alarm")),
                    ("库存健康", getattr(item, "stock_health")),
                )
                if value is None
            ]
            if not missing:
                continue
            ref = cls._inventory_ref(item, tenant=tenant)
            if _member_key(ref) not in available_keys:
                continue
            candidates.append(cls._candidate(
                kind=OperationCaseCandidateKind.INVENTORY_DATA_GAP,
                title="库存资料待核对",
                summary=f"商品库存缺少{'、'.join(missing)}，需补齐正式来源后再处理。",
                priority="high",
                ref=ref,
            ))
        for item in aftersale_items:
            ref = cls._aftersale_ref(item, tenant=tenant)
            if _member_key(ref) not in available_keys:
                continue
            candidates.append(cls._candidate(
                kind=OperationCaseCandidateKind.AFTERSALE_FOLLOWUP,
                title="售后事项待处理",
                summary=(
                    f"售后事项类型为 {item.event_type}、状态为 {item.status}，"
                    "需运营人员确认内部处理路径。"
                ),
                priority="normal",
                ref=ref,
            ))
        return candidates

    @staticmethod
    def _candidate(
        *,
        kind: OperationCaseCandidateKind,
        title: str,
        summary: str,
        priority: Literal["normal", "high"],
        ref: ExactOriginalRef,
    ) -> OperationCaseWorkspaceCandidate:
        identity = f"{kind.value}:{ref.resource_type}:{ref.resource_id}:{ref.content_hash}"
        return OperationCaseWorkspaceCandidate(
            candidate_id=hashlib.sha256(identity.encode()).hexdigest(),
            kind=kind,
            title=title,
            summary=summary,
            priority=priority,
            member_refs=[ref],
            external_effect_allowed=False,
        )


__all__ = ["EcommerceOperationCaseWorkspace"]
