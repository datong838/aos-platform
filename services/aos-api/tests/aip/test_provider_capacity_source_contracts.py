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
