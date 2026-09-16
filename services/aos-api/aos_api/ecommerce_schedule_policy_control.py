"""Immutable authority joining an approved SchedulePolicy write to its runtime epoch."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from psycopg.types.json import Jsonb

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


class SchedulePolicyRuntimeBinding(AipContractModel):
    installation_id: str = Field(min_length=36, max_length=36)
    generation: str = Field(min_length=36, max_length=36)
    execution_epoch: int = Field(ge=1)


class SchedulePolicyControlReceipt(AipContractModel):
    schema_version: Literal["aos.ecommerce.schedule-policy-control-receipt/v1"]
    tenant: TenantContext
    receipt_ref: InvestigationExactRef
    policy_ref: InvestigationExactRef
    case_ref: InvestigationExactRef
    approval_ref: InvestigationExactRef
    command_receipt_id: str = Field(min_length=1, max_length=200)
    dispatch: SchedulePolicyRuntimeBinding
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_authority(self):
        if (
            self.receipt_ref.resource_type != "SchedulePolicyControlReceipt"
            or self.receipt_ref.revision != 1
            or self.receipt_ref.content_hash != self.content_hash
            or self.policy_ref.resource_type != "SchedulePolicyRevision"
            or self.case_ref.resource_type != "BusinessInvestigationCaseRevision"
            or self.approval_ref.resource_type != "ActionApprovalEvent"
        ):
            raise ValueError("schedule control exact reference kind differs")
        body = self.model_dump(mode="json", by_alias=True, exclude={"content_hash", "receipt_ref"})
        if canonical_sha256(body) != self.content_hash:
            raise ValueError("schedule control Receipt content hash differs")
        return self


class SchedulePolicyControlStore:
    def put(
        self,
        transaction: HostTransaction,
        scope: TenantScope,
        *,
        idempotency_key: str,
        policy_ref: InvestigationExactRef,
        case_ref: InvestigationExactRef,
        approval_ref: InvestigationExactRef,
        installation_id: str,
        generation: str,
        execution_epoch: int,
    ) -> SchedulePolicyControlReceipt:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("exact schedule control transaction and tenant required")
        request = {
            "schemaVersion": "aos.ecommerce.schedule-policy-control/v1",
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "idempotencyKey": idempotency_key,
            "policyRef": policy_ref.model_dump(mode="json", by_alias=True),
            "caseRef": case_ref.model_dump(mode="json", by_alias=True),
            "approvalRef": approval_ref.model_dump(mode="json", by_alias=True),
            "dispatch": {
                "installationId": installation_id,
                "generation": generation,
                "executionEpoch": execution_epoch,
            },
        }
        row = transaction.execute(
            "SELECT public.ecommerce_schedule_policy_control_put_a0v_078(%s) AS authority",
            (Jsonb(request),),
        ).fetchone()
        if row is None or not isinstance(row["authority"], dict):
            raise ValueError("schedule control Receipt write returned no authority")
        authority = SchedulePolicyControlReceipt.model_validate(row["authority"])
        if authority.tenant != TenantContext(orgId=scope.org_id, projectId=scope.project_id):
            raise ValueError("schedule control Receipt tenant differs")
        return authority


__all__ = [
    "SchedulePolicyControlReceipt",
    "SchedulePolicyControlStore",
    "SchedulePolicyRuntimeBinding",
]
