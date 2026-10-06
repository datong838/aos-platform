"""Original inputs can produce claims only, not verified physical authority."""
from uuid import uuid4
from datetime import UTC,datetime,timedelta

import pytest

from tests.aip.test_provider_capacity_request_pg import original_inputs,SCOPE


def test_original_owner_provider_and_evidence_produce_nonexecuting_account_candidate(original_inputs):
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate
    maker,provider,evidence=original_inputs
    candidate=ProviderPhysicalAccountCandidate.model_validate(dict(schemaVersion=1,
        tenant=dict(orgId=SCOPE.org_id,projectId=SCOPE.project_id),physicalAccountId='draft-account-'+uuid4().hex,
        supplierId='test-only-supplier-'+uuid4().hex,supplierAccountFingerprint='f'*64,
        providerRefs=[dict(assetType='ProviderInstanceRevision',assetId=provider.provider_instance_id,
            revision=provider.revision,contentHash=provider.content_hash)],
        evidenceRef=dict(assetType='EvidenceBundleRevision',assetId=evidence.bundle_id,
            revision=evidence.revision,contentHash=evidence.content_hash)))
    # Formal Provider and original bundle already exist before the missing producer is tested.
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    store=ProviderCapacityCandidateStore();key='source-account-'+uuid4().hex
    saved=store.create_account(SCOPE,maker,key,candidate)
    assert saved['authorization_mode']=='CANDIDATE_ONLY_NO_CAPACITY_NO_START'
    assert saved['basis_verified'] is False and saved['execution_allowed'] is False
    assert saved['request_json']['makerSubject']==maker.subject
    assert store.create_account(SCOPE,maker,key,candidate)==saved


@pytest.fixture
def account_input(original_inputs):
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate
    maker,provider,evidence=original_inputs
    candidate=ProviderPhysicalAccountCandidate.model_validate(dict(schemaVersion=1,
        tenant=dict(orgId=SCOPE.org_id,projectId=SCOPE.project_id),physicalAccountId='draft-account-'+uuid4().hex,
        supplierId='test-only-supplier-'+uuid4().hex,supplierAccountFingerprint='f'*64,
        providerRefs=[dict(assetType='ProviderInstanceRevision',assetId=provider.provider_instance_id,
            revision=provider.revision,contentHash=provider.content_hash)],
        evidenceRef=dict(assetType='EvidenceBundleRevision',assetId=evidence.bundle_id,
            revision=evidence.revision,contentHash=evidence.content_hash)))
    return maker,provider,evidence,candidate


def test_exact_account_basis_candidate_replay_remains_unverified(account_input):
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore,ProviderCapacityCandidateConflict
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityBasisCandidate
    from aos_api.db import connect
    maker,_,_,candidate=account_input;store=ProviderCapacityCandidateStore()
    account=store.create_account(SCOPE,maker,'parent-'+uuid4().hex,candidate)
    now=datetime.now(UTC)
    basis=ProviderCapacityBasisCandidate.model_validate(dict(schemaVersion=1,tenant=candidate.tenant.model_dump(by_alias=True),
        basisKind='owner_allocation',physicalAccountRef=dict(assetType='ProviderPhysicalAccountCandidateRevision',
            assetId=account['candidate_id'],revision=1,contentHash=account['content_hash']),
        evidenceRef=candidate.evidence_ref.model_dump(by_alias=True),maxConcurrency=2,
        tokenLimit=dict(mode='inflight_upper_bound',unit='token',maxTokens=20000),
        observedAt=now,validFrom=now,validUntil=now+timedelta(hours=1)))
    key='basis-'+uuid4().hex
    row=store.create_basis(SCOPE,maker,key,basis)
    assert row['basis_verified'] is False and row['execution_allowed'] is False
    assert store.create_basis(SCOPE,maker,key,basis)==row
    with pytest.raises(ProviderCapacityCandidateConflict):
        store.create_basis(SCOPE,maker,key,basis.model_copy(update={'max_concurrency':3}))
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_provider_capacity_candidate WHERE candidate_id=%s",(row['candidate_id'],)).fetchone()['n']==1


@pytest.mark.parametrize('fault',['owner','provider_hash','evidence_hash','mutated','provider_head','revoke'])
def test_original_candidate_dependencies_reject_without_new_rows(account_input,https_signer,fault):
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore,ProviderCapacityCandidateBlocked
    from aos_api.auth import resolve_principal
    from aos_api.db import connect
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker,provider,evidence,candidate=account_input
    if fault=='owner':maker=resolve_principal(token=https_signer[0]('nonowner-'+uuid4().hex),header_org=SCOPE.org_id,header_project=SCOPE.project_id)
    elif fault=='provider_hash':candidate=candidate.model_copy(update={'provider_refs':[candidate.provider_refs[0].model_copy(update={'content_hash':'0'*64})]})
    elif fault=='evidence_hash':candidate=candidate.model_copy(update={'evidence_ref':candidate.evidence_ref.model_copy(update={'content_hash':'0'*64})})
    elif fault=='mutated':candidate=candidate.model_copy(update={'supplier_account_fingerprint':True})
    elif fault=='provider_head':
        with isolated_owner() as conn:
            conn.execute('UPDATE aip_provider_instance_head SET current_revision=current_revision+1 WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',(*SCOPE.key,provider.provider_instance_id))
    else:AipProductionContractStore().revoke_evidence_bundle(SCOPE,ACTOR,evidence.bundle_id,'revoke-'+uuid4().hex,
        RevokeEvidenceBundleRequest(expectedRevision=evidence.revision,expectedContentHash=evidence.content_hash,reason='candidate input invalidation'))
    with connect(SCOPE) as conn:before=conn.execute('SELECT count(*) AS n FROM aip_provider_capacity_candidate').fetchone()['n']
    with pytest.raises(ProviderCapacityCandidateBlocked):ProviderCapacityCandidateStore().create_account(SCOPE,maker,'deny-'+uuid4().hex,candidate)
    with connect(SCOPE) as conn:assert conn.execute('SELECT count(*) AS n FROM aip_provider_capacity_candidate').fetchone()['n']==before


def test_candidate_sql_cannot_promote_or_mutate_and_canary_is_empty(account_input):
    import psycopg
    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore,ProviderCapacityCandidateBlocked
    maker,_,_,candidate=account_input
    store=ProviderCapacityCandidateStore();saved=store.create_account(SCOPE,maker,'immutable-'+uuid4().hex,candidate)
    for statement in ('UPDATE aip_provider_capacity_candidate SET basis_verified=true',
                      'DELETE FROM aip_provider_capacity_candidate','TRUNCATE aip_provider_capacity_candidate'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connect(SCOPE) as conn:conn.execute(statement)
    with pytest.raises(psycopg.errors.CheckViolation):
        with connect(SCOPE) as conn:
            conn.execute('INSERT INTO aip_provider_capacity_candidate(org_id,project_id,candidate_id,candidate_kind,idempotency_key,content_hash,request_json,created_by,basis_verified) '
                'SELECT org_id,project_id,%s,candidate_kind,%s,content_hash,request_json,created_by,true FROM aip_provider_capacity_candidate WHERE candidate_id=%s',
                ('false-grant-'+uuid4().hex,'false-key-'+uuid4().hex,saved['candidate_id']))
    canary=TenantScope('dev-org','dev-project')
    with pytest.raises(ProviderCapacityCandidateBlocked):store.create_account(canary,maker,'canary-'+uuid4().hex,candidate)
    with connect(canary) as conn:assert conn.execute('SELECT count(*) AS n FROM aip_provider_capacity_candidate').fetchone()['n']==0


from tests.aip.test_provider_capacity_formal_boundary_pg import (
    approved_command,private_database,source_proposal,source_inputs,drafted)
from tests.aip.test_provider_capacity_source_contracts import signed_capacity_documents


@pytest.fixture
def native_signed_source(approved_command,private_database,signed_capacity_documents):
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api import aip_provider_capacity_source_contracts as c
    from aos_api.aip_action_store import canonical_hash
    f=signed_capacity_documents;maker,_,source,_,command=approved_command
    with connect(SCOPE) as conn:
        account=ProviderCapacitySourceActionGuard._candidate(conn,SCOPE,source.physical_account_ref,'account',c.ProviderPhysicalAccountCandidate,maker.subject)
        basis=ProviderCapacitySourceActionGuard._candidate(conn,SCOPE,source.basis_ref,'basis',c.ProviderCapacityBasisCandidate,maker.subject)
    f['attestation'].update(supplierId=account.supplier_id,supplierAccountFingerprint=account.supplier_account_fingerprint,
        providerRefs=[v.model_dump(mode='json',by_alias=True) for v in account.provider_refs],
        evidenceRef=basis.evidence_ref.model_dump(mode='json',by_alias=True),maxConcurrency=basis.max_concurrency,
        tokenLimit=basis.token_limit.model_dump(mode='json',by_alias=True))
    f['policy']['supplierId']=account.supplier_id
    f['maker']=maker.subject
    def actual_command():
        policy,attestation=f['documents']()
        return command.model_copy(update={
            'source_policy_ref':command.source_policy_ref.model_copy(update=dict(asset_id=policy.payload.asset_id,revision=policy.payload.revision,
                content_hash=canonical_hash(policy.payload.model_dump(mode='json',by_alias=True)))),
            'supplier_attestation_ref':command.supplier_attestation_ref.model_copy(update=dict(asset_id=attestation.payload.asset_id,revision=attestation.payload.revision,
                content_hash=canonical_hash(attestation.payload.model_dump(mode='json',by_alias=True))))}),policy,attestation
    return f,actual_command,basis,source,private_database


def test_actual_private_source_matches_original_approved_inputs_and_real_signed_documents(native_signed_source):
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_contracts import capacity_issuance_binding
    f,actual_command,_,_,config=native_signed_source;command,policy,attestation=actual_command()
    with connect_capacity_issuer(config,SCOPE) as conn:
        before=conn.execute('SELECT count(*) AS n FROM aip_action_approval_event').fetchone()['n']
        result=check_native_capacity_supplier_inputs(conn,command,policy,attestation,trust_roots=f['provider'])
        assert result.authorization=='SUPPLIER_DOCUMENT_SIGNATURES_ONLY_NO_CAPACITY_NO_START'
        assert result.execution_allowed is False
        assert result.request_hash==capacity_issuance_binding(SCOPE,f['maker'],command).content_hash
        assert result.source_policy_hash==command.source_policy_ref.content_hash
        assert result.supplier_attestation_hash==command.supplier_attestation_ref.content_hash
        assert conn.execute('SELECT count(*) AS n FROM aip_action_approval_event').fetchone()['n']==before
        assert conn.execute('SELECT session_user AS login,current_user AS role').fetchone()==dict(login='aos_provider_capacity_issuer',role='aos_provider_capacity_issuer')


@pytest.mark.parametrize('target,entry',[('source','native'),('allocation','native'),('allocation','review'),('source','review')])
def test_committed_direct_withdrawal_event_denies_both_original_capacity_approvals(native_signed_source,target,entry):
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs,ProviderCapacityIssuanceBlocked
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard,ProviderCapacitySourceActionBlocked
    f,actual_command,_,source,config=native_signed_source
    command,policy,attestation=actual_command()
    # First prove the original two approvals and authentic signed inputs match.
    with connect_capacity_issuer(config,SCOPE) as conn:
        assert check_native_capacity_supplier_inputs(conn,command,policy,attestation,
            trust_roots=f['provider']).execution_allowed is False
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT current_user AS role').fetchone()['role']=='aos_runtime'
        if target=='source':proposal_id=command.approved_proposal.asset_id
        else:
            proposal_id=conn.execute('SELECT proposal_id FROM aip_action_approval_event '
                'WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
                (*SCOPE.key,source.allocation_approval_ref.asset_id)).fetchone()['proposal_id']
        row=conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
            (*SCOPE.key,proposal_id)).fetchone()
        assert row['status']=='approved' and row['version']==2
        # Use the actual granted INSERT path, without the Store's proposal UPDATE.
        conn.execute('INSERT INTO aip_action_withdrawal_event '
            '(org_id,project_id,withdrawal_event_id,proposal_id,proposal_version,proposal_hash,actor_id,reason,idempotency_key,request_hash) '
            'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (*SCOPE.key,'direct-withdraw-'+uuid4().hex,proposal_id,row['version']+1,row['proposal_hash'],
                row['created_by'],'isolated direct withdrawal authority','direct-key-'+uuid4().hex,'c'*64))
        conn.commit()
        unchanged=conn.execute('SELECT status,version FROM aip_action_proposal '
            'WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,proposal_id)).fetchone()
        assert unchanged==dict(status='approved',version=2)
        assert conn.execute('SELECT count(*) AS n FROM aip_action_withdrawal_event '
            'WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,proposal_id)).fetchone()['n']==1
    if entry=='native':
        with connect_capacity_issuer(config,SCOPE) as conn:
            with pytest.raises(ProviderCapacityIssuanceBlocked):
                check_native_capacity_supplier_inputs(conn,command,policy,attestation,trust_roots=f['provider'])
    else:
        with connect(SCOPE) as conn:
            row=conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (*SCOPE.key,command.approved_proposal.asset_id)).fetchone()
            checker=conn.execute('SELECT actor_id FROM aip_action_approval_event '
                'WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
                (*SCOPE.key,command.approval_event.asset_id)).fetchone()['actor_id']
            with pytest.raises(ProviderCapacitySourceActionBlocked):
                ProviderCapacitySourceActionGuard().check_proposal(conn,SCOPE,checker,row,checker=True)


@pytest.mark.parametrize('fault',['fingerprint','supplier','provider_id','provider_revision','provider_hash','extra_provider',
    'evidence','low_concurrency','low_tokens','other_mode','short_validity','runtime'])
def test_actual_private_source_rejects_resigned_documents_mismatching_approved_terms(native_signed_source,fault):
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs,ProviderCapacityIssuanceBlocked
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.db import connect
    f,actual_command,basis,source,config=native_signed_source
    if fault=='fingerprint':f['attestation']['supplierAccountFingerprint']='e'*64
    elif fault=='supplier':f['attestation']['supplierId']=f['policy']['supplierId']='other-supplier'
    elif fault.startswith('provider_'):
        key={'provider_id':'assetId','provider_revision':'revision','provider_hash':'contentHash'}[fault]
        f['attestation']['providerRefs'][0][key]={'provider_id':'other-provider','provider_revision':99,'provider_hash':'e'*64}[fault]
    elif fault=='extra_provider':f['attestation']['providerRefs'].append(dict(assetType='ProviderInstanceRevision',assetId='extra-provider',revision=1,contentHash='d'*64))
    elif fault=='evidence':f['attestation']['evidenceRef']['assetId']='other-evidence'
    elif fault=='low_concurrency':f['attestation']['maxConcurrency']=basis.max_concurrency-1
    elif fault=='low_tokens':f['attestation']['tokenLimit']['maxTokens']=basis.token_limit.max_tokens-1
    elif fault=='other_mode':
        f['policy']['allowedTokenModes']=['inflight_upper_bound','fixed_window_rate']
        f['attestation']['tokenLimit']=dict(mode='fixed_window_rate',unit='token',maxTokens=basis.token_limit.max_tokens,windowSeconds=60,windowAnchor=f['now'])
    elif fault=='short_validity':f['attestation']['validUntil']=source.valid_until-timedelta(seconds=1)
    command,policy,attestation=actual_command()
    # Both signatures and new exact hashes are valid. The native original-row
    # comparison must refuse the mismatch, rather than a stale document hash.
    context=connect(SCOPE) if fault=='runtime' else connect_capacity_issuer(config,SCOPE)
    with context as conn:
        with pytest.raises(ProviderCapacityIssuanceBlocked):
            check_native_capacity_supplier_inputs(conn,command,policy,attestation,trust_roots=f['provider'])
        conn.rollback()


@pytest.mark.parametrize('fault',[None,'window_seconds','window_anchor'])
def test_native_signed_source_fixed_window_requires_exact_approved_window(native_signed_source,approved_command,fault):
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api import aip_provider_capacity_source_contracts as c
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source,decide_provider_capacity_source
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs,ProviderCapacityIssuanceBlocked
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    f,actual_command,basis,source,config=native_signed_source;maker,checker=approved_command[:2]
    rate=dict(mode='fixed_window_rate',unit='token',maxTokens=basis.token_limit.max_tokens,windowSeconds=60,windowAnchor=f['now'])
    raw=basis.model_dump(mode='python',by_alias=True);raw['tokenLimit']=rate
    rate_basis=c.ProviderCapacityBasisCandidate.model_validate(raw)
    stored=ProviderCapacityCandidateStore().create_basis(SCOPE,maker,'rate-basis-'+uuid4().hex,rate_basis)
    rate_source=source.model_copy(update={'basis_ref':FormalExactRef(assetType='ProviderCapacityBasisCandidateRevision',
        assetId=stored['candidate_id'],revision=1,contentHash=stored['content_hash'])})
    proposal=propose_provider_capacity_source(maker,rate_source,'rate-source-proposal-'+uuid4().hex,source.valid_until)
    result=decide_provider_capacity_source(checker,proposal.proposal.id,'rate-source-approved-'+uuid4().hex,
        DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
            expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='isolated fixed-window Source approval',approvalExpiresAt=source.valid_until)))
    f['policy']['allowedTokenModes']=['fixed_window_rate'];f['attestation']['tokenLimit']=dict(rate)
    if fault=='window_seconds':f['attestation']['tokenLimit']['windowSeconds']=120
    elif fault=='window_anchor':f['attestation']['tokenLimit']['windowAnchor']=f['now']+timedelta(seconds=1)
    command,policy,attestation=actual_command()
    command=command.model_copy(update={'approved_proposal':FormalExactRef(assetType='ActionProposal',assetId=result.proposal.id,
        revision=2,contentHash=result.proposal.proposal_hash),'approval_event':FormalExactRef(assetType='ActionApprovalEvent',
        assetId=result.approvals[0].id,revision=1,contentHash=canonical_hash(result.approvals[0].model_dump(mode='json',by_alias=True)))})
    with connect_capacity_issuer(config,SCOPE) as conn:
        if fault is None:
            checked=check_native_capacity_supplier_inputs(conn,command,policy,attestation,trust_roots=f['provider'])
            assert checked.execution_allowed is False
        else:
            with pytest.raises(ProviderCapacityIssuanceBlocked):check_native_capacity_supplier_inputs(conn,command,policy,attestation,trust_roots=f['provider'])
            conn.rollback()


def test_native_signed_source_rereads_real_root_after_matching(native_signed_source,monkeypatch):
    import json
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs,ProviderCapacityIssuanceBlocked
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    f,actual_command,_,_,config=native_signed_source;command,policy,attestation=actual_command()
    original=FileTrustRootProvider.snapshot;calls=[]
    def snapshot_and_withdraw(self):
        frozen=original(self);calls.append(1)
        if len(calls)==1:
            f['roots'][1]['revokedAt']=(datetime.now(UTC)-timedelta(seconds=1)).isoformat()
            f['rootfile'].write_text(json.dumps(dict(trustRoots=f['roots'])))
        return frozen
    monkeypatch.setattr(FileTrustRootProvider,'snapshot',snapshot_and_withdraw)
    with connect_capacity_issuer(config,SCOPE) as conn:
        with pytest.raises(ProviderCapacityIssuanceBlocked):
            check_native_capacity_supplier_inputs(conn,command,policy,attestation,trust_roots=f['provider'])
        conn.rollback()
    assert len(calls)==2


@pytest.mark.parametrize('target', ['source', 'allocation'])
def test_direct_withdrawal_committed_after_native_serial_snapshot_is_rejected(native_signed_source, target):
    from aos_api.db import connect
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs, ProviderCapacityIssuanceBlocked
    f, actual_command, _, source, config = native_signed_source
    command, policy, attestation = actual_command()
    with connect(SCOPE) as lookup:
        proposal_id = command.approved_proposal.asset_id if target == 'source' else lookup.execute(
            'SELECT proposal_id FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
            (*SCOPE.key, source.allocation_approval_ref.asset_id)).fetchone()['proposal_id']
        row = lookup.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                             (*SCOPE.key, proposal_id)).fetchone()
    with connect_capacity_issuer(config, SCOPE) as reader:
        assert reader.execute('SHOW transaction_isolation').fetchone()['transaction_isolation'] == 'serializable'
        assert reader.execute('SELECT count(*) AS n FROM aip_action_withdrawal_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                              (*SCOPE.key, proposal_id)).fetchone()['n'] == 0
        with connect(SCOPE) as writer:
            writer.execute('INSERT INTO aip_action_withdrawal_event '
                           '(org_id,project_id,withdrawal_event_id,proposal_id,proposal_version,proposal_hash,actor_id,reason,idempotency_key,request_hash) '
                           'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                           (*SCOPE.key, 'snapshot-withdraw-'+uuid4().hex, proposal_id, row['version']+1, row['proposal_hash'],
                            row['created_by'], 'isolated writer-first old snapshot', 'snapshot-key-'+uuid4().hex, 'd'*64))
            writer.commit()
            assert writer.execute('SELECT count(*) AS n FROM aip_action_withdrawal_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                                  (*SCOPE.key, proposal_id)).fetchone()['n'] == 1
        with pytest.raises(ProviderCapacityIssuanceBlocked):
            check_native_capacity_supplier_inputs(reader, command, policy, attestation, trust_roots=f['provider'])
