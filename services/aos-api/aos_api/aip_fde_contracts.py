"""Strict contracts for the first three FDE onboarding skills."""
from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_task_models import PlanRevisionSnapshot, RunControlResult, TaskSnapshot

_SECRET_REF = re.compile(r"^(?:keychain|secret|vault)://[A-Za-z0-9][A-Za-z0-9._/@:-]{2,300}$")
_INLINE_SECRET = re.compile(
    r"(?i)(?:api[ _-]?key|app[ _-]?secret|client[ _-]?secret|password|passwd|token)\s*[:=]\s*[^\s,;]{4,}"
)


class FdeStepStatus(StrEnum):
    READY = "ready"
    PAUSED = "paused"
    BLOCKED = "blocked"
    PARTIAL = "partial"
    EXTERNAL_REQUIRED = "external_required"


class FdeIntakeRequest(AipContractModel):
    requirement: str = Field(min_length=1, max_length=4000)
    platform: str = Field(min_length=1, max_length=80)
    data_types: list[str] = Field(min_length=1, max_length=20)
    sync_frequency: Literal["realtime", "hourly", "daily"] = "hourly"
    merchant_ref: str | None = Field(default=None, max_length=240)
    auth_scheme: str | None = Field(default=None, max_length=80)
    secret_ref: str | None = Field(default=None, max_length=320)
    secret_version: str | None = Field(default=None, max_length=120)
    adapter_pack_ref: str = "platform.ecommerce.niushop@1.0.0"

    @field_validator("requirement", "platform", "adapter_pack_ref")
    @classmethod
    def _normalized_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or cleaned != value:
            raise ValueError("required text must be non-blank and normalized")
        return cleaned

    @field_validator("merchant_ref", "auth_scheme", "secret_ref", "secret_version")
    @classmethod
    def _normalized_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or cleaned != value:
            raise ValueError("optional text must be non-blank and normalized")
        return cleaned

    @field_validator("data_types")
    @classmethod
    def _data_types(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value]
        if any(not item or item != raw for item, raw in zip(normalized, value, strict=True)):
            raise ValueError("dataTypes must be normalized lowercase identifiers")
        if len(set(normalized)) != len(normalized):
            raise ValueError("dataTypes must be unique")
        return normalized

    @model_validator(mode="after")
    def _no_inline_secret(self) -> "FdeIntakeRequest":
        for value in (self.requirement, self.merchant_ref or ""):
            if _INLINE_SECRET.search(value):
                raise ValueError("secret payload is forbidden; submit only an opaque secretRef")
        if self.secret_ref is not None and not _SECRET_REF.fullmatch(self.secret_ref):
            raise ValueError("secretRef must use keychain://, secret:// or vault://")
        if self.secret_version and not self.secret_ref:
            raise ValueError("secretVersion requires secretRef")
        return self


class FdeStepEvidence(AipContractModel):
    step_key: Literal["fde.s1.requirement", "fde.s2.auth-draft", "fde.s3.capability-probe"]
    status: FdeStepStatus
    artifact_type: str
    artifact_ref: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary: str
    blocker_codes: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)


class FdeSessionPreview(AipContractModel):
    tenant: TenantContext
    status: FdeStepStatus
    executable: bool
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    steps: list[FdeStepEvidence] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _ordered_steps(self) -> "FdeSessionPreview":
        expected = ["fde.s1.requirement", "fde.s2.auth-draft", "fde.s3.capability-probe"]
        if [step.step_key for step in self.steps] != expected:
            raise ValueError("FDE preview must contain ordered S1-S3 evidence")
        if self.executable and any(
            step.status in {FdeStepStatus.BLOCKED, FdeStepStatus.PAUSED, FdeStepStatus.PARTIAL}
            for step in self.steps
        ):
            raise ValueError("blocked, paused or partial preview cannot be executable")
        return self


class FdeSessionCreated(AipContractModel):
    preview: FdeSessionPreview
    task: TaskSnapshot
    plan: PlanRevisionSnapshot
    execution_authority: Literal["not_approved_not_started"] = "not_approved_not_started"


class ExecuteFdeRunRequest(AipContractModel):
    worker_id: str = Field(min_length=1, max_length=120)
    lease_seconds: int = Field(default=30, ge=5, le=300)

    @field_validator("worker_id")
    @classmethod
    def _worker(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned != value:
            raise ValueError("workerId must be normalized")
        return cleaned


class ExecuteFdeRunResponse(AipContractModel):
    result: RunControlResult
    timeline_ref: str
