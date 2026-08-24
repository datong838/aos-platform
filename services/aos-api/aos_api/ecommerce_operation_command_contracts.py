"""Strict W3-12B operation command-readiness contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


OPERATION_COMMAND_READINESS_SCHEMA_VERSION = (
    "aos.ecommerce-workshop.operation-command-readiness/v1"
)


class OperationCommandId(StrEnum):
    CLASSIFY = "classify"
    CREATE_CASE = "createCase"
    CHANGE_MEMBERSHIP = "changeMembership"
    MANAGE_SLA = "manageSla"
    AUTOMATION_KILL = "automationKill"
    REFUND = "refund"


class OperationCommandStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class OperationCommandRisk(StrEnum):
    CONTROLLED = "controlled"
    HIGH = "high"


class OperationCommandSideEffect(StrEnum):
    INTERNAL_AUTHORITY = "internalAuthority"
    EXTERNAL = "external"


class OperationCommandBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=160)
    required_action: str = Field(min_length=1, max_length=500)


class OperationCommandDescriptor(AipContractModel):
    command_id: OperationCommandId
    label: str = Field(min_length=1, max_length=80)
    status: OperationCommandStatus
    risk: OperationCommandRisk
    side_effect: OperationCommandSideEffect
    blockers: list[OperationCommandBlocker] = Field(max_length=10)

    @model_validator(mode="after")
    def _status_matches_blockers(self) -> OperationCommandDescriptor:
        if self.status is OperationCommandStatus.READY and self.blockers:
            raise ValueError("ready operation commands cannot have blockers")
        if self.status is OperationCommandStatus.BLOCKED and not self.blockers:
            raise ValueError("blocked operation commands require blockers")
        return self


class OperationCommandReadinessEnvelope(AipContractModel):
    schema_version: Literal[OPERATION_COMMAND_READINESS_SCHEMA_VERSION] = (
        OPERATION_COMMAND_READINESS_SCHEMA_VERSION
    )
    tenant: TenantContext
    evaluated_at: datetime
    commands: list[OperationCommandDescriptor] = Field(min_length=6, max_length=6)

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("operation command readiness time requires a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_order(self) -> OperationCommandReadinessEnvelope:
        if [item.command_id for item in self.commands] != list(OperationCommandId):
            raise ValueError("operation commands must use canonical order and identity")
        return self


__all__ = [
    "OPERATION_COMMAND_READINESS_SCHEMA_VERSION",
    "OperationCommandBlocker",
    "OperationCommandDescriptor",
    "OperationCommandId",
    "OperationCommandReadinessEnvelope",
    "OperationCommandRisk",
    "OperationCommandSideEffect",
    "OperationCommandStatus",
]
