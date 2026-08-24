"""Zero-side-effect conformance harness for Action adapter capabilities."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Protocol

from aos_api.aip_action_adapters import AdapterOutcome
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
)


class ConformanceAdapter(Protocol):
    side_effect_free: bool
    adapter_revision_ref: ImmutableExactRevisionRef

    def resolve_account(
        self, *, account_ref: ImmutableExactRevisionRef, tenant: TenantIdentity
    ) -> AuthorizedAccountContext: ...

    def dry_validate(self, *, envelope: AdapterInvocationEnvelope) -> DryValidationReceipt: ...

    def execute(self, *, payload: dict, idempotency_key: str) -> AdapterOutcome: ...

    def reconcile(self, *, provider_request_id: str, request_fingerprint: str) -> AdapterOutcome: ...

    def normalize_usage(self, *, outcome: AdapterOutcome) -> NormalizedUsageCandidate: ...


@dataclass(frozen=True)
class AdapterConformanceFixture:
    sandbox_identity: str
    envelope: AdapterInvocationEnvelope


@dataclass(frozen=True)
class AdapterConformanceReport:
    adapter_revision_ref: ImmutableExactRevisionRef
    sandbox_identity: str
    checks: tuple[str, ...]
    blockers: tuple[str, ...]
    report_hash: str

    @property
    def green(self) -> bool:
        return not self.blockers


def _report(
    revision: AdapterCapabilityRevision,
    fixture: AdapterConformanceFixture,
    checks: list[str],
    blockers: list[str],
) -> AdapterConformanceReport:
    body = {
        "adapterRevisionRef": revision.exact_ref().model_dump(mode="json", by_alias=True),
        "sandboxIdentity": fixture.sandbox_identity,
        "checks": checks,
        "blockers": blockers,
    }
    digest = sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AdapterConformanceReport(
        adapter_revision_ref=revision.exact_ref(),
        sandbox_identity=fixture.sandbox_identity,
        checks=tuple(checks),
        blockers=tuple(blockers),
        report_hash=digest,
    )


def run_adapter_conformance(
    revision: AdapterCapabilityRevision,
    adapter: ConformanceAdapter,
    fixture: AdapterConformanceFixture,
) -> AdapterConformanceReport:
    """Run deterministic contract checks without granting production readiness."""
    checks: list[str] = ["definition.hash", "definition.exact_refs"]
    blockers: list[str] = []
    if not fixture.sandbox_identity.startswith("deterministic://"):
        blockers.append("CONFORMANCE_SANDBOX_NOT_DETERMINISTIC")
    if getattr(adapter, "side_effect_free", False) is not True:
        blockers.append("CONFORMANCE_ADAPTER_SIDE_EFFECT_FREE_REQUIRED")
    if getattr(adapter, "adapter_revision_ref", None) != revision.exact_ref():
        blockers.append("CONFORMANCE_ADAPTER_REVISION_DRIFT")
    if fixture.envelope.capability_ref != revision.capability_ref:
        blockers.append("CONFORMANCE_CAPABILITY_REVISION_DRIFT")
    if revision.lifecycle is not AdapterLifecycle.PUBLISHED:
        blockers.append("CONFORMANCE_REVISION_NOT_PUBLISHED")
    if revision.cancel_mode is AdapterSupportMode.PROVIDER and not callable(
        getattr(adapter, "cancel", None)
    ):
        blockers.append("CONFORMANCE_DECLARED_CANCEL_METHOD_MISSING")
    if revision.partial_mode is AdapterSupportMode.ITEMIZED and not callable(
        getattr(adapter, "normalize_partial", None)
    ):
        blockers.append("CONFORMANCE_DECLARED_PARTIAL_METHOD_MISSING")
    if revision.webhook_contract_ref is not None and not callable(
        getattr(adapter, "verify_webhook", None)
    ):
        blockers.append("CONFORMANCE_DECLARED_WEBHOOK_METHOD_MISSING")
    if blockers:
        return _report(revision, fixture, checks, blockers)

    try:
        account = adapter.resolve_account(
            account_ref=fixture.envelope.account_ref,
            tenant=fixture.envelope.tenant,
        )
        checks.append("account.resolve")
        if account.account_ref != fixture.envelope.account_ref or account.tenant != fixture.envelope.tenant:
            blockers.append("CONFORMANCE_ACCOUNT_SCOPE_DRIFT")
        if account.provider != revision.provider:
            blockers.append("CONFORMANCE_ACCOUNT_PROVIDER_DRIFT")
        if account.account_kind != revision.account_kind:
            blockers.append("CONFORMANCE_ACCOUNT_KIND_DRIFT")
        if account.readiness is not AdapterReadiness.AVAILABLE:
            blockers.append("CONFORMANCE_ACCOUNT_NOT_AVAILABLE")
        if fixture.envelope.purpose not in account.allowed_purposes:
            blockers.append("CONFORMANCE_PURPOSE_NOT_ALLOWED")
        if not set(account.required_markings).issubset(fixture.envelope.markings):
            blockers.append("CONFORMANCE_MARKING_REQUIRED")

        dry = adapter.dry_validate(envelope=fixture.envelope)
        checks.append("dry_validate")
        if dry.request_fingerprint != fixture.envelope.request_fingerprint:
            blockers.append("CONFORMANCE_DRY_VALIDATION_FINGERPRINT_DRIFT")
        if dry.status is not AdapterReadiness.AVAILABLE:
            blockers.append("CONFORMANCE_DRY_VALIDATION_BLOCKED")
            blockers.extend(f"DRY:{item.code}" for item in dry.blockers)
        if blockers:
            return _report(revision, fixture, checks, blockers)

        first = adapter.execute(
            payload=dict(fixture.envelope.payload),
            idempotency_key=fixture.envelope.idempotency_key,
        )
        second = adapter.execute(
            payload=dict(fixture.envelope.payload),
            idempotency_key=fixture.envelope.idempotency_key,
        )
        checks.extend(("execute.status", "execute.idempotency"))
        allowed = {"accepted", "applied", "failed", "unknown"}
        if first.status not in allowed or second.status not in allowed:
            blockers.append("CONFORMANCE_PROVIDER_STATUS_INVALID")
        if first != second:
            blockers.append("CONFORMANCE_IDEMPOTENCY_REPLAY_DRIFT")
        terminal = first
        if first.status == "unknown":
            if not first.provider_request_id:
                blockers.append("CONFORMANCE_UNKNOWN_REQUEST_REF_REQUIRED")
            else:
                terminal = adapter.reconcile(
                    provider_request_id=first.provider_request_id,
                    request_fingerprint=fixture.envelope.request_fingerprint,
                )
                checks.append("reconcile.unknown")
                if terminal.status not in {"applied", "failed", "unknown"}:
                    blockers.append("CONFORMANCE_RECONCILE_STATUS_INVALID")

        usage = adapter.normalize_usage(outcome=terminal)
        checks.append("usage.normalize")
        if terminal.provider_request_id and usage.provider_request_id != terminal.provider_request_id:
            blockers.append("CONFORMANCE_USAGE_REQUEST_REF_DRIFT")
    except Exception as exc:  # adapters must fail as blockers, not escape the suite
        blockers.append(f"CONFORMANCE_ADAPTER_EXCEPTION:{type(exc).__name__}")
    return _report(revision, fixture, checks, blockers)


__all__ = [
    "AdapterConformanceFixture",
    "AdapterConformanceReport",
    "ConformanceAdapter",
    "run_adapter_conformance",
]
