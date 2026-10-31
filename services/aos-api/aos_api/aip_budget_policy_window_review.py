"""One readonly parent snapshot for the separate initial-window review family.

These are metadata observations. Native approval/consumption and runtime
admission still recheck their own authorities; no child dates are invented here.
"""
from contextlib import contextmanager
from typing import Literal

from psycopg import IsolationLevel
from pydantic import AwareDatetime, Field, StrictBool, field_validator, model_validator

from aos_api.aip_budget_activation_store import _identity, _key, _member, _require_inquiry_connection
from aos_api.aip_budget_contracts import BudgetRevision
from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal, DevelopmentRiskProposal, _exact_ref
from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
from aos_api.aip_budget_policy_renewal_contracts import ExactVersion
from aos_api.aip_budget_policy_renewal_identity import _HUMAN
from aos_api.aip_budget_policy_window_contracts import Identity
from aos_api.aip_budget_store import AipBudgetAuthorityStore, BudgetNotFound, canonical_hash
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeNotFound
from aos_api.db import connect_read_only

_SCOPE = ('org-org', 'dev-project')


class BudgetPolicyWindowReviewDenied(ValueError):
    pass


class BudgetPolicyWindowReviewUnavailable(RuntimeError):
    pass


class ParentCostObservation(AipContractModel):
    proposal_id: Identity
    proposal_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    proposal: BudgetCostBasisProposal
    decision_id: Identity | None
    decision: Literal['approved', 'rejected', 'missing']
    revoked: StrictBool

    @field_validator('proposal', mode='before')
    @classmethod
    def _proposal(cls, value):
        if isinstance(value, BudgetCostBasisProposal):
            value = value.canonical_payload()
        if isinstance(value, dict) and {'accounts','currency','period'} & value.keys():
            return BudgetCostBasisProposal.from_canonical_payload(value)
        return BudgetCostBasisProposal.model_validate(value)

    @model_validator(mode='after')
    def _parent(self):
        if (self.proposal.proposal_hash != self.proposal_hash
                or not isinstance(self.proposal.basis, DevelopmentRiskProposal)
                or self.proposal.checker_subject != _HUMAN
                or (self.decision == 'missing') != (self.decision_id is None)
                or (self.revoked and self.decision != 'approved')):
            raise ValueError('parent cost observation drift')
        return self


class ParentConsumptionObservation(AipContractModel):
    receipt_id: Identity
    request_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    result_ref: dict
    created_by: Identity


class WindowProviderObservation(AipContractModel):
    """Minimal public metadata; no endpoint, opaque secret reference or credential."""
    tenant: TenantContext
    ref: VersionedAssetRef
    lifecycle: ModelRuntimeLifecycle

    @field_validator('ref', mode='before')
    @classmethod
    def _exact_provider_ref(cls, value):
        return _exact_ref(value, 'ProviderInstanceRevision')

    @model_validator(mode='after')
    def _provider(self):
        if self.ref.asset_type != 'ProviderInstanceRevision':
            raise ValueError('provider reference required')
        return self


class _WindowReviewFacts(AipContractModel):
    schema_version: Literal['aos.budget-policy-window.review-source/v1']
    tenant: TenantContext
    evaluated_at: AwareDatetime
    parent: ParentCostObservation
    consumption: ParentConsumptionObservation | None
    source_budget: BudgetRevision | None
    current_budget: BudgetRevision | None
    current_budget_head_version: ExactVersion | None
    source_provider: WindowProviderObservation | None
    current_provider: WindowProviderObservation | None
    approval_verified: Literal[False] = False
    activation_eligible: Literal[False] = False
    native_write_allowed: Literal[False] = False
    runtime_admission_allowed: Literal[False] = False
    native_parent_verification: Literal['not-performed'] = 'not-performed'

    @field_validator('approval_verified', 'activation_eligible', 'native_write_allowed',
                     'runtime_admission_allowed', mode='before')
    @classmethod
    def _no_grant(cls, value):
        if value is not False:
            raise ValueError('observation cannot grant authority')
        return value

    @model_validator(mode='before')
    @classmethod
    def _fresh_nested(cls, data):
        if isinstance(data, AipContractModel):
            data = data.model_dump(mode='python', by_alias=True)
        if isinstance(data, dict):
            return {k: (v.model_dump(mode='python', by_alias=True)
                        if isinstance(v, AipContractModel) else v) for k, v in data.items()}
        return data

    def observation_blockers(self):
        reasons = []
        p = self.parent.proposal
        if self.parent.decision != 'approved':
            reasons.append('WINDOW_PARENT_APPROVAL_NOT_OBSERVED')
        if self.parent.revoked:
            reasons.append('WINDOW_PARENT_REVOKED')
        if self.consumption is None:
            reasons.append('WINDOW_PARENT_CONSUMPTION_NOT_OBSERVED')
        target = p.canonical_payload()['target']
        target_hash = canonical_hash(target)
        for label, budget in (('SOURCE', self.source_budget), ('CURRENT', self.current_budget)):
            if budget is None:
                reasons.append(f'WINDOW_{label}_BUDGET_MISSING')
            else:
                body = budget.model_dump(mode='json', by_alias=True)
                clean = {k: v for k, v in body.items() if k not in {'tenant','contentHash','createdBy','createdAt'}}
                if (budget.content_hash != target_hash or clean != target):
                    reasons.append(f'WINDOW_{label}_BUDGET_CHANGED')
                if budget.lifecycle != 'active':
                    reasons.append(f'WINDOW_{label}_BUDGET_NOT_ACTIVE')
                if not budget.effective_from <= self.evaluated_at < budget.effective_until:
                    reasons.append(f'WINDOW_{label}_BUDGET_WINDOW_UNAVAILABLE')
        if self.current_budget_head_version != p.expected_head_version + 1:
            reasons.append('WINDOW_PARENT_BUDGET_HEAD_CHANGED')
        for label, provider in (('SOURCE', self.source_provider), ('CURRENT', self.current_provider)):
            if provider is None:
                reasons.append(f'WINDOW_{label}_PROVIDER_MISSING')
            elif provider.ref != p.basis.provider or provider.lifecycle != 'active':
                reasons.append(f'WINDOW_{label}_PROVIDER_CHANGED')
        return reasons

class BudgetPolicyWindowReviewSource(_WindowReviewFacts):
    state: Literal['observed', 'blocked']
    blockers: list[str]

    @model_validator(mode='after')
    def _consistent(self):
        p = self.parent.proposal
        if (self.tenant.org_id, self.tenant.project_id) != _SCOPE or p.tenant != self.tenant:
            raise ValueError('window review tenant drift')
        for item in (self.source_budget, self.current_budget, self.source_provider, self.current_provider):
            if item is not None and item.tenant != self.tenant:
                raise ValueError('window review source crosses tenant')
        if self.consumption is not None:
            digest = canonical_hash(dict(domain='aos.budget-cost-consume/v1',
                tenant=self.tenant.model_dump(mode='json', by_alias=True),
                proposalId=self.parent.proposal_id, proposalHash=self.parent.proposal_hash,
                decisionId=self.parent.decision_id))
            expected = dict(resourceType='BudgetRevision', resourceId=p.target.budget_id,
                revision=p.target.revision, contentHash=canonical_hash(p.canonical_payload()['target']),
                proposalId=self.parent.proposal_id, proposalHash=self.parent.proposal_hash,
                decisionId=self.parent.decision_id, receiptId='budget-cost-consume-'+digest)
            r = self.consumption
            if (self.parent.decision != 'approved' or r.request_hash != digest
                    or r.receipt_id != expected['receiptId'] or r.result_ref != expected
                    or r.created_by != p.maker_subject):
                raise ValueError('window parent consumption observation drift')
        reasons = self.observation_blockers()
        if self.blockers != reasons or self.state != ('blocked' if reasons else 'observed'):
            raise ValueError('window review observation state drift')
        return self


def build_source(**fields):
    """Validate fresh nested facts before deriving observation-only blockers."""
    facts = _WindowReviewFacts.model_validate({k: v for k, v in fields.items()
        if k not in {'state', 'blockers'}})
    reasons = facts.observation_blockers()
    return BudgetPolicyWindowReviewSource.model_validate(dict(
        **facts.model_dump(mode='python', by_alias=True),
        state='blocked' if reasons else 'observed', blockers=reasons))


class BudgetPolicyWindowReviewReader:
    def __init__(self, connect_factory=None):
        self._connect_factory = connect_read_only if connect_factory is None else connect_factory

    def read(self, principal, proposal_id):
        try:
            scope, actor = _identity(principal)
            _key(proposal_id)
            if scope.key != _SCOPE or actor != _HUMAN:
                raise ValueError()
        except Exception:
            raise BudgetPolicyWindowReviewDenied('WINDOW_REVIEW_ORIGINAL_CHECKER_REQUIRED') from None
        try:
            with self._connect_factory(scope) as conn:
                if conn.read_only is not True or conn.isolation_level != IsolationLevel.REPEATABLE_READ:
                    raise BudgetPolicyWindowReviewUnavailable('WINDOW_REVIEW_READONLY_SNAPSHOT_REQUIRED')
                _require_inquiry_connection(conn, scope)

                @contextmanager
                def borrow(request_scope):
                    if request_scope != scope:
                        raise BudgetPolicyWindowReviewUnavailable('WINDOW_REVIEW_SCOPE_CHANGED')
                    yield conn

                cost = BudgetCostProposalStore(read_connect_factory=borrow).review(principal, proposal_id)
                p = BudgetCostBasisProposal.from_canonical_payload(cost['proposal']['proposal'])
                _member(conn, scope, p.maker_subject, label='MAKER', lock=False)
                if p.checker_subject != actor or not isinstance(p.basis, DevelopmentRiskProposal):
                    raise BudgetPolicyWindowReviewDenied('WINDOW_REVIEW_PARENT_CHECKER_REQUIRED')
                decision = cost['decision']
                parent = ParentCostObservation(proposal_id=proposal_id,
                    proposal_hash=cost['proposal']['proposalHash'], proposal=p,
                    decision_id=decision['decisionId'] if decision else None,
                    decision=decision['decision'] if decision else 'missing', revoked=cost['revocation'] is not None)
                row = conn.execute('SELECT receipt_id,request_hash,result_ref,created_by FROM public.aip_budget_receipt '
                    'WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s',
                    (*scope.key,'budget_revision.activate_cost',proposal_id)).fetchone()
                consumption = ParentConsumptionObservation(**row) if row is not None else None
                budgets = AipBudgetAuthorityStore(connect_factory=borrow)
                providers = AipModelRuntimeStore(connect_factory=borrow)

                def optional(get, missing, *args):
                    try:
                        return get(*args)
                    except missing:
                        return None

                source_budget = optional(budgets.get, BudgetNotFound, scope, p.target.budget_id, p.target.revision)
                current_budget = optional(budgets.get, BudgetNotFound, scope, p.target.budget_id)
                head = conn.execute('SELECT current_revision,version FROM public.aip_budget_head '
                    'WHERE org_id=%s AND project_id=%s AND budget_id=%s', (*scope.key,p.target.budget_id)).fetchone()
                if head and current_budget is not None and head['current_revision'] != current_budget.revision:
                    raise BudgetPolicyWindowReviewUnavailable('WINDOW_REVIEW_HEAD_DRIFT')

                def provider(revision):
                    value = optional(providers.get_provider, ModelRuntimeNotFound,
                                     scope, p.basis.provider.asset_id, revision)
                    if value is None:
                        return None
                    return WindowProviderObservation(tenant=value.tenant, lifecycle=value.lifecycle,
                        ref=VersionedAssetRef(asset_type='ProviderInstanceRevision', asset_id=value.provider_instance_id,
                                              revision=value.revision, content_hash=value.content_hash))

                source_provider, current_provider = provider(p.basis.provider.revision), provider(None)
                now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                return build_source(schema_version='aos.budget-policy-window.review-source/v1',
                    tenant=p.tenant, evaluated_at=now, parent=parent, consumption=consumption,
                    source_budget=source_budget, current_budget=current_budget,
                    current_budget_head_version=head['version'] if head else None,
                    source_provider=source_provider, current_provider=current_provider)
        except BudgetPolicyWindowReviewDenied:
            raise
        except Exception:
            # No database details, connection values or secret material escape.
            raise BudgetPolicyWindowReviewUnavailable('WINDOW_REVIEW_SOURCE_UNAVAILABLE') from None
