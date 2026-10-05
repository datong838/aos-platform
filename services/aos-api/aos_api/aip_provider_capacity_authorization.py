"""Unapproved Owner allocation terms; no supplier limit or execution authority."""
from datetime import datetime, timedelta
from typing import Literal
from pydantic import ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef, FormalEvaluationTenant


class ProviderCapacityRequest(AipContractModel):
    model_config = ConfigDict(revalidate_instances='always')
    schema_version: StrictInt = Field(ge=1, le=1)
    tenant: FormalEvaluationTenant
    provider_ref: FormalExactRef
    physical_account_id: StrictStr = Field(min_length=1, max_length=200)
    requested_max_concurrency: StrictInt = Field(ge=1, le=1000000)
    requested_max_token_units: StrictInt = Field(ge=1, le=1000000000000)
    token_unit: Literal['token']
    basis_kind: Literal['owner_requested_allocation']
    basis_evidence_ref: FormalExactRef
    valid_from: datetime
    valid_until: datetime
    proposal_expires_at: datetime

    @field_validator('physical_account_id')
    @classmethod
    def canonical_account(cls, value):
        if value != value.strip(): raise ValueError('canonical physical account required')
        return value

    @model_validator(mode='after')
    def exact_terms(self):
        if (self.provider_ref.asset_type != 'ProviderInstanceRevision'
            or self.basis_evidence_ref.asset_type != 'EvidenceBundleRevision'
            or any(value.utcoffset() is None for value in
                   (self.valid_from,self.valid_until,self.proposal_expires_at))
            or not self.valid_from < self.proposal_expires_at <= self.valid_until
            or self.valid_until-self.valid_from > timedelta(days=366)):
            raise ValueError('exact provider/basis and aware bounded windows required')
        return self
