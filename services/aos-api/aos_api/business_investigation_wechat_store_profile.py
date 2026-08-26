"""Disabled WeChat Store semantic page and governed export Profile."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Self

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.business_investigation_shared_contracts import InvestigationExactRef


PROFILE_SCHEMA = "aos.business-investigation.wechat-store-profile/v1"
ACCEPTANCE_SCHEMA = "aos.business-investigation.wechat-store-profile-acceptance/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"

WECHAT_STORE_SEMANTIC_FAMILIES = {
    "store_trust",
    "product_supply",
    "order_fulfillment",
    "aftersales_service",
    "traffic_content_ecosystem",
    "customer_membership",
    "marketing_promotion",
    "creator_alliance",
    "finance_settlement",
    "store_analytics",
}
WECHAT_STORE_EXPORT_FAMILIES = {
    "product",
    "order",
    "aftersales",
    "traffic",
    "customer",
    "alliance",
    "settlement",
    "analytics",
}


def _canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class WechatStorePageSemantic(AipContractModel):
    semantic_id: str = Field(min_length=1, max_length=120)
    fact_families: list[str] = Field(min_length=1, max_length=10)
    required_observations: list[str] = Field(min_length=1, max_length=12)
    requires_observation: Literal[True]


class WechatStoreExportMapping(AipContractModel):
    mapping_id: str = Field(min_length=1, max_length=120)
    fact_families: list[str] = Field(min_length=1, max_length=10)
    artifact_schema_ref: InvestigationExactRef
    requires_permission: Literal[True]
    permission_verified: Literal[False]
    export_allowed: Literal[False]
    coverage_verification_required: Literal[True]
    freshness_verification_required: Literal[True]

    @model_validator(mode="after")
    def _artifact_schema_only(self) -> Self:
        if self.artifact_schema_ref.resource_type != "ControlledExportArtifactSchemaRevision":
            raise ValueError("export mapping must reference ControlledExportArtifactSchemaRevision")
        return self


class WechatStoreFailurePolicy(AipContractModel):
    permission_insufficient: Literal["BLOCKED_PERMISSION"]
    async_loading_timeout: Literal["PARTIAL_LOADING_TIMEOUT"]
    virtual_list_truncated: Literal["PARTIAL_PAGINATION"]
    masked_value: Literal["BLOCKED_MASKED_VALUE"]
    page_drift: Literal["BLOCKED_PAGE_DRIFT"]
    external_unknown: Literal["UNKNOWN_RECONCILE"]
    automatic_retry: Literal[False]
    empty_observed: Literal[False]
    external_effect: Literal[False]


class WechatStoreProfile(AipContractModel):
    schema_version: str = PROFILE_SCHEMA
    profile_id: str = Field(min_length=1, max_length=160)
    revision: Literal[1]
    content_hash: str = Field(pattern=SHA256)
    platform: Literal["wechat_store"]
    source_kind: Literal["synthetic", "historical_redacted"]
    generic_capability_ref: InvestigationExactRef
    enabled: Literal[False]
    source_access_authorized: Literal[False]
    installation_ref: None
    instance_overlay_ref: None
    observation_modes: list[Literal["browser_observation", "controlled_export"]] = Field(min_length=2, max_length=2)
    page_semantics: list[WechatStorePageSemantic] = Field(min_length=1, max_length=30)
    export_mappings: list[WechatStoreExportMapping] = Field(min_length=1, max_length=30)
    failure_policy: WechatStoreFailurePolicy
    known_risks: list[str] = Field(min_length=1, max_length=20)
    non_claims: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != PROFILE_SCHEMA:
            raise ValueError("unsupported WeChat Store Profile schema")
        if self.generic_capability_ref.resource_type != "AdapterCapabilityMatrixRevision":
            raise ValueError("genericCapabilityRef must reference AdapterCapabilityMatrixRevision")
        if set(self.observation_modes) != {"browser_observation", "controlled_export"}:
            raise ValueError("required observation modes are incomplete")
        if len({item.semantic_id for item in self.page_semantics}) != len(self.page_semantics):
            raise ValueError("page semantic IDs must be unique")
        if len({item.mapping_id for item in self.export_mappings}) != len(self.export_mappings):
            raise ValueError("export mapping IDs must be unique")
        page_families = {family for item in self.page_semantics for family in item.fact_families}
        if not WECHAT_STORE_SEMANTIC_FAMILIES <= page_families:
            raise ValueError("required WeChat Store page semantic families are incomplete")
        export_families = {family for item in self.export_mappings for family in item.fact_families}
        if not WECHAT_STORE_EXPORT_FAMILIES <= export_families:
            raise ValueError("required WeChat Store export families are incomplete")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        return _canonical_hash(value)


class WechatStoreProfileAcceptanceReceipt(AipContractModel):
    schema_version: str = ACCEPTANCE_SCHEMA
    profile_ref: InvestigationExactRef
    page_semantic_count: int = Field(ge=1)
    export_mapping_count: int = Field(ge=1)
    status: Literal["passed"]
    non_claims: list[str] = Field(min_length=1)


def evaluate_wechat_store_profile(profile: WechatStoreProfile) -> WechatStoreProfileAcceptanceReceipt:
    if profile.calculated_hash() != profile.content_hash:
        raise ValueError("profile content hash drifted")
    return WechatStoreProfileAcceptanceReceipt(
        profileRef={
            "resourceType": "WechatStoreAdapterProfileRevision",
            "resourceId": profile.profile_id,
            "revision": profile.revision,
            "contentHash": profile.content_hash,
        },
        pageSemanticCount=len(profile.page_semantics),
        exportMappingCount=len(profile.export_mappings),
        status="passed",
        nonClaims=[
            "NO_PLATFORM_ACCESS",
            "NO_EXPORT_EXECUTION",
            "NO_PERMISSION_VERIFICATION",
            "NO_ADAPTER_INSTALLATION",
            "NO_EXTERNAL_EFFECT",
        ],
    )
