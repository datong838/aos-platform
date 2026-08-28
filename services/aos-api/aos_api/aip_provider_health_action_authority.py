"""Code-backed authority for the Provider Health probe Action.

This module never registers a global adapter, persists an Action Type, resolves a
secret, or performs a Provider call on import.  Registration is explicit and
requires an injected runtime refresh callable.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Callable

from aos_api.aip_action_adapters import ActionAdapterRegistry, AdapterOutcome
from aos_api.aip_adapter_conformance import (
    AdapterConformanceFixture,
    AdapterConformanceReport,
    run_adapter_conformance,
)
from aos_api.aip_adapter_contracts import (
    AdapterCapabilityRevision,
    AdapterInvocationEnvelope,
    AdapterLifecycle,
    AdapterReadiness,
    AdapterSupportMode,
    AuthorizedAccountContext,
    DryValidationReceipt,
    ImmutableExactRevisionRef,
    NormalizedUsageCandidate,
    TenantIdentity,
    UsageQuality,
)
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
    ProviderHealthProbeActionAdapter,
)

PROVIDER_HEALTH_ACTION_PURPOSE = "刷新文本 Provider 健康证据"
PROVIDER_HEALTH_ADAPTER_ID = "aip.provider-health-probe.agnes-text"


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _ref(resource_type: str, resource_id: str) -> ImmutableExactRevisionRef:
    return ImmutableExactRevisionRef(
        resourceType=resource_type,
        resourceId=resource_id,
        revision=1,
        contentHash=_digest(
            {"resourceType": resource_type, "resourceId": resource_id, "revision": 1}
        ),
    )


def provider_health_action_type_snapshot() -> dict[str, Any]:
    snapshot = {
        "id": PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
        "name": "文本 Provider 健康探测",
        "objectType": "ProviderHealthObservation",
        "parameters": [
            {"name": "providerId", "type": "string", "required": True},
            {"name": "providerRevision", "type": "integer", "required": True},
            {"name": "probeCount", "type": "integer", "required": True},
            {"name": "outputPolicy", "type": "string", "required": True},
        ],
        "requiredMarkings": ["restricted"],
        "submissionCriteria": [
            {"field": "providerId", "op": "eq", "value": "agnes-text-qyh-dev"},
            {"field": "providerRevision", "op": "eq", "value": 7},
            {"field": "probeCount", "op": "eq", "value": 3},
            {"field": "outputPolicy", "op": "eq", "value": "metadata-only"},
        ],
    }
    return {**snapshot, "revisionHash": _digest(snapshot)}


def provider_health_adapter_revision() -> AdapterCapabilityRevision:
    return AdapterCapabilityRevision.seal(
        adapter_id=PROVIDER_HEALTH_ADAPTER_ID,
        revision=1,
        lifecycle=AdapterLifecycle.PUBLISHED,
        provider="agnes",
        account_kind="provider-health",
        capability_ref=_ref("CapabilityRevision", PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID),
        action_type_family=PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
        input_schema_ref=_ref("InputSchemaRevision", "provider-health-probe-input"),
        output_schema_ref=_ref("OutputSchemaRevision", "provider-health-probe-output"),
        receipt_schema_ref=_ref(
            "ReceiptSchemaRevision", "provider-health-probe-receipt"
        ),
        usage_schema_ref=_ref("UsageSchemaRevision", "provider-health-probe-usage"),
        risk_floor=ActionRiskLevel.R2,
        idempotency_domain="agnes/provider-health-probe",
        timeout_seconds=60,
        dry_validate_mode=AdapterSupportMode.REQUIRED,
        reconcile_mode=AdapterSupportMode.MANUAL,
        cancel_mode=AdapterSupportMode.UNSUPPORTED,
        partial_mode=AdapterSupportMode.UNSUPPORTED,
        rate_policy_ref=_ref("RatePolicyRevision", "provider-health-single-cycle"),
        capacity_policy_ref=_ref(
            "CapacityPolicyRevision", "provider-health-three-probes"
        ),
        license_policy_ref=_ref("LicensePolicyRevision", "agnes-provider-health"),
        redaction_policy_ref=_ref(
            "RedactionPolicyRevision", "provider-health-metadata-only"
        ),
        readiness_policy_ref=_ref(
            "ReadinessPolicyRevision", "provider-health-exact-lease"
        ),
    )


class _DeterministicConformanceAdapter(ProviderHealthProbeActionAdapter):
    side_effect_free = True

    def __init__(self, revision: AdapterCapabilityRevision) -> None:
        super().__init__(
            lambda: {
                "status": "PROVIDER_HEALTH_REFRESH_GREEN",
                "observationId": "deterministic-observation",
                "expiresAt": "2099-01-01T00:00:00Z",
                "providerCalls": 3,
                "secretPayloadReadsReported": 0,
                "promptOrAnswerBodiesReported": 0,
            }
        )
        self.adapter_revision_ref = revision.exact_ref()

    def resolve_account(self, *, account_ref, tenant):
        return AuthorizedAccountContext(
            tenant=tenant,
            accountRef=account_ref,
            provider="agnes",
            accountKind="provider-health",
            allowedPurposes=(PROVIDER_HEALTH_ACTION_PURPOSE,),
            requiredMarkings=("restricted",),
            readiness=AdapterReadiness.AVAILABLE,
            secretRef="secret://deterministic/provider-health-conformance",
        )

    def dry_validate(self, *, envelope):
        return DryValidationReceipt(
            status=AdapterReadiness.AVAILABLE,
            requestFingerprint=envelope.request_fingerprint,
            reversible=False,
        )

    def normalize_usage(self, *, outcome):
        return NormalizedUsageCandidate(
            providerRequestId=outcome.provider_request_id,
            quality=UsageQuality.MEASURED,
            amount=3,
            unit="probe",
        )


def _conformance_fixture(
    revision: AdapterCapabilityRevision,
) -> AdapterConformanceFixture:
    return AdapterConformanceFixture(
        sandbox_identity="deterministic://agnes/provider-health-contract-suite",
        envelope=AdapterInvocationEnvelope(
            tenant=TenantIdentity(orgId="org-org", projectId="dev-project"),
            proposalRef=_ref("ActionProposalRevision", "provider-health-proposal"),
            leaseRef=_ref("ExecutionLeaseRevision", "provider-health-lease"),
            capabilityRef=revision.capability_ref,
            accountRef=_ref("AccountRevision", "provider-health-account"),
            purpose=PROVIDER_HEALTH_ACTION_PURPOSE,
            markings=("restricted",),
            payload={
                "providerId": "agnes-text-qyh-dev",
                "providerRevision": 7,
                "probeCount": 3,
                "outputPolicy": "metadata-only",
            },
            requestFingerprint=_digest({"fixture": "provider-health"}),
            idempotencyKey="provider-health-conformance",
        ),
    )


def register_provider_health_action_adapter(
    registry: ActionAdapterRegistry,
    refresh: Callable[[], dict[str, Any]],
) -> tuple[ProviderHealthProbeActionAdapter, AdapterCapabilityRevision, AdapterConformanceReport]:
    """Explicitly register one exact adapter instance after deterministic conformance."""
    revision = provider_health_adapter_revision()
    report = run_adapter_conformance(
        revision,
        _DeterministicConformanceAdapter(revision),
        _conformance_fixture(revision),
    )
    adapter = ProviderHealthProbeActionAdapter(refresh)
    adapter.adapter_revision_ref = revision.exact_ref()
    registry.register_conformant(revision, adapter, report)
    registry.register(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID, adapter)
    return adapter, revision, report


__all__ = [
    "PROVIDER_HEALTH_ACTION_PURPOSE",
    "PROVIDER_HEALTH_ADAPTER_ID",
    "provider_health_action_type_snapshot",
    "provider_health_adapter_revision",
    "register_provider_health_action_adapter",
]
