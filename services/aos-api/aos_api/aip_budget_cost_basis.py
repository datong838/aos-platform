"""Versioned first-budget cost *proposals*, not evidence or execution authority.

A formal producer must resolve references, read current heads and membership,
then persist the exact proposal for an independent checker. These value types
perform no I/O and cannot replace that transaction or authorize an activation.
"""
from __future__ import annotations

from datetime import UTC
from typing import Annotated, Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevisionCreate
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_contracts import AipContractModel, TenantContext


# Exact integer range also survives the product's JSON/JavaScript boundary.
PositiveInt = Annotated[StrictInt, Field(ge=1, le=9_007_199_254_740_991)]


def _identifier(value: str) -> str:
    if not value or value != value.strip() or not value.isprintable():
        raise ValueError('canonical printable identity required')
    return value


def _exact_ref(value, asset_type: str) -> VersionedAssetRef:
    if isinstance(value, VersionedAssetRef):
        value = value.model_dump(by_alias=True)
    if not isinstance(value, dict):
        raise ValueError('exact reference required')
    revision = value.get('revision')
    if type(revision) is not int or not 1 <= revision <= 9_007_199_254_740_991:
        raise ValueError('exact integer reference revision required')
    for alias, name in (('assetId', 'asset_id'), ('assetType', 'asset_type')):
        identity = value.get(alias, value.get(name))
        if type(identity) is not str:
            raise ValueError('exact reference identity required')
        _identifier(identity)
    ref = VersionedAssetRef.model_validate(value)
    if ref.asset_type != asset_type:
        raise ValueError('wrong cost source reference type')
    return ref


class ExternalReconciliationReference(AipContractModel):
    """A locator for an independent authority; supplied content is not trusted."""
    kind: Literal['external_reconciliation_reference']
    statement: VersionedAssetRef

    @field_validator('statement', mode='before')
    @classmethod
    def _statement(cls, value):
        return _exact_ref(value, 'BudgetUsageReconciliationRevision')


class DevelopmentRiskProposal(AipContractModel):
    """Proposed risk reservations, never a known price or actual cost claim."""
    kind: Literal['development_risk_proposal']
    provider: VersionedAssetRef
    provider_model_id: str = Field(min_length=1, max_length=240)
    per_request_risk_minor: PositiveInt
    total_risk_minor: PositiveInt
    max_requests: PositiveInt

    @field_validator('provider', mode='before')
    @classmethod
    def _provider(cls, value):
        return _exact_ref(value, 'ProviderInstanceRevision')

    @field_validator('provider_model_id')
    @classmethod
    def _model(cls, value):
        return _identifier(value)

    @model_validator(mode='after')
    def _risk(self):
        if self.per_request_risk_minor * self.max_requests > self.total_risk_minor:
            raise ValueError('total risk must cover proposed request reservations')
        return self


CostBasis = Annotated[
    ExternalReconciliationReference | DevelopmentRiskProposal,
    Field(discriminator='kind'),
]


class BudgetCostBasisProposal(AipContractModel):
    """Review input. Hash equality proves content equality, not authorization."""
    schema_version: Literal[1]
    tenant: TenantContext
    target: BudgetRevisionCreate
    draft_revision: PositiveInt
    expected_head_version: PositiveInt
    maker_subject: str = Field(min_length=1, max_length=200)
    checker_subject: str = Field(min_length=1, max_length=200)
    basis: CostBasis

    @field_validator('target', mode='before')
    @classmethod
    def _target(cls, value):
        if isinstance(value, BudgetRevisionCreate):
            value = value.model_dump(by_alias=True)
        if not isinstance(value, dict):
            raise ValueError('exact target payload required')
        for alias, name in (('revision', 'revision'), ('dailyLimitMinor', 'daily_limit_minor'),
                            ('monthlyLimitMinor', 'monthly_limit_minor'),
                            ('alertThresholdPct', 'alert_threshold_pct')):
            number = value.get(alias, value.get(name))
            if type(number) is not int or not 1 <= number <= 9_007_199_254_740_991:
                raise ValueError('exact integer target field required')
        for alias, name in (('budgetId', 'budget_id'), ('owner', 'owner'),
                            ('overBudgetApprover', 'over_budget_approver')):
            identity = value.get(alias, value.get(name))
            if type(identity) is not str:
                raise ValueError('exact target identity required')
            _identifier(identity)
        if value.get('hardStop', value.get('hard_stop', True)) is not True:
            raise ValueError('literal hard-stop flag required')
        return BudgetRevisionCreate.model_validate(value)

    @field_validator('schema_version', mode='before')
    @classmethod
    def _version(cls, value):
        if type(value) is not int:
            raise ValueError('integer schema version required')
        return value

    @field_validator('maker_subject', 'checker_subject')
    @classmethod
    def _subject(cls, value):
        return _identifier(value)

    @model_validator(mode='after')
    def _binding(self):
        if (self.tenant.org_id, self.tenant.project_id) != ('org-org', 'dev-project'):
            raise ValueError('first budget cost proposal tenant is not approved')
        if self.maker_subject == self.checker_subject:
            raise ValueError('independent checker required')
        if (self.target.lifecycle is not BudgetLifecycle.ACTIVE
                or self.target.revision != self.draft_revision + 1):
            raise ValueError('next active budget target required')
        if isinstance(self.basis, DevelopmentRiskProposal):
            if (self.basis.per_request_risk_minor > self.target.daily_limit_minor
                    or self.basis.total_risk_minor > self.target.monthly_limit_minor):
                raise ValueError('proposed risk exceeds target budget limits')
        return self

    def canonical_payload(self) -> dict:
        # Reparse a fresh tree; model_copy and nested mutation bypass Pydantic's
        # construction validators and must never silently create a usable hash.
        checked = type(self).model_validate(self.model_dump(mode='python', by_alias=True))
        target = checked.target.model_copy(update={
            'effective_from': checked.target.effective_from.astimezone(UTC),
            'effective_until': checked.target.effective_until.astimezone(UTC),
        })
        body = checked.model_dump(mode='json', by_alias=True)
        body['target'] = target.model_dump(mode='json', by_alias=True)
        body['accounts'] = {'daily': f'{target.budget_id}:daily', 'pilot': f'{target.budget_id}:pilot'}
        body['currency'] = target.currency
        body['period'] = {'start': body['target']['effectiveFrom'], 'end': body['target']['effectiveUntil']}
        return body

    @property
    def proposal_hash(self) -> str:
        return canonical_hash({'domain': 'aos.budget-cost-proposal/v1', 'proposal': self.canonical_payload()})
