"""Disabled Douyin Store semantic page/export Profile with drift detection."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Self

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.business_investigation_shared_contracts import InvestigationExactRef


PROFILE_SCHEMA = "aos.business-investigation.douyin-store-profile/v1"
ACCEPTANCE_SCHEMA = "aos.business-investigation.douyin-store-profile-acceptance/v1"
OBSERVATION_SCHEMA = "aos.business-investigation.douyin-page-observation-evaluation/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"

DOUYIN_STORE_SEMANTIC_FAMILIES = {
    "store_experience", "product_structure", "search_shelf", "content_live",
    "creator_alliance", "order_fulfillment", "aftersales_expectation",
    "customer_membership", "market_competition", "unit_economics",
}
DOUYIN_STORE_EXPORT_FAMILIES = {
    "product", "order", "aftersales", "traffic", "content", "creator",
    "marketing", "settlement", "analytics",
}


def _canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class DouyinStorePageSemantic(AipContractModel):
    semantic_id: str = Field(min_length=1, max_length=120)
    fact_families: list[str] = Field(min_length=1, max_length=10)
    required_observations: list[str] = Field(min_length=1, max_length=12)
    semantic_landmarks: list[str] = Field(min_length=2, max_length=12)
    signature_hash: str = Field(pattern=SHA256)
    requires_observation: Literal[True]

    @model_validator(mode="after")
    def _signature_integrity(self) -> Self:
        if len(set(self.semantic_landmarks)) != len(self.semantic_landmarks):
            raise ValueError("semantic landmarks must be unique")
        if self.calculated_signature_hash() != self.signature_hash:
            raise ValueError("page signature hash drifted")
        return self

    def calculated_signature_hash(self) -> str:
        return _canonical_hash({
            "semanticId": self.semantic_id,
            "factFamilies": self.fact_families,
            "requiredObservations": self.required_observations,
            "semanticLandmarks": self.semantic_landmarks,
        })


class DouyinStoreExportMapping(AipContractModel):
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


class DouyinStoreFailurePolicy(AipContractModel):
    permission_insufficient: Literal["BLOCKED_PERMISSION"]
    page_drift: Literal["BLOCKED_PAGE_DRIFT"]
    dynamic_menu_unknown: Literal["UNKNOWN_DYNAMIC_MENU"]
    metric_definition_conflict: Literal["BLOCKED_METRIC_DEFINITION"]
    profile_disable_on_page_drift: Literal[True]
    automatic_retry: Literal[False]
    empty_observed: Literal[False]
    external_effect: Literal[False]


class DouyinStoreProfile(AipContractModel):
    schema_version: str = PROFILE_SCHEMA
    profile_id: str = Field(min_length=1, max_length=160)
    revision: Literal[1]
    content_hash: str = Field(pattern=SHA256)
    platform: Literal["douyin_store"]
    source_kind: Literal["synthetic", "historical_redacted"]
    generic_capability_ref: InvestigationExactRef
    enabled: Literal[False]
    source_access_authorized: Literal[False]
    installation_ref: None
    instance_overlay_ref: None
    observation_modes: list[Literal["browser_observation", "controlled_export"]] = Field(min_length=2, max_length=2)
    page_semantics: list[DouyinStorePageSemantic] = Field(min_length=1, max_length=30)
    export_mappings: list[DouyinStoreExportMapping] = Field(min_length=1, max_length=30)
    failure_policy: DouyinStoreFailurePolicy
    known_risks: list[str] = Field(min_length=1, max_length=20)
    non_claims: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != PROFILE_SCHEMA:
            raise ValueError("unsupported Douyin Store Profile schema")
        if self.generic_capability_ref.resource_type != "AdapterCapabilityMatrixRevision":
            raise ValueError("genericCapabilityRef must reference AdapterCapabilityMatrixRevision")
        if set(self.observation_modes) != {"browser_observation", "controlled_export"}:
            raise ValueError("required observation modes are incomplete")
        if len({item.semantic_id for item in self.page_semantics}) != len(self.page_semantics):
            raise ValueError("page semantic IDs must be unique")
        if len({item.mapping_id for item in self.export_mappings}) != len(self.export_mappings):
            raise ValueError("export mapping IDs must be unique")
        page_families = {family for item in self.page_semantics for family in item.fact_families}
        if not DOUYIN_STORE_SEMANTIC_FAMILIES <= page_families:
            raise ValueError("required Douyin Store page semantic families are incomplete")
        export_families = {family for item in self.export_mappings for family in item.fact_families}
        if not DOUYIN_STORE_EXPORT_FAMILIES <= export_families:
            raise ValueError("required Douyin Store export families are incomplete")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        return _canonical_hash(value)


class DouyinPageObservationEvaluation(AipContractModel):
    schema_version: str = OBSERVATION_SCHEMA
    semantic_id: str
    status: Literal["MATCHED", "BLOCKED_PAGE_DRIFT"]
    semantic_contract_usable: bool
    profile_activation_allowed: Literal[False]
    missing_landmarks: list[str]
    disable_reason: Literal["NONE", "SEMANTIC_LANDMARK_MISSING"]
    automatic_retry: Literal[False]
    external_effect: Literal[False]


class DouyinStoreProfileAcceptanceReceipt(AipContractModel):
    schema_version: str = ACCEPTANCE_SCHEMA
    profile_ref: InvestigationExactRef
    page_semantic_count: int = Field(ge=1)
    export_mapping_count: int = Field(ge=1)
    status: Literal["passed"]
    non_claims: list[str] = Field(min_length=1)


def evaluate_douyin_page_observation(
    profile: DouyinStoreProfile,
    semantic_id: str,
    observed_landmarks: set[str],
) -> DouyinPageObservationEvaluation:
    page = next((item for item in profile.page_semantics if item.semantic_id == semantic_id), None)
    if page is None:
        raise ValueError("unknown page semantic")
    missing = sorted(set(page.semantic_landmarks) - observed_landmarks)
    drifted = bool(missing)
    return DouyinPageObservationEvaluation(
        semanticId=semantic_id,
        status="BLOCKED_PAGE_DRIFT" if drifted else "MATCHED",
        semanticContractUsable=not drifted,
        profileActivationAllowed=False,
        missingLandmarks=missing,
        disableReason="SEMANTIC_LANDMARK_MISSING" if drifted else "NONE",
        automaticRetry=False,
        externalEffect=False,
    )


def evaluate_douyin_store_profile(profile: DouyinStoreProfile) -> DouyinStoreProfileAcceptanceReceipt:
    if profile.calculated_hash() != profile.content_hash:
        raise ValueError("profile content hash drifted")
    return DouyinStoreProfileAcceptanceReceipt(
        profileRef={
            "resourceType": "DouyinStoreAdapterProfileRevision",
            "resourceId": profile.profile_id,
            "revision": profile.revision,
            "contentHash": profile.content_hash,
        },
        pageSemanticCount=len(profile.page_semantics),
        exportMappingCount=len(profile.export_mappings),
        status="passed",
        nonClaims=[
            "NO_PLATFORM_ACCESS", "NO_EXPORT_EXECUTION", "NO_API_VERIFICATION",
            "NO_PROFILE_ACTIVATION", "NO_EXTERNAL_EFFECT",
        ],
    )
