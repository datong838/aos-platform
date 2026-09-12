from copy import deepcopy

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest, preview_registration
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS


def payload():
    return dict(schemaVersion='aos.ecommerce.first-dispatch-registration/v1',
        installationRef=dict(installationId='11111111-1111-4111-8111-111111111111',revision=5,
            lockHash='sha256:'+'1'*64,overlayRevision='overlay-1'),
        generation='22222222-2222-4222-8222-222222222222',bindingRevision=4,executionEpoch=3,
        configRef=dict(configurationId='33333333-3333-4333-8333-333333333333',revision=1,hash='sha256:'+'2'*64),
        groupId='44444444-4444-4444-8444-444444444444',idempotencyKey='first-registration-1')


def test_preview_is_complete_fenced_detached_and_not_authority():
    request=FirstDispatchRegistrationRequest.model_validate(payload())
    before=request.model_dump(mode='json',by_alias=True)
    view=preview_registration(request)
    assert view['executable'] is False and view['authorityValidated'] is False
    assert [v['operationId'] for v in view['proposedDispatchSnapshot']]==sorted(ECOMMERCE_GROWTH_OPERATIONS)
    for row in view['proposedDispatchSnapshot']:
        assert row['handlerKind']=='legacy' and row['operationFence'] is True
        assert row['installationId'] is row['generation'] is row['executionEpoch'] is None
        assert row['revision']==row['cutoverGroupRevision']==1
    view['proposedDispatchSnapshot'][0]['operationFence']=False
    view['request']['installationRef']['revision']=99
    assert request.model_dump(mode='json',by_alias=True)==before
    assert preview_registration(request)['proposedDispatchSnapshot'][0]['operationFence'] is True


@pytest.mark.parametrize('key,value', [('operationIds',[]),('handlerKind','extension'),
    ('actor','admin'),('sql','SELECT 1'),('credentials',{}),('executable',True)])
def test_arbitrary_control_fields_are_forbidden(key,value):
    data=payload();data[key]=value
    with pytest.raises(ValidationError):FirstDispatchRegistrationRequest.model_validate(data)


@pytest.mark.parametrize('key,value', [('generation','bad'),('groupId','44444444444444448444444444444444'),
    ('bindingRevision',True),('bindingRevision','4'),('executionEpoch',0),('executionEpoch',2**63),
    ('idempotencyKey',' bad'),('idempotencyKey','bad\x00key'),('schemaVersion','unknown')])
def test_noncanonical_request_rejected(key,value):
    data=payload();data[key]=value
    with pytest.raises((ValidationError,ValueError)):FirstDispatchRegistrationRequest.model_validate(data)


@pytest.mark.parametrize('path,value', [('installationRef.revision',6),('installationRef.lockHash','sha256:'+'3'*64),
    ('installationRef.overlayRevision','overlay-2'),('bindingRevision',5),('executionEpoch',4),
    ('configRef.revision',2),('configRef.hash','sha256:'+'4'*64),
    ('generation','55555555-5555-4555-8555-555555555555'),('groupId','66666666-6666-4666-8666-666666666666'),
    ('idempotencyKey','first-registration-2')])
def test_exact_target_changes_are_visible_in_hash(path,value):
    original=payload();changed=deepcopy(original)
    keys=path.split('.');target=changed
    for key in keys[:-1]:target=target[key]
    target[keys[-1]]=value
    a=FirstDispatchRegistrationRequest.model_validate(original)
    b=FirstDispatchRegistrationRequest.model_validate(changed)
    assert a.request_hash()!=b.request_hash()
    assert a.request_hash()==FirstDispatchRegistrationRequest.model_validate(original).request_hash()


def test_preview_requires_validated_request_and_revalidates_unsafe_construct():
    with pytest.raises(TypeError):preview_registration(payload())
    data=payload();data['bindingRevision']=True
    unsafe=FirstDispatchRegistrationRequest.model_construct(**data)
    with pytest.raises((ValidationError,ValueError)):preview_registration(unsafe)
