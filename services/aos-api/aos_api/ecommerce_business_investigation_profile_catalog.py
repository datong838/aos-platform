"""Versioned L1 authorities for ecommerce InvestigationProfile and Scope.

The catalog is intentionally tenant- and runtime-independent.  It publishes
stable analysis intent only; AIP compilation still has to resolve exact Logic,
SkillBinding, ResponsibilityPlan and ProductionContext references separately.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


StageId = Literal["portrait", "diagnosis", "solution-design"]
STAGE_ORDER: tuple[StageId, ...] = ("portrait", "diagnosis", "solution-design")


def _content_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class EcommerceInvestigationProfileStage(AipContractModel):
    stage_id: StageId
    required_capability_ids: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _capabilities_are_unique(self) -> "EcommerceInvestigationProfileStage":
        if len(self.required_capability_ids) != len(set(self.required_capability_ids)):
            raise ValueError("requiredCapabilityIds must be unique within a stage")
        return self


class EcommerceInvestigationProfileRevision(AipContractModel):
    schema_version: Literal["aos.ecommerce.investigation-profile/v1"] = (
        "aos.ecommerce.investigation-profile/v1"
    )
    profile_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    profile_type: Literal["ecommerce.business-investigation"] = (
        "ecommerce.business-investigation"
    )
    analysis_type: Literal["initial_store_analysis"]
    display_name: str = Field(min_length=1, max_length=200)
    stages: tuple[EcommerceInvestigationProfileStage, ...] = Field(
        min_length=3, max_length=3
    )
    required_fact_profiles: tuple[str, ...] = Field(min_length=1, max_length=64)
    responsibility_template_code: str = Field(min_length=1, max_length=120)
    handoff_policy_code: str = Field(min_length=1, max_length=120)
    safety_mode: Literal["read-only"] = "read-only"
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _is_canonical_revision(self) -> "EcommerceInvestigationProfileRevision":
        if tuple(stage.stage_id for stage in self.stages) != STAGE_ORDER:
            raise ValueError("stages must use portrait, diagnosis, solution-design order")
        capabilities = [
            capability
            for stage in self.stages
            for capability in stage.required_capability_ids
        ]
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("required capabilities must be unique across stages")
        if len(self.required_fact_profiles) != len(set(self.required_fact_profiles)):
            raise ValueError("requiredFactProfiles must be unique")
        if self.calculated_content_hash() != self.content_hash:
            raise ValueError("InvestigationProfile contentHash mismatch")
        return self

    def calculated_content_hash(self) -> str:
        return _content_hash(
            self.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
        )

    @property
    def exact_ref(self) -> InvestigationExactRef:
        return InvestigationExactRef(
            resourceType="InvestigationProfileRevision",
            resourceId=self.profile_id,
            revision=self.revision,
            contentHash=self.content_hash,
        )


class EcommerceInvestigationScopeRevision(AipContractModel):
    schema_version: Literal["aos.ecommerce.investigation-scope/v1"] = (
        "aos.ecommerce.investigation-scope/v1"
    )
    scope_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    analysis_type: Literal["initial_store_analysis"]
    business_entity_selector: Literal["current-business-entity"] = (
        "current-business-entity"
    )
    coverage: Literal["full-store"] = "full-store"
    access_mode: Literal["read-only"] = "read-only"
    object_types: tuple[str, ...] = Field(min_length=1, max_length=64)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _is_canonical_revision(self) -> "EcommerceInvestigationScopeRevision":
        if len(self.object_types) != len(set(self.object_types)):
            raise ValueError("objectTypes must be unique")
        if self.calculated_content_hash() != self.content_hash:
            raise ValueError("InvestigationScope contentHash mismatch")
        return self

    def calculated_content_hash(self) -> str:
        return _content_hash(
            self.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
        )

    @property
    def exact_ref(self) -> InvestigationExactRef:
        return InvestigationExactRef(
            resourceType="InvestigationScopeRevision",
            resourceId=self.scope_id,
            revision=self.revision,
            contentHash=self.content_hash,
        )


def _build_profile() -> EcommerceInvestigationProfileRevision:
    payload = {
        "schemaVersion": "aos.ecommerce.investigation-profile/v1",
        "profileId": "ecommerce.initial-store-analysis",
        "revision": 1,
        "profileType": "ecommerce.business-investigation",
        "analysisType": "initial_store_analysis",
        "displayName": "全店经营基线分析",
        "stages": (
            {
                "stageId": "portrait",
                "requiredCapabilityIds": (
                    "frame-problem",
                    "build-evidence-pack",
                    "identify-data-gaps",
                    "profile-data-semantics",
                ),
            },
            {
                "stageId": "diagnosis",
                "requiredCapabilityIds": (
                    "form-hypotheses",
                    "diagnose-metric-change",
                    "analyze-root-cause",
                ),
            },
            {
                "stageId": "solution-design",
                "requiredCapabilityIds": (
                    "compare-alternatives",
                    "estimate-impact",
                    "rank-recommendations",
                    "prepare-handoff",
                ),
            },
        ),
        "requiredFactProfiles": tuple(source.object_type for source in CANONICAL_QYH_SOURCES),
        "responsibilityTemplateCode": "ecommerce.business-investigation.readonly",
        "handoffPolicyCode": "ecommerce.business-investigation.review-required",
        "safetyMode": "read-only",
    }
    return EcommerceInvestigationProfileRevision.model_validate(
        {**payload, "contentHash": _content_hash(payload)}
    )


def _build_scope() -> EcommerceInvestigationScopeRevision:
    payload = {
        "schemaVersion": "aos.ecommerce.investigation-scope/v1",
        "scopeId": "ecommerce.current-business-entity.full-store.readonly",
        "revision": 1,
        "analysisType": "initial_store_analysis",
        "businessEntitySelector": "current-business-entity",
        "coverage": "full-store",
        "accessMode": "read-only",
        "objectTypes": tuple(source.object_type for source in CANONICAL_QYH_SOURCES),
    }
    return EcommerceInvestigationScopeRevision.model_validate(
        {**payload, "contentHash": _content_hash(payload)}
    )


INITIAL_STORE_PROFILE = _build_profile()
INITIAL_STORE_SCOPE = _build_scope()


class EcommerceInvestigationProfileCatalog:
    """Resolve one immutable L1 profile/scope pair by exact analysis type."""

    def read(
        self, analysis_type: str
    ) -> tuple[
        EcommerceInvestigationProfileRevision, EcommerceInvestigationScopeRevision
    ] | None:
        if analysis_type != "initial_store_analysis":
            return None
        return INITIAL_STORE_PROFILE, INITIAL_STORE_SCOPE
