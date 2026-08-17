"""Immutable tenant-scoped technical network boundary contracts."""
from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_runtime_guard_policy_contracts import GuardPolicyLifecycle


class NetworkPolicyRevisionCreate(AipContractModel):
    policy_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    allowed_schemes: list[Literal["https"]] = Field(min_length=1, max_length=1)
    allowed_hosts: list[str] = Field(min_length=1, max_length=32)
    allowed_ports: list[Literal[443]] = Field(min_length=1, max_length=1)
    tls_required: Literal[True] = True
    public_fallback_allowed: Literal[False] = False
    egress_policy_ref: VersionedAssetRef
    effective_from: datetime
    effective_until: datetime
    owner: str = Field(min_length=1, max_length=160)
    approval_ref: str = Field(min_length=1, max_length=240)
    lifecycle: GuardPolicyLifecycle

    @field_validator("policy_id", "owner", "approval_ref")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("network policy identity fields must not be blank")
        return cleaned

    @field_validator("allowed_hosts")
    @classmethod
    def _safe_hosts(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().lower() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("network hosts must be unique and non-blank")
        for host in cleaned:
            if "*" in host or host == "localhost":
                raise ValueError("network hosts must be exact public DNS names")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("network hosts must not be IP literals")
            labels = host.split(".")
            if len(labels) < 2 or any(not label or not label.replace("-", "a").isalnum() for label in labels):
                raise ValueError("network hosts must be valid exact DNS names")
        return cleaned

    @model_validator(mode="after")
    def _fail_closed(self) -> "NetworkPolicyRevisionCreate":
        if self.egress_policy_ref.asset_type != "EgressPolicyRevision":
            raise ValueError("egress_policy_ref must reference EgressPolicyRevision")
        if self.effective_from.tzinfo is None or self.effective_until.tzinfo is None:
            raise ValueError("effective network policy window requires timezone")
        if self.effective_until <= self.effective_from:
            raise ValueError("effectiveUntil must be after effectiveFrom")
        return self


class NetworkPolicyRevision(NetworkPolicyRevisionCreate):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
