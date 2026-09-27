"""D01 exact packet proposal contract; a proposal never authorizes execution.

The approved selection Owner and its durable decision Receipt are separate.
This module carries references and bounds only, never source material.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_d01_issuer import D01SourcePacket
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef


class D01SourceSelectionProposal(AipContractModel):
    tenant: TenantContext
    task_run_ref: ResourceRef
    plan_ref: ResourceRef
    plan_content_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    source_selection_ref: PipelineExactRef
    packet: D01SourcePacket
    proposed_by: str = Field(min_length=1, max_length=240)
    proposed_at: datetime

    @model_validator(mode='after')
    def _bounded_candidate(self):
        refs = (
            (self.task_run_ref, 'TaskRun'),
            (self.plan_ref, 'PlanRevision'),
        )
        if (any(not value or value != value.strip()
                for value in (self.tenant.org_id, self.tenant.project_id, self.proposed_by))
                or any(ref.resource_type != kind or ref.authority != 'postgresql'
                       or ref.revision is None or not ref.revision.isdigit()
                       or int(ref.revision) < 1 for ref, kind in refs)
                or self.source_selection_ref.resource_type != 'SourceSelectionRevision'
                or type(self.source_selection_ref.revision) is not int
                or self.proposed_at.utcoffset() is None
                or self.packet.cutoff_at > self.proposed_at):
            raise ValueError('bounded D01 packet proposal identity required')
        return self

    @property
    def selection_id(self) -> str:
        return 'd01-source-' + canonical_hash({
            'tenant': [self.tenant.org_id, self.tenant.project_id],
            'taskRunId': self.task_run_ref.resource_id,
            'planRevisionId': self.plan_ref.resource_id,
        })[:40]
