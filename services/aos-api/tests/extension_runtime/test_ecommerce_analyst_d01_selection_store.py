"""The selection Store must not turn an arbitrary packet into approval."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_analyst_d01_source_selection import D01SourceSelectionProposal
from aos_api.ecommerce_analyst_d01_source_selection_store import D01SourceSelectionStore
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_d01_issuer import NOW, SCOPE, _packet, _resource, _timeline


def _proposal(plan_hash='a' * 64):
    return D01SourceSelectionProposal.model_validate(dict(
        tenant={'orgId': SCOPE.org_id, 'projectId': SCOPE.project_id},
        taskRunRef=_resource('TaskRun', 'run-1', '2'),
        planRef=_resource('PlanRevision', 'plan-1'),
        planContentHash=plan_hash,
        sourceSelectionRef={'resourceType': 'SourceSelectionRevision',
                            'resourceId': 'source-selection-1', 'revision': 1,
                            'contentHash': 'sha256:' + 'a' * 64},
        packet=_packet(), proposedBy='analyst-owner',
        proposedAt=NOW + timedelta(seconds=1),
    ))


@pytest.mark.parametrize('scope,actor', [
    (TenantScope('dev-org', 'dev-project'), 'analyst-owner'),
    (SCOPE, 'other-actor'),
])
def test_proposal_scope_or_actor_drift_never_calls_storage(scope, actor):
    class Never:
        def execute(self, *_args):
            raise AssertionError('storage touched before identity preflight')
    with pytest.raises((ValueError, PermissionError)):
        D01SourceSelectionStore().propose(
            HostTransaction(Never()), scope, _proposal(),
            key='proposal-key', actor=actor)


def test_proposal_uses_original_plan_and_independent_row_readback(monkeypatch):
    timeline = _timeline()
    monkeypatch.setattr('aos_api.ecommerce_analyst_d01_source_selection_store.AipTaskStore.timeline',
                        lambda _self, _scope, _run_id: timeline)
    proposal = _proposal(timeline.plan.content_hash)
    payload = proposal.model_dump(mode='json', by_alias=True)
    content_hash = canonical_hash(payload)
    request_hash = canonical_hash({'key': 'proposal-key', 'proposal': payload})
    receipt = {'resourceType':'D01SourceSelectionProposal',
               'resourceId':proposal.selection_id,'revision':1,
               'contentHash':'sha256:'+content_hash,
               'receiptId':'d01-proposal:'+proposal.selection_id}
    calls = []
    class Connection:
        def execute(self, sql, params):
            calls.append(sql)
            if 'set_config' in sql:
                return None
            if 'source_propose_a0v_107' in sql:
                return SimpleNamespace(fetchone=lambda: {'receipt': receipt})
            return SimpleNamespace(fetchone=lambda: {
                'payload': payload, 'content_hash': content_hash,
                'request_hash': request_hash, 'proposal_key': 'proposal-key'})
    result = D01SourceSelectionStore().propose(
        HostTransaction(Connection()), SCOPE, proposal,
        key='proposal-key', actor='analyst-owner')
    assert result == receipt and len(calls) == 3
    timeline.plan.steps[0].input_refs = []
    with pytest.raises(ValueError, match='approved D01 proposal lineage'):
        D01SourceSelectionStore().propose(
            HostTransaction(Connection()), SCOPE, proposal,
            key='proposal-key', actor='analyst-owner')
    assert len(calls) == 3


def test_checker_and_revoker_reuse_one_verified_proposal_without_commit():
    proposal = _proposal()
    payload = proposal.model_dump(mode='json', by_alias=True)
    content_hash = canonical_hash(payload)
    proposal_key = 'proposal-key'
    proposal_row = {
        'payload': payload, 'content_hash': content_hash,
        'proposal_key': proposal_key,
        'request_hash': canonical_hash({'key': proposal_key, 'proposal': payload}),
    }
    approved_at = proposal.proposed_at + timedelta(seconds=1)
    revoked_at = approved_at + timedelta(seconds=1)
    approval_receipt = {'resourceType':'D01SourceSelectionApproval',
                        'resourceId':proposal.selection_id,
                        'receiptId':'d01-approval:'+proposal.selection_id}
    revocation_receipt = {'resourceType':'D01SourceSelectionRevocation',
                          'resourceId':proposal.selection_id,
                          'receiptId':'d01-revocation:'+proposal.selection_id}
    calls = []
    class Connection:
        def execute(self, sql, params):
            calls.append(sql)
            if 'set_config' in sql:
                return None
            if 'source_propose' in sql:
                raise AssertionError('approval must not resubmit the proposal')
            if 'FROM public.ecommerce_d01_source_proposal' in sql:
                return SimpleNamespace(fetchone=lambda: proposal_row)
            if 'source_approve_a0v_107' in sql:
                return SimpleNamespace(fetchone=lambda: {'receipt':approval_receipt})
            if 'FROM public.ecommerce_d01_source_approval' in sql:
                return SimpleNamespace(fetchone=lambda: {
                    'approval_key':'approval-key',
                    'request_hash':canonical_hash({
                        'selectionId':proposal.selection_id,'key':'approval-key',
                        'checker':'reviewer','proposalHash':content_hash,
                        'approvedAt':approved_at.isoformat()}),
                    'proposal_hash':content_hash,'checker':'reviewer',
                    'approved_at':approved_at,'receipt_ref':approval_receipt})
            if 'source_revoke_a0v_107' in sql:
                return SimpleNamespace(fetchone=lambda: {'receipt':revocation_receipt})
            return SimpleNamespace(fetchone=lambda: {
                'revocation_key':'revoke-key',
                'request_hash':canonical_hash({
                    'selectionId':proposal.selection_id,'key':'revoke-key',
                    'actor':'reviewer','reason':'withdrawn',
                    'revokedAt':revoked_at.isoformat()}),
                'actor':'reviewer','reason':'withdrawn',
                'revoked_at':revoked_at,'receipt_ref':revocation_receipt})
    store = D01SourceSelectionStore()
    transaction = HostTransaction(Connection())
    with pytest.raises(PermissionError, match='maker cannot approve'):
        store.approve(transaction, SCOPE, proposal.selection_id,
                      key='approval-key', checker='analyst-owner',
                      approved_at=approved_at)
    assert not any('source_approve_a0v_107' in query for query in calls)
    assert store.approve(transaction, SCOPE, proposal.selection_id,
                         key='approval-key', checker='reviewer',
                         approved_at=approved_at) == approval_receipt
    assert store.revoke(transaction, SCOPE, proposal.selection_id,
                        key='revoke-key', actor='reviewer', reason='withdrawn',
                        revoked_at=revoked_at) == revocation_receipt


@pytest.mark.parametrize('approved,revoked', [(False, False), (True, True)])
def test_read_current_rejects_missing_approval_or_revoked_decision(monkeypatch,
                                                                    approved, revoked):
    timeline = _timeline()
    monkeypatch.setattr('aos_api.ecommerce_analyst_d01_source_selection_store.AipTaskStore.timeline',
                        lambda _self, _scope, _run_id: timeline)
    proposal = _proposal(timeline.plan.content_hash)
    payload = proposal.model_dump(mode='json', by_alias=True)
    row = {'selection_id': proposal.selection_id, 'payload': payload,
           'content_hash': canonical_hash(payload), 'proposal_key': 'key',
           'request_hash': canonical_hash({'key': 'key', 'proposal': payload})}
    class Connection:
        def execute(self, sql, _params):
            if 'SELECT selection_id FROM public.ecommerce_d01_source_proposal' in sql:
                return SimpleNamespace(fetchall=lambda: [{'selection_id': proposal.selection_id}])
            if 'FROM public.ecommerce_d01_source_proposal' in sql:
                return SimpleNamespace(fetchone=lambda: row)
            if 'FROM public.ecommerce_d01_source_approval' in sql:
                return SimpleNamespace(fetchone=lambda: None if not approved else {
                    'proposal_hash': row['content_hash'], 'checker': 'reviewer',
                    'approved_at': proposal.proposed_at,
                    'receipt_ref': {'resourceType': 'D01SourceSelectionApproval',
                                    'resourceId': proposal.selection_id,
                                    'receiptId': 'd01-approval:' + proposal.selection_id,
                                    'contentHash': 'sha256:' + 'a' * 64}})
            return SimpleNamespace(fetchone=lambda: {'selection_id': proposal.selection_id}
                                   if revoked else None)
    with pytest.raises(ValueError, match='approved D01 selection unavailable'):
        D01SourceSelectionStore().read_current(
            HostTransaction(Connection()), SCOPE, 'run-1', 'plan-1',
            'analyst-owner', proposal.proposed_at + timedelta(seconds=2))


@pytest.mark.parametrize('drift', [None, 'checker', 'hash', 'plan', 'actor'])
def test_read_current_returns_only_exact_current_approved_packet(monkeypatch, drift):
    timeline = _timeline()
    timeline.plan.approved_by = 'reviewer'
    monkeypatch.setattr('aos_api.ecommerce_analyst_d01_source_selection_store.AipTaskStore.timeline',
                        lambda _self, _scope, _run_id: timeline)
    proposal = _proposal(timeline.plan.content_hash)
    payload = proposal.model_dump(mode='json', by_alias=True)
    row = {'selection_id': proposal.selection_id, 'payload': payload,
           'content_hash': canonical_hash(payload), 'proposal_key': 'key',
           'request_hash': canonical_hash({'key': 'key', 'proposal': payload})}
    approval = {'proposal_hash': row['content_hash'], 'checker': 'reviewer',
                'approved_at': proposal.proposed_at,
                'receipt_ref': {'resourceType': 'D01SourceSelectionApproval',
                                'resourceId': proposal.selection_id,
                                'receiptId': 'd01-approval:' + proposal.selection_id,
                                'contentHash': 'sha256:' + 'a' * 64}}
    if drift == 'checker':
        approval['checker'] = 'analyst-owner'
    if drift == 'hash':
        row['content_hash'] = 'b' * 64
    if drift == 'plan':
        timeline.plan.content_hash = 'b' * 64
    class Connection:
        def execute(self, sql, _params):
            if 'SELECT selection_id FROM public.ecommerce_d01_source_proposal' in sql:
                return SimpleNamespace(fetchall=lambda: [{'selection_id': proposal.selection_id}])
            if 'FROM public.ecommerce_d01_source_proposal' in sql:
                return SimpleNamespace(fetchone=lambda: row)
            if 'FROM public.ecommerce_d01_source_approval' in sql:
                return SimpleNamespace(fetchone=lambda: approval)
            return SimpleNamespace(fetchone=lambda: None)
    read = lambda: D01SourceSelectionStore().read_current(
        HostTransaction(Connection()), SCOPE, 'run-1', 'plan-1',
        'other-actor' if drift == 'actor' else 'analyst-owner',
        proposal.proposed_at + timedelta(seconds=2))
    if drift:
        with pytest.raises(ValueError):
            read()
    else:
        assert read() == (proposal.packet, approval['receipt_ref'])
