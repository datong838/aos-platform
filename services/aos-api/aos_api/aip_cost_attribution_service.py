"""Canonical cost attribution and exact capability receipt orchestration."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import (
    AttributionSubjectType,
    CapabilityReceipt,
    CapabilityReceiptIngestRequest,
    CostAttributionSummary,
    UsageAttribution,
    UsageAttributionRequest,
)
from aos_api.tenant_scope import TenantScope


class AipCostAttributionService:
    """Assign server identities and derive quality-separated cost summaries."""

    def __init__(self, store: AipEvalAuthorityStore | None = None) -> None:
        self._store = store or AipEvalAuthorityStore()

    def ingest_capability_receipt(
        self,
        scope: TenantScope,
        request: CapabilityReceiptIngestRequest,
    ) -> CapabilityReceipt:
        receipt = CapabilityReceipt(
            tenant=self._tenant(scope),
            capability_receipt_id=self._id(
                "capability", scope, request.provider, request.provider_receipt_id
            ),
            **request.model_dump(),
        )
        return self._store.append_capability_receipt(scope, receipt)

    def list_capability_receipts(
        self, scope: TenantScope, lineage_id: str
    ) -> list[CapabilityReceipt]:
        return self._store.list_capability_receipts(scope, lineage_id)

    def attribute_usage(
        self,
        scope: TenantScope,
        request: UsageAttributionRequest,
        *,
        created_at: datetime | None = None,
    ) -> UsageAttribution:
        receipt = self._store.get_usage_receipt(scope, request.receipt_id)
        attribution = UsageAttribution(
            tenant=self._tenant(scope),
            attribution_id=self._id(
                "attribution",
                scope,
                request.receipt_id,
                request.subject_type.value,
                request.subject.resource_id,
                request.subject.revision or "",
            ),
            lineage_id=receipt.lineage_id,
            created_at=created_at or datetime.now(UTC),
            **request.model_dump(),
        )
        return self._store.append_usage_attribution(scope, attribution)

    def summarize_cost(
        self,
        scope: TenantScope,
        *,
        subject_type: AttributionSubjectType,
        subject_id: str,
        subject_revision: str,
    ) -> list[CostAttributionSummary]:
        rows = self._store.cost_attribution_rows(
            scope,
            subject_type=subject_type.value,
            subject_id=subject_id,
            subject_revision=subject_revision,
        )
        buckets: dict[str, list[object]] = defaultdict(list)
        for row in rows:
            if row["usage_kind"] == "cost":
                buckets[str(row["currency"])].append(row)
        if not buckets:
            return [
                CostAttributionSummary(
                    tenant=self._tenant(scope),
                    subject_type=subject_type,
                    subject_id=subject_id,
                    subject_revision=subject_revision,
                    currency=None,
                    measured_amount=0,
                    estimated_amount=0,
                    unknown_receipt_count=1,
                    receipt_count=0,
                    hard_budget_eligible=False,
                    hard_budget_amount=None,
                )
            ]
        return [
            self._summarize_bucket(
                scope,
                subject_type,
                subject_id,
                subject_revision,
                currency,
                bucket,
            )
            for currency, bucket in sorted(buckets.items())
        ]

    def _summarize_bucket(
        self,
        scope: TenantScope,
        subject_type: AttributionSubjectType,
        subject_id: str,
        subject_revision: str,
        currency: str,
        rows: list[Any],
    ) -> CostAttributionSummary:
        measured = 0.0
        estimated = 0.0
        unknown = 0
        for row in rows:
            quantity = row["quantity"]
            if quantity is None:
                unknown += 1
                continue
            effective = float(quantity) + float(row["adjustment_total"])
            if effective < 0:
                unknown += 1
                continue
            amount = effective * float(row["weight"])
            qualities = {row["receipt_quality"], row["attribution_quality"]}
            if "unknown" in qualities:
                unknown += 1
            elif "estimated" in qualities:
                estimated += amount
            else:
                measured += amount
        eligible = unknown == 0 and estimated == 0 and len(rows) > 0
        return CostAttributionSummary(
            tenant=self._tenant(scope),
            subject_type=subject_type,
            subject_id=subject_id,
            subject_revision=subject_revision,
            currency=currency,
            measured_amount=measured,
            estimated_amount=estimated,
            unknown_receipt_count=unknown,
            receipt_count=len(rows),
            hard_budget_eligible=eligible,
            hard_budget_amount=measured if eligible else None,
        )

    @staticmethod
    def _id(prefix: str, scope: TenantScope, *parts: str) -> str:
        material = ":".join((scope.org_id, scope.project_id, *parts))
        return f"{prefix}-{hashlib.sha256(material.encode()).hexdigest()[:28]}"

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)


__all__ = ["AipCostAttributionService"]
