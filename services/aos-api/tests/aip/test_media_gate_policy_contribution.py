"""Contribution format tests never grant real signature or canonical Rule authority."""
import pytest
from pydantic import ValidationError
from aos_api.aip_media_gate_policy_contribution import MediaGatePolicyContribution
from aos_api.aip_production_contracts import RegisterMediaGateProfileRequest


def document():
    return {'schema':'aos.ecommerce-media-gate-policy/v1','policyId':'fixture-media-policy',
        'revision':1,'profileId':'fixture-media-full','profileRevision':1,
        'gates':[{'gateId':'media.'+kind,'kind':kind,'ruleRef':{'resourceType':'EvalRuleRevision','resourceId':'fixture-rule-'+kind,'revision':1,'contentHash':'1'*64},'returnStage':'review'} for kind in ['fact','brand','copyright','platform']]}


def test_exact_four_rule_contribution_has_no_authority_claim():
    value=MediaGatePolicyContribution.model_validate(document())
    assert len(value.gates)==4
    assert set(value.model_dump(by_alias=True))=={'schema','policyId','revision','profileId','profileRevision','gates'}

@pytest.mark.parametrize('field',['sourceBundleRef','signatureRef','policyRef','tenant','actor','approved','current','authority'])
def test_self_reference_and_caller_authority_fields_forbidden(field):
    body=document();body[field]={}
    with pytest.raises(ValidationError):MediaGatePolicyContribution.model_validate(body)

@pytest.mark.parametrize('mutation',['missing','duplicate','id','ruleType','override','zeroRevision','unknownSchema'])
def test_bad_contribution_refused(mutation):
    body=document()
    if mutation=='missing':body['gates'].pop()
    if mutation=='duplicate':body['gates'][3]=dict(body['gates'][0])
    if mutation=='id':body['gates'][0]['gateId']='media.platform'
    if mutation=='ruleType':body['gates'][0]['ruleRef']['resourceType']='ApprovalRevision'
    if mutation=='override':body['gates'][0]['allowOverride']=True
    if mutation=='zeroRevision':body['revision']=0
    if mutation=='unknownSchema':body['schema']='aos.ecommerce-production-profile/v1'
    with pytest.raises(ValidationError):MediaGatePolicyContribution.model_validate(body)


def test_shared_four_gate_validation_keeps_registration_semantics():
    contribution=document()
    def ref(kind):return {'resourceType':kind,'resourceId':'fixture-'+kind,'revision':1,'contentHash':'1'*64}
    body={'profileId':contribution['profileId'],'revision':1,'sourceBundleRef':ref('BundleManifestRevision'),'signatureRef':ref('BundleSignatureVerification'),'policyRef':ref('MediaGatePolicyRevision'),'gates':contribution['gates']}
    assert len(RegisterMediaGateProfileRequest.model_validate(body).gates)==4
    body['gates'][3]=dict(body['gates'][0])
    with pytest.raises(ValidationError):RegisterMediaGateProfileRequest.model_validate(body)

@pytest.mark.parametrize('revision',[True,'1',0])
def test_revision_must_be_explicit_positive_integer(revision):
    body=document();body['revision']=revision
    with pytest.raises(ValidationError):MediaGatePolicyContribution.model_validate(body)


def test_shared_helper_refuses_extra_duplicate_gate():
    from aos_api.aip_production_contracts import MediaGateDefinition, require_four_media_gates
    gates=[MediaGateDefinition.model_validate(x) for x in document()['gates']]
    with pytest.raises(ValueError):require_four_media_gates(gates+gates[:1])
