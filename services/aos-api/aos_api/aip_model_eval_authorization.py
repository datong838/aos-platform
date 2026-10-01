"""Read-only first-Eval preflight; never a Provider or runtime admission token."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext


class ModelEvalPreflight(AipContractModel):
    tenant: TenantContext
    source_ref: VersionedAssetRef
    target_ref: VersionedAssetRef
    expected_head_version: int = Field(strict=True, ge=1)
    provider_ref: VersionedAssetRef
    price_ref: VersionedAssetRef
    quota_policy_ref: VersionedAssetRef
    budget_policy_ref: VersionedAssetRef
    checked_at: datetime
    blocker_codes: list[str] = Field(min_length=1, max_length=32)
    purpose: Literal["quality-eval"] = "quality-eval"
    execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _exact_preflight(self) -> "ModelEvalPreflight":
        source, target = self.source_ref, self.target_ref
        if (
            source.asset_type != "RegisteredModelRevision"
            or target.asset_type != source.asset_type
            or target.asset_id != source.asset_id
            or target.revision != source.revision + 1
            or self.provider_ref.asset_type != "ProviderInstanceRevision"
            or self.price_ref.asset_type != "ModelPriceSnapshotRevision"
            or self.quota_policy_ref.asset_type != "QuotaPolicyRevision"
            or self.budget_policy_ref.asset_type != "BudgetPolicyRevision"
            or self.checked_at.utcoffset() is None
            or len(set(self.blocker_codes)) != len(self.blocker_codes)
            or any(not code or code.strip() != code for code in self.blocker_codes)
        ):
            raise ValueError("exact blocked Model first-Eval preflight required")
        return self


__all__ = ["ModelEvalPreflight"]
