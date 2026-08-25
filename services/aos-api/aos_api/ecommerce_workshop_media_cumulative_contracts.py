"""Fail-closed W7-11 cumulative media gate contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


MEDIA_CUMULATIVE_SCHEMA_VERSION = "aos.ecommerce-workshop.media-cumulative-gates/v1"


class MediaCumulativeGateId(StrEnum):
    CONTRACT = "contract_green"
    SERVICE = "service_green"
    DATABASE_RESTART = "database_restart_green"
    TENANT_RLS = "tenant_rls_green"
    BROWSER_POSITIVE = "browser_positive_green"
    BROWSER_NEGATIVE = "browser_negative_green"
    SECURITY = "security_green"
    FAULT_INJECTION = "fault_injection_green"
    PROVIDER_ADAPTER = "provider_adapter_green"
    PUBLISH_CANARY = "publish_canary_green"
    OPERATIONAL_READY = "operational_ready"


class MediaCumulativeEvidenceRef(AipContractModel):
    resource_type: Literal["DeliveryReceipt", "EvidencePack"]
    resource_id: str = Field(min_length=1, max_length=240)
    revision: str = Field(pattern=r"^AOS-[0-9]{6}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class MediaCumulativeGate(AipContractModel):
    gate_id: MediaCumulativeGateId
    status: Literal["ready", "blocked", "unknown", "stale"]
    evidence_ref: MediaCumulativeEvidenceRef | None = None
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    observed_at: datetime | None = None
    external_effects_observed: Literal[False] = False

    @field_validator("observed_at")
    @classmethod
    def _aware_observation(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("gate observation requires timezone")
        return value

    @model_validator(mode="after")
    def _honest_status(self) -> "MediaCumulativeGate":
        if self.status == "ready" and (self.evidence_ref is None or self.observed_at is None):
            raise ValueError("ready cumulative gate requires current evidence")
        if self.status != "ready" and self.evidence_ref is not None:
            raise ValueError("non-ready cumulative gate cannot attach passing evidence")
        return self


class MediaCumulativeGateSet(AipContractModel):
    schema_version: Literal[MEDIA_CUMULATIVE_SCHEMA_VERSION] = MEDIA_CUMULATIVE_SCHEMA_VERSION
    release_revision: str = Field(pattern=r"^AOS-[0-9]{6}$")
    evaluated_at: datetime
    gates: list[MediaCumulativeGate] = Field(min_length=11, max_length=11)
    overall_status: Literal["ready", "blocked"]
    blocker_codes: list[str] = Field(default_factory=list, max_length=32)
    external_effects_allowed: Literal[False] = False
    release_allowed: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def _aware_evaluation(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("cumulative evaluation requires timezone")
        return value

    @model_validator(mode="after")
    def _all_or_blocked(self) -> "MediaCumulativeGateSet":
        if [item.gate_id for item in self.gates] != list(MediaCumulativeGateId):
            raise ValueError("cumulative gates require canonical eleven-column order")
        external_ids = {
            MediaCumulativeGateId.PROVIDER_ADAPTER,
            MediaCumulativeGateId.PUBLISH_CANARY,
            MediaCumulativeGateId.OPERATIONAL_READY,
        }
        if any(item.gate_id in external_ids and item.status == "ready" for item in self.gates):
            raise ValueError("external operational columns require a separately authorized contract")
        expected_blockers = sorted(item.reason_code for item in self.gates if item.status != "ready")
        if self.blocker_codes != expected_blockers:
            raise ValueError("cumulative blockers must equal every non-ready column")
        if self.overall_status == "ready" or not self.blocker_codes:
            raise ValueError("W7-11 cannot claim operational ready without external authorization")
        return self


__all__ = [name for name in globals() if name.startswith("MEDIA_CUMULATIVE") or name.startswith("MediaCumulative")]
