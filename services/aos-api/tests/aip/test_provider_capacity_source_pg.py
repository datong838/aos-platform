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
