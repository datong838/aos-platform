"""Untrusted complete withdrawal transport; authority is verified in PostgreSQL."""
from typing import Literal

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator

from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.aip_provider_capacity_publication_contracts import _PublicationDocument, _refs
from aos_api.aip_provider_capacity_source_contracts import _identifier


class ProviderCapacityOriginWithdrawal(_PublicationDocument):
    purpose: Literal['provider_capacity_origin_withdrawal']
    anchor_revision: StrictStr = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    publisher_subject: StrictStr
    policy_publisher_role: Literal['aos_provider_capacity_policy_publisher']
    origin_ref: FormalExactRef
    expected_epoch: StrictInt = Field(ge=1, le=9223372036854775806)

    @field_validator('publisher_subject')
    @classmethod
    def subject_identity(cls, value):
        return _identifier(value)

    @model_validator(mode='after')
    def original_origin(self):
        _refs([self.origin_ref], {'ProviderCapacityOriginBootstrapRevision'})
        return self
