"""Disabled tenant-bound Business Investigation Adapter InstanceOverlay."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef


OVERLAY_SCHEMA = "aos.business-investigation.instance-overlay/v1"
ACCEPTANCE_SCHEMA = "aos.business-investigation.instance-overlay-acceptance/v1"
TENANT_EVALUATION_SCHEMA = "aos.business-investigation.instance-overlay-tenant-evaluation/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"
OPAQUE_SECRET_REF = r"^(vault|secret|keychain)://[A-Za-z0-9][A-Za-z0-9._/-]{2,255}$"


def _canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class OverlaySessionPolicy(AipContractModel):
    policy_ref: InvestigationExactRef
    session_authorized: Literal[False]
    session_created: Literal[False]
    short_lived: Literal[True]
    revocable: Literal[True]
    purpose_bound: Literal[True]
    entity_bound: Literal[True]
    max_ttl_seconds: int = Field(ge=60, le=3600)


class OverlaySchedulePolicy(AipContractModel):
    enabled: Literal[False]
    timezone: Literal["Asia/Shanghai"]
    cadence: Literal["manual", "daily", "weekly"]
    data_cutoff_lag_seconds: int = Field(ge=0, le=86400)
    max_budget_units: int = Field(ge=1, le=10000)
    retention_days: int = Field(ge=1, le=365)


class OverlayFeatureFlags(AipContractModel):
    browser_observation: Literal[False]
    controlled_export: Literal[False]
    api_read: Literal[False]
    hydration: Literal[False]


class OverlayMappingException(AipContractModel):
    exception_id: str = Field(min_length=1, max_length=120)
    semantic_scope: str = Field(min_length=1, max_length=160)
    verification_required: Literal[True]
    hydration_allowed: Literal[False]


class OverlayFulfillmentPolicy(AipContractModel):
    approval_required: Literal[True]
    source_readiness_required: Literal[True]
    exact_receipt_required: Literal[True]
    automatic_retry: Literal[False]
    external_unknown_action: Literal["UNKNOWN_RECONCILE"]


class BusinessInvestigationInstanceOverlay(AipContractModel):
    schema_version: str = OVERLAY_SCHEMA
    overlay_id: str = Field(min_length=1, max_length=160)
    revision: Literal[1]
    content_hash: str = Field(pattern=SHA256)
    source_kind: Literal["synthetic", "historical_redacted"]
    tenant: TenantContext
    platform: Literal["niushop", "wechat_store", "douyin_store"]
    entity_ref: InvestigationExactRef
    channel_ref: InvestigationExactRef
    account_ref: InvestigationExactRef
    profile_ref: InvestigationExactRef
    installation_lock_ref: InvestigationExactRef
    secret_ref: str = Field(min_length=1, max_length=320)
    session_policy: OverlaySessionPolicy
    allowed_semantic_domains: list[str] = Field(min_length=1, max_length=30)
    schedule_policy: OverlaySchedulePolicy
    mapping_exceptions: list[OverlayMappingException] = Field(max_length=30)
    fulfillment_policy: OverlayFulfillmentPolicy
    feature_flags: OverlayFeatureFlags
    enabled: Literal[False]
    activation_allowed: Literal[False]
    installation_locked: Literal[True]
    kill_switch_engaged: Literal[True]
    non_claims: list[str] = Field(min_length=1, max_length=20)

    @field_validator("secret_ref")
    @classmethod
    def _opaque_secret(cls, value: str) -> str:
        if "?" in value or "#" in value or re.fullmatch(OPAQUE_SECRET_REF, value) is None:
            raise ValueError("secretRef must be an opaque SecretRef without query or fragment")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        expected_types = {
            "entity_ref": "BusinessEntityRevision", "channel_ref": "ChannelRevision",
            "account_ref": "PlatformAccountRevision", "installation_lock_ref": "AdapterInstallationLockRevision",
            "session_policy.policy_ref": "SessionPolicyRevision",
        }
        values = {
            "entity_ref": self.entity_ref, "channel_ref": self.channel_ref,
            "account_ref": self.account_ref, "installation_lock_ref": self.installation_lock_ref,
            "session_policy.policy_ref": self.session_policy.policy_ref,
        }
        display_names = {"entity_ref": "entityRef", "channel_ref": "channelRef", "account_ref": "accountRef", "installation_lock_ref": "installationLockRef", "session_policy.policy_ref": "sessionPolicy.policyRef"}
        for name, expected in expected_types.items():
            if values[name].resource_type != expected:
                raise ValueError(f"{display_names[name]} must reference {expected}")
        profile_types = {"niushop": "NiushopAdapterProfileRevision", "wechat_store": "WechatStoreAdapterProfileRevision", "douyin_store": "DouyinStoreAdapterProfileRevision"}
        if self.profile_ref.resource_type != profile_types[self.platform]:
            raise ValueError("profileRef does not match platform")
        if len(set(self.allowed_semantic_domains)) != len(self.allowed_semantic_domains):
            raise ValueError("allowed semantic domains must be unique")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        return _canonical_hash(value)


class OverlayTenantEvaluation(AipContractModel):
    schema_version: str = TENANT_EVALUATION_SCHEMA
    status: Literal["MATCHED_DISABLED", "BLOCKED_TENANT_MISMATCH"]
    overlay_visible: bool
    activation_allowed: Literal[False]
    blocker: Literal["NONE", "TENANT_SCOPE_MISMATCH"]
    external_effect: Literal[False]


class InstanceOverlayAcceptanceReceipt(AipContractModel):
    schema_version: str = ACCEPTANCE_SCHEMA
    overlay_ref: InvestigationExactRef
    status: Literal["passed"]
    non_claims: list[str] = Field(min_length=1)


def evaluate_overlay_tenant(overlay: BusinessInvestigationInstanceOverlay, org_id: str, project_id: str) -> OverlayTenantEvaluation:
    matched = overlay.tenant.org_id == org_id and overlay.tenant.project_id == project_id
    return OverlayTenantEvaluation(
        status="MATCHED_DISABLED" if matched else "BLOCKED_TENANT_MISMATCH",
        overlayVisible=matched,
        activationAllowed=False,
        blocker="NONE" if matched else "TENANT_SCOPE_MISMATCH",
        externalEffect=False,
    )


def evaluate_instance_overlay(overlay: BusinessInvestigationInstanceOverlay) -> InstanceOverlayAcceptanceReceipt:
    if overlay.calculated_hash() != overlay.content_hash:
        raise ValueError("overlay content hash drifted")
    return InstanceOverlayAcceptanceReceipt(
        overlayRef={"resourceType": "BusinessInvestigationInstanceOverlayRevision", "resourceId": overlay.overlay_id, "revision": overlay.revision, "contentHash": overlay.content_hash},
        status="passed",
        nonClaims=["NO_SECRET_RESOLUTION", "NO_SESSION_CREATION", "NO_SCHEDULE_RUNTIME", "NO_PROFILE_ACTIVATION", "NO_EXTERNAL_EFFECT"],
    )
