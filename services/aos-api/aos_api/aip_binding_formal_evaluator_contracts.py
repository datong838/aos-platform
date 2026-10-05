"""Exact formal-evaluation transport. Validation confers no database authority."""
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


class FormalExactRef(AipContractModel):
    model_config = ConfigDict(revalidate_instances='always')
    asset_type: StrictStr = Field(min_length=1, max_length=80)
    asset_id: StrictStr = Field(min_length=1, max_length=200)
    revision: StrictInt = Field(ge=1)
    content_hash: StrictStr = Field(pattern=r'^[0-9a-f]{64}$')

    @field_validator('asset_type', 'asset_id')
    @classmethod
    def canonical_identity(cls, value: str) -> str:
        if value != value.strip() or not value:
            raise ValueError('exact reference identity must be canonical')
        return value


class FormalEvaluationTenant(AipContractModel):
    model_config = ConfigDict(revalidate_instances='always')
    org_id: Literal['org-org']
    project_id: Literal['dev-project']


class FormalBindingEvaluationRequest(AipContractModel):
    model_config = ConfigDict(revalidate_instances='always')
    schema_version: StrictInt = Field(ge=1, le=1)
    tenant: FormalEvaluationTenant
    expected_version: StrictInt = Field(ge=1)
    installation_id: StrictStr
    installation_revision: StrictInt = Field(ge=1)
    installation_etag: StrictInt = Field(ge=1)
    provider_ref: FormalExactRef
    model_ref: FormalExactRef
    policy_ref: FormalExactRef
    route_ref: FormalExactRef
    price_ref: FormalExactRef
    capacity_ref: FormalExactRef
    route_eval_gate_ref: FormalExactRef
    model_eval_gate_ref: FormalExactRef
    eval_contract_ref: FormalExactRef
    budget_policy_ref: FormalExactRef
    source_refs: list[FormalExactRef] = Field(min_length=1, max_length=128)
    data_dependency_refs: list[FormalExactRef] = Field(max_length=128)
    tool_dependency_refs: list[FormalExactRef] = Field(max_length=128)

    @field_validator('installation_id')
    @classmethod
    def canonical_uuid(cls, value: str) -> str:
        if str(UUID(value)) != value:
            raise ValueError('installationId must be a canonical UUID')
        return value

    @model_validator(mode='after')
    def exact_kinds_and_unique_dependencies(self) -> 'FormalBindingEvaluationRequest':
        kinds = {
            'provider_ref': 'ProviderInstanceRevision', 'model_ref': 'RegisteredModelRevision',
            'policy_ref': 'RuntimePolicyRevision', 'route_ref': 'ModelRouteRevision',
            'price_ref': 'ModelPriceSnapshotRevision', 'capacity_ref': 'ModelCapacityPoolRevision',
            'route_eval_gate_ref': 'EvalGateDecision', 'model_eval_gate_ref': 'EvalGateDecision',
            'eval_contract_ref': 'EvalContractRevision', 'budget_policy_ref': 'BudgetPolicyRevision',
        }
        for name, kind in kinds.items():
            if getattr(self, name).asset_type != kind:
                raise ValueError(f'{name} requires {kind}')
        for name in ('source_refs', 'data_dependency_refs', 'tool_dependency_refs'):
            refs = getattr(self, name)
            allowed = {'EvidenceBundleRevision'} if name == 'source_refs' else {
                'EvidenceBundleRevision', 'EvalDatasetRevision'}
            identities = [(ref.asset_type, ref.asset_id) for ref in refs]
            if len(identities) != len(set(identities)):
                raise ValueError(f'{name} contains duplicate resource identities')
            if any(ref.asset_type not in allowed for ref in refs):
                raise ValueError(f'{name} contains an unsupported authority kind')
        return self
