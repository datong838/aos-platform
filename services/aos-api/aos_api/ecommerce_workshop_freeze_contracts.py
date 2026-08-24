"""Strict Workshop contracts for the W3-04 four-contract freeze command."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef, ProductionContextRevision
from aos_api.ecommerce_workshop_prepare_contracts import PrepareSideEffectCounters


class WorkshopFreezeRequest(AipContractModel):
    command: Literal["freeze"] = "freeze"
    preparation_id: str = Field(min_length=1, max_length=200)
    production_profile_ref: ExactRevisionRef
    evidence_bundle_ref: ExactRevisionRef
    eval_contract_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _exact_ref_kinds(self) -> "WorkshopFreezeRequest":
        expected = {
            "production_profile_ref": "ProductionProfileRevision",
            "evidence_bundle_ref": "EvidenceBundleRevision",
            "eval_contract_ref": "EvalContractRevision",
            "responsibility_plan_ref": "ResponsibilityPlanRevision",
        }
        for field, resource_type in expected.items():
            if getattr(self, field).resource_type != resource_type:
                raise ValueError(f"{field} must reference {resource_type}")
        return self


class WorkshopFreezeReceipt(AipContractModel):
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    preparation_ref: ExactRevisionRef
    production_context_ref: ExactRevisionRef
    side_effects: PrepareSideEffectCounters
    next_allowed_commands: list[str] = Field(default_factory=list)


class WorkshopFreezeResponse(AipContractModel):
    tenant: TenantContext
    module_id: str
    production_profile_ref: ExactRevisionRef
    context: ProductionContextRevision
    receipt: WorkshopFreezeReceipt
