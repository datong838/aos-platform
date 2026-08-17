"""Canonical contracts for durable AgentRun execution attempts."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from aos_api.aip_agent_registry_contracts import RegistryReceipt, VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, ArtifactRef, ResourceRef, TenantContext


class AgentRunExecutionStatus(StrEnum):
    PREPARED = "prepared"
    INVOKING = "invoking"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class CreateAgentRunExecutionAttemptRequest(AipContractModel):
    attempt_id: str = Field(min_length=1, max_length=200)
    agent_run_ref: ResourceRef
    attempt_no: int = Field(ge=1)
    route_ref: VersionedAssetRef
    policy_ref: VersionedAssetRef
    model_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    price_snapshot_ref: VersionedAssetRef
    budget_ref: VersionedAssetRef
    capacity_reservation_ref: ResourceRef
    data_classification: str = Field(pattern=r"^(public|internal|confidential)$")
    lineage_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _exact_kinds(self) -> "CreateAgentRunExecutionAttemptRequest":
        expected = {
            "route_ref": "ModelRouteRevision",
            "policy_ref": "RuntimePolicyRevision",
            "model_ref": "RegisteredModelRevision",
            "provider_ref": "ProviderInstanceRevision",
            "price_snapshot_ref": "ModelPriceSnapshotRevision",
            "budget_ref": "BudgetRevision",
        }
        for field_name, asset_type in expected.items():
            if getattr(self, field_name).asset_type != asset_type:
                raise ValueError(f"{field_name} must reference {asset_type}")
        if self.agent_run_ref.resource_type != "AgentRun" or not self.agent_run_ref.revision:
            raise ValueError("agent_run_ref must be an exact AgentRun reference")
        if self.capacity_reservation_ref.resource_type != "CapacityReservation":
            raise ValueError("capacity_reservation_ref must reference CapacityReservation")
        return self


class TransitionAgentRunExecutionAttemptRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: AgentRunExecutionStatus
    to_status: AgentRunExecutionStatus
    provider_receipt_id: str | None = Field(default=None, min_length=1, max_length=240)
    usage_receipt_ids: list[str] = Field(default_factory=list, max_length=32)
    output_artifact_ref: ArtifactRef | None = None
    reason_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{3,120}$")

    @model_validator(mode="after")
    def _terminal_evidence(self) -> "TransitionAgentRunExecutionAttemptRequest":
        evidence = (
            self.provider_receipt_id,
            self.usage_receipt_ids,
            self.output_artifact_ref,
            self.reason_code,
        )
        if self.to_status is AgentRunExecutionStatus.SUCCEEDED:
            if not all(evidence[:3]) or self.reason_code is not None:
                raise ValueError("succeeded attempt requires provider, usage and artifact evidence")
        elif self.to_status in {AgentRunExecutionStatus.FAILED, AgentRunExecutionStatus.UNKNOWN}:
            if self.reason_code is None:
                raise ValueError("failed or unknown attempt requires reason_code")
        elif any(evidence):
            raise ValueError("non-terminal transition cannot carry terminal evidence")
        return self


class AgentRunExecutionAttempt(AipContractModel):
    tenant: TenantContext
    attempt_id: str
    agent_run_id: str
    agent_run_version: int
    attempt_no: int
    route_ref: VersionedAssetRef
    policy_ref: VersionedAssetRef
    model_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    price_snapshot_ref: VersionedAssetRef
    budget_ref: VersionedAssetRef
    capacity_reservation_ref: ResourceRef
    data_classification: str
    lineage_id: str
    request_hash: str
    status: AgentRunExecutionStatus
    provider_receipt_id: str | None = None
    usage_receipt_ids: list[str] = Field(default_factory=list)
    output_artifact_ref: ArtifactRef | None = None
    reason_code: str | None = None
    version: int
    prepared_at: datetime
    invoking_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: str
    updated_at: datetime


class AgentRunExecutionAttemptCommandResponse(AipContractModel):
    tenant: TenantContext
    attempt: AgentRunExecutionAttempt
    receipt: RegistryReceipt


class AgentRunExecutionAttemptListResponse(AipContractModel):
    tenant: TenantContext
    items: list[AgentRunExecutionAttempt]
    count: int = Field(ge=0)
