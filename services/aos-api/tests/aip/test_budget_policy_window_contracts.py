"""A policy subwindow draft binds claims, never approval or Owner facts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aos_api.aip_budget_policy_window_contracts import BudgetPolicyWindowDraft


def window_draft_payload():
    return {
        'schemaVersion': 1,
        'tenant': {'orgId': 'org-org', 'projectId': 'dev-project'},
        'masterBudgetRef': {'assetType': 'BudgetRevision', 'assetId': 'budget-1',
                            'revision': 2, 'contentHash': 'a' * 64},
        'providerRef': {'assetType': 'ProviderInstanceRevision', 'assetId': 'provider-1',
                        'revision': 1, 'contentHash': 'b' * 64},
        'providerModelId': 'model-1',
        'costProposalId': 'cost-proposal-1', 'costProposalHash': 'c' * 64,
        'costDecisionId': 'cost-decision-1',
        'costConsumptionReceiptId': 'cost-consumption-1',
        'claimedBudgetWindow': {'effectiveFrom': '2026-10-01T00:00:00Z',
                                'effectiveUntil': '2026-11-01T00:00:00Z'},
        'requestedPolicyWindow': {'effectiveFrom': '2026-10-01T00:00:00Z',
                                  'effectiveUntil': '2026-10-15T00:00:00Z'},
        'makerSubject': 'formal-machine-claim', 'checkerSubject': 'human-claim',
    }


def test_draft_roundtrip_is_not_a_cost_proposal_or_execution_envelope():
    draft = BudgetPolicyWindowDraft.model_validate(window_draft_payload())
    restored = BudgetPolicyWindowDraft.model_validate_json(draft.model_dump_json(by_alias=True))
    assert restored.canonical_payload() == window_draft_payload()
    assert restored.draft_hash == draft.draft_hash
    assert len(draft.draft_hash) == 64
    assert not hasattr(draft, 'proposal_hash')
    assert not {'approvalVerified', 'activationEligible', 'nativeWriteAllowed'} & draft.canonical_payload().keys()


@pytest.mark.parametrize('part,field,value', [
    ('requestedPolicyWindow', 'effectiveFrom', '2026-09-30T23:59:59Z'),
    ('requestedPolicyWindow', 'effectiveUntil', '2026-11-01T00:00:00Z'),
    ('requestedPolicyWindow', 'effectiveUntil', '2026-11-02T00:00:00Z'),
    ('requestedPolicyWindow', 'effectiveUntil', '2026-10-01T00:00:00Z'),
    ('requestedPolicyWindow', 'effectiveFrom', '2026-10-16T00:00:00Z'),
    ('claimedBudgetWindow', 'effectiveFrom', '2026-11-01T00:00:00Z'),
    ('claimedBudgetWindow', 'effectiveUntil', '2026-09-01T00:00:00Z'),
    ('requestedPolicyWindow', 'effectiveFrom', '2026-10-01T00:00:00'),
    ('claimedBudgetWindow', 'effectiveUntil', 1793491200),
])
def test_invalid_or_ambiguous_windows_never_produce_a_hash(part, field, value):
    data = window_draft_payload(); data[part][field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyWindowDraft.model_validate(data)


@pytest.mark.parametrize('ref,field,value', [
    ('masterBudgetRef', 'assetType', 'BudgetPolicyRevision'),
    ('providerRef', 'assetType', 'BudgetRevision'),
    ('masterBudgetRef', 'revision', True), ('providerRef', 'revision', '1'),
    ('masterBudgetRef', 'revision', 1.0), ('providerRef', 'revision', 0),
    ('masterBudgetRef', 'revision', 9_007_199_254_740_992),
    ('providerRef', 'assetId', ' provider-1 '),
    ('masterBudgetRef', 'assetId', 'budget-1\n'),
    ('providerRef', 'contentHash', 'B' * 64),
    ('masterBudgetRef', 'contentHash', b'a' * 64),
    ('masterBudgetRef', 'approved', True),
])
def test_exact_refs_reject_coercion_and_forged_facts(ref, field, value):
    data = window_draft_payload(); data[ref][field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyWindowDraft.model_validate(data)


@pytest.mark.parametrize('field,value', [
    ('schemaVersion', True), ('schemaVersion', '1'), ('schemaVersion', 2),
    ('checkerSubject', 'formal-machine-claim'), ('makerSubject', ' maker '),
    ('checkerSubject', ''), ('providerModelId', 'model\n'),
    ('costProposalId', ' '), ('costDecisionId', ''),
    ('costConsumptionReceiptId', '\treceipt'), ('costProposalHash', 'bad'),
    ('costProposalHash', b'c' * 64),
    ('approved', True), ('approvalVerified', True), ('activationEligible', True),
    ('nativeWriteAllowed', True), ('proposalHash', 'd' * 64),
    ('amountMinor', 100), ('ownerVerified', True),
])
def test_caller_cannot_smuggle_authority_or_inexact_identity(field, value):
    data = window_draft_payload(); data[field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyWindowDraft.model_validate(data)


@pytest.mark.parametrize('field,value', [('orgId', ''), ('projectId', ' '),
                                        ('orgId', 9), ('projectId', None)])
def test_both_tenant_dimensions_are_canonical_claims(field, value):
    data = window_draft_payload(); data['tenant'][field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyWindowDraft.model_validate(data)


@pytest.mark.parametrize('path,value', [
    (('tenant', 'orgId'), 'another-org'), (('tenant', 'projectId'), 'another-project'),
    (('masterBudgetRef', 'assetId'), 'budget-2'), (('masterBudgetRef', 'revision'), 3),
    (('masterBudgetRef', 'contentHash'), 'd' * 64),
    (('providerRef', 'assetId'), 'provider-2'), (('providerRef', 'revision'), 2),
    (('providerRef', 'contentHash'), 'd' * 64),
    (('providerModelId',), 'model-2'), (('costProposalId',), 'cost-proposal-2'),
    (('costProposalHash',), 'd' * 64), (('costDecisionId',), 'decision-2'),
    (('costConsumptionReceiptId',), 'receipt-2'),
    (('makerSubject',), 'maker-2'), (('checkerSubject',), 'checker-2'),
    (('claimedBudgetWindow', 'effectiveFrom'), '2026-09-30T00:00:00Z'),
    (('claimedBudgetWindow', 'effectiveUntil'), '2026-11-02T00:00:00Z'),
    (('requestedPolicyWindow', 'effectiveFrom'), '2026-10-02T00:00:00Z'),
    (('requestedPolicyWindow', 'effectiveUntil'), '2026-10-16T00:00:00Z'),
])
def test_hash_binds_every_claimed_source_and_window(path, value):
    data = window_draft_payload()
    original = BudgetPolicyWindowDraft.model_validate(data).draft_hash
    changed = deepcopy(data)
    target = changed if len(path) == 1 else changed[path[0]]
    target[path[-1]] = value
    assert BudgetPolicyWindowDraft.model_validate(changed).draft_hash != original


def test_utc_equivalent_instants_have_one_hash():
    data = window_draft_payload(); other = deepcopy(data)
    for key in ('claimedBudgetWindow', 'requestedPolicyWindow'):
        for field, value in data[key].items():
            other[key][field] = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(
                timezone(timedelta(hours=8)))
    assert BudgetPolicyWindowDraft.model_validate(data).draft_hash == BudgetPolicyWindowDraft.model_validate(other).draft_hash


@pytest.mark.parametrize('mutation', ['outer_copy', 'nested_ref', 'nested_window', 'tenant', 'ref_copy'])
def test_canonical_boundary_rechecks_mutable_models(mutation):
    draft = BudgetPolicyWindowDraft.model_validate(window_draft_payload())
    if mutation == 'outer_copy': draft = draft.model_copy(update={'checker_subject': draft.maker_subject})
    elif mutation == 'nested_ref': draft.master_budget_ref.revision = True
    elif mutation == 'nested_window': draft.requested_policy_window.effective_until = draft.claimed_budget_window.effective_until
    elif mutation == 'tenant': draft.tenant.project_id = ''
    else: draft.provider_ref = draft.provider_ref.model_copy(update={'asset_type': 'BudgetRevision'})
    with pytest.raises(ValidationError):
        draft.canonical_payload()
    with pytest.raises(ValidationError):
        _ = draft.draft_hash
