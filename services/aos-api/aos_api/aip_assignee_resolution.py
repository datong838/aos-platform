"""Four-kind AssigneeResolutionReceipt (W-L20).

Never treats a tenant-global catalog hit as a resolved Tool/Provider binding.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef


class AssigneeResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    BLOCKED = "blocked"


class ResolveAssigneeRequest(AipContractModel):
    assignee: AssigneeRef
    subject_id: str = Field(min_length=1, max_length=240)
    require_instance_scope: bool = True


class AssigneeResolutionReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str
    subject_id: str
    kind: AssigneeKind
    resource_id: str
    version: int = Field(ge=1)
    status: AssigneeResolutionStatus
    resolved_ref: str | None = None
    blocker_codes: list[str] = Field(default_factory=list)
    actor: str
    created_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class UpsertToolBindingRequest(AipContractModel):
    binding_id: str = Field(min_length=1, max_length=200)
    tool_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    agent_instance_id: str = Field(min_length=1, max_length=200)
    status: str = Field(default="active", pattern=r"^(active|disabled)$")


class ToolBindingRecord(AipContractModel):
    tenant: TenantContext
    binding_id: str
    tool_id: str
    version: int
    agent_instance_id: str
    status: str


__all__ = [
    "AssigneeResolutionReceipt",
    "AssigneeResolutionStatus",
    "ResolveAssigneeRequest",
    "ToolBindingRecord",
    "UpsertToolBindingRequest",
]
