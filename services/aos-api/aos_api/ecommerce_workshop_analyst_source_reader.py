"""SourceReadiness-backed canonical reader for the Workshop analyst view.

Only current, tenant-bound READY sources may contribute business metric values.
FAILED/STALE sources contribute to the quality distribution only; their
projection counts are never surfaced as trustworthy business observations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Protocol

from aos_api.ecommerce_workshop_analyst_contracts import (
    AnalystAxisReadiness,
    AnalystBlocker,
    AnalystExactRef,
    AnalystMetricValue,
    AnalystReadinessAxis,
    AnalystViewId,
)
from aos_api.ecommerce_workshop_analyst_reader import AnalystReadError, AnalystViewObservation
from aos_api.source_readiness import build_source_readiness_service
from aos_api.source_readiness_contracts import ObservationStatus, PolicyCheckStatus, SourceReadinessEnvelope, SourceReadinessStatus
from aos_api.tenant_scope import TenantScope


class SourceReadinessReader(Protocol):
    def read(self, *, org_id: str, project_id: str) -> SourceReadinessEnvelope: ...


_BUSINESS_METRICS: dict[str, tuple[str, str]] = {
    "Shop": ("shop_count", "店铺数"),
    "Product": ("product_count", "商品数"),
    "ProductSku": ("product_sku_count", "商品SKU数"),
    "Category": ("category_count", "类目数"),
    "Order": ("order_count", "订单数"),
    "OrderLine": ("order_line_count", "订单明细数"),
    "CustomerLite": ("customer_count", "会员数"),
    "Weapp": ("weapp_count", "小程序数"),
    "ProductReview": ("product_review_count", "商品评价数"),
}

_VIEW_OBJECT_TYPES: dict[AnalystViewId, tuple[str, ...]] = {
    AnalystViewId.OVERVIEW: ("Order", "Product", "CustomerLite"),
    AnalystViewId.DRIVERS: ("Product", "ProductReview", "CustomerLite"),
    AnalystViewId.DIAGNOSIS: ("Order", "OrderLine", "CustomerLite"),
}


def _canonical_payload(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", by_alias=True)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_payload(value)).hexdigest()


def _revision(value: Any) -> int:
    return int(_digest(value)[:12], 16) or 1


def _exact_ref(*, resource_type: str, resource_id: str, value: Any, receipt_id: str) -> AnalystExactRef:
    return AnalystExactRef(
        resourceType=resource_type,
        resourceId=resource_id,
        revision=_revision(value),
        contentHash=f"sha256:{_digest(value)}",
        receiptId=receipt_id,
    )


def _source_ref(value: Any, *, fallback_type: str, fallback_id: str, receipt_id: str) -> AnalystExactRef:
    if value is None:
        raise AnalystReadError(f"missing exact source reference: {fallback_id}")
    content_hash = str(getattr(value, "content_hash", ""))
    if len(content_hash) != 64:
        raise AnalystReadError(f"invalid exact source reference: {fallback_id}")
    revision_text = str(getattr(value, "revision", "1"))
    try:
        revision = int(revision_text)
    except ValueError:
        revision = _revision(revision_text)
    return AnalystExactRef(
        resourceType=str(getattr(value, "resource_type", fallback_type)),
        resourceId=str(getattr(value, "resource_id", fallback_id)),
        revision=max(revision, 1),
        contentHash=f"sha256:{content_hash}",
        receiptId=receipt_id,
    )


def _ready_axes(snapshot_ref: AnalystExactRef) -> tuple[AnalystAxisReadiness, ...]:
    return tuple(
        AnalystAxisReadiness(axis=axis, status="ready", exactRef=snapshot_ref)
        if axis is AnalystReadinessAxis.METRIC_QUERY
        else AnalystAxisReadiness(axis=axis, status="not_applicable")
        for axis in AnalystReadinessAxis
    )


def _observational_axes(snapshot_ref: AnalystExactRef, *, view_id: AnalystViewId) -> tuple[AnalystAxisReadiness, ...]:
    blocker = AnalystBlocker(
        code=f"ANALYST_{view_id.value.upper()}_NON_CAUSAL_BOUNDARY",
        dependency=f"workshop.analyst.{view_id.value}.model-eval",
        requiredAction="仅展示当前经营观察；需 exact 模型与评价证据后才能形成归因或因果结论",
    )
    result: list[AnalystAxisReadiness] = []
    for axis in AnalystReadinessAxis:
        if axis is AnalystReadinessAxis.METRIC_QUERY:
            result.append(AnalystAxisReadiness(axis=axis, status="ready", exactRef=snapshot_ref))
        elif axis in {AnalystReadinessAxis.MODEL, AnalystReadinessAxis.EVAL}:
            result.append(AnalystAxisReadiness(axis=axis, status="blocked", blockers=[blocker]))
        else:
            result.append(AnalystAxisReadiness(axis=axis, status="not_applicable"))
    return tuple(result)


class EcommerceWorkshopAnalystSourceReader:
    """Project current SourceReadiness into bounded, read-only analyst metrics."""

    def __init__(self, source_service: SourceReadinessReader | None = None) -> None:
        self._source_service = source_service or build_source_readiness_service()
        self._cached_key: tuple[TenantScope, datetime] | None = None
        self._cached_envelope: SourceReadinessEnvelope | None = None

    def read_view(self, scope: TenantScope, *, view_id: AnalystViewId, cutoff: datetime, limit: int) -> AnalystViewObservation:
        if limit != 100:
            raise AnalystReadError("analyst source reader requires the bounded limit 100")
        if view_id in {AnalystViewId.PLAN, AnalystViewId.EFFECTS, AnalystViewId.EVIDENCE}:
            raise AnalystReadError(f"{view_id.value} canonical authority is not available")
        envelope = self._read_once(scope=scope, cutoff=cutoff)
        snapshot_ref = _exact_ref(
            resource_type="SourceReadinessSnapshot",
            resource_id=f"{scope.org_id}/{scope.project_id}",
            value=envelope,
            receipt_id=f"source-readiness:{envelope.checked_at.isoformat()}",
        )
        revision = snapshot_ref.revision
        if view_id is AnalystViewId.QUALITY:
            metrics = self._quality_metrics(envelope=envelope, snapshot_ref=snapshot_ref)
            axes = _ready_axes(snapshot_ref)
        else:
            metrics = self._business_metrics(envelope=envelope, object_types=_VIEW_OBJECT_TYPES[view_id])
            if not metrics:
                raise AnalystReadError(f"{view_id.value} has no trustworthy current metrics")
            axes = _ready_axes(snapshot_ref) if view_id is AnalystViewId.OVERVIEW else _observational_axes(snapshot_ref, view_id=view_id)
        refs = {(
            ref.resource_type,
            ref.resource_id,
            ref.revision,
            ref.content_hash,
            ref.receipt_id,
        ): ref for metric in metrics for ref in (
            metric.definition_ref,
            metric.observation_ref,
            metric.source_run_ref,
            metric.quality_ref,
            metric.reconciliation_ref,
        ) if ref is not None}
        refs[(snapshot_ref.resource_type, snapshot_ref.resource_id, snapshot_ref.revision, snapshot_ref.content_hash, snapshot_ref.receipt_id)] = snapshot_ref
        return AnalystViewObservation(
            scope=scope,
            resource_revision=revision,
            data_cutoff=cutoff,
            readiness_axes=axes,
            metrics=metrics,
            authority_refs=tuple(refs.values()),
        )

    def _read_once(self, *, scope: TenantScope, cutoff: datetime) -> SourceReadinessEnvelope:
        key = (scope, cutoff)
        if self._cached_key == key and self._cached_envelope is not None:
            return self._cached_envelope
        try:
            envelope = self._source_service.read(org_id=scope.org_id, project_id=scope.project_id)
        except Exception as exc:  # canonical dependency failures remain fail-closed
            raise AnalystReadError("source readiness read failed") from exc
        if (envelope.tenant.org_id, envelope.tenant.project_id) != scope.key:
            raise AnalystReadError("source readiness tenant scope mismatch")
        self._cached_key = key
        self._cached_envelope = envelope
        return envelope

    def _business_metrics(self, *, envelope: SourceReadinessEnvelope, object_types: tuple[str, ...]) -> tuple[AnalystMetricValue, ...]:
        by_type = {item.object_type: item for item in envelope.sources}
        metrics: list[AnalystMetricValue] = []
        for object_type in object_types:
            item = by_type.get(object_type)
            if item is None or item.status is not SourceReadinessStatus.READY:
                continue
            if item.latest_run.status is not ObservationStatus.SUCCEEDED or item.quality.status is not PolicyCheckStatus.PASS or item.reconciliation.status is not PolicyCheckStatus.PASS:
                continue
            value = item.counts.projection_total
            if value is None or value <= 0 or not item.latest_run.run_id or item.data_cutoff is None:
                continue
            metric_id, label = _BUSINESS_METRICS[object_type]
            receipt_id = f"source-run:{item.latest_run.run_id}"
            definition = {"metricId": metric_id, "label": label, "objectType": object_type, "measure": "projection_total", "unit": "条"}
            definition_ref = _exact_ref(resource_type="MetricDefinitionRevision", resource_id=f"workshop.analyst.{metric_id}", value=definition, receipt_id="analyst-metric-definition:v1")
            observation_ref = _exact_ref(resource_type="MetricObservation", resource_id=f"{item.pipeline_id}:{item.latest_run.run_id}", value=item, receipt_id=receipt_id)
            source_run_ref = _exact_ref(resource_type="SourceRunObservation", resource_id=item.latest_run.run_id, value=item.latest_run, receipt_id=receipt_id)
            quality_ref = _source_ref(item.quality.rule_ref, fallback_type="QualityPolicy", fallback_id=f"{item.pipeline_id}:quality", receipt_id=receipt_id)
            reconciliation_ref = _source_ref(item.reconciliation.rule_ref, fallback_type="ReconciliationPolicy", fallback_id=f"{item.pipeline_id}:reconciliation", receipt_id=receipt_id)
            metrics.append(AnalystMetricValue(
                metricId=metric_id,
                status="ready",
                definitionRef=definition_ref,
                observationRef=observation_ref,
                value=float(value),
                unit="条",
                grain="当前租户",
                window=item.data_cutoff.isoformat(),
                timezone="Asia/Shanghai",
                cohortFilter=f"正式数据来源 {item.source_id} · {label}",
                numerator=float(value),
                denominator=float(value),
                sourceRunRef=source_run_ref,
                qualityRef=quality_ref,
                reconciliationRef=reconciliation_ref,
                lineageId=f"source-run:{item.latest_run.run_id}",
            ))
        return tuple(metrics)

    def _quality_metrics(self, *, envelope: SourceReadinessEnvelope, snapshot_ref: AnalystExactRef) -> tuple[AnalystMetricValue, ...]:
        groups = (
            ("ready_source_count", "可读取数据源", SourceReadinessStatus.READY),
            ("failed_source_count", "失败数据源", SourceReadinessStatus.FAILED),
            ("stale_source_count", "过期数据源", SourceReadinessStatus.STALE),
        )
        total = len(envelope.sources)
        if total <= 0:
            raise AnalystReadError("source readiness canonical set is empty")
        run_ids = [item.latest_run.run_id or f"{item.pipeline_id}:unknown" for item in envelope.sources]
        quality_payload = {item.pipeline_id: item.quality.status.value for item in envelope.sources}
        reconciliation_payload = {item.pipeline_id: item.reconciliation.status.value for item in envelope.sources}
        source_run_ref = _exact_ref(resource_type="SourceRunSetObservation", resource_id=f"{envelope.tenant.org_id}/{envelope.tenant.project_id}", value=run_ids, receipt_id=snapshot_ref.receipt_id)
        quality_ref = _exact_ref(resource_type="QualityObservationSet", resource_id=f"{envelope.tenant.org_id}/{envelope.tenant.project_id}", value=quality_payload, receipt_id=snapshot_ref.receipt_id)
        reconciliation_ref = _exact_ref(resource_type="ReconciliationObservationSet", resource_id=f"{envelope.tenant.org_id}/{envelope.tenant.project_id}", value=reconciliation_payload, receipt_id=snapshot_ref.receipt_id)
        result: list[AnalystMetricValue] = []
        for metric_id, label, status in groups:
            value = sum(item.status is status for item in envelope.sources)
            definition = {"metricId": metric_id, "label": label, "measure": "source_status_count", "status": status.value}
            result.append(AnalystMetricValue(
                metricId=metric_id,
                status="ready",
                definitionRef=_exact_ref(resource_type="MetricDefinitionRevision", resource_id=f"workshop.analyst.{metric_id}", value=definition, receipt_id="analyst-metric-definition:v1"),
                observationRef=snapshot_ref,
                value=float(value),
                unit="个",
                grain="当前租户数据源",
                window=envelope.checked_at.isoformat(),
                timezone="Asia/Shanghai",
                cohortFilter="栖月汇 canonical P01-P12 数据源集合",
                numerator=float(value),
                denominator=float(total),
                sourceRunRef=source_run_ref,
                qualityRef=quality_ref,
                reconciliationRef=reconciliation_ref,
                lineageId=f"source-readiness:{snapshot_ref.content_hash[7:23]}",
            ))
        return tuple(result)


__all__ = ["EcommerceWorkshopAnalystSourceReader"]
