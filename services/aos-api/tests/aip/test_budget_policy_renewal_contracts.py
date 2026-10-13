"""Public renewal inputs cannot supply actors, approval facts or policy payloads.

These are contract tests only; their fixtures are not approvals or real actors.
"""
from copy import deepcopy

import pytest
from pydantic import ValidationError


def command(kind='proposal'):
    value = dict(schemaVersion=1, orgId='org-org', projectId='dev-project',
                 idempotencyKey='renewal-request-1')
    if kind == 'proposal':
        value.update(sourcePolicyId='a0v-ecommerce-budget-policy-v1',
                     expectedSourceRevision=13, expectedHeadVersion=13,
                     expectedSourceHash='a' * 64,
                     effectiveFrom='2026-10-13T04:00:00Z',
                     effectiveUntil='2026-10-13T04:30:00Z')
    else:
        value.update(proposalId='renewal-proposal-1', proposalHash='b' * 64)
        if kind == 'decision':
            value.update(targetActiveHash='c' * 64, decision='approved')
        else:
            value.update(decisionId='renewal-decision-1', decisionHash='d' * 64)
    return value


def model(kind):
    from aos_api import aip_budget_policy_renewal_contracts as contracts
    return {'proposal': contracts.RenewalProposalCommand,
            'decision': contracts.RenewalDecisionCommand,
            'consume': contracts.RenewalConsumeCommand}[kind]


@pytest.mark.parametrize('kind', ['proposal', 'decision', 'consume'])
def test_valid_input_is_metadata_only_and_not_authority(kind):
    parsed = model(kind).model_validate(command(kind))
    assert len(parsed.request_hash) == 64
    assert parsed.activation_eligible is False
    assert not ({'makerSubject', 'checkerSubject', 'bearerToken', 'targetPolicy'}
                & parsed.canonical_payload().keys())


@pytest.mark.parametrize('kind', ['proposal', 'decision', 'consume'])
@pytest.mark.parametrize('field,value', [
    ('makerSubject', 'pretend-machine'), ('checkerSubject', 'pretend-human'),
    ('actor', 'pretend-admin'), ('approvalVerified', True),
    ('activationEligible', True), ('targetPolicy', {'lifecycle': 'active'}),
])
def test_request_cannot_inject_actor_or_publication_authority(kind, field, value):
    raw = command(kind)
    raw[field] = value
    with pytest.raises(ValidationError):
        model(kind).model_validate(raw)


@pytest.mark.parametrize('kind', ['proposal', 'decision', 'consume'])
@pytest.mark.parametrize('field,value', [
    ('schemaVersion', True), ('orgId', 'dev-org'), ('projectId', 'other'),
    ('idempotencyKey', ' key'), ('idempotencyKey', ''),
])
def test_all_entries_fail_closed_for_bad_scope_or_key(kind, field, value):
    raw = command(kind)
    raw[field] = value
    with pytest.raises(ValidationError):
        model(kind).model_validate(raw)


@pytest.mark.parametrize('field,value', [
    ('expectedSourceRevision', True), ('expectedHeadVersion', 13.0),
    ('expectedHeadVersion', 0), ('expectedSourceRevision', 9007199254740992),
    ('expectedSourceHash', 'A' * 64), ('expectedSourceHash', 'g' * 64),
    ('effectiveFrom', 1791864000), ('effectiveFrom', '2026-10-13T04:00:00'),
    ('effectiveUntil', '2026-10-13T04:00:00Z'),
])
def test_proposal_requires_exact_versions_hash_and_explicit_window(field, value):
    raw = command()
    raw[field] = value
    with pytest.raises(ValidationError):
        model('proposal').model_validate(raw)


def test_equivalent_timezone_and_key_do_not_change_semantic_request_hash():
    raw = command()
    first = model('proposal').model_validate(raw)
    raw.update(idempotencyKey='renewal-request-2',
               effectiveFrom='2026-10-13T12:00:00+08:00',
               effectiveUntil='2026-10-13T12:30:00+08:00')
    second = model('proposal').model_validate(raw)
    assert first.request_hash == second.request_hash
    assert first.canonical_payload()['effectiveFrom'] == second.canonical_payload()['effectiveFrom']


@pytest.mark.parametrize('field,value', [
    ('effectiveUntil', '2027-01-01T00:00:00Z'),
    ('targetActiveHash', 'e' * 63), ('decision', 'revoked'),
])
def test_decision_cannot_mutate_window_or_repurpose_operation(field, value):
    raw = command('decision')
    raw[field] = value
    with pytest.raises(ValidationError):
        model('decision').model_validate(raw)


def test_decision_hash_binds_outcome_and_exact_target():
    raw = command('decision')
    first = model('decision').model_validate(raw)
    raw['decision'] = 'rejected'
    assert model('decision').model_validate(raw).request_hash != first.request_hash
    raw = command('decision')
    raw['targetActiveHash'] = 'e' * 64
    assert model('decision').model_validate(raw).request_hash != first.request_hash


def test_copy_bypass_cannot_yield_usable_hash():
    parsed = model('consume').model_validate(command('consume'))
    changed = parsed.model_copy(update={'proposal_hash': 'wrong'})
    with pytest.raises(ValidationError):
        _ = changed.request_hash
    assert parsed.canonical_payload() == model('consume').model_validate(
        deepcopy(command('consume'))).canonical_payload()


def revocation_input():
    return {**command('consume'), 'reasonCode': 'approval_withdrawn'}


def test_revocation_binds_original_decision_and_separate_operation():
    from aos_api.aip_budget_policy_renewal_contracts import RenewalRevocationCommand
    raw = revocation_input()
    parsed = RenewalRevocationCommand.model_validate(raw)
    assert parsed.activation_eligible is False
    assert parsed.request_hash != model('consume').model_validate(command('consume')).request_hash
    raw['decisionHash'] = 'e' * 64
    assert RenewalRevocationCommand.model_validate(raw).request_hash != parsed.request_hash
    raw = revocation_input()
    raw['reasonCode'] = 'scope_changed'
    assert RenewalRevocationCommand.model_validate(raw).request_hash != parsed.request_hash


@pytest.mark.parametrize('field,value', [
    ('reasonCode', None), ('reasonCode', ''), ('reasonCode', 'automatic_approval'),
    ('checkerSubject', 'pretend-human'), ('decision', 'approved'),
    ('decisionHash', 'wrong'), ('orgId', 'dev-org'),
])
def test_revocation_cannot_inject_actor_or_replace_exact_approved_decision(field, value):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalRevocationCommand
    raw = revocation_input()
    raw[field] = value
    with pytest.raises(ValidationError):
        RenewalRevocationCommand.model_validate(raw)


def test_revocation_requires_explicit_reason_and_revalidates_copy():
    from aos_api.aip_budget_policy_renewal_contracts import RenewalRevocationCommand
    with pytest.raises(ValidationError):
        RenewalRevocationCommand.model_validate(command('consume'))
    parsed = RenewalRevocationCommand.model_validate(revocation_input())
    with pytest.raises(ValidationError):
        _ = parsed.model_copy(update={'reason_code': 'pretend'}).request_hash
