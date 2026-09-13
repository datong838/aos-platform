from uuid import uuid4
import pytest
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked, canonical_hash
from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ApprovalDecision
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS


def material():
    snapshot = dict(id='ecommerce_growth_cutover', name='internal cutover', objectType='BundleInstallation', parameters=[], requiredMarkings=[], submissionCriteria=[])
    snapshot['revisionHash'] = canonical_hash(snapshot)
    ref = lambda kind: dict(resourceType=kind, resourceId=str(uuid4()), revision=1, contentHash='sha256:'+'a'*64)
    payload = dict(cutoverGroupId=str(uuid4()), expectedGroupRevision=1, targetInstallationId=str(uuid4()),
        targetGeneration=str(uuid4()), targetExecutionEpoch=3, targetRuntimeRevision=4,
        operationIds=sorted(ECOMMERCE_GROWTH_OPERATIONS), policyRef=ref('Policy'), registrationReceiptRef=ref('FirstDispatchRegistrationReceipt'))
    return snapshot, payload


def test_internal_proposal_owner_binds_and_rechecks_before_replay(monkeypatch):
    from aos_api.ecommerce_growth_cutover_action_binding import internal_cutover_binding_hash
    snapshot, payload = material()
    scope = TenantScope('org-org', 'dev-project')
    calls = []
    revoked = set()
    def gate(**kwargs):
        calls.append((kwargs['actor'], kwargs['operation']))
        if kwargs['actor'] in revoked:
            raise ValueError('current permission denied')
        return internal_cutover_binding_hash(scope=scope, action_snapshot=kwargs['action_snapshot'], payload=kwargs['payload']), ('asset-install-approver',)
    monkeypatch.setattr('aos_api.ecommerce_growth_cutover_proposal_gate.require_internal_cutover_binding', gate)
    body = CreateActionProposalRequest(actionTypeId=snapshot['id'], payload=payload, purpose='internal cutover')
    risk = classify_action_risk(snapshot['id'], snapshot, payload, None)
    store = AipActionStore()
    key = 'cutover-proposal-' + uuid4().hex
    result = store.create_proposal(scope, 'maker', key, body, snapshot, risk)
    expected = internal_cutover_binding_hash(scope=scope, action_snapshot=snapshot, payload=payload)
    assert result.proposal.action_binding_hash == expected
    assert store.create_proposal(scope, 'maker', key, body, snapshot, risk).proposal.id == result.proposal.id
    revoked.add('maker')
    with pytest.raises(AipActionTransitionBlocked):
        store.create_proposal(scope, 'maker', key, body, snapshot, risk)
    revoked.clear()
    decision = DecideActionProposalRequest(decision=ApprovalDecision.APPROVED,
        expectedProposalVersion=result.proposal.version, expectedProposalHash=result.proposal.proposal_hash)
    with pytest.raises(AipActionTransitionBlocked):
        store.decide(scope, 'maker', result.proposal.id, uuid4().hex, decision)
    approval_key = uuid4().hex
    approved = store.decide(scope, 'checker', result.proposal.id, approval_key, decision, actor_roles=('owner',))
    assert approved.proposal.status.value == 'approved'
    assert approved.approvals[0].eligibility_snapshot_hash == canonical_hash({
        'tenant': {'orgId': scope.org_id, 'projectId': scope.project_id},
        'actorId': 'checker', 'roles': ['asset-install-approver'], 'slotId': 'checker.1',
        'approvalPolicyHash': approved.proposal.approval_policy_hash,
    })
    revoked.add('checker')
    with pytest.raises(AipActionTransitionBlocked):
        store.decide(scope, 'checker', result.proposal.id, approval_key, decision, actor_roles=('admin',))
    assert ('maker', 'bundle_installations.apply') in calls
    assert ('checker', 'bundle_installations.approve') in calls


@pytest.mark.parametrize('case', ['draft-replay', 'submit-replay', 'old-unbound', 'business-task', 'risk-drift'])
def test_internal_owner_rejects_stale_or_mixed_paths(monkeypatch, case):
    from aos_api.ecommerce_growth_cutover_action_binding import internal_cutover_binding_hash
    from aos_api.aip_action_models import CreateActionDraftRequest, SubmitActionDraftRequest
    from aos_api.aip_contracts import ActionRiskLevel
    snapshot, payload = material()
    scope = TenantScope('org-org', 'dev-project')
    denied = []
    def gate(**kwargs):
        if denied:
            raise ValueError('current permission denied')
        return internal_cutover_binding_hash(scope=scope, action_snapshot=kwargs['action_snapshot'], payload=kwargs['payload']), ('admin',)
    monkeypatch.setattr('aos_api.ecommerce_growth_cutover_proposal_gate.require_internal_cutover_binding', gate)
    body = CreateActionDraftRequest(actionTypeId=snapshot['id'], payload=payload, purpose='internal cutover')
    risk = classify_action_risk(snapshot['id'], snapshot, payload, None)
    store = AipActionStore()
    key = uuid4().hex
    if case == 'business-task':
        body = body.model_copy(update={'task_id': 'not-a-business-task'})
        with pytest.raises(AipActionTransitionBlocked, match='BUSINESS_BINDING'):
            store.create_proposal(scope, 'maker', key, body, snapshot, risk)
    elif case == 'risk-drift':
        low = classify_action_risk('ordinary', {}, {}, ActionRiskLevel.R0)
        with pytest.raises(AipActionTransitionBlocked, match='RISK_OR_ACTION'):
            store.create_proposal(scope, 'maker', key, body, snapshot, low)
    elif case == 'old-unbound':
        with monkeypatch.context() as patch:
            patch.setattr(store, '_internal_request_binding', lambda *a: None)
            old = store.create_proposal(scope, 'maker', key, body, snapshot, risk)
        assert old.proposal.action_binding_hash is None
        with pytest.raises(AipActionTransitionBlocked, match='BINDING_DRIFTED'):
            store.create_proposal(scope, 'maker', key, body, snapshot, risk)
    else:
        draft = store.create_action_draft(scope, 'maker', key, body, snapshot, risk)
        if case == 'draft-replay':
            denied.append(True)
            with pytest.raises(AipActionTransitionBlocked):
                store.create_action_draft(scope, 'maker', key, body, snapshot, risk)
        else:
            submit = SubmitActionDraftRequest(expectedRevision=draft.revision, expectedContentHash=draft.content_hash)
            submit_key = uuid4().hex
            result = store.submit_action_draft(scope, 'maker', draft.draft_id, submit_key, submit)
            assert result.proposal.action_binding_hash is not None
            denied.append(True)
            with pytest.raises(AipActionTransitionBlocked):
                store.submit_action_draft(scope, 'maker', draft.draft_id, submit_key, submit)
