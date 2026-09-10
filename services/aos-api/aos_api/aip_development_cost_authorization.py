"""Development cost deferral values; persistence and authorization stay with policy Owner."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.tenant_scope import TenantScope


class DevelopmentCostAuthorization(AipContractModel):
    tenant: TenantContext
    provider: VersionedAssetRef
    provider_model_id: str = Field(min_length=1, max_length=240)
    approval_ref: str = Field(min_length=1, max_length=240)
    environment: Literal['development'] = 'development'
    effective_from: datetime
    effective_until: datetime

    @field_validator('provider_model_id', 'approval_ref')
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError('authorization identity must be nonblank and canonical')
        return value

    @model_validator(mode='after')
    def bounded_authorization(self):
        if (self.tenant.org_id, self.tenant.project_id) != ('org-org', 'dev-project'):
            raise ValueError('development cost authorization tenant is not approved')
        if self.provider.asset_type != 'ProviderInstanceRevision':
            raise ValueError('development cost authorization requires exact Provider')
        if self.effective_from.utcoffset() is None or self.effective_until.utcoffset() is None:
            raise ValueError('development cost authorization requires timezone')
        if self.effective_until <= self.effective_from:
            raise ValueError('development cost authorization window is invalid')
        return self

    def require_scope(self, *, scope: TenantScope, provider: VersionedAssetRef,
                      provider_model_id: str, approval_ref: str, now: datetime) -> None:
        """Call only on an exact active policy read from its Owner, never request input."""
        if (
            scope.key != (self.tenant.org_id, self.tenant.project_id)
            or provider != self.provider
            or provider_model_id != self.provider_model_id
            or approval_ref != self.approval_ref
            or now.utcoffset() is None
            or not self.effective_from <= now < self.effective_until
        ):
            raise ValueError('development_cost_authorization_scope_blocked')


class DeferredTokenCost(AipContractModel):
    cost_status: Literal['deferred'] = 'deferred'
    amount_minor: None = None
    usage_quality: Literal['measured'] = 'measured'
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    total_tokens: StrictInt = Field(ge=0)

    @model_validator(mode='after')
    def measured_total(self):
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError('measured token total mismatch')
        return self
