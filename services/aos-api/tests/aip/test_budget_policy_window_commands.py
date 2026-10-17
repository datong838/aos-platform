"""Wire inputs bind exact consent; parsed commands are never consent facts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aos_api.aip_budget_policy_window_commands import (
    WindowProposeCommand, WindowDecisionCommand, WindowRevocationCommand, WindowConsumeCommand,
)
from test_budget_policy_window_contracts import window_draft_payload


def command_payload(kind='propose'):
    common = dict(schemaVersion=1, orgId='org-org', projectId='dev-project',
                  idempotencyKey='window:test-1')
    if kind == 'propose':
        draft = window_draft_payload()
        return dict(common, parentCostProposalId=draft['costProposalId'],
            parentCostProposalHash=draft['costProposalHash'], parentCostDecisionId=draft['costDecisionId'],
            parentConsumptionReceiptId=draft['costConsumptionReceiptId'],
            expectedBudgetRef=draft['masterBudgetRef'], expectedBudgetHeadVersion=3,
            expectedProviderRef=draft['providerRef'], expectedProviderModelId=draft['providerModelId'],
            effectiveFrom='2026-10-01T00:00:00Z', effectiveUntil='2026-10-15T00:00:00Z')
    common.update(proposalId='window-proposal-1', proposalHash='d' * 64)
    if kind == 'decide': return dict(common, targetPairHash='e' * 64, decision='approved')
    if kind == 'revoke':
        return dict(common, originalDecisionId='window-decision-1',
                    originalDecisionHash='f' * 64, reason='withdraw this child configuration')
    return dict(common, decisionId='window-decision-1', decisionHash='f' * 64, targetPairHash='e' * 64)


TYPES = {'propose': WindowProposeCommand, 'decide': WindowDecisionCommand,
         'revoke': WindowRevocationCommand, 'consume': WindowConsumeCommand}


@pytest.mark.parametrize('kind', TYPES)
def test_commands_roundtrip_without_actor_or_authority(kind):
    command = TYPES[kind].model_validate(command_payload(kind))
    restored = TYPES[kind].model_validate(command.canonical_payload())
    assert restored.request_hash == command.request_hash
    assert len(command.request_hash) == 64
    assert not {'actor', 'makerSubject', 'checkerSubject', 'approvalVerified', 'activationEligible'} & command.canonical_payload().keys()


@pytest.mark.parametrize('kind', TYPES)
@pytest.mark.parametrize('field,value', [
    ('orgId', 'dev-org'), ('projectId', ''), ('schemaVersion', True), ('schemaVersion', '1'),
    ('idempotencyKey', ' key '), ('idempotencyKey', '含中文'), ('idempotencyKey', ''),
    ('actor', 'human'), ('makerSubject', 'maker'), ('checkerSubject', 'human'),
    ('bearerToken', 'not-a-token'), ('approved', True), ('activationEligible', True),
    ('targetActive', {}), ('amountMinor', 100),
])
def test_public_wire_rejects_impersonation_and_noncanonical_scope(kind, field, value):
    data = command_payload(kind); data[field] = value
    with pytest.raises(ValidationError): TYPES[kind].model_validate(data)


@pytest.mark.parametrize('kind', TYPES)
def test_key_is_bound_by_receipt_identity_not_the_semantic_hash(kind):
    data = command_payload(kind); first = TYPES[kind].model_validate(data)
    data['idempotencyKey'] = 'different-key'
    other = TYPES[kind].model_validate(data)
    assert first.request_hash == other.request_hash
    assert first.canonical_payload()['idempotencyKey'] != other.canonical_payload()['idempotencyKey']


@pytest.mark.parametrize('path,value', [
    (('expectedBudgetRef', 'assetType'), 'BudgetPolicyRevision'),
    (('expectedProviderRef', 'assetType'), 'BudgetRevision'),
    (('expectedBudgetRef', 'assetType'), ' BudgetRevision '),
    (('expectedBudgetRef', 'revision'), True), (('expectedProviderRef', 'revision'), '1'),
    (('expectedBudgetRef', 'revision'), 9_007_199_254_740_992),
    (('expectedProviderRef', 'assetId'), ' provider-1 '),
    (('expectedBudgetRef', 'contentHash'), b'a' * 64),
    (('expectedBudgetHeadVersion',), True), (('expectedBudgetHeadVersion',), 0),
    (('parentCostProposalHash',), b'c' * 64),
    (('parentConsumptionReceiptId',), ''), (('expectedProviderModelId',), 'model\n'),
    (('effectiveFrom',), '2026-10-01T00:00:00'), (('effectiveUntil',), 1790000000),
    (('effectiveUntil',), '2026-10-01T00:00:00Z'),
])
def test_proposal_exact_refs_and_time_shapes(path, value):
    data = command_payload(); parent = data if len(path) == 1 else data[path[0]]
    parent[path[-1]] = value
    with pytest.raises(ValidationError): WindowProposeCommand.model_validate(data)


def test_equivalent_times_have_exact_six_digit_utc_wire_and_one_hash():
    data = command_payload(); other = deepcopy(data)
    for field in ('effectiveFrom', 'effectiveUntil'):
        other[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00')).astimezone(
            timezone(timedelta(hours=8)))
    one, two = (WindowProposeCommand.model_validate(x) for x in (data, other))
    assert one.canonical_payload()['effectiveFrom'] == '2026-10-01T00:00:00.000000Z'
    assert one.canonical_payload() == two.canonical_payload()
    assert one.request_hash == two.request_hash


@pytest.mark.parametrize('field,value', [
    ('parentCostProposalId', 'another-parent'), ('parentCostProposalHash', 'a' * 64),
    ('parentCostDecisionId', 'another-decision'), ('parentConsumptionReceiptId', 'another-receipt'),
    ('expectedBudgetHeadVersion', 4), ('expectedProviderModelId', 'another-model'),
    ('effectiveFrom', '2026-10-02T00:00:00Z'), ('effectiveUntil', '2026-10-16T00:00:00Z'),
])
def test_proposal_hash_changes_for_source_or_window_tampering(field, value):
    data = command_payload(); first = WindowProposeCommand.model_validate(data).request_hash
    data[field] = value
    assert WindowProposeCommand.model_validate(data).request_hash != first


def test_distinct_operations_and_checker_outcome_are_domain_separated():
    approved = WindowDecisionCommand.model_validate(command_payload('decide'))
    other = command_payload('decide'); other['decision'] = 'rejected'
    assert approved.request_hash != WindowDecisionCommand.model_validate(other).request_hash
    hashes = {TYPES[k].model_validate(command_payload(k)).request_hash for k in TYPES}
    assert len(hashes) == 4


@pytest.mark.parametrize('kind,field,value', [
    ('decide', 'proposalId', 'another-proposal'), ('decide', 'proposalHash', 'a' * 64),
    ('decide', 'targetPairHash', 'a' * 64),
    ('revoke', 'originalDecisionId', 'another-decision'),
    ('revoke', 'originalDecisionHash', 'a' * 64), ('revoke', 'reason', 'different reason'),
    ('consume', 'decisionId', 'another-decision'), ('consume', 'decisionHash', 'a' * 64),
    ('consume', 'targetPairHash', 'a' * 64),
])
def test_consent_and_consumption_hashes_bind_exact_reviewed_targets(kind, field, value):
    data = command_payload(kind); first = TYPES[kind].model_validate(data).request_hash
    data[field] = value
    assert TYPES[kind].model_validate(data).request_hash != first


@pytest.mark.parametrize('kind', TYPES)
def test_canonical_rechecks_model_copy(kind):
    command = TYPES[kind].model_validate(command_payload(kind)).model_copy(update={'org_id': 'dev-org'})
    with pytest.raises(ValidationError): command.canonical_payload()
    with pytest.raises(ValidationError): _ = command.request_hash


def test_nested_ref_mutation_and_missing_source_cannot_be_hashed():
    command = WindowProposeCommand.model_validate(command_payload())
    command.expected_budget_ref.revision = True
    with pytest.raises(ValidationError): _ = command.request_hash
    data = command_payload(); del data['parentConsumptionReceiptId']
    with pytest.raises(ValidationError): WindowProposeCommand.model_validate(data)
