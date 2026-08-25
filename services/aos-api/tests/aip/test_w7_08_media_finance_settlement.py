"""W7-08 media finance authority, cancellation and settlement tests."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_media_finance_contracts import (
    BindMediaUsageRequest,
    MediaCancelOutcome,
    MediaFeeConclusion,
    MediaFinanceEventKind,
    MediaSettlementStatus,
    ObserveMediaCancelRequest,
    PrepareMediaFinanceRequest,
    SettleMediaFinanceRequest,
)
from aos_api.aip_media_finance_store import (
    AipMediaFinanceStore,
    MediaFinanceDependencyBlocked,
)
from aos_api.aip_media_provider_job_contracts import (
    MediaJobStatus,
    MediaProviderBindingSnapshot,
    MediaScanVerdict,
    PrepareMediaProviderJobRequest,
    ProviderOperationResult,
    ServerOwnedMediaScanResult,
)
from aos_api.aip_media_provider_job_service import AipMediaProviderJobService
from aos_api.aip_media_provider_job_store import AipMediaProviderJobStore
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NEGATIVE_SCOPE = TenantScope("dev-org", "dev-project")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ref(kind: str, name: str, revision: int = 1) -> ExactRevisionRef:
    return ExactRevisionRef(resourceType=kind, resourceId=name, revision=revision, contentHash=_hash(f"{kind}:{name}:{revision}"))


def _provider_request(marker: str) -> PrepareMediaProviderJobRequest:
    return PrepareMediaProviderJobRequest(
        taskRunRef=_ref("TaskRun", f"task-{marker}"),
        stepRunRef=_ref("StepRunAttempt", f"step-{marker}"),
        capabilityRef=_ref("CapabilityRevision", "media-generate"),
        bindingRef=_ref("CapabilityBindingRevision", "content-officer-media"),
        modelRouteRef=_ref("ModelRouteRevision", "image-route"),
        runtimePolicyRef=_ref("RuntimePolicyRevision", "media-policy"),
        adapterRef=_ref("MediaProviderAdapterRevision", "provider-adapter"),
        licenseRef=_ref("MediaLicenseDecision", "license-decision"),
        scanPolicyRef=_ref("MediaAssetScanPolicyRevision", "scan-policy"),
        scannerRef=_ref("MediaAssetScannerRevision", "scanner"),
        inputArtifactRefs=[_ref("Artifact", f"input-{marker}")],
        expectedOutputModality="image",
        purpose="W7-08 offline settlement test",
        dataClassification="internal",
    )


def _binding(body: PrepareMediaProviderJobRequest) -> MediaProviderBindingSnapshot:
    return MediaProviderBindingSnapshot(
        capabilityRef=body.capability_ref,
        bindingRef=body.binding_ref,
        modelRouteRef=body.model_route_ref,
        modelRef=_ref("RegisteredModelRevision", "image-model"),
        providerRef=_ref("ProviderInstanceRevision", "provider"),
        runtimePolicyRef=body.runtime_policy_ref,
        providerPluginRef=_ref("ProviderPluginRevision", "plugin"),
        priceSnapshotRef=_ref("ModelPriceSnapshotRevision", "price"),
        adapterRef=body.adapter_ref,
        licenseRef=body.license_ref,
        evalGateRef=_ref("EvalGateDecision", "eval"),
    )


def _seed_finance_authorities(capacity_ref: ExactRevisionRef, budget_ref: ExactRevisionRef, now: datetime) -> None:
    versioned = lambda kind, name: {"assetType": kind, "assetId": name, "revision": 1, "contentHash": _hash(f"{kind}:{name}")}
    with connect(SCOPE) as conn:
        conn.execute(
            "INSERT INTO aip_model_capacity_pool_head(org_id,project_id,pool_id,current_revision,version) VALUES(%s,%s,%s,1,1)",
            (*SCOPE.key, capacity_ref.resource_id),
        )
        conn.execute(
            """INSERT INTO aip_model_capacity_pool_revision(
               org_id,project_id,pool_id,revision,content_hash,route_ref,model_ref,provider_ref,
               route_id,route_revision,route_hash,model_id,model_revision,model_hash,
               provider_id,provider_revision,provider_hash,max_concurrency,max_token_units,
               token_unit_per_reservation,lease_seconds,lifecycle,created_by,created_at)
               VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,1,%s,%s,1,%s,%s,1,%s,2,1000,100,3600,'active','test:w7-08',%s)""",
            (*SCOPE.key, capacity_ref.resource_id, capacity_ref.revision, capacity_ref.content_hash,
             json.dumps(versioned("ModelRouteRevision", "route")), json.dumps(versioned("RegisteredModelRevision", "model")), json.dumps(versioned("ProviderInstanceRevision", "provider")),
             "route", _hash("ModelRouteRevision:route"),
             "model", _hash("RegisteredModelRevision:model"),
             "provider", _hash("ProviderInstanceRevision:provider"), now),
        )
        conn.execute(
            "INSERT INTO aip_budget_head(org_id,project_id,budget_id,current_revision,version) VALUES(%s,%s,%s,1,1)",
            (*SCOPE.key, budget_ref.resource_id),
        )
        payload = {"budgetId": budget_ref.resource_id, "revision": 1, "currency": "CNY", "lifecycle": "active"}
        conn.execute(
            """INSERT INTO aip_budget_revision(
               org_id,project_id,budget_id,revision,content_hash,lifecycle,environment,currency,
               daily_limit_minor,monthly_limit_minor,alert_threshold_pct,hard_stop,
               unknown_usage_behavior,effective_from,effective_until,owner,over_budget_approver,
               payload,created_by,created_at)
               VALUES(%s,%s,%s,%s,%s,'active','development','CNY',5000,50000,80,TRUE,'block',%s,%s,'owner','approver',%s::jsonb,'test:w7-08',%s)""",
            (*SCOPE.key, budget_ref.resource_id, budget_ref.revision, budget_ref.content_hash, now - timedelta(hours=1), now + timedelta(days=1), json.dumps(payload), now),
        )
        conn.commit()


def test_contracts_do_not_invent_unknown_cost_or_zero_charge() -> None:
    with pytest.raises(ValidationError, match="unknown usage must not invent amount"):
        BindMediaUsageRequest(
            expectedVersion=1,
            usageReceiptRef=_ref("UsageReceipt", "usage"),
            providerReceiptRef=_ref("MediaProviderReceipt", "provider"),
            quality="unknown",
            amountMinor=0,
            currency="CNY",
            observedAt=datetime.now(UTC),
        )


def test_submit_without_finance_reservation_fails_before_adapter_call() -> None:
    marker = uuid.uuid4().hex
    now = datetime.now(UTC)
    body = _provider_request(marker)
    scan = ServerOwnedMediaScanResult(
        detectedMime="image/png", byteSize=12,
        contentHash=body.input_artifact_refs[0].content_hash,
        verdict=MediaScanVerdict.PASSED, findings=[], scannedAt=now,
    )
    store = AipMediaProviderJobStore()
    job = store.prepare_job(SCOPE, "test:w7-08", f"job-{marker}", body, _binding(body), [scan])

    class Guard:
        def require_submit_ready(self, scope: TenantScope, candidate) -> None:
            raise MediaFinanceDependencyBlocked("MEDIA_FINANCE_RESERVATION_REQUIRED")

    class Adapter:
        adapter_ref = job.binding.adapter_ref
        calls = 0

        def submit(self, candidate) -> ProviderOperationResult:
            self.calls += 1
            return ProviderOperationResult(status=MediaJobStatus.SUBMITTED, observedAt=now)

    adapter = Adapter()
    service = AipMediaProviderJobService(
        store=store,
        adapter=adapter,
        finance_submit_guard=Guard(),
    )
    with pytest.raises(MediaFinanceDependencyBlocked, match="MEDIA_FINANCE_RESERVATION_REQUIRED"):
        service.submit(
            SCOPE, "test:w7-08", job.job_id, f"submit-{marker}",
            expected_sequence=job.sequence,
        )
    assert adapter.calls == 0
    with pytest.raises(ValidationError, match="no-charge cancel requires Provider receipt"):
        ObserveMediaCancelRequest(
            expectedVersion=1,
            outcome="accepted",
            feeConclusion="no_charge",
            observedAt=datetime.now(UTC),
        )


def test_append_only_authority_matures_unknown_and_preserves_currency_buckets() -> None:
    marker = uuid.uuid4().hex
    now = datetime.now(UTC)
    body = _provider_request(marker)
    scan = ServerOwnedMediaScanResult(
        detectedMime="image/png", byteSize=12,
        contentHash=body.input_artifact_refs[0].content_hash,
        verdict=MediaScanVerdict.PASSED, findings=[], scannedAt=now,
    )
    job_store = AipMediaProviderJobStore()
    job = job_store.prepare_job(SCOPE, "test:w7-08", f"job-{marker}", body, _binding(body), [scan])
    event = job_store.list_events(SCOPE, job.job_id)[-1]
    store = AipMediaFinanceStore()
    capacity_ref = _ref("ModelCapacityPoolRevision", f"media-capacity-{marker}")
    budget_ref = _ref("BudgetRevision", f"media-budget-{marker}")
    _seed_finance_authorities(capacity_ref, budget_ref, now)
    snapshot = store.prepare(
        SCOPE,
        "test:w7-08",
        f"finance-{marker}",
        PrepareMediaFinanceRequest(
            jobId=job.job_id,
            expectedJobSequence=job.sequence,
            capacityPoolRef=capacity_ref,
            budgetRevisionRef=budget_ref,
            projectedMinMinor=800,
            projectedMaxMinor=1200,
            currency="CNY",
            expiresAt=now + timedelta(hours=1),
        ),
        job,
        event,
        now=now,
    )
    assert snapshot.reservations_active
    assert snapshot.capacity_reservation_ref.resource_type == "MediaCapacityReservation"
    assert snapshot.budget_reservation_ref.resource_type == "MediaBudgetReservation"
    assert store.list(NEGATIVE_SCOPE).count == 0

    unknown_ref = _ref("UsageReceipt", f"unknown-{marker}")
    snapshot = store.append(
        SCOPE, "test:w7-08", f"unknown-{marker}", snapshot.finance_id,
        MediaFinanceEventKind.USAGE_BOUND,
        BindMediaUsageRequest(
            expectedVersion=snapshot.version,
            usageReceiptRef=unknown_ref,
            providerReceiptRef=_ref("MediaProviderReceipt", f"provider-unknown-{marker}"),
            quality="unknown", amountMinor=None, currency="CNY", observedAt=now,
        ),
    )
    with pytest.raises(MediaFinanceDependencyBlocked, match="MEDIA_USAGE_UNKNOWN_RECONCILE_REQUIRED"):
        store.append(
            SCOPE, "test:w7-08", f"settle-too-early-{marker}", snapshot.finance_id,
            MediaFinanceEventKind.SETTLED,
            SettleMediaFinanceRequest(
                expectedVersion=snapshot.version,
                status="settled",
                decisionRef=_ref("MediaSettlementDecision", f"decision-early-{marker}"),
                reasonHash=_hash("too-early"), observedAt=now,
            ),
        )

    snapshot = store.append(
        SCOPE, "test:w7-08", f"mature-{marker}", snapshot.finance_id,
        MediaFinanceEventKind.USAGE_BOUND,
        BindMediaUsageRequest(
            expectedVersion=snapshot.version,
            usageReceiptRef=_ref("UsageReceipt", f"measured-{marker}"),
            providerReceiptRef=_ref("MediaProviderReceipt", f"provider-measured-{marker}"),
            supersedesUsageReceiptRef=unknown_ref,
            quality="measured", amountMinor=1000, currency="CNY", observedAt=now,
        ),
    )
    snapshot = store.append(
        SCOPE, "test:w7-08", f"usd-{marker}", snapshot.finance_id,
        MediaFinanceEventKind.USAGE_BOUND,
        BindMediaUsageRequest(
            expectedVersion=snapshot.version,
            usageReceiptRef=_ref("UsageReceipt", f"usd-{marker}"),
            providerReceiptRef=_ref("MediaProviderReceipt", f"provider-usd-{marker}"),
            quality="estimated", amountMinor=25, currency="USD", observedAt=now,
        ),
    )
    snapshot = store.append(
        SCOPE, "test:w7-08", f"cancel-{marker}", snapshot.finance_id,
        MediaFinanceEventKind.CANCEL_OBSERVED,
        ObserveMediaCancelRequest(
            expectedVersion=snapshot.version,
            outcome=MediaCancelOutcome.TOO_LATE,
            feeConclusion=MediaFeeConclusion.CHARGEABLE,
            providerReceiptRef=_ref("MediaProviderReceipt", f"provider-cancel-{marker}"),
            observedAt=now,
        ),
    )
    snapshot = store.append(
        SCOPE, "test:w7-08", f"settle-{marker}", snapshot.finance_id,
        MediaFinanceEventKind.SETTLED,
        SettleMediaFinanceRequest(
            expectedVersion=snapshot.version,
            status=MediaSettlementStatus.SETTLED,
            decisionRef=_ref("MediaSettlementDecision", f"decision-{marker}"),
            adjustmentMinor=100,
            refundMinor=50,
            reasonHash=_hash("final settlement"),
            observedAt=now,
        ),
    )
    assert snapshot.settlement_status is MediaSettlementStatus.SETTLED
    assert snapshot.cancel_outcome is MediaCancelOutcome.TOO_LATE
    assert [item.currency for item in snapshot.currency_buckets] == ["CNY", "USD"]
    cny, usd = snapshot.currency_buckets
    assert (cny.measured_minor, cny.unknown_count, cny.adjustment_minor, cny.refund_minor, cny.residual_minor) == (1000, 0, 100, 50, -150)
    assert (usd.estimated_minor, usd.residual_minor) == (25, 25)
    assert len(snapshot.usage_receipt_refs) == 3
    assert snapshot.external_effects_allowed is False

    with connect(SCOPE) as conn:
        with pytest.raises(Exception):
            conn.execute(
                "UPDATE aip_media_attempt_finance SET created_by='tampered' WHERE org_id=%s AND project_id=%s AND finance_id=%s",
                (*SCOPE.key, snapshot.finance_id),
            )
        conn.rollback()


def test_migration_is_rls_append_only_reversible_and_secret_free() -> None:
    path = __import__("pathlib").Path(__file__).resolve().parents[2] / "alembic/versions/w7_006_media_finance_settlement.py"
    text = path.read_text()
    assert 'down_revision: str | Sequence[str] | None = "w7_005"' in text
    for table in ("aip_media_attempt_finance", "aip_media_attempt_finance_event", "aip_media_attempt_finance_idempotency"):
        assert table in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip4_append_only" in text
    assert "DROP TABLE aip_media_attempt_finance_event;" in text
    assert "CASCADE" not in text
    assert "secret" not in text.lower()


def test_default_api_prepare_fails_closed_without_exact_authority_validators(client, auth_headers) -> None:
    response = client.post(
        "/v1/aip/media-finance",
        headers={**auth_headers, "Idempotency-Key": f"api-w7-08-{uuid.uuid4().hex}"},
        json=PrepareMediaFinanceRequest(
            jobId="missing-job",
            expectedJobSequence=1,
            capacityPoolRef=_ref("ModelCapacityPoolRevision", "pool"),
            budgetRevisionRef=_ref("BudgetRevision", "budget"),
            projectedMinMinor=1,
            projectedMaxMinor=2,
            currency="CNY",
            expiresAt=datetime.now(UTC) + timedelta(hours=1),
        ).model_dump(mode="json", by_alias=True),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "MEDIA_FINANCE_DEPENDENCY_BLOCKED"
    assert "MEDIA_CAPACITY_POOL_REF_BLOCKED" in response.text
