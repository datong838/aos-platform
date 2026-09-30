"""Cost proposals are typed inputs, never external evidence or activation permission."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal


def payload(kind='development_risk_proposal'):
    basis = dict(kind=kind, provider=dict(assetType='ProviderInstanceRevision',
        assetId='provider-1', revision=1, contentHash='a'*64), providerModelId='model-1',
        perRequestRiskMinor=10, totalRiskMinor=100, maxRequests=10)
    if kind == 'external_reconciliation_reference':
        basis = dict(kind=kind, statement=dict(assetType='BudgetUsageReconciliationRevision',
            assetId='statement-1', revision=1, contentHash='b'*64))
    return dict(schemaVersion=1, tenant=dict(orgId='org-org',projectId='dev-project'),
        draftRevision=1, expectedHeadVersion=2, makerSubject='maker', checkerSubject='checker',
        target=dict(budgetId='budget-1',revision=2,lifecycle='active',dailyLimitMinor=50,
            monthlyLimitMinor=500,alertThresholdPct=80,owner='owner',overBudgetApprover='reviewer',
            effectiveFrom='2026-10-01T00:00:00Z',effectiveUntil='2026-10-02T00:00:00Z'),basis=basis)


@pytest.mark.parametrize('kind',['development_risk_proposal','external_reconciliation_reference'])
def test_roundtrip_is_pending_input_without_authority_flags(kind):
    proposal = BudgetCostBasisProposal.model_validate(payload(kind))
    body = proposal.canonical_payload()
    assert body['accounts'] == {'daily':'budget-1:daily','pilot':'budget-1:pilot'}
    assert body['currency'] == 'CNY'
    assert body['period'] == {'start':'2026-10-01T00:00:00Z','end':'2026-10-02T00:00:00Z'}
    assert len(proposal.proposal_hash) == 64
    restored = BudgetCostBasisProposal.model_validate_json(proposal.model_dump_json(by_alias=True))
    assert restored.proposal_hash == proposal.proposal_hash
    assert not {'approved','externalUsageProven','activationEligible','usageKnown'} & body.keys()


@pytest.mark.parametrize('field,value', [('approvalRef','approved'),('amountMinor',0),
    ('externalUsageProven',True),('usageKnown',True),('activationEligible',True),('approved',True)])
def test_caller_cannot_assert_authority(field,value):
    data=payload();data['basis'][field]=value
    with pytest.raises(ValidationError):BudgetCostBasisProposal.model_validate(data)


@pytest.mark.parametrize('field,value',[('perRequestRiskMinor',True),('totalRiskMinor','100'),
    ('maxRequests',1.5),('maxRequests',0),('perRequestRiskMinor',0),
    ('totalRiskMinor',501),('perRequestRiskMinor',51)])
def test_risk_proposal_rejects_coercion_or_excess(field,value):
    data=payload();data['basis'][field]=value
    with pytest.raises(ValidationError):BudgetCostBasisProposal.model_validate(data)


@pytest.mark.parametrize('change',['tenant','same_actor','head_bool','draft_string','target_revision',
    'draft_target','provider_type','provider_revision_bool','provider_padding','model_blank','maker_padding','kind',
    'total_below_request','request_count_exceeds_total'])
def test_exact_scope_target_and_bounds(change):
    data=payload()
    if change=='tenant':data['tenant']['orgId']='dev-org'
    elif change=='same_actor':data['checkerSubject']='maker'
    elif change=='head_bool':data['expectedHeadVersion']=True
    elif change=='draft_string':data['draftRevision']='1'
    elif change=='target_revision':data['target']['revision']=3
    elif change=='draft_target':data['target']['lifecycle']='draft'
    elif change=='provider_type':data['basis']['provider']['assetType']='BudgetPolicyRevision'
    elif change=='provider_revision_bool':data['basis']['provider']['revision']=True
    elif change=='provider_padding':data['basis']['provider']['assetId']=' provider-1 '
    elif change=='model_blank':data['basis']['providerModelId']=' '
    elif change=='maker_padding':data['makerSubject']=' maker'
    elif change=='kind':data['basis']['kind']='already_approved'
    elif change=='total_below_request':data['basis']['totalRiskMinor']=5
    elif change=='request_count_exceeds_total':data['basis']['maxRequests']=11
    with pytest.raises(ValidationError):BudgetCostBasisProposal.model_validate(data)


@pytest.mark.parametrize('change',['head','maker','checker','amount','provider','model','risk','count','statement'])
def test_hash_binds_every_review_dimension(change):
    data=payload('external_reconciliation_reference' if change=='statement' else 'development_risk_proposal')
    original=BudgetCostBasisProposal.model_validate(data).proposal_hash
    changed=deepcopy(data)
    if change=='head':changed['expectedHeadVersion']=3
    elif change=='maker':changed['makerSubject']='maker-2'
    elif change=='checker':changed['checkerSubject']='checker-2'
    elif change=='amount':changed['target']['monthlyLimitMinor']=600
    elif change=='provider':changed['basis']['provider']['revision']=2
    elif change=='model':changed['basis']['providerModelId']='model-2'
    elif change=='risk':changed['basis']['totalRiskMinor']=110
    elif change=='count':changed['basis']['maxRequests']=9
    elif change=='statement':changed['basis']['statement']['contentHash']='c'*64
    assert BudgetCostBasisProposal.model_validate(changed).proposal_hash != original


def test_equivalent_timezone_produces_same_hash():
    a=payload();b=deepcopy(a)
    for field in ('effectiveFrom','effectiveUntil'):
        b['target'][field]=datetime.fromisoformat(a['target'][field].replace('Z','+00:00')).astimezone(timezone(timedelta(hours=8)))
    assert BudgetCostBasisProposal.model_validate(a).proposal_hash == BudgetCostBasisProposal.model_validate(b).proposal_hash


@pytest.mark.parametrize('change',['copy','nested','target'])
def test_serialization_revalidates_mutated_models(change):
    proposal=BudgetCostBasisProposal.model_validate(payload())
    if change=='copy':proposal=proposal.model_copy(update={'checker_subject':'maker'})
    elif change=='nested':proposal.basis.total_risk_minor=0
    else:proposal.target.revision=8
    with pytest.raises(ValidationError):proposal.canonical_payload()


def test_external_statement_is_not_a_telemetry_usage_receipt():
    data=payload('external_reconciliation_reference')
    data['basis']['statement']['assetType']='UsageReceipt'
    with pytest.raises(ValidationError):BudgetCostBasisProposal.model_validate(data)


@pytest.mark.parametrize('field,value',[('revision','2'),('dailyLimitMinor',50.0),
    ('monthlyLimitMinor','500'),('budgetId',' budget-1 '),('hardStop',1)])
def test_new_proposal_does_not_silently_coerce_existing_budget_dto(field,value):
    data=payload();data['target'][field]=value
    with pytest.raises(ValidationError):BudgetCostBasisProposal.model_validate(data)
