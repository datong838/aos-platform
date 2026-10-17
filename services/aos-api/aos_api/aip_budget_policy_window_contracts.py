"""Initial policy subwindow *claims*, separate from cost proposal V1.

No Owner is read here. A draft hash establishes only content equality: it is
neither an approval hash nor an instruction accepted by a native consumer.
"""
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, Field, StrictStr, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_contracts import AipContractModel, TenantContext


def _identity(value: str) -> str:
    if value != value.strip() or not value.isprintable():
        raise ValueError('canonical printable identity required')
    return value


Identity = Annotated[StrictStr, Field(min_length=1, max_length=240), AfterValidator(_identity)]


class BudgetPolicyWindow(AipContractModel):
    effective_from: AwareDatetime
    effective_until: AwareDatetime

    @field_validator('effective_from', 'effective_until', mode='before')
    @classmethod
    def _timestamp(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError('explicit timezone-aware timestamp required')
        return value

    @field_validator('effective_from', 'effective_until')
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode='after')
    def _ordered(self):
        if self.effective_until <= self.effective_from:
            raise ValueError('positive window required')
        return self


class BudgetPolicyWindowDraft(AipContractModel):
    schema_version: Literal[1]
    tenant: TenantContext
    master_budget_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    provider_model_id: Identity
    cost_proposal_id: Identity
    cost_proposal_hash: StrictStr = Field(pattern=r'^[0-9a-f]{64}$')
    cost_decision_id: Identity
    cost_consumption_receipt_id: Identity
    claimed_budget_window: BudgetPolicyWindow
    requested_policy_window: BudgetPolicyWindow
    maker_subject: Identity
    checker_subject: Identity

    @field_validator('schema_version', mode='before')
    @classmethod
    def _version(cls, value):
        if type(value) is not int:
            raise ValueError('integer schema version required')
        return value

    @field_validator('tenant', mode='before')
    @classmethod
    def _tenant_claim(cls, value):
        if isinstance(value, TenantContext):
            value = value.model_dump(by_alias=True)
        if not isinstance(value, dict):
            raise ValueError('both tenant claim dimensions required')
        for alias, name in (('orgId', 'org_id'), ('projectId', 'project_id')):
            identity = value.get(alias, value.get(name))
            if type(identity) is not str or not identity:
                raise ValueError('both tenant claim dimensions required')
            _identity(identity)
        return value

    @field_validator('master_budget_ref', 'provider_ref', mode='before')
    @classmethod
    def _reference_claim(cls, value, info):
        if isinstance(value, VersionedAssetRef):
            value = value.model_dump(by_alias=True)
        if not isinstance(value, dict):
            raise ValueError('exact reference claim required')
        revision = value.get('revision')
        if type(revision) is not int or not 1 <= revision <= 9_007_199_254_740_991:
            raise ValueError('exact safe integer reference revision required')
        for alias, name in (('assetId', 'asset_id'), ('assetType', 'asset_type')):
            identity = value.get(alias, value.get(name))
            if type(identity) is not str or not identity:
                raise ValueError('canonical reference identity required')
            _identity(identity)
        if type(value.get('contentHash', value.get('content_hash'))) is not str:
            raise ValueError('exact reference content hash required')
        ref = VersionedAssetRef.model_validate(value)
        expected = 'BudgetRevision' if info.field_name == 'master_budget_ref' else 'ProviderInstanceRevision'
        if ref.asset_type != expected:
            raise ValueError('wrong source reference kind')
        return ref

    @field_validator('claimed_budget_window', 'requested_policy_window', mode='before')
    @classmethod
    def _window_claim(cls, value):
        return value.model_dump(by_alias=True) if isinstance(value, BudgetPolicyWindow) else value

    @model_validator(mode='after')
    def _relationship(self):
        if self.maker_subject == self.checker_subject:
            raise ValueError('independent checker subject required')
        parent, policy = self.claimed_budget_window, self.requested_policy_window
        if not (parent.effective_from <= policy.effective_from
                < policy.effective_until < parent.effective_until):
            raise ValueError('policy subwindow must leave positive parent window remainder')
        return self

    def canonical_payload(self) -> dict:
        # Dump and reparse *nested* claims, including caller-mutated instances.
        checked = BudgetPolicyWindowDraft.model_validate(self.model_dump(mode='python', by_alias=True))
        return checked.model_dump(mode='json', by_alias=True)

    @property
    def draft_hash(self) -> str:
        return canonical_hash({
            'domain': 'aos.budget-policy-window-draft/v1',
            'draft': self.canonical_payload(),
        })
