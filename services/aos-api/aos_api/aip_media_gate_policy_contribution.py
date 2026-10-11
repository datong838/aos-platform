"""Publisher media policy artifact format, without runtime authorization.

Manifest and signature references must be derived outside their signed artifact.
Validated payloads still require the original Registry/current-installation and
canonical Rule readers; this model never registers a profile or approves it.
"""
from __future__ import annotations
from typing import Literal, Self
from pydantic import Field, model_validator
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_production_contracts import MediaGateDefinition, require_four_media_gates


class MediaGatePolicyContribution(AipContractModel):
    schema_id: Literal['aos.ecommerce-media-gate-policy/v1'] = Field(alias='schema')
    policy_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1, strict=True)
    profile_id: str = Field(min_length=1, max_length=200)
    profile_revision: int = Field(ge=1, strict=True)
    gates: list[MediaGateDefinition] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def _original_four_gate_invariant(self) -> Self:
        require_four_media_gates(self.gates)
        return self
