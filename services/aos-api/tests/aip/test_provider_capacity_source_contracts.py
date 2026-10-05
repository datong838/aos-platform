"""Candidates preserve provenance and accounting dimensions, never grant capacity."""
from datetime import UTC,datetime,timedelta

import pytest
from pydantic import ValidationError


def ref(kind, identity='id'):
    return dict(assetType=kind,assetId=identity,revision=1,contentHash='a'*64)


def account():
    return dict(schemaVersion=1,tenant=dict(orgId='org-org',projectId='dev-project'),
        physicalAccountId='stable-account',supplierId='supplier',supplierAccountFingerprint='b'*64,
        providerRefs=[ref('ProviderInstanceRevision','provider-a'),ref('ProviderInstanceRevision','provider-b')],
        evidenceRef=ref('EvidenceBundleRevision'))


def basis():
    now=datetime.now(UTC)
    return dict(schemaVersion=1,tenant=dict(orgId='org-org',projectId='dev-project'),
        basisKind='supplier_limit_claim',physicalAccountRef=ref('ProviderPhysicalAccountCandidateRevision'),
        evidenceRef=ref('EvidenceBundleRevision'),maxConcurrency=2,
        tokenLimit=dict(mode='inflight_upper_bound',maxTokens=20000,unit='token'),
        observedAt=now-timedelta(minutes=1),validFrom=now-timedelta(minutes=1),validUntil=now+timedelta(hours=1))


def source():
    now=datetime.now(UTC)
    return dict(schemaVersion=1,tenant=dict(orgId='org-org',projectId='dev-project'),
        physicalAccountRef=ref('ProviderPhysicalAccountCandidateRevision'),basisRef=ref('ProviderCapacityBasisCandidateRevision'),
        allocationRequestRef=ref('ProviderCapacityRequest'),allocationApprovalRef=ref('ActionApprovalEvent'),
        validFrom=now-timedelta(minutes=1),validUntil=now+timedelta(hours=1),executionAllowed=False)


def test_account_can_map_multiple_exact_providers_without_revision_in_identity():
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate
    original=ProviderPhysicalAccountCandidate.model_validate(account())
    raw=account();raw['providerRefs'][0]['revision']=2
    changed=ProviderPhysicalAccountCandidate.model_validate(raw)
    assert changed.physical_account_id==original.physical_account_id
    assert len(original.provider_refs)==2


@pytest.mark.parametrize('fault',['verified','active','canary','duplicate','wrong_kind','blank','provider_revision','credential'])
def test_account_rejects_self_authority_or_ambiguous_mapping(fault):
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate
    raw=account()
    if fault=='verified':raw['basisVerified']=True
    elif fault=='active':raw['lifecycle']='active'
    elif fault=='canary':raw['tenant']['orgId']='dev-org'
    elif fault=='duplicate':raw['providerRefs'].append(raw['providerRefs'][0])
    elif fault=='wrong_kind':raw['providerRefs'][0]['assetType']='ModelRevision'
    elif fault=='blank':raw['physicalAccountId']='\taccount'
    elif fault=='provider_revision':raw['providerRevision']=2
    else:raw['apiKey']='must-not-be-accepted'
    with pytest.raises(ValidationError):ProviderPhysicalAccountCandidate.model_validate(raw)


@pytest.mark.parametrize('fault',['boolean','zero','missing_window','wrong_unit','inflight_window','naive','verified_kind','verified_flag','wrong_account','fractional'])
def test_basis_rejects_unverified_claims_and_mixed_measurement(fault):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityBasisCandidate
    raw=basis()
    if fault=='boolean':raw['maxConcurrency']=True
    elif fault=='zero':raw['tokenLimit']['maxTokens']=0
    elif fault=='missing_window':raw['tokenLimit']['mode']='fixed_window_rate'
    elif fault=='wrong_unit':raw['tokenLimit']['unit']='tokens_per_minute'
    elif fault=='inflight_window':raw['tokenLimit']['windowSeconds']=60
    elif fault=='naive':raw['validUntil']=datetime(2026,10,6)
    elif fault=='verified_kind':raw['basisKind']='verified_supplier_limit'
    elif fault=='verified_flag':raw['basisVerified']=True
    elif fault=='wrong_account':raw['physicalAccountRef']['assetType']='ProviderInstanceRevision'
    else:raw['tokenLimit']['maxTokens']=1.5
    with pytest.raises(ValidationError):ProviderCapacityBasisCandidate.model_validate(raw)


def test_fixed_window_rate_remains_distinct_from_inflight_occupation():
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityBasisCandidate
    raw=basis();raw['tokenLimit']=dict(mode='fixed_window_rate',unit='token',maxTokens=20000,
        windowSeconds=60,windowAnchor=datetime.now(UTC))
    rate=ProviderCapacityBasisCandidate.model_validate(raw)
    assert rate.token_limit.mode=='fixed_window_rate'
    raw['basisKind']='owner_allocation'
    assert ProviderCapacityBasisCandidate.model_validate(raw).basis_kind=='owner_allocation'


@pytest.mark.parametrize('fault',['execute','wrong_basis','wrong_approval','naive','window','verified'])
def test_source_candidate_cannot_promote_itself_or_rebind_provenance(fault):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourceCandidate
    raw=source()
    if fault=='execute':raw['executionAllowed']=True
    elif fault=='wrong_basis':raw['basisRef']['assetType']='QuotaPolicyRevision'
    elif fault=='wrong_approval':raw['allocationApprovalRef']['assetType']='ActionProposal'
    elif fault=='naive':raw['validFrom']=datetime(2026,10,5)
    elif fault=='window':raw['validUntil']=raw['validFrom']
    else:raw['basisVerified']=True
    with pytest.raises(ValidationError):ProviderCapacitySourceCandidate.model_validate(raw)


def test_source_exact_candidate_is_still_not_an_execution_grant():
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourceCandidate
    item=ProviderCapacitySourceCandidate.model_validate(source())
    assert item.execution_allowed is False


@pytest.mark.parametrize('fault',['nested_boolean','mutated_kind','integer_false'])
def test_revalidation_rejects_mutated_native_candidates(fault):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityBasisCandidate,ProviderCapacitySourceCandidate
    if fault=='integer_false':
        item=ProviderCapacitySourceCandidate.model_validate(source()).model_copy(update={'execution_allowed':0})
        with pytest.raises(ValidationError):ProviderCapacitySourceCandidate.model_validate(item)
    else:
        item=ProviderCapacityBasisCandidate.model_validate(basis())
        if fault=='nested_boolean':
            item=item.model_copy(update={'token_limit':item.token_limit.model_copy(update={'max_tokens':True})})
        else:
            item=item.model_copy(update={'physical_account_ref':item.physical_account_ref.model_copy(update={'asset_type':'ProviderInstanceRevision'})})
        with pytest.raises(ValidationError):ProviderCapacityBasisCandidate.model_validate(item)


@pytest.mark.parametrize('target,field,formal_kind', [
    ('basis','physicalAccountRef','ProviderPhysicalAccountRevision'),
    ('source','physicalAccountRef','ProviderPhysicalAccountRevision'),
    ('source','basisRef','ProviderCapacityBasisRevision'),
])
def test_candidate_input_rejects_formal_authority_reference(target,field,formal_kind):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityBasisCandidate,ProviderCapacitySourceCandidate
    raw=basis() if target=='basis' else source()
    raw[field]['assetType']=formal_kind
    contract=ProviderCapacityBasisCandidate if target=='basis' else ProviderCapacitySourceCandidate
    with pytest.raises(ValidationError):contract.model_validate(raw)


# Full Source issuance ingress: these references request issuance, never grant it.
def issuance():
    proposal=ref('ActionProposal','source-proposal');proposal['revision']=2
    return dict(schemaVersion=1,tenant=dict(orgId='org-org',projectId='dev-project'),
        bearerToken='aaa.bbb.ccc',idempotencyKey='capacity-issue-1',approvedProposal=proposal,
        approvalEvent=ref('ActionApprovalEvent','source-approved-event'),
        supplierAttestationRef=ref('SupplierCapacityAttestationRevision','supplier-attestation'),
        sourcePolicyRef=ref('ProviderCapacitySourcePolicyRevision','source-policy'))


@pytest.mark.parametrize('field,value',[
    ('basisVerified',True),('executionAllowed',True),('maker','owner'),('roles',['owner']),
    ('maxConcurrency',2),('physicalAccountId','client-account'),('schemaVersion',True),
    ('idempotencyKey','key with whitespace'),('bearerToken','unsigned'),
    ('tenant',dict(orgId='dev-org',projectId='dev-project'))])
def test_issuance_command_rejects_caller_authority_and_inexact_input(field,value):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
    with pytest.raises(ValidationError):ProviderCapacityIssuanceCommand.model_validate({**issuance(),field:value})


@pytest.mark.parametrize('field,bad_kind',[
    ('approvedProposal','ProviderCapacitySourceCandidateRevision'),('approvalEvent','ActionProposal'),
    ('supplierAttestationRef','EvidenceBundleRevision'),('sourcePolicyRef','LicensePolicy')])
def test_issuance_command_requires_separate_formal_reference_types(field,bad_kind):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
    raw=issuance();raw[field]['assetType']=bad_kind
    with pytest.raises(ValidationError):ProviderCapacityIssuanceCommand.model_validate(raw)


@pytest.mark.parametrize('field,value', [('approvedProposal',1),('approvedProposal',3),
    ('approvalEvent',2),('supplierAttestationRef',True),('sourcePolicyRef','1')])
def test_issuance_command_rejects_nonexact_reference_revisions(field,value):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
    raw=issuance();raw[field]['revision']=value
    with pytest.raises(ValidationError):ProviderCapacityIssuanceCommand.model_validate(raw)


def test_issuance_binding_binds_maker_and_all_refs_without_secret_or_key():
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand,capacity_issuance_binding
    from aos_api.tenant_scope import TenantScope
    scope=TenantScope('org-org','dev-project')
    command=ProviderCapacityIssuanceCommand.model_validate(issuance())
    binding=capacity_issuance_binding(scope,'maker',command)
    assert binding.authorization=='ISSUANCE_REQUEST_ONLY_NO_CAPACITY_NO_START'
    assert capacity_issuance_binding(scope,'maker',ProviderCapacityIssuanceCommand.model_validate(
        {**issuance(),'bearerToken':'ddd.eee.fff','idempotencyKey':'different-key'}))==binding
    assert capacity_issuance_binding(scope,'another-maker',command)!=binding
    for field in ('approvedProposal','approvalEvent','supplierAttestationRef','sourcePolicyRef'):
        raw=issuance();raw[field]['contentHash']='b'*64
        assert capacity_issuance_binding(scope,'maker',ProviderCapacityIssuanceCommand.model_validate(raw))!=binding
    assert 'aaa.bbb.ccc' not in repr(command)
    with pytest.raises(ValueError):capacity_issuance_binding(TenantScope('dev-org','dev-project'),'maker',command)
    with pytest.raises(ValueError):capacity_issuance_binding(scope,'unknown',command)


@pytest.mark.parametrize('field',['approved_proposal','approval_event','supplier_attestation_ref','source_policy_ref'])
def test_issuance_binding_revalidates_nested_mutated_refs(field):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand,capacity_issuance_binding
    from aos_api.tenant_scope import TenantScope
    command=ProviderCapacityIssuanceCommand.model_validate(issuance())
    corrupted=command.model_copy(update={field:getattr(command,field).model_copy(update={'revision':True})})
    with pytest.raises(ValueError):capacity_issuance_binding(TenantScope('org-org','dev-project'),'maker',corrupted)


def test_capacity_issuer_rejects_plain_principal_and_subclass_before_authentication():
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command,ProviderCapacityIssuanceBlocked
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
    from aos_api.auth import Principal
    with pytest.raises(ProviderCapacityIssuanceBlocked):
        authenticate_capacity_issuance_command(Principal(subject='maker',org_id='org-org',project_id='dev-project',roles=['owner'],token_kind='oidc'))
    class Derived(ProviderCapacityIssuanceCommand):pass
    with pytest.raises(ProviderCapacityIssuanceBlocked):authenticate_capacity_issuance_command(Derived.model_validate(issuance()))


def test_capacity_issuer_verifies_actual_https_jwks_and_reauthenticates(https_signer):
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
    sign,requests=https_signer
    command=ProviderCapacityIssuanceCommand.model_validate({**issuance(),'bearerToken':sign('capacity-issuer-maker')})
    assert authenticate_capacity_issuance_command(command).subject=='capacity-issuer-maker'
    assert authenticate_capacity_issuance_command(command).subject=='capacity-issuer-maker'
    assert requests and all(path=='/jwks' for path in requests)


@pytest.mark.parametrize('fault',['wrong_key','expired','audience','scope','issuer','missing_subject'])
def test_capacity_issuer_actual_jwt_rejection_never_leaks_token(https_signer,fault):
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command,ProviderCapacityIssuanceBlocked
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
    sign,_=https_signer
    changes={'expired':{'exp':1},'audience':{'aud':'other'},'scope':{'org_id':'dev-org'},
        'issuer':{'iss':'https://wrong-issuer.integration.test'}}.get(fault)
    token=sign('capacity-issuer-maker',changes=changes,omit='sub' if fault=='missing_subject' else None,wrong_key=fault=='wrong_key')
    command=ProviderCapacityIssuanceCommand.model_validate({**issuance(),'bearerToken':token})
    with pytest.raises(ProviderCapacityIssuanceBlocked) as caught:authenticate_capacity_issuance_command(command)
    assert token not in str(caught.value) and caught.value.__cause__ is None


@pytest.mark.parametrize('name,value',[('AOS_AUTH_ALLOW_DEV','1'),('AOS_AUTH_EXTERNAL_ONLY','0'),
    ('AOS_OIDC_JWKS_URL','http://127.0.0.1/jwks'),('AOS_OIDC_ISSUER',''),('AOS_OIDC_AUDIENCE','')])
def test_capacity_issuer_rejects_unsafe_auth_config_before_jwks(https_signer,monkeypatch,name,value):
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command,ProviderCapacityIssuanceBlocked
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
    sign,requests=https_signer
    command=ProviderCapacityIssuanceCommand.model_validate({**issuance(),'bearerToken':sign('capacity-issuer-maker')})
    monkeypatch.setenv(name,value)
    with pytest.raises(ProviderCapacityIssuanceBlocked):authenticate_capacity_issuance_command(command)
    assert requests==[]


@pytest.fixture
def signed_capacity_documents(tmp_path):
    import base64,json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.asset_registry.canonical_json import canonical_json
    from aos_api.aip_action_store import canonical_hash
    from aos_api import aip_provider_capacity_source_contracts as c
    now=datetime.now(UTC)
    keys={name:Ed25519PrivateKey.generate() for name in ('aos-capacity-source-policy','test-only-supplier-publisher')}
    roots=[dict(publisher=name,keyId='test-key',algorithm='Ed25519',
        publicKey=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode(),
        notBefore=(now-timedelta(hours=1)).isoformat(),notAfter=(now+timedelta(hours=2)).isoformat(),
        revokedAt=None,revision='sha256:'+'c'*64) for name,key in keys.items()]
    directory=tmp_path/'capacity-roots';directory.mkdir(mode=0o700)
    rootfile=directory/'roots.json';rootfile.write_text(json.dumps(dict(trustRoots=roots)));rootfile.chmod(0o600)
    common=dict(schemaVersion=1,tenant=dict(orgId='org-org',projectId='dev-project'),revision=1,
        keyId='test-key',validFrom=now-timedelta(minutes=1),validUntil=now+timedelta(hours=1))
    policy=dict(common,assetId='source-policy',publisher='aos-capacity-source-policy',purpose='provider_capacity_source',
        supplierId='test-only-supplier',attestationPublisher='test-only-supplier-publisher',attestationKeyId='test-key',
        attestationRootRevision='sha256:'+'c'*64,maxObservationAgeSeconds=300,maxFutureSkewSeconds=5,
        allowedTokenModes=['inflight_upper_bound'],deploymentTarget=dict(host='127.0.0.1',port=5433,database='aos_test_protocol',
            databaseOid=12345,clusterIdentifier='1234567890123456789',issuerRole='aos_provider_capacity_issuer'))
    attestation=dict(common,assetId='supplier-attestation',publisher='test-only-supplier-publisher',purpose='supplier_capacity_attestation',
        supplierId='test-only-supplier',supplierAccountFingerprint='f'*64,providerRefs=[ref('ProviderInstanceRevision','provider')],
        evidenceRef=ref('EvidenceBundleRevision','evidence'),maxConcurrency=2,
        tokenLimit=dict(mode='inflight_upper_bound',unit='token',maxTokens=20000),observedAt=now-timedelta(seconds=10))
    def sign(body,model,envelope,key=None):
        parsed=model.model_validate(body);payload=parsed.model_dump(mode='json',by_alias=True)
        signer=key or keys[parsed.publisher]
        return envelope.model_validate(dict(payload=payload,signature=base64.b64encode(signer.sign(canonical_json(payload))).decode()))
    def documents():
        return sign(policy,c.ProviderCapacitySourcePolicy,c.SignedCapacitySourcePolicy),sign(attestation,c.SupplierCapacityAttestation,c.SignedSupplierCapacityAttestation)
    pdoc,adoc=documents()
    raw=issuance();raw['sourcePolicyRef']=dict(assetType='ProviderCapacitySourcePolicyRevision',assetId=policy['assetId'],revision=1,contentHash=canonical_hash(pdoc.payload.model_dump(mode='json',by_alias=True)))
    raw['supplierAttestationRef']=dict(assetType='SupplierCapacityAttestationRevision',assetId=attestation['assetId'],revision=1,contentHash=canonical_hash(adoc.payload.model_dump(mode='json',by_alias=True)))
    return dict(command=c.ProviderCapacityIssuanceCommand.model_validate(raw),policy=policy,attestation=attestation,
        documents=documents,sign=sign,roots=roots,rootfile=rootfile,provider=FileTrustRootProvider(rootfile),now=now,keys=keys)


def test_signed_capacity_documents_verify_real_ed25519_and_all_four_reference_binding(signed_capacity_documents):
    from aos_api.aip_provider_capacity_source_issuer import check_signed_capacity_documents
    from aos_api.aip_provider_capacity_source_contracts import capacity_issuance_binding
    f=signed_capacity_documents;pdoc,adoc=f['documents']()
    checked=check_signed_capacity_documents(f['command'],'authenticated-maker',pdoc,adoc,trust_roots=f['provider'],checked_at=f['now'])
    assert checked.authorization=='SUPPLIER_DOCUMENT_SIGNATURES_ONLY_NO_CAPACITY_NO_START'
    assert checked.execution_allowed is False
    assert checked.request_hash==capacity_issuance_binding(__import__('aos_api.tenant_scope',fromlist=['TenantScope']).TenantScope('org-org','dev-project'),'authenticated-maker',f['command']).content_hash
    assert checked.source_policy_hash==f['command'].source_policy_ref.content_hash
    assert checked.supplier_attestation_hash==f['command'].supplier_attestation_ref.content_hash


@pytest.mark.parametrize('fault',['signature','wrong_key','publisher','supplier','mode','future','stale','expired',
    'policy_expired','tenant','root_revoked','root_expired','root_revision','ref_hash','ref_id','ref_revision','client_key','verified','construct'])
def test_signed_capacity_documents_reject_actual_signature_and_source_drift(signed_capacity_documents,fault):
    import base64,json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from aos_api.aip_provider_capacity_source_issuer import check_signed_capacity_documents
    from aos_api import aip_provider_capacity_source_contracts as c
    from aos_api.aip_action_store import canonical_hash
    f=signed_capacity_documents;pdoc,adoc=f['documents']();command=f['command']
    with pytest.raises(ValueError):
        if fault=='signature':adoc=adoc.model_copy(update={'signature':base64.b64encode(b'0'*64).decode()})
        elif fault=='wrong_key':adoc=f['sign'](f['attestation'],c.SupplierCapacityAttestation,c.SignedSupplierCapacityAttestation,Ed25519PrivateKey.generate())
        elif fault in {'root_revoked','root_expired'}:
            f['roots'][1]['revokedAt' if fault=='root_revoked' else 'notAfter']=(f['now']-timedelta(seconds=1)).isoformat()
            f['rootfile'].write_text(json.dumps(dict(trustRoots=f['roots'])))
        elif fault in {'ref_hash','ref_id','ref_revision'}:
            bad=command.supplier_attestation_ref.model_copy(update={{'ref_hash':'content_hash','ref_id':'asset_id','ref_revision':'revision'}[fault]:{'ref_hash':'0'*64,'ref_id':'other-attestation','ref_revision':2}[fault]})
            command=command.model_copy(update={'supplier_attestation_ref':bad})
        elif fault=='construct':adoc=c.SignedSupplierCapacityAttestation.model_construct(payload=adoc.payload.model_copy(update={'max_concurrency':True}),signature=adoc.signature)
        else:
            if fault=='publisher':f['attestation']['publisher']='aos-capacity-source-policy'
            elif fault=='supplier':f['attestation']['supplierId']='other-supplier'
            elif fault=='mode':f['attestation']['tokenLimit']=dict(mode='fixed_window_rate',unit='token',maxTokens=20000,windowSeconds=60,windowAnchor=f['now'])
            elif fault=='future':f['attestation']['observedAt']=f['now']+timedelta(minutes=1)
            elif fault=='stale':f['attestation']['observedAt']=f['now']-timedelta(minutes=10)
            elif fault=='expired':f['attestation']['validUntil']=f['now']-timedelta(seconds=1)
            elif fault=='policy_expired':f['policy']['validUntil']=f['now']-timedelta(seconds=1)
            elif fault=='tenant':f['attestation']['tenant']['orgId']='dev-org'
            elif fault=='root_revision':f['policy']['attestationRootRevision']='sha256:'+'d'*64
            elif fault=='client_key':f['attestation']['publicKey']='client-injected'
            elif fault=='verified':f['attestation']['supplierVerified']=True
            pdoc,adoc=f['documents']()
            # Rebind exact hashes after valid re-signing so semantic refusals
            # cannot pass merely because the original reference is stale.
            command=command.model_copy(update={'source_policy_ref':command.source_policy_ref.model_copy(update={'content_hash':canonical_hash(pdoc.payload.model_dump(mode='json',by_alias=True))}),
                'supplier_attestation_ref':command.supplier_attestation_ref.model_copy(update={'content_hash':canonical_hash(adoc.payload.model_dump(mode='json',by_alias=True))})})
        check_signed_capacity_documents(command,'authenticated-maker',pdoc,adoc,trust_roots=f['provider'],checked_at=f['now'])
