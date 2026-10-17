"""Offline shape planning must not manufacture execution permission."""
import socket

import psycopg
import pytest
from pydantic import ValidationError

from aos_api.aip_budget_policy_window_contracts import BudgetPolicyWindowDraft
from aos_api.aip_budget_policy_window_plan import plan_policy_window
from test_budget_policy_window_contracts import window_draft_payload


def test_planning_without_network_or_database_always_requires_owner_facts(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('offline draft planning must not perform I/O')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    data = window_draft_payload()
    result = plan_policy_window(data).model_dump(mode='json', by_alias=True)
    assert result['sourceVerification'] == 'unverified_input'
    assert result['approvalVerified'] is False
    assert result['activationEligible'] is False
    assert result['nativeWriteAllowed'] is False
    assert result['draftHash'] == BudgetPolicyWindowDraft.model_validate(data).draft_hash
    assert result['claimedFollowOnWindow'] == {
        'effectiveFrom': '2026-10-15T00:00:00Z', 'effectiveUntil': '2026-11-01T00:00:00Z'}
    assert set(result['pendingOwnerChecks']) == {
        'parent_budget_current_exact_active', 'provider_current_exact_active',
        'cost_parent_approved_consumed_not_revoked', 'maker_checker_current_members',
        'explicit_new_policy_approval', 'paired_price_authorization',
        'model_owner_successor_and_eval', 'native_transaction_receipt',
    }
    assert not {'command', 'proposalHash', 'approved', 'budgetAmount'} & result.keys()


def test_different_tenant_claims_are_never_reported_as_owner_verified():
    data = window_draft_payload(); data['tenant']['orgId'] = 'unverified-other-org'
    result = plan_policy_window(data)
    assert result.source_verification == 'unverified_input'
    assert not result.approval_verified and not result.native_write_allowed
    assert result.draft_hash != plan_policy_window(window_draft_payload()).draft_hash


@pytest.mark.parametrize('kind', ['copy', 'nested'])
def test_model_input_is_revalidated_before_planning(kind):
    draft = BudgetPolicyWindowDraft.model_validate(window_draft_payload())
    if kind == 'copy': draft = draft.model_copy(update={'cost_proposal_hash': 'invalid'})
    else: draft.requested_policy_window.effective_until = draft.claimed_budget_window.effective_until
    with pytest.raises(ValidationError): plan_policy_window(draft)


@pytest.mark.parametrize('field', ['approvalVerified', 'activationEligible', 'nativeWriteAllowed'])
def test_forged_approval_is_not_used_as_a_planning_hint(field):
    data = window_draft_payload(); data[field] = True
    with pytest.raises(ValidationError): plan_policy_window(data)


def test_planner_output_cannot_be_reused_as_an_input_proposal():
    result = plan_policy_window(window_draft_payload())
    with pytest.raises(ValidationError): plan_policy_window(result.model_dump(by_alias=True))


def test_returns_independent_derived_window():
    draft = BudgetPolicyWindowDraft.model_validate(window_draft_payload())
    result = plan_policy_window(draft)
    old = result.model_dump(mode='json', by_alias=True)
    draft.requested_policy_window.effective_until = draft.claimed_budget_window.effective_until
    assert result.model_dump(mode='json', by_alias=True) == old
