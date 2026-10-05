"""Full Source terms need their own independent review, without granting capacity."""
from datetime import UTC,datetime
from uuid import uuid4

import pytest

from tests.aip.test_provider_capacity_action_pg import drafted
from tests.aip.test_provider_capacity_request_pg import original_inputs,SCOPE


@pytest.fixture
def source_inputs(drafted):
    from aos_api.aip_provider_capacity_action import decide_provider_capacity_request
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api.aip_provider_capacity_source_contracts import (
        ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate,ProviderCapacitySourceCandidate)
    maker,checker,_,_,request,saved,proposal,decision=drafted
    approved=decide_provider_capacity_request(checker,proposal.proposal.id,'old-approval-'+uuid4().hex,decision)
    event=approved.approvals[0]
    assert event.proposal_version==1 and approved.proposal.version==2
    store=ProviderCapacityCandidateStore()
    account=ProviderPhysicalAccountCandidate.model_validate(dict(schemaVersion=1,
        tenant=request.tenant.model_dump(by_alias=True),physicalAccountId=request.physical_account_id,
        supplierId='test-only-supplier',supplierAccountFingerprint='f'*64,
        providerRefs=[request.provider_ref.model_dump(by_alias=True)],
        evidenceRef=request.basis_evidence_ref.model_dump(by_alias=True)))
    account_row=store.create_account(SCOPE,maker,'source-account-'+uuid4().hex,account)
    account_ref=dict(assetType='ProviderPhysicalAccountCandidateRevision',assetId=account_row['candidate_id'],
        revision=1,contentHash=account_row['content_hash'])
    now=datetime.now(UTC)
    basis=ProviderCapacityBasisCandidate.model_validate(dict(schemaVersion=1,
        tenant=request.tenant.model_dump(by_alias=True),basisKind='owner_allocation',
        physicalAccountRef=account_ref,evidenceRef=request.basis_evidence_ref.model_dump(by_alias=True),
        maxConcurrency=request.requested_max_concurrency,
        tokenLimit=dict(mode='inflight_upper_bound',unit='token',maxTokens=request.requested_max_token_units),
        observedAt=now,validFrom=now,validUntil=event.expires_at))
    basis_row=store.create_basis(SCOPE,maker,'source-basis-'+uuid4().hex,basis)
    candidate=ProviderCapacitySourceCandidate.model_validate(dict(schemaVersion=1,
        tenant=request.tenant.model_dump(by_alias=True),physicalAccountRef=account_ref,
        basisRef=dict(assetType='ProviderCapacityBasisCandidateRevision',assetId=basis_row['candidate_id'],
            revision=1,contentHash=basis_row['content_hash']),
        allocationRequestRef=dict(assetType='ProviderCapacityRequest',assetId=saved['request_id'],
            revision=1,contentHash=saved['request_hash']),
        allocationApprovalRef=dict(assetType='ActionApprovalEvent',assetId=event.id,revision=1,
            contentHash=canonical_hash(event.model_dump(mode='json',by_alias=True))),
        validFrom=now,validUntil=event.expires_at,executionAllowed=False))
    return maker,checker,candidate,approved


def test_actual_candidates_and_old_approval_need_new_source_review(source_inputs):
    from aos_api.aip_action_models import DecideActionProposalRequest
    maker,checker,candidate,_=source_inputs
    # All original inputs have been persisted before testing the missing Source entry.
    from aos_api.aip_provider_capacity_source_action import (
        propose_provider_capacity_source,decide_provider_capacity_source,ProviderCapacitySourceActionBlocked)
    proposal=propose_provider_capacity_source(maker,candidate,'source-review-'+uuid4().hex,candidate.valid_until)
    assert proposal.proposal.policy_snapshot['executionAllowed'] is False
    decision=DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='isolated Source terms review',
        approvalExpiresAt=candidate.valid_until))
    with pytest.raises(ProviderCapacitySourceActionBlocked):
        decide_provider_capacity_source(maker,proposal.proposal.id,'source-self-'+uuid4().hex,decision)
    approved=decide_provider_capacity_source(checker,proposal.proposal.id,'source-check-'+uuid4().hex,decision)
    assert approved.proposal.status.value=='approved'
    assert approved.proposal.policy_snapshot['executionAllowed'] is False
    assert len(approved.approvals)==1


def effects():
    from aos_api.db import connect
    with connect(SCOPE) as conn:
        return {table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
            for table in ('aip_action_proposal','aip_action_approval_event',
                'aip_model_capacity_reservation','aip_model_eval_budget_reservation')}


@pytest.mark.parametrize('fault',['account_hash','basis_hash','approval_hash','request_hash',
    'account_id','concurrency','basis_account','future','expiry','native_kind','non_oidc','canary'])
def test_source_terms_drift_denies_before_proposal(source_inputs,fault):
    from dataclasses import replace
    from datetime import timedelta
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source,ProviderCapacitySourceActionBlocked
    maker,_,candidate,_=source_inputs
    expiry=candidate.valid_until
    fields={'account_hash':'physical_account_ref','basis_hash':'basis_ref',
        'approval_hash':'allocation_approval_ref','request_hash':'allocation_request_ref'}
    if fault in fields:
        field=fields[fault];candidate=candidate.model_copy(update={field:getattr(candidate,field).model_copy(update={'content_hash':'0'*64})})
    elif fault in {'account_id','concurrency','basis_account'}:
        with connect(SCOPE) as conn:
            account=ProviderPhysicalAccountCandidate.model_validate(conn.execute(
                'SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',
                (candidate.physical_account_ref.asset_id,)).fetchone()['request_json']['candidate'])
            basis=ProviderCapacityBasisCandidate.model_validate(conn.execute(
                'SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',
                (candidate.basis_ref.asset_id,)).fetchone()['request_json']['candidate'])
        store=ProviderCapacityCandidateStore()
        if fault in {'account_id','basis_account'}:
            account=account.model_copy(update={'physical_account_id':'different-account-'+uuid4().hex})
            new=store.create_account(SCOPE,maker,'changed-account-'+uuid4().hex,account)
            ref=candidate.physical_account_ref.model_copy(update={'asset_id':new['candidate_id'],'content_hash':new['content_hash']})
            if fault=='account_id':candidate=candidate.model_copy(update={'physical_account_ref':ref})
            basis=basis.model_copy(update={'physical_account_ref':ref})
        else:basis=basis.model_copy(update={'max_concurrency':basis.max_concurrency+1})
        new=store.create_basis(SCOPE,maker,'changed-basis-'+uuid4().hex,basis)
        candidate=candidate.model_copy(update={'basis_ref':candidate.basis_ref.model_copy(update={
            'asset_id':new['candidate_id'],'content_hash':new['content_hash']})})
    elif fault=='future':candidate=candidate.model_copy(update={'valid_from':datetime.now(UTC)+timedelta(seconds=30)})
    elif fault=='expiry':expiry+=timedelta(seconds=1)
    elif fault=='native_kind':candidate=candidate.model_copy(update={'physical_account_ref':candidate.physical_account_ref.model_copy(update={'asset_type':'ProviderPhysicalAccountRevision'})})
    elif fault=='non_oidc':maker=replace(maker,token_kind='opaque')
    else:maker=replace(maker,org_id='dev-org')
    before=effects()
    with pytest.raises(ProviderCapacitySourceActionBlocked):
        propose_provider_capacity_source(maker,candidate,'deny-source-'+uuid4().hex,expiry)
    assert effects()==before


@pytest.fixture
def source_proposal(source_inputs):
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source
    from aos_api.aip_action_models import DecideActionProposalRequest
    maker,checker,candidate,old=source_inputs
    proposal=propose_provider_capacity_source(maker,candidate,'source-draft-'+uuid4().hex,candidate.valid_until)
    decision=DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='isolated Source terms',
        approvalExpiresAt=candidate.valid_until))
    return maker,checker,candidate,old,proposal,decision


@pytest.mark.parametrize('fault',['maker_role','checker_role','old_checker_role','provider_head','revoke',
    'metadata','old_second_approval','old_later_rejection'])
def test_actual_dependency_drift_denies_new_approval(source_proposal,https_signer,fault):
    from aos_api.db import connect
    from aos_api.auth import resolve_principal
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_provider_capacity_action import decide_provider_capacity_request
    from aos_api.aip_provider_capacity_source_action import decide_provider_capacity_source,ProviderCapacitySourceActionBlocked,ACTION_ID
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    maker,checker,candidate,old,proposal,decision=source_proposal
    restore=None
    if fault in {'maker_role','checker_role','old_checker_role'}:
        # Use a distinct new checker for checker-only drift; the old checker remains current.
        if fault=='checker_role':
            subject='new-source-checker-'+uuid4().hex
            with isolated_owner() as conn:conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,subject))
            checker=resolve_principal(token=https_signer[0](subject),header_org=SCOPE.org_id,header_project=SCOPE.project_id)
        subject=maker.subject if fault=='maker_role' else checker.subject
        with isolated_owner() as conn:conn.execute("UPDATE meta_membership SET role='admin' WHERE org_id=%s AND project_id=%s AND subject=%s",(*SCOPE.key,subject))
    elif fault in {'provider_head','revoke'}:
        with connect(SCOPE) as conn:
            account=ProviderPhysicalAccountCandidate.model_validate(conn.execute('SELECT request_json FROM aip_provider_capacity_candidate WHERE candidate_id=%s',
                (candidate.physical_account_ref.asset_id,)).fetchone()['request_json']['candidate'])
        if fault=='provider_head':
            with isolated_owner() as conn:conn.execute('UPDATE aip_provider_instance_head SET current_revision=current_revision+1 WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',
                (*SCOPE.key,account.provider_refs[0].asset_id))
        else:AipProductionContractStore().revoke_evidence_bundle(SCOPE,ACTOR,account.evidence_ref.asset_id,'source-revoke-'+uuid4().hex,
            RevokeEvidenceBundleRequest(expectedRevision=account.evidence_ref.revision,expectedContentHash=account.evidence_ref.content_hash,reason='isolated Source withdrawal'))
    elif fault=='metadata':
        with isolated_owner() as conn:
            restore=conn.execute('SELECT name FROM meta_action_type WHERE id=%s',(ACTION_ID,)).fetchone()['name']
            conn.execute("UPDATE meta_action_type SET name='drift' WHERE id=%s",(ACTION_ID,))
    else:
        subject='later-checker-'+uuid4().hex
        with isolated_owner() as conn:conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,subject))
        later=resolve_principal(token=https_signer[0](subject),header_org=SCOPE.org_id,header_project=SCOPE.project_id)
        next_decision=DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=old.proposal.version,
            expectedProposalHash=old.proposal.proposal_hash,decision='approved' if fault=='old_second_approval' else 'rejected',
            reason='isolated later review',approvalExpiresAt=candidate.valid_until))
        decide_provider_capacity_request(later,old.proposal.id,'old-later-'+uuid4().hex,next_decision)
    before=effects()
    try:
        with pytest.raises(ProviderCapacitySourceActionBlocked):
            decide_provider_capacity_source(checker,proposal.proposal.id,'new-denied-'+uuid4().hex,decision)
        assert effects()==before
    finally:
        if restore is not None:
            with isolated_owner() as conn:conn.execute('UPDATE meta_action_type SET name=%s WHERE id=%s',(restore,ACTION_ID))


def test_source_checker_replay_is_exact_and_never_reserves(source_proposal,https_signer):
    from aos_api.auth import resolve_principal
    from aos_api.aip_provider_capacity_source_action import decide_provider_capacity_source,propose_provider_capacity_source,ProviderCapacitySourceActionBlocked
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker,checker,candidate,_,proposal,decision=source_proposal
    before=effects();key='source-idempotent-'+uuid4().hex
    first=decide_provider_capacity_source(checker,proposal.proposal.id,key,decision)
    after=effects()
    assert decide_provider_capacity_source(checker,proposal.proposal.id,key,decision).approvals==first.approvals
    assert effects()==after
    assert after['aip_action_approval_event']==before['aip_action_approval_event']+1
    for table in ('aip_model_capacity_reservation','aip_model_eval_budget_reservation'):assert before[table]==after[table]
    assert first.approvals[0].expires_at<=candidate.valid_until
    subject='different-source-checker-'+uuid4().hex
    with isolated_owner() as conn:conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,subject))
    other=resolve_principal(token=https_signer[0](subject),header_org=SCOPE.org_id,header_project=SCOPE.project_id)
    with pytest.raises(AipActionTransitionBlocked,match='CHECKER_REPLAY'):
        decide_provider_capacity_source(other,proposal.proposal.id,key,decision)
    with pytest.raises(ProviderCapacitySourceActionBlocked):
        propose_provider_capacity_source(other,candidate,'nonmaker-'+uuid4().hex,candidate.valid_until)
    assert effects()==after


def test_generic_source_guard_cannot_replace_protected_entry():
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.aip_provider_capacity_source_action import ACTION_ID
    for checker in (False,True):
        with pytest.raises(AipActionTransitionBlocked,match='SOURCE_GUARD_REQUIRED'):
            AipActionStore()._internal_proposal_guard(None,SCOPE,'actor',
                dict(action_type_id=ACTION_ID,action_type_snapshot=dict(id=ACTION_ID)),checker=checker)


def test_source_approval_cannot_acquire_original_execution_lease(source_proposal):
    from aos_api.db import connect
    from aos_api.auth import Principal
    from aos_api.aip_action_models import AcquireExecutionLeaseRequest
    from aos_api.aip_action_adapters import ActionAdapterRegistry
    from aos_api.aip_action_execution import AipActionExecutionService
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.aip_provider_capacity_source_action import decide_provider_capacity_source
    _,checker,_,_,proposal,decision=source_proposal
    approved=decide_provider_capacity_source(checker,proposal.proposal.id,'no-source-start-'+uuid4().hex,decision)
    with connect(SCOPE) as conn:before=conn.execute('SELECT count(*) AS n FROM aip_action_execution_lease').fetchone()['n']
    executor=Principal(subject='source-execution-probe-'+uuid4().hex,org_id=SCOPE.org_id,project_id=SCOPE.project_id,
        roles=['executor'],token_kind='oidc')
    with pytest.raises(AipActionTransitionBlocked,match='execution is disabled'):
        AipActionExecutionService(AipActionStore(),ActionAdapterRegistry()).acquire_lease(executor,proposal.proposal.id,
            'forbidden-source-lease-'+uuid4().hex,AcquireExecutionLeaseRequest.model_validate(dict(
                expectedProposalVersion=approved.proposal.version,expectedProposalHash=approved.proposal.proposal_hash)))
    with connect(SCOPE) as conn:assert conn.execute('SELECT count(*) AS n FROM aip_action_execution_lease').fetchone()['n']==before


def test_source_metadata_is_reserved_and_canary_has_no_review_rows(source_inputs):
    import psycopg
    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_provider_capacity_source_action import ACTION_ID
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect(SCOPE) as conn:conn.execute("UPDATE meta_action_type SET name='client-overwrite' WHERE id=%s",(ACTION_ID,))
    with connect(TenantScope('dev-org','dev-project')) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_action_proposal WHERE action_type_id=%s',(ACTION_ID,)).fetchone()['n']==0


def test_source_review_naturally_expires_without_new_effect(source_inputs):
    import time
    from datetime import timedelta
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source,decide_provider_capacity_source,ProviderCapacitySourceActionBlocked
    maker,checker,candidate,_=source_inputs
    candidate=candidate.model_copy(update={'valid_until':datetime.now(UTC)+timedelta(seconds=2)})
    proposal=propose_provider_capacity_source(maker,candidate,'expiring-source-'+uuid4().hex,candidate.valid_until)
    decision=DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='must reject expired Source'))
    before=effects()
    time.sleep(2.1)
    with pytest.raises(ProviderCapacitySourceActionBlocked,match='WINDOW_DRIFTED'):
        decide_provider_capacity_source(checker,proposal.proposal.id,'expired-source-'+uuid4().hex,decision)
    assert effects()==before
