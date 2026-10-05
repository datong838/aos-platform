"""Strict capacity-source claims; parsing never verifies a supplier or grants capacity."""
from datetime import datetime,timedelta
from dataclasses import dataclass,field
import re
from typing import Annotated,Literal

from pydantic import ConfigDict,Field,SecretStr,StrictBool,StrictInt,StrictStr,field_validator,model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef,FormalEvaluationTenant


def _window(start: datetime, end: datetime):
    if start.utcoffset() is None or end.utcoffset() is None or not start < end:
        raise ValueError('aware increasing validity required')
    if end-start > timedelta(days=366):
        raise ValueError('bounded source validity required')


class _Candidate(AipContractModel):
    model_config=ConfigDict(revalidate_instances='always')
    schema_version: StrictInt=Field(ge=1,le=1)
    tenant: FormalEvaluationTenant


class ProviderPhysicalAccountCandidate(_Candidate):
    physical_account_id: StrictStr=Field(min_length=1,max_length=200)
    supplier_id: StrictStr=Field(min_length=1,max_length=200)
    supplier_account_fingerprint: StrictStr=Field(pattern=r'^[0-9a-f]{64}$')
    provider_refs: list[FormalExactRef]=Field(min_length=1,max_length=1000)
    evidence_ref: FormalExactRef

    @field_validator('physical_account_id','supplier_id')
    @classmethod
    def canonical(cls,value):
        if value != value.strip(): raise ValueError('canonical account identity required')
        return value

    @model_validator(mode='after')
    def exact_mapping(self):
        if (self.evidence_ref.asset_type != 'EvidenceBundleRevision'
            or any(ref.asset_type != 'ProviderInstanceRevision' for ref in self.provider_refs)
            or len({ref.asset_id for ref in self.provider_refs}) != len(self.provider_refs)):
            raise ValueError('unique exact Provider mapping and evidence required')
        return self


class InflightTokenLimit(AipContractModel):
    model_config=ConfigDict(revalidate_instances='always')
    mode: Literal['inflight_upper_bound']
    unit: Literal['token']
    max_tokens: StrictInt=Field(ge=1,le=1000000000000)


class FixedWindowTokenLimit(AipContractModel):
    model_config=ConfigDict(revalidate_instances='always')
    mode: Literal['fixed_window_rate']
    unit: Literal['token']
    max_tokens: StrictInt=Field(ge=1,le=1000000000000)
    window_seconds: StrictInt=Field(ge=1,le=86400)
    window_anchor: datetime

    @field_validator('window_anchor')
    @classmethod
    def aware_anchor(cls,value):
        if value.utcoffset() is None: raise ValueError('aware rate-window anchor required')
        return value


class ProviderCapacityBasisCandidate(_Candidate):
    basis_kind: Literal['owner_allocation','supplier_limit_claim']
    physical_account_ref: FormalExactRef
    evidence_ref: FormalExactRef
    max_concurrency: StrictInt=Field(ge=1,le=1000000)
    token_limit: Annotated[InflightTokenLimit|FixedWindowTokenLimit,Field(discriminator='mode')]
    observed_at: datetime
    valid_from: datetime
    valid_until: datetime

    @model_validator(mode='after')
    def exact_basis(self):
        _window(self.valid_from,self.valid_until)
        if (self.observed_at.utcoffset() is None or self.observed_at > self.valid_until
            or self.physical_account_ref.asset_type != 'ProviderPhysicalAccountCandidateRevision'
            or self.evidence_ref.asset_type != 'EvidenceBundleRevision'):
            raise ValueError('exact account/evidence and aware observation required')
        return self


class ProviderCapacitySourceCandidate(_Candidate):
    physical_account_ref: FormalExactRef
    basis_ref: FormalExactRef
    allocation_request_ref: FormalExactRef
    allocation_approval_ref: FormalExactRef
    valid_from: datetime
    valid_until: datetime
    execution_allowed: StrictBool

    @model_validator(mode='after')
    def exact_source(self):
        _window(self.valid_from,self.valid_until)
        if (self.execution_allowed is not False
            or self.physical_account_ref.asset_type != 'ProviderPhysicalAccountCandidateRevision'
            or self.basis_ref.asset_type != 'ProviderCapacityBasisCandidateRevision'
            or self.allocation_request_ref.asset_type != 'ProviderCapacityRequest'
            or self.allocation_request_ref.revision != 1
            or self.allocation_approval_ref.asset_type != 'ActionApprovalEvent'
            or self.allocation_approval_ref.revision != 1):
            raise ValueError('nonexecuting exact source provenance required')
        return self


def _identifier(value):
    if (type(value) is not str or not 1<=len(value)<=200 or value!=value.strip()
        or not value.isprintable() or any(char.isspace() for char in value)):
        raise ValueError('canonical bounded identifier required')
    return value


class ProviderCapacityIssuanceCommand(_Candidate):
    """Request-only references; the issuer must prove all facts in its transaction."""
    model_config=ConfigDict(revalidate_instances='always',hide_input_in_errors=True)
    bearer_token: SecretStr
    idempotency_key: StrictStr=Field(min_length=1,max_length=200)
    approved_proposal: FormalExactRef
    approval_event: FormalExactRef
    supplier_attestation_ref: FormalExactRef
    source_policy_ref: FormalExactRef

    @field_validator('idempotency_key')
    @classmethod
    def exact_key(cls,value):
        return _identifier(value)

    @field_validator('bearer_token')
    @classmethod
    def external_token(cls,value):
        token=value.get_secret_value()
        if len(token)>8192 or not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}',token):
            raise ValueError('bounded external signed JWT required')
        return value

    @model_validator(mode='after')
    def exact_issuance_refs(self):
        for field_name,kind,revision in (
            ('approved_proposal','ActionProposal',2),('approval_event','ActionApprovalEvent',1),
            ('supplier_attestation_ref','SupplierCapacityAttestationRevision',None),
            ('source_policy_ref','ProviderCapacitySourcePolicyRevision',None)):
            ref=FormalExactRef.model_validate(getattr(self,field_name).model_dump(mode='python',by_alias=True))
            _identifier(ref.asset_id)
            if ref.asset_type!=kind or (revision is not None and ref.revision!=revision):
                raise ValueError('exact issuance reference required')
        return self


@dataclass(frozen=True,slots=True)
class ProviderCapacityIssuanceBinding:
    content_hash: str
    authorization: Literal['ISSUANCE_REQUEST_ONLY_NO_CAPACITY_NO_START']=field(
        default='ISSUANCE_REQUEST_ONLY_NO_CAPACITY_NO_START',init=False)


def capacity_issuance_binding(scope,maker,command):
    from aos_api.aip_action_store import canonical_hash
    from aos_api.tenant_scope import TenantScope
    try:
        if type(scope) is not TenantScope or type(command) is not ProviderCapacityIssuanceCommand:
            raise ValueError('native command and scope required')
        _identifier(maker)
        if maker=='unknown':raise ValueError('authenticated maker required')
        command=ProviderCapacityIssuanceCommand.model_validate(command.model_dump(mode='python',by_alias=True))
        if scope.key!=(command.tenant.org_id,command.tenant.project_id):
            raise ValueError('exact tenant required')
        payload=command.model_dump(mode='json',by_alias=True,exclude={'bearer_token','idempotency_key'})
        return ProviderCapacityIssuanceBinding(canonical_hash(dict(
            protocol='aos-provider-capacity-issuance-request/v1',maker=maker,command=payload)))
    except (ValueError,TypeError,AttributeError):
        raise ValueError('CAPACITY_ISSUANCE_REQUEST_INVALID') from None
