from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.aip_action_adapters import ActionAdapterRegistry, AdapterOutcome
from aos_api.aip_adapter_conformance import AdapterConformanceFixture, run_adapter_conformance
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


HASH = "1" * 64
FINGERPRINT = "2" * 64


def ref(resource_type: str, resource_id: str, digest: str = HASH) -> ImmutableExactRevisionRef:
    return ImmutableExactRevisionRef(
        resourceType=resource_type,
        resourceId=resource_id,
        revision=1,
        contentHash=digest,
    )


def revision(**changes) -> AdapterCapabilityRevision:
    definition = {
        "adapter_id": "adapter.demo",
        "revision": 1,
        "lifecycle": AdapterLifecycle.PUBLISHED,
        "provider": "provider.demo",
        "account_kind": "shop",
        "capability_ref": ref("CapabilityRevision", "cap.order.remark"),
        "action_type_family": "order.remark",
        "input_schema_ref": ref("InputSchemaRevision", "schema.input"),
        "output_schema_ref": ref("OutputSchemaRevision", "schema.output"),
        "receipt_schema_ref": ref("ReceiptSchemaRevision", "schema.receipt"),
        "usage_schema_ref": ref("UsageSchemaRevision", "schema.usage"),
        "risk_floor": ActionRiskLevel.R2,
        "idempotency_domain": "provider.demo/order.remark",
        "timeout_seconds": 20,
        "dry_validate_mode": AdapterSupportMode.REQUIRED,
        "reconcile_mode": AdapterSupportMode.PROVIDER,
        "cancel_mode": AdapterSupportMode.UNSUPPORTED,
        "partial_mode": AdapterSupportMode.UNSUPPORTED,
        "webhook_contract_ref": None,
        "rate_policy_ref": ref("RatePolicyRevision", "rate.default"),
        "capacity_policy_ref": ref("CapacityPolicyRevision", "capacity.default"),
        "license_policy_ref": ref("LicensePolicyRevision", "license.default"),
        "redaction_policy_ref": ref("RedactionPolicyRevision", "redaction.default"),
        "readiness_policy_ref": ref("ReadinessPolicyRevision", "readiness.default"),
    }
    definition.update(changes)
    return AdapterCapabilityRevision.seal(**definition)


def envelope(**changes) -> AdapterInvocationEnvelope:
    body = {
        "tenant": TenantIdentity(orgId="org-org", projectId="dev-project"),
        "proposal_ref": ref("ActionProposalRevision", "proposal-1"),
        "lease_ref": ref("ExecutionLeaseRevision", "lease-1"),
        "capability_ref": ref("CapabilityRevision", "cap.order.remark"),
        "account_ref": ref("AccountRevision", "account-1"),
        "purpose": "order-support",
        "markings": ("internal",),
        "payload": {"orderId": "order-1", "remark": "checked"},
        "request_fingerprint": FINGERPRINT,
        "idempotency_key": "idem-1",
    }
    body.update(changes)
    return AdapterInvocationEnvelope(**body)


class DeterministicAdapter:
    side_effect_free = True

    def __init__(self, item: AdapterCapabilityRevision, *, unknown: bool = False) -> None:
        self.adapter_revision_ref = item.exact_ref()
        self.unknown = unknown
        self.execute_calls = 0
        self.reconcile_calls = 0

    def resolve_account(self, *, account_ref, tenant):
        return AuthorizedAccountContext(
            tenant=tenant,
            accountRef=account_ref,
            provider="provider.demo",
            accountKind="shop",
            allowedPurposes=("order-support",),
            requiredMarkings=("internal",),
            readiness=AdapterReadiness.AVAILABLE,
            secretRef="secret://org-org/dev-project/account-1",
        )

    def dry_validate(self, *, envelope):
        return DryValidationReceipt(
            status=AdapterReadiness.AVAILABLE,
            requestFingerprint=envelope.request_fingerprint,
            reversible=True,
            estimatedCost=0.01,
            currency="CNY",
        )

    def execute(self, *, payload, idempotency_key):
        self.execute_calls += 1
        status = "unknown" if self.unknown else "applied"
        return AdapterOutcome(status, "provider-request-1", {"idempotencyKey": idempotency_key})

    def reconcile(self, *, provider_request_id, request_fingerprint):
        self.reconcile_calls += 1
        return AdapterOutcome("applied", provider_request_id, {"fingerprint": request_fingerprint})

    def normalize_usage(self, *, outcome):
        return NormalizedUsageCandidate(
            providerRequestId=outcome.provider_request_id,
            quality=UsageQuality.MEASURED,
            amount=1,
            unit="request",
        )


def fixture(item: AdapterCapabilityRevision, **changes) -> AdapterConformanceFixture:
    body = {
        "sandbox_identity": "deterministic://provider.demo/contract-suite",
        "envelope": envelope(capability_ref=item.capability_ref),
    }
    body.update(changes)
    return AdapterConformanceFixture(**body)


def test_revision_is_canonical_immutable_and_camel_case() -> None:
    item = revision()
    assert item.content_hash == item.expected_content_hash()
    assert item.model_dump(by_alias=True)["capabilityRef"]["resourceType"] == "CapabilityRevision"
    with pytest.raises(ValidationError, match="frozen"):
        item.provider = "changed"  # type: ignore[misc]


def test_revision_rejects_unknown_field_and_hash_drift() -> None:
    item = revision()
    payload = item.model_dump(mode="json", by_alias=True)
    payload["provider"] = "provider.changed"
    with pytest.raises(ValidationError, match="contentHash"):
        AdapterCapabilityRevision.model_validate(payload)
    payload = item.model_dump(mode="json", by_alias=True)
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        AdapterCapabilityRevision.model_validate(payload)


def test_revision_rejects_wrong_exact_ref_types_and_missing_dry_validation() -> None:
    with pytest.raises(ValidationError, match="capability_ref"):
        revision(capability_ref=ref("SkillRevision", "skill-1"))
    with pytest.raises(ValidationError, match="dryValidateMode"):
        revision(dry_validate_mode=AdapterSupportMode.UNSUPPORTED)
    with pytest.raises(ValidationError, match="reconcileMode"):
        revision(reconcile_mode=AdapterSupportMode.UNSUPPORTED)


def test_account_requires_opaque_secret_ref_and_exact_account_type() -> None:
    tenant = TenantIdentity(orgId="org-org", projectId="dev-project")
    base = {
        "tenant": tenant,
        "accountRef": ref("AccountRevision", "account-1"),
        "provider": "provider.demo",
        "accountKind": "shop",
        "allowedPurposes": ("order-support",),
        "readiness": AdapterReadiness.AVAILABLE,
    }
    with pytest.raises(ValidationError, match="secret://"):
        AuthorizedAccountContext(**base, secretRef="plaintext-token")
    with pytest.raises(ValidationError, match="AccountRevision"):
        AuthorizedAccountContext(**{**base, "accountRef": ref("Account", "account-1")}, secretRef="secret://safe/ref")


def test_envelope_rejects_cross_contract_ref_types() -> None:
    with pytest.raises(ValidationError, match="lease_ref"):
        envelope(lease_ref=ref("ExecutionLease", "lease-1"))


def test_envelope_rejects_nested_secret_material_fields() -> None:
    with pytest.raises(ValidationError, match="must not contain secret"):
        envelope(payload={"orderId": "order-1", "auth": {"accessToken": "never-store"}})


def test_dry_validation_requires_blockers_for_non_available_state() -> None:
    with pytest.raises(ValidationError, match="requires blockers"):
        DryValidationReceipt(
            status=AdapterReadiness.BLOCKED,
            requestFingerprint=FINGERPRINT,
            reversible=False,
        )


def test_unknown_usage_cannot_be_reported_as_zero() -> None:
    with pytest.raises(ValidationError, match="must not invent"):
        NormalizedUsageCandidate(quality=UsageQuality.UNKNOWN, amount=0, unit="request")


def test_deterministic_suite_is_green_and_checks_idempotency() -> None:
    item = revision()
    adapter = DeterministicAdapter(item)
    report = run_adapter_conformance(item, adapter, fixture(item))
    assert report.green is True
    assert adapter.execute_calls == 2
    assert "execute.idempotency" in report.checks
    assert len(report.report_hash) == 64


def test_unknown_is_reconciled_without_a_third_execute() -> None:
    item = revision()
    adapter = DeterministicAdapter(item, unknown=True)
    report = run_adapter_conformance(item, adapter, fixture(item))
    assert report.green is True
    assert adapter.execute_calls == 2
    assert adapter.reconcile_calls == 1
    assert "reconcile.unknown" in report.checks


@pytest.mark.parametrize(
    ("sandbox_identity", "side_effect_free", "blocker"),
    [
        ("sandbox://provider.demo", True, "CONFORMANCE_SANDBOX_NOT_DETERMINISTIC"),
        ("deterministic://provider.demo", False, "CONFORMANCE_ADAPTER_SIDE_EFFECT_FREE_REQUIRED"),
    ],
)
def test_suite_rejects_unsafe_fixture_before_execute(sandbox_identity, side_effect_free, blocker) -> None:
    item = revision()
    adapter = DeterministicAdapter(item)
    adapter.side_effect_free = side_effect_free
    report = run_adapter_conformance(
        item,
        adapter,
        fixture(item, sandbox_identity=sandbox_identity),
    )
    assert report.green is False
    assert blocker in report.blockers
    assert adapter.execute_calls == 0


def test_suite_fails_closed_on_account_scope_drift() -> None:
    item = revision()

    class DriftedAccountAdapter(DeterministicAdapter):
        def resolve_account(self, *, account_ref, tenant):
            value = super().resolve_account(account_ref=account_ref, tenant=tenant)
            return value.model_copy(
                update={"tenant": TenantIdentity(orgId="dev-org", projectId="dev-project")}
            )

    report = run_adapter_conformance(item, DriftedAccountAdapter(item), fixture(item))
    assert report.green is False
    assert "CONFORMANCE_ACCOUNT_SCOPE_DRIFT" in report.blockers


def test_registry_accepts_only_green_exact_revision_and_preserves_legacy_api() -> None:
    item = revision()
    adapter = DeterministicAdapter(item)
    green = run_adapter_conformance(item, adapter, fixture(item))
    registry = ActionAdapterRegistry()
    registry.register("legacy.action", adapter)
    assert registry.get("legacy.action") is adapter
    registry.register_conformant(item, adapter, green)
    assert registry.get_conformant(item.exact_ref()) == (item, adapter)
    drifted = ref("AdapterCapabilityRevision", item.adapter_id, "f" * 64)
    assert registry.get_conformant(drifted) is None


def test_registry_rejects_red_report() -> None:
    item = revision()
    adapter = DeterministicAdapter(item)
    red = run_adapter_conformance(
        item,
        adapter,
        fixture(item, sandbox_identity="sandbox://not-deterministic"),
    )
    with pytest.raises(ValueError, match="GREEN"):
        ActionAdapterRegistry().register_conformant(item, adapter, red)


@pytest.mark.parametrize(
    ("changes", "blocker"),
    [
        ({"lifecycle": AdapterLifecycle.DRAFT}, "CONFORMANCE_REVISION_NOT_PUBLISHED"),
        ({"cancel_mode": AdapterSupportMode.PROVIDER}, "CONFORMANCE_DECLARED_CANCEL_METHOD_MISSING"),
        ({"partial_mode": AdapterSupportMode.ITEMIZED}, "CONFORMANCE_DECLARED_PARTIAL_METHOD_MISSING"),
        (
            {"webhook_contract_ref": ref("WebhookContractRevision", "webhook.default")},
            "CONFORMANCE_DECLARED_WEBHOOK_METHOD_MISSING",
        ),
    ],
)
def test_declared_revision_capabilities_fail_closed_before_execute(changes, blocker) -> None:
    item = revision(**changes)
    adapter = DeterministicAdapter(item)
    report = run_adapter_conformance(item, adapter, fixture(item))
    assert blocker in report.blockers
    assert adapter.execute_calls == 0
