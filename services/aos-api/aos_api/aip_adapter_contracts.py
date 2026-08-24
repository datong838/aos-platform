"""Immutable contracts for versioned Action adapter capabilities.

The contracts in this module are intentionally store- and transport-neutral.
They do not publish an adapter, resolve a real secret, or authorize an Action.
"""
from __future__ import annotations

from hashlib import sha256
import json
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import ActionRiskLevel, AipContractModel


class AdapterContractModel(AipContractModel):
    model_config = ConfigDict(frozen=True)


class ImmutableExactRevisionRef(AdapterContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdapterLifecycle(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"


class AdapterSupportMode(StrEnum):
    REQUIRED = "required"
    PROVIDER = "provider"
    MANUAL = "manual"
    ITEMIZED = "itemized"
    UNSUPPORTED = "unsupported"


class AdapterReadiness(StrEnum):
    AVAILABLE = "available"
    BLOCKED = "blocked"
    STALE = "stale"
    UNKNOWN = "unknown"


class UsageQuality(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class AdapterCapabilityRevision(AdapterContractModel):
    adapter_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle: AdapterLifecycle
    provider: str = Field(min_length=1, max_length=120)
    account_kind: str = Field(min_length=1, max_length=120)
    capability_ref: ImmutableExactRevisionRef
    action_type_family: str = Field(min_length=1, max_length=160)
    input_schema_ref: ImmutableExactRevisionRef
    output_schema_ref: ImmutableExactRevisionRef
    receipt_schema_ref: ImmutableExactRevisionRef
    usage_schema_ref: ImmutableExactRevisionRef
    risk_floor: ActionRiskLevel
    idempotency_domain: str = Field(min_length=1, max_length=160)
    timeout_seconds: int = Field(ge=1, le=600)
    dry_validate_mode: AdapterSupportMode
    reconcile_mode: AdapterSupportMode
    cancel_mode: AdapterSupportMode
    partial_mode: AdapterSupportMode
    webhook_contract_ref: ImmutableExactRevisionRef | None = None
    rate_policy_ref: ImmutableExactRevisionRef
    capacity_policy_ref: ImmutableExactRevisionRef
    license_policy_ref: ImmutableExactRevisionRef
    redaction_policy_ref: ImmutableExactRevisionRef
    readiness_policy_ref: ImmutableExactRevisionRef

    @field_validator("adapter_id", "provider", "account_kind", "action_type_family", "idempotency_domain")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("contract strings must not contain surrounding whitespace")
        return value

    @model_validator(mode="after")
    def _exact_types_and_hash(self) -> "AdapterCapabilityRevision":
        expected_types = {
            "capability_ref": {"CapabilityRevision"},
            "input_schema_ref": {"SchemaRevision", "InputSchemaRevision"},
            "output_schema_ref": {"SchemaRevision", "OutputSchemaRevision"},
            "receipt_schema_ref": {"SchemaRevision", "ReceiptSchemaRevision"},
            "usage_schema_ref": {"SchemaRevision", "UsageSchemaRevision"},
            "rate_policy_ref": {"RatePolicyRevision"},
            "capacity_policy_ref": {"CapacityPolicyRevision"},
            "license_policy_ref": {"LicensePolicyRevision"},
            "redaction_policy_ref": {"RedactionPolicyRevision"},
            "readiness_policy_ref": {"ReadinessPolicyRevision"},
        }
        for field_name, allowed in expected_types.items():
            ref = getattr(self, field_name)
            if ref.resource_type not in allowed:
                raise ValueError(f"{field_name} must reference {sorted(allowed)}")
        if self.dry_validate_mode is not AdapterSupportMode.REQUIRED:
            raise ValueError("dryValidateMode must be required")
        if self.reconcile_mode not in {AdapterSupportMode.PROVIDER, AdapterSupportMode.MANUAL}:
            raise ValueError("reconcileMode must be provider or manual")
        if self.cancel_mode not in {
            AdapterSupportMode.PROVIDER,
            AdapterSupportMode.MANUAL,
            AdapterSupportMode.UNSUPPORTED,
        }:
            raise ValueError("cancelMode must be provider, manual or unsupported")
        if self.partial_mode not in {AdapterSupportMode.ITEMIZED, AdapterSupportMode.UNSUPPORTED}:
            raise ValueError("partialMode must be itemized or unsupported")
        if self.webhook_contract_ref is not None and self.webhook_contract_ref.resource_type != "WebhookContractRevision":
            raise ValueError("webhookContractRef must reference WebhookContractRevision")
        if self.content_hash != self.expected_content_hash():
            raise ValueError("contentHash does not match canonical adapter capability definition")
        return self

    def definition_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude={"content_hash"})

    def expected_content_hash(self) -> str:
        canonical = json.dumps(
            self.definition_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return sha256(canonical).hexdigest()

    def exact_ref(self) -> ImmutableExactRevisionRef:
        return ImmutableExactRevisionRef(
            resourceType="AdapterCapabilityRevision",
            resourceId=self.adapter_id,
            revision=self.revision,
            contentHash=self.content_hash,
        )

    @classmethod
    def seal(cls, **definition: Any) -> "AdapterCapabilityRevision":
        if "content_hash" in definition or "contentHash" in definition:
            raise ValueError("seal computes contentHash")
        provisional = cls.model_construct(content_hash="0" * 64, **definition)
        return cls(contentHash=provisional.expected_content_hash(), **definition)


class TenantIdentity(AdapterContractModel):
    org_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)


class AuthorizedAccountContext(AdapterContractModel):
    tenant: TenantIdentity
    account_ref: ImmutableExactRevisionRef
    provider: str = Field(min_length=1, max_length=120)
    account_kind: str = Field(min_length=1, max_length=120)
    allowed_purposes: tuple[str, ...] = Field(min_length=1)
    required_markings: tuple[str, ...] = ()
    readiness: AdapterReadiness
    secret_ref: str = Field(min_length=10, max_length=500)

    @model_validator(mode="after")
    def _safe_account(self) -> "AuthorizedAccountContext":
        if self.account_ref.resource_type != "AccountRevision":
            raise ValueError("accountRef must reference AccountRevision")
        if not self.secret_ref.startswith("secret://"):
            raise ValueError("secretRef must be an opaque secret:// reference")
        if len(set(self.allowed_purposes)) != len(self.allowed_purposes):
            raise ValueError("allowedPurposes must be unique")
        return self


class AdapterInvocationEnvelope(AdapterContractModel):
    tenant: TenantIdentity
    proposal_ref: ImmutableExactRevisionRef
    lease_ref: ImmutableExactRevisionRef
    capability_ref: ImmutableExactRevisionRef
    account_ref: ImmutableExactRevisionRef
    purpose: str = Field(min_length=1, max_length=500)
    markings: tuple[str, ...] = ()
    payload: dict[str, Any]
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _exact_envelope_types(self) -> "AdapterInvocationEnvelope":
        expected = {
            "proposal_ref": "ActionProposalRevision",
            "lease_ref": "ExecutionLeaseRevision",
            "capability_ref": "CapabilityRevision",
            "account_ref": "AccountRevision",
        }
        for field_name, resource_type in expected.items():
            if getattr(self, field_name).resource_type != resource_type:
                raise ValueError(f"{field_name} must reference {resource_type}")
        sensitive = {"secret", "token", "cookie", "password", "authorization", "apikey"}

        def contains_sensitive_key(value: Any) -> bool:
            if isinstance(value, dict):
                for key, nested in value.items():
                    normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
                    if any(marker in normalized for marker in sensitive):
                        return True
                    if contains_sensitive_key(nested):
                        return True
            if isinstance(value, (list, tuple)):
                return any(contains_sensitive_key(item) for item in value)
            return False

        if contains_sensitive_key(self.payload):
            raise ValueError("payload must not contain secret, token, cookie or password fields")
        return self


class AdapterBlocker(AdapterContractModel):
    code: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)


class DryValidationReceipt(AdapterContractModel):
    status: AdapterReadiness
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    blockers: tuple[AdapterBlocker, ...] = ()
    estimated_cost: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=12)
    reversible: bool

    @model_validator(mode="after")
    def _status_consistency(self) -> "DryValidationReceipt":
        if self.status is AdapterReadiness.AVAILABLE and self.blockers:
            raise ValueError("available dry validation cannot contain blockers")
        if self.status is not AdapterReadiness.AVAILABLE and not self.blockers:
            raise ValueError("non-available dry validation requires blockers")
        if (self.estimated_cost is None) != (self.currency is None):
            raise ValueError("estimatedCost and currency must be provided together")
        return self


class NormalizedUsageCandidate(AdapterContractModel):
    provider_request_id: str | None = Field(default=None, max_length=500)
    quality: UsageQuality
    amount: float | None = Field(default=None, ge=0)
    unit: str = Field(min_length=1, max_length=80)
    currency: str | None = Field(default=None, min_length=3, max_length=12)

    @model_validator(mode="after")
    def _unknown_is_not_zero(self) -> "NormalizedUsageCandidate":
        if self.quality is UsageQuality.UNKNOWN and self.amount is not None:
            raise ValueError("unknown usage must not invent an amount")
        if self.quality is not UsageQuality.UNKNOWN and self.amount is None:
            raise ValueError("measured or estimated usage requires amount")
        return self


__all__ = [
    "AdapterBlocker",
    "AdapterCapabilityRevision",
    "AdapterInvocationEnvelope",
    "AdapterLifecycle",
    "AdapterReadiness",
    "AdapterSupportMode",
    "AuthorizedAccountContext",
    "DryValidationReceipt",
    "ImmutableExactRevisionRef",
    "NormalizedUsageCandidate",
    "TenantIdentity",
    "UsageQuality",
]
