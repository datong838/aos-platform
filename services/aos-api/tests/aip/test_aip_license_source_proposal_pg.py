"""b88 request contracts first; actual Owner approval integration follows.

Pure binding cases grant no license or approval. No mocked positive authority.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from aos_api.tenant_scope import TenantScope


def requested_grant():
    now=datetime.now(timezone.utc)
    return dict(source={'resourceType':'EvidenceBundleRevision','resourceId':'b88.source','revision':1,'contentHash':'a'*64},
        sourceRequestHash='b'*64,installationId=str(uuid4()),installationEtag=4,installationRevision=2,
        releaseRef={'publisher':'aos','bundleId':'solution.ecommerce.growth','version':'1.13.0',
            'contentHash':'sha256:'+'c'*64,'signatureFingerprint':'sha256:'+'d'*64,'releaseEvidenceRevision':'sha256:'+'f'*64},
        policyRef={'assetType':'LicensePolicy','assetId':'policy.license','revision':1,'contentHash':'e'*64},
        licenseId='b88.explicit-license',usagePurpose='内部经营分析的精确来源许可',
        permittedUses=['internal_business_analysis','traceable_derivation'],
        rightsAttestation='owner_authorized_for_exact_source_and_uses',
        validFrom=now-timedelta(minutes=1),validUntil=now+timedelta(hours=1),
        proposalExpiresAt=now+timedelta(minutes=5))


def test_exact_request_binding_does_not_claim_source_or_owner_authority():
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest, source_license_request_binding
    request=SourceLicenseProposalRequest.model_validate(requested_grant())
    first=source_license_request_binding(TenantScope('org-org','dev-project'),'maker',request)
    second=source_license_request_binding(TenantScope('org-org','dev-project'),'maker',request)
    assert first==second and len(first.content_hash)==64
    assert first.authorization=='REQUEST_ONLY_NO_START'
    assert first.content_hash!=source_license_request_binding(TenantScope('dev-org','dev-project'),'maker',request).content_hash
    assert first.content_hash!=source_license_request_binding(TenantScope('org-org','dev-project'),'other-maker',request).content_hash


@pytest.mark.parametrize('key,value',[
    ('sourceRequestHash','f'*64),('installationEtag',5),('installationRevision',3),
    ('installationId',str(uuid4())),('licenseId','another-exact-license'),
    ('usagePurpose','another exact use'),('permittedUses',['internal_business_analysis']),
])
def test_all_grant_terms_change_binding(key,value):
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest, source_license_request_binding
    raw=requested_grant(); scope=TenantScope('org-org','dev-project')
    first=source_license_request_binding(scope,'maker',SourceLicenseProposalRequest.model_validate(raw))
    changed={**raw,key:value}
    assert first.content_hash!=source_license_request_binding(scope,'maker',SourceLicenseProposalRequest.model_validate(changed)).content_hash


@pytest.mark.parametrize('path,value',[
    (('source','resourceType'),'KnowledgeSourceRef'),(('source','revision'),True),
    (('policyRef','assetType'),'LicensePolicyRevision'),(('policyRef','revision'),2),
    (('installationEtag',),True),(('installationRevision',),0),
    (('installationId',),'not-a-uuid'),(('sourceRequestHash',),'sha256:'+'a'*64),
    (('permittedUses',),['external_send']),(('permittedUses',),['internal_business_analysis']*2),
    (('rightsAttestation',),'inferred-from-MIT'),(('licenseId',),'  implicit  '),
    (('validUntil',),datetime(2026,1,1)),
])
def test_invalid_request_cannot_create_request_binding(path,value):
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest
    raw=requested_grant(); target=raw
    for part in path[:-1]: target=target[part]
    target[path[-1]]=value
    with pytest.raises(ValidationError):
        SourceLicenseProposalRequest.model_validate(raw)


def test_reparse_blocks_model_copy_validation_bypass():
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest, source_license_request_binding
    request=SourceLicenseProposalRequest.model_validate(requested_grant()).model_copy(update={'installation_etag':True})
    with pytest.raises(ValueError,match='REQUEST_INVALID'):
        source_license_request_binding(TenantScope('org-org','dev-project'),'maker',request)


def assert_active_signed_source_request(installation_id,loader,release_policy):
    """Actual PG Owner + original Store build + actual signed current policy.

    Isolated test Owner is not a supplied production identity or rights proof.
    """
    import json
    import psycopg
    from psycopg import IsolationLevel
    from psycopg.rows import dict_row
    from aos_api.db import get_dsn
    from aos_api.tenant_scope import apply_transaction_scope
    from aos_api.extension_runtime.current_installation_release_evidence import _read_exact_in_transaction
    from tests.aip.test_evidence_bundle_provenance_pg import build_inputs, ACTOR, SCOPE
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest
    from aos_api.aip_license_source_proposal import read_source_license_request_facts, SourceLicenseProposalBlocked

    store,key,body=build_inputs.__wrapped__()
    source=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    maker='b88-owner-'+uuid4().hex
    admin_actor='b88-admin-'+uuid4().hex
    with isolated_owner() as admin:
        admin.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,maker))
        admin.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'admin')",(*SCOPE.key,admin_actor))
    with psycopg.connect(get_dsn(),row_factory=dict_row) as conn:
        conn.isolation_level=IsolationLevel.SERIALIZABLE
        apply_transaction_scope(conn,SCOPE)
        view,row,records=_read_exact_in_transaction(conn,scope=SCOPE,exact_installation=installation_id,
            release_policy=release_policy,loader=loader)
        release=next(item for item in view.releases if item.bundle_id=='solution.ecommerce.growth')
        source_ref=next(entry[2] for entry in records if entry[0].id==release.bundle_id)
        loaded=loader.load(source_ref)
        artifact=next(item for item in loaded.artifacts if item.relative_path=='content/policies/aip6-runtime-policies.json')
        document=json.loads(loader.read_verified_artifact(source_ref,artifact.relative_path,expected_digest=artifact.digest,limit=262144))
        policy=next(item for item in document['artifacts'] if item['assetType']=='LicensePolicy')
        provenance=conn.execute('SELECT request_hash FROM aip_evidence_bundle_build_provenance WHERE org_id=%s AND project_id=%s AND bundle_id=%s',(*SCOPE.key,source.bundle_id)).fetchone()
        raw=requested_grant()
        raw.update(source={'resourceType':'EvidenceBundleRevision','resourceId':source.bundle_id,'revision':source.revision,'contentHash':source.content_hash},
            sourceRequestHash=provenance['request_hash'],installationId=installation_id,
            installationEtag=view.etag_version,installationRevision=view.current_revision,
            releaseRef={'publisher':release.publisher,'bundleId':release.bundle_id,'version':release.version,
                'contentHash':release.content_hash,'signatureFingerprint':release.signature_fingerprint,
                'releaseEvidenceRevision':release.release_evidence_revision},
            policyRef={'assetType':'LicensePolicy','assetId':policy['id'],'revision':1,'contentHash':artifact.digest.removeprefix('sha256:')})
        request=SourceLicenseProposalRequest.model_validate(raw)
        args=dict(conn=conn,scope=SCOPE,maker=maker,request=request,loader=loader,release_policy=release_policy)
        fact=read_source_license_request_facts(**args)
        assert fact.authorization=='SOURCE_REQUEST_FACTS_ONLY_NO_START'
        assert fact.binding_hash and fact.source_request_hash==provenance['request_hash']
        assert fact.policy.installation_etag==view.etag_version
        assert release.version=='1.13.0'
        for changes,reason in [
            ({'maker':'missing-owner'},'CURRENT_OWNER_REQUIRED'),
            ({'maker':admin_actor},'CURRENT_OWNER_REQUIRED'),
            ({'scope':TenantScope('dev-org','dev-project')},'SCOPE_MISMATCH'),
            ({'request':request.model_copy(update={'source_request_hash':'0'*64})},'PROVENANCE_DRIFT'),
            ({'request':request.model_copy(update={'installation_etag':view.etag_version+1})},'INSTALLATION_DRIFT'),
            ({'request':request.model_copy(update={'installation_revision':view.current_revision+1})},'INSTALLATION_DRIFT'),
            ({'request':request.model_copy(update={'source':request.source.model_copy(update={'content_hash':'0'*64})})},'PROVENANCE_UNAVAILABLE'),
            ({'request':request.model_copy(update={'policy_ref':request.policy_ref.model_copy(update={'content_hash':'0'*64})})},'CURRENT_SIGNED_POLICY_UNAVAILABLE'),
        ]:
            with pytest.raises(SourceLicenseProposalBlocked,match=reason):
                with conn.transaction():
                    read_source_license_request_facts(**{**args,**changes})
        assert conn.execute('SELECT count(*) AS n FROM aip_license_source_issuance WHERE org_id=%s AND project_id=%s AND bundle_id=%s',(*SCOPE.key,source.bundle_id)).fetchone()['n']==0

        # Real exact-PID lock proof: current Owner withdrawal, installation
        # writer lock and READ COMMITTED raw revoke all wait until this caller
        # releases its request-fact transaction. Every writer rolls back.
        from concurrent.futures import ThreadPoolExecutor
        from queue import Queue
        from tests.aip.test_aip_license_source_authority_pg import raw_revoke,wait_blocked
        pids=Queue()
        def writer(kind):
            with isolated_owner() as writer_conn:
                writer_conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
                assert writer_conn.execute('SHOW transaction_isolation').fetchone()['transaction_isolation']=='read committed'
                pids.put(writer_conn.info.backend_pid)
                try:
                    if kind=='owner':
                        writer_conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*SCOPE.key,maker))
                    elif kind=='installation':
                        writer_conn.execute('SELECT installation_pk FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE',(*SCOPE.key,installation_id))
                    else:
                        raw_revoke(writer_conn,source.bundle_id,content_hash=source.content_hash)
                finally:
                    writer_conn.rollback()
        pool=ThreadPoolExecutor(max_workers=3)
        futures=[]
        try:
            futures=[pool.submit(writer,kind) for kind in ('owner','installation','revoke')]
            writer_pids=[pids.get(timeout=6) for _ in futures]
            with isolated_owner() as observer:
                wait_blocked(observer,writer_pids,conn.info.backend_pid,futures)
        finally:
            conn.rollback()
            for future in futures:
                future.result(timeout=8)
            pool.shutdown(wait=True)
    # Actual isolated RSA signature/JWKS verification, not production IdP supply.
    from aos_api.auth import Principal
    from aos_api.aip_license_source_proposal import propose_source_license_in_transaction
    from tests.aip.test_source_license_approval_pg import isolated_source_oidc
    from aos_api.aip_license_source_approval import propose_authenticated_source_license_in_transaction
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseMakerCommand
    proposal_key='b88-request-'+uuid4().hex
    with isolated_source_oidc(maker) as token, psycopg.connect(get_dsn(),row_factory=dict_row) as maker_conn:
        maker_conn.isolation_level=IsolationLevel.SERIALIZABLE
        apply_transaction_scope(maker_conn,SCOPE)
        command=SourceLicenseMakerCommand(schemaVersion=1,bearerToken=token,orgId=SCOPE.org_id,projectId=SCOPE.project_id,idempotencyKey=proposal_key,request=request)
        proposal=propose_authenticated_source_license_in_transaction(command,conn=maker_conn,loader=loader,release_policy=release_policy)
        assert proposal.proposal.status.value=='drafted'
        assert proposal.proposal.risk_level.value=='R2'
        assert proposal.proposal.payload['requestedGrant']==request.model_dump(mode='json',by_alias=True)
        replay=propose_authenticated_source_license_in_transaction(command,conn=maker_conn,loader=loader,release_policy=release_policy)
        assert replay.proposal.id==proposal.proposal.id
        # A valid maker request still grants no generic approval route.
        from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
        from aos_api.aip_action_models import DecideActionProposalRequest
        from aos_api.ecommerce_growth_host_ports import HostTransaction
        from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
        with pytest.raises(AipActionTransitionBlocked,match='SOURCE_LICENSE_PRODUCER_REQUIRED'):
            AipActionStore(TransactionBoundConnectFactory(HostTransaction(maker_conn),SCOPE)).decide(
                SCOPE,'different-checker',proposal.proposal.id,'b88-no-generic-approval-'+uuid4().hex,
                DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,
                    expectedProposalHash=proposal.proposal.proposal_hash,decision='approved'))
        for table in ('aip_action_proposal','aip_action_draft'):
            with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_LICENSE_INDEPENDENT_APPROVAL_ISSUER_REQUIRED'):
                with maker_conn.transaction():
                    version_clause=',version=version+1' if table=='aip_action_proposal' else ''
                    maker_conn.execute(f"UPDATE {table} SET status='approved'{version_clause} WHERE org_id=%s AND project_id=%s AND proposal_id=%s",(*SCOPE.key,proposal.proposal.id))
        assert maker_conn.execute('SELECT count(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,proposal.proposal.id)).fetchone()['n']==0
        assert maker_conn.execute('SELECT count(*) AS n FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND idempotency_key=%s',(*SCOPE.key,proposal_key)).fetchone()['n']==1
    from tests.aip.test_source_license_approval_pg import assert_independent_signed_source_approval
    assert_independent_signed_source_approval(proposal,maker,loader,release_policy)
    with isolated_owner() as observer:
        assert observer.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE org_id=%s AND project_id=%s AND bundle_id=%s',(*SCOPE.key,source.bundle_id)).fetchone()['n']==0
        assert observer.execute('SELECT count(*) AS n FROM aip_license_source_issuance WHERE org_id=%s AND project_id=%s AND bundle_id=%s',(*SCOPE.key,source.bundle_id)).fetchone()['n']==0

@pytest.mark.parametrize('path,value',[
    (('source','resourceId'),'another-source'),(('source','revision'),2),
    (('source','contentHash'),'0'*64),
    (('policyRef','assetId'),'another-policy'),(('policyRef','contentHash'),'0'*64),
    (('releaseRef','publisher'),'another.publisher'),(('releaseRef','bundleId'),'another.bundle'),
    (('releaseRef','version'),'1.14.0'),(('releaseRef','contentHash'),'sha256:'+'0'*64),
    (('releaseRef','signatureFingerprint'),'sha256:'+'0'*64),
    (('releaseRef','releaseEvidenceRevision'),'sha256:'+'0'*64),
])
def test_exact_source_policy_and_all_release_identifiers_change_binding(path,value):
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest, source_license_request_binding
    raw=requested_grant(); changed=deepcopy(raw); target=changed
    for part in path[:-1]: target=target[part]
    target[path[-1]]=value
    scope=TenantScope('org-org','dev-project')
    assert source_license_request_binding(scope,'maker',SourceLicenseProposalRequest.model_validate(raw)).content_hash!=source_license_request_binding(scope,'maker',SourceLicenseProposalRequest.model_validate(changed)).content_hash


@pytest.mark.parametrize('field',['validFrom','validUntil','proposalExpiresAt'])
def test_each_exact_grant_deadline_changes_binding(field):
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest, source_license_request_binding
    raw=requested_grant(); changed={**raw,field:raw[field]+timedelta(seconds=1)}
    scope=TenantScope('org-org','dev-project')
    assert source_license_request_binding(scope,'maker',SourceLicenseProposalRequest.model_validate(raw)).content_hash!=source_license_request_binding(scope,'maker',SourceLicenseProposalRequest.model_validate(changed)).content_hash


def test_equivalent_utc_and_use_set_encodings_share_one_binding():
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest, source_license_request_binding
    raw=requested_grant(); changed={**raw,'permittedUses':list(reversed(raw['permittedUses']))}
    for key in ('validFrom','validUntil','proposalExpiresAt'):
        changed[key]=raw[key].astimezone(timezone(timedelta(hours=8)))
    scope=TenantScope('org-org','dev-project')
    assert source_license_request_binding(scope,'maker',SourceLicenseProposalRequest.model_validate(raw))==source_license_request_binding(scope,'maker',SourceLicenseProposalRequest.model_validate(changed))


def test_source_store_rejects_arbitrary_guard_callbacks_before_any_connection():
    from aos_api.aip_action_store import AipActionStore
    with pytest.raises(TypeError,match='exact source license proposal guard'):
        AipActionStore(source_license_guard=object())
