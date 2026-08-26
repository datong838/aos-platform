"""BI-W4-04 governed ecommerce investigation artifact revision contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef


ARTIFACT_SCHEMA = "aos.ecommerce.business-investigation-artifact-revision/v1"
BINDING_SCHEMA = "aos.ecommerce.business-investigation-artifact-binding/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


class BusinessInvestigationArtifactType(StrEnum):
    DOSSIER = "BusinessDossierRevision"
    PROBLEM_MAP = "ProblemMapRevision"
    OPPORTUNITY_MAP = "OpportunityMapRevision"
    SOLUTION_PORTFOLIO = "SolutionPortfolioRevision"


_ALLOWED_INPUTS = {
    BusinessInvestigationArtifactType.DOSSIER: {
        "DataRequirementRevision",
        "DataFulfillmentReceipt",
        "SourceReadinessEnvelope",
        "OntologySnapshotRevision",
        "EvidenceBundleRevision",
    },
    BusinessInvestigationArtifactType.PROBLEM_MAP: {
        "BusinessDossierRevision",
        "EvidenceBundleRevision",
        "InsightRevision",
    },
    BusinessInvestigationArtifactType.OPPORTUNITY_MAP: {
        "BusinessDossierRevision",
        "ProblemMapRevision",
        "EvidenceBundleRevision",
        "InsightRevision",
        "DecisionSummaryRevision",
    },
    BusinessInvestigationArtifactType.SOLUTION_PORTFOLIO: {
        "ProblemMapRevision",
        "OpportunityMapRevision",
        "EvidenceBundleRevision",
        "InsightRevision",
        "DecisionSummaryRevision",
    },
}

_REQUIRED_INPUTS = {
    BusinessInvestigationArtifactType.DOSSIER: {"DataRequirementRevision", "SourceReadinessEnvelope"},
    BusinessInvestigationArtifactType.PROBLEM_MAP: {"BusinessDossierRevision", "EvidenceBundleRevision"},
    BusinessInvestigationArtifactType.OPPORTUNITY_MAP: {
        "BusinessDossierRevision",
        "ProblemMapRevision",
        "EvidenceBundleRevision",
    },
    BusinessInvestigationArtifactType.SOLUTION_PORTFOLIO: {
        "ProblemMapRevision",
        "OpportunityMapRevision",
        "DecisionSummaryRevision",
    },
}


def _canonical_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


class BusinessInvestigationArtifactRevision(AipContractModel):
    schema_version: str = ARTIFACT_SCHEMA
    tenant: TenantContext
    artifact_id: str = Field(min_length=1, max_length=200)
    artifact_type: BusinessInvestigationArtifactType
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    prior_ref: InvestigationExactRef | None = None
    content_hash: str = Field(pattern=SHA256)
    case_ref: InvestigationExactRef
    run_ref: InvestigationExactRef
    input_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=200)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("createdAt must include timezone")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != ARTIFACT_SCHEMA:
            raise ValueError("unsupported artifact schema")
        if self.version != self.revision:
            raise ValueError("version must equal revision")
        if self.case_ref.resource_type != "BusinessInvestigationCaseRevision" or not isinstance(
            self.case_ref.revision, int
        ):
            raise ValueError("caseRef must be a numeric BusinessInvestigationCaseRevision")
        if self.run_ref.resource_type != "BusinessInvestigationRun" or not isinstance(self.run_ref.revision, int):
            raise ValueError("runRef must be a numeric BusinessInvestigationRun")
        if self.revision == 1:
            if self.prior_ref is not None:
                raise ValueError("revision 1 must not have priorRef")
        else:
            if (
                self.prior_ref is None
                or self.prior_ref.resource_type != self.artifact_type.value
                or self.prior_ref.resource_id != self.artifact_id
                or self.prior_ref.revision != self.revision - 1
            ):
                raise ValueError("successor revision requires exact preceding priorRef")
        keys = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash) for ref in self.input_refs]
        if len(keys) != len(set(keys)):
            raise ValueError("inputRefs must be unique")
        input_types = {ref.resource_type for ref in self.input_refs}
        unexpected = input_types - _ALLOWED_INPUTS[self.artifact_type]
        missing = _REQUIRED_INPUTS[self.artifact_type] - input_types
        if unexpected:
            raise ValueError(f"inputRefs contain unsupported types: {sorted(unexpected)}")
        if missing:
            raise ValueError(f"inputRefs are missing required types: {sorted(missing)}")
        for ref in self.input_refs:
            if ref.resource_type in {"DataFulfillmentReceipt", "SourceReadinessEnvelope"} and ref.receipt_id is None:
                raise ValueError(f"{ref.resource_type} input requires receiptId")
        return self

    def calculated_content_hash(self) -> str:
        payload = self.model_dump(by_alias=True, mode="json")
        payload.pop("contentHash")
        return _canonical_hash(payload)


class BusinessInvestigationArtifactBinding(AipContractModel):
    schema_version: str = BINDING_SCHEMA
    tenant: TenantContext
    binding_id: str = Field(min_length=1, max_length=200)
    binding_hash: str = Field(pattern=SHA256)
    artifact_ref: InvestigationExactRef
    selected_channel_ref: InvestigationExactRef
    selected_entity_ref: InvestigationExactRef
    case_ref: InvestigationExactRef
    run_ref: InvestigationExactRef
    selection_revision: int = Field(ge=1)
    data_cutoff: datetime
    lineage_ref: InvestigationExactRef
    bound_by: str = Field(min_length=1, max_length=200)
    bound_at: datetime

    @field_validator("data_cutoff", "bound_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("binding timestamps must include timezone")
        return value

    @model_validator(mode="after")
    def _binding_integrity(self) -> Self:
        if self.schema_version != BINDING_SCHEMA:
            raise ValueError("unsupported artifact binding schema")
        if self.artifact_ref.resource_type not in {item.value for item in BusinessInvestigationArtifactType} or not isinstance(
            self.artifact_ref.revision, int
        ):
            raise ValueError("artifactRef must reference a governed investigation artifact")
        expected_types = (
            (self.selected_channel_ref, "ChannelRevision", "selectedChannelRef"),
            (self.selected_entity_ref, "BusinessEntityRevision", "selectedEntityRef"),
            (self.case_ref, "BusinessInvestigationCaseRevision", "caseRef"),
            (self.run_ref, "BusinessInvestigationRun", "runRef"),
        )
        for ref, expected, field in expected_types:
            if ref.resource_type != expected or not isinstance(ref.revision, int):
                raise ValueError(f"{field} must be a numeric {expected}")
        if self.lineage_ref.resource_type not in {"LineageEventRevision", "LineageRevision"} or not isinstance(
            self.lineage_ref.revision, int
        ):
            raise ValueError("lineageRef must be an exact governed lineage revision")
        if self.data_cutoff > self.bound_at:
            raise ValueError("dataCutoff must not be later than boundAt")
        return self

    def calculated_binding_hash(self) -> str:
        payload = self.model_dump(by_alias=True, mode="json")
        payload.pop("bindingHash")
        return _canonical_hash(payload)


__all__ = [
    "ARTIFACT_SCHEMA",
    "BINDING_SCHEMA",
    "BusinessInvestigationArtifactBinding",
    "BusinessInvestigationArtifactRevision",
    "BusinessInvestigationArtifactType",
]
