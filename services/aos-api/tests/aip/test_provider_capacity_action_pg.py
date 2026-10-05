"""Original requests need independent approval; approvals cannot execute capacity."""
from uuid import uuid4

import pytest

from tests.aip.test_provider_capacity_request_pg import original_inputs, exact_request, SCOPE


def test_original_capacity_application_independent_checker_without_execution(original_inputs, https_signer):
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore
    from aos_api.auth import resolve_principal
    from aos_api.aip_action_models import DecideActionProposalRequest
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker, _, _ = original_inputs
    request = exact_request(original_inputs)
    saved = ProviderCapacityRequestStore().create(SCOPE, maker, 'capacity-action-'+uuid4().hex, request)
    # The real original request must exist before the new Action entry is tested.
    from aos_api.aip_provider_capacity_action import (
        ProviderCapacityActionBlocked, propose_provider_capacity_request,
        decide_provider_capacity_request,
    )
    proposal = propose_provider_capacity_request(maker, saved['request_id'],
        'capacity-proposal-'+uuid4().hex, request.proposal_expires_at)
    assert proposal.proposal.policy_snapshot['executionAllowed'] is False
    decision = DecideActionProposalRequest.model_validate(dict(
        expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash,
        decision='approved', reason='isolated Owner allocation terms review',
        approvalExpiresAt=request.proposal_expires_at))
    with pytest.raises(ProviderCapacityActionBlocked, match='INDEPENDENT_CHECKER'):
        decide_provider_capacity_request(maker, proposal.proposal.id, 'self-'+uuid4().hex, decision)
    subject = 'capacity-checker-'+uuid4().hex
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')", (*SCOPE.key,subject))
    checker = resolve_principal(token=https_signer[0](subject), header_org=SCOPE.org_id, header_project=SCOPE.project_id)
    approved = decide_provider_capacity_request(checker, proposal.proposal.id, 'approve-'+uuid4().hex, decision)
    assert approved.proposal.status.value == 'approved'
    assert approved.proposal.policy_snapshot['executionAllowed'] is False
    assert len(approved.approvals) == 1


@pytest.fixture
def drafted(original_inputs, https_signer):
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore
    from aos_api.aip_provider_capacity_action import propose_provider_capacity_request
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.auth import resolve_principal
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker, provider, source = original_inputs
    request = exact_request(original_inputs)
    saved = ProviderCapacityRequestStore().create(SCOPE,maker,'draft-'+uuid4().hex,request)
    proposal = propose_provider_capacity_request(maker,saved['request_id'],'proposal-'+uuid4().hex,request.proposal_expires_at)
    subject='checker-'+uuid4().hex
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,subject))
    checker=resolve_principal(token=https_signer[0](subject),header_org=SCOPE.org_id,header_project=SCOPE.project_id)
    decision=DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='isolated exact terms',
        approvalExpiresAt=request.proposal_expires_at))
    return maker,checker,provider,source,request,saved,proposal,decision


def effects():
    from aos_api.db import connect
    with connect(SCOPE) as conn:
        return {table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                for table in ('aip_action_approval_event','aip_model_capacity_reservation','aip_model_eval_budget_reservation')}


@pytest.mark.parametrize('fault',['checker_role','maker_role','provider_head','basis_revoke','metadata','hash','scope'])
def test_actual_drift_denies_approval_without_effect(drafted,fault):
    from datetime import timedelta
    from aos_api.db import connect
    from aos_api.aip_action_store import AipActionStoreError
    from aos_api.aip_provider_capacity_action import decide_provider_capacity_request, ACTION_ID
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker,checker,provider,source,request,saved,proposal,decision=drafted
    before=effects()
    if fault in {'checker_role','maker_role'}:
        subject=checker.subject if fault=='checker_role' else maker.subject
        with isolated_owner() as conn:
            conn.execute("UPDATE meta_membership SET role='admin' WHERE org_id=%s AND project_id=%s AND subject=%s",(*SCOPE.key,subject))
    elif fault=='provider_head':
        with isolated_owner() as conn:
            conn.execute('UPDATE aip_provider_instance_head SET current_revision=current_revision+1 WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',(*SCOPE.key,provider.provider_instance_id))
    elif fault=='basis_revoke':
        AipProductionContractStore().revoke_evidence_bundle(SCOPE,ACTOR,source.bundle_id,'capacity-revoke-'+uuid4().hex,
            RevokeEvidenceBundleRequest(expectedRevision=source.revision,expectedContentHash=source.content_hash,reason='isolated basis withdrawal'))
    elif fault=='metadata':
        with isolated_owner() as conn:
            old=conn.execute('SELECT name FROM meta_action_type WHERE id=%s',(ACTION_ID,)).fetchone()['name']
            conn.execute('UPDATE meta_action_type SET name=%s WHERE id=%s',('drift',ACTION_ID))
    elif fault=='hash': decision=decision.model_copy(update={'expected_proposal_hash':'0'*64})
    else:
        from dataclasses import replace
        checker=replace(checker,org_id='dev-org')
    try:
        with pytest.raises(AipActionStoreError):
            decide_provider_capacity_request(checker,proposal.proposal.id,'denied-'+uuid4().hex,decision)
        assert effects()==before
        with connect(SCOPE) as conn:
            row=conn.execute('SELECT status FROM aip_action_proposal WHERE proposal_id=%s',(proposal.proposal.id,)).fetchone()
            assert row['status']=='drafted'
    finally:
        if fault=='metadata':
            with isolated_owner() as conn:conn.execute('UPDATE meta_action_type SET name=%s WHERE id=%s',(old,ACTION_ID))


def test_approval_replay_and_nonmaker_rejected(drafted):
    from aos_api.aip_provider_capacity_action import propose_provider_capacity_request,decide_provider_capacity_request,ProviderCapacityActionBlocked
    maker,checker,_,_,request,saved,proposal,decision=drafted
    before=effects()
    with pytest.raises(ProviderCapacityActionBlocked):
        propose_provider_capacity_request(checker,saved['request_id'],'wrong-maker-'+uuid4().hex,request.proposal_expires_at)
    assert effects()==before
    key='actual-approve-'+uuid4().hex
    first=decide_provider_capacity_request(checker,proposal.proposal.id,key,decision)
    after=effects()
    again=decide_provider_capacity_request(checker,proposal.proposal.id,key,decision)
    assert again.proposal.id==first.proposal.id
    assert effects()==after
    assert after['aip_action_approval_event']==before['aip_action_approval_event']+1
    assert after['aip_model_capacity_reservation']==before['aip_model_capacity_reservation']
    assert after['aip_model_eval_budget_reservation']==before['aip_model_eval_budget_reservation']


def test_generic_guard_cannot_replace_provider_approval():
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.aip_provider_capacity_action import ACTION_ID
    for checker in (False,True):
        with pytest.raises(AipActionTransitionBlocked,match='PROVIDER_CAPACITY_ACTION_GUARD_REQUIRED'):
            AipActionStore()._internal_proposal_guard(None,SCOPE,'actor',
                {'action_type_id':ACTION_ID,'action_type_snapshot':{'id':ACTION_ID}},checker=checker)


@pytest.mark.parametrize('field',['policy_snapshot','action_binding_hash','approval_policy_hash'])
def test_guard_rejects_actual_row_with_mutated_binding(drafted,field):
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_action import ProviderCapacityActionGuard,ProviderCapacityActionBlocked
    _,checker,_,_,_,_,proposal,_=drafted
    with connect(SCOPE) as conn:
        row=dict(conn.execute('SELECT * FROM aip_action_proposal WHERE proposal_id=%s',(proposal.proposal.id,)).fetchone())
        row[field]={'executionAllowed':True} if field=='policy_snapshot' else '0'*64
        with pytest.raises(ProviderCapacityActionBlocked):
            ProviderCapacityActionGuard().check_proposal(conn,SCOPE,checker.subject,row,checker=True)


def test_original_approval_expiry_is_bounded_by_request(drafted):
    from datetime import timedelta
    from aos_api.aip_provider_capacity_action import decide_provider_capacity_request
    _,checker,_,_,request,_,proposal,decision=drafted
    decision=decision.model_copy(update={'approval_expires_at':request.proposal_expires_at+timedelta(minutes=1)})
    approved=decide_provider_capacity_request(checker,proposal.proposal.id,'bounded-'+uuid4().hex,decision)
    assert approved.approvals[0].expires_at <= request.proposal_expires_at


def test_original_approval_replay_cannot_change_checker(drafted, https_signer):
    from aos_api.auth import resolve_principal
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_provider_capacity_action import decide_provider_capacity_request
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    _,checker,_,_,_,_,proposal,decision=drafted
    key='checker-bound-'+uuid4().hex
    decide_provider_capacity_request(checker,proposal.proposal.id,key,decision)
    other='other-checker-'+uuid4().hex
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,other))
    principal=resolve_principal(token=https_signer[0](other),header_org=SCOPE.org_id,header_project=SCOPE.project_id)
    before=effects()
    with pytest.raises(AipActionTransitionBlocked,match='CHECKER_REPLAY'):
        decide_provider_capacity_request(principal,proposal.proposal.id,key,decision)
    assert effects()==before


@pytest.mark.parametrize('fault',['long_proposal','naive_proposal','non_oidc'])
def test_proposal_input_window_and_identity_rejected(drafted,fault):
    from dataclasses import replace
    from datetime import timedelta
    from aos_api.aip_provider_capacity_action import propose_provider_capacity_request,ProviderCapacityActionBlocked
    maker,_,_,_,request,saved,_,_=drafted
    expiry=request.proposal_expires_at
    if fault=='long_proposal': expiry+=timedelta(minutes=1)
    elif fault=='naive_proposal': expiry=expiry.replace(tzinfo=None)
    else: maker=replace(maker,token_kind='dev')
    before=effects()
    with pytest.raises(ProviderCapacityActionBlocked):
        propose_provider_capacity_request(maker,saved['request_id'],'input-'+uuid4().hex,expiry)
    assert effects()==before


def test_approved_allocation_cannot_acquire_original_execution_lease(drafted):
    from aos_api.auth import Principal
    from aos_api.db import connect
    from aos_api.aip_action_models import AcquireExecutionLeaseRequest
    from aos_api.aip_action_adapters import ActionAdapterRegistry
    from aos_api.aip_action_execution import AipActionExecutionService
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.aip_provider_capacity_action import decide_provider_capacity_request
    _,checker,_,_,_,_,proposal,decision=drafted
    approved=decide_provider_capacity_request(checker,proposal.proposal.id,'no-start-'+uuid4().hex,decision)
    with connect(SCOPE) as conn:
        before=conn.execute('SELECT count(*) AS n FROM aip_action_execution_lease').fetchone()['n']
    executor=Principal(subject='execution-probe-'+uuid4().hex,org_id=SCOPE.org_id,project_id=SCOPE.project_id,
        roles=['executor'],token_kind='oidc')
    with pytest.raises(AipActionTransitionBlocked,match='execution is disabled'):
        AipActionExecutionService(AipActionStore(),ActionAdapterRegistry()).acquire_lease(executor,proposal.proposal.id,
            'forbidden-lease-'+uuid4().hex,AcquireExecutionLeaseRequest.model_validate(dict(
                expectedProposalVersion=approved.proposal.version,expectedProposalHash=approved.proposal.proposal_hash)))
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_action_execution_lease').fetchone()['n']==before


def test_original_request_naturally_expires_before_approval(original_inputs, https_signer):
    import time
    from datetime import UTC,datetime,timedelta
    from aos_api.auth import resolve_principal
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore
    from aos_api.aip_provider_capacity_action import propose_provider_capacity_request,decide_provider_capacity_request,ProviderCapacityActionBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker,_,_=original_inputs
    subject='expiry-checker-'+uuid4().hex
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,subject))
    checker=resolve_principal(token=https_signer[0](subject),header_org=SCOPE.org_id,header_project=SCOPE.project_id)
    request=exact_request(original_inputs).model_copy(update={'proposal_expires_at':datetime.now(UTC)+timedelta(seconds=2)})
    saved=ProviderCapacityRequestStore().create(SCOPE,maker,'expires-'+uuid4().hex,request)
    proposal=propose_provider_capacity_request(maker,saved['request_id'],'expiring-'+uuid4().hex,request.proposal_expires_at)
    decision=DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='must be denied after expiry'))
    before=effects()
    time.sleep(2.1)
    with pytest.raises(ProviderCapacityActionBlocked,match='APPLICATION_NOT_CURRENT'):
        decide_provider_capacity_request(checker,proposal.proposal.id,'expired-'+uuid4().hex,decision)
    assert effects()==before
