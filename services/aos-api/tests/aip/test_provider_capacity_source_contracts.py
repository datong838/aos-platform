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
