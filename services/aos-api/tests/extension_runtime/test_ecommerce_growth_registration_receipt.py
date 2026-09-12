from copy import deepcopy
from uuid import uuid4

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest, preview_registration
from aos_api.ecommerce_growth_registration_receipt import decode_registration_receipt
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_registration_contracts import payload


def row():
    request=FirstDispatchRegistrationRequest.model_validate(payload());identity=str(uuid4())
    body=dict(schemaVersion='aos.ecommerce.first-dispatch-registration-receipt/v1',
        tenant=dict(orgId='org-a',projectId='project-a'),receiptId=identity,
        installationId=request.installationRef.installation_id,generation=request.generation,
        groupId=request.groupId,requestHash=request.request_hash(),idempotencyKey=request.idempotencyKey,
        actor='actor',request=request.model_dump(mode='json',by_alias=True),
        dispatchSnapshot=preview_registration(request)['proposedDispatchSnapshot'],executable=False,
        createdAt='2026-09-13T00:00:00+00:00')
    return dict(org_id='org-a',project_id='project-a',receipt_id=identity,installation_id=body['installationId'],
        generation=body['generation'],group_id=body['groupId'],idempotency_key=body['idempotencyKey'],
        request_hash=body['requestHash'],payload=body,content_hash=canonical_sha256(body))


def check(value):return decode_registration_receipt(value,scope=TenantScope('org-a','project-a'))


def test_hash_and_identity_checked_and_detached():
    value=row();before=deepcopy(value)
    result=check(value);result['request']['bindingRevision']=99
    assert value==before and check(value)['request']['bindingRevision']==4


@pytest.mark.parametrize('mutation',['hash','tenant','row_scope','fence','operations','request','executable','clock','actor'])
def test_corrupt_receipt_even_with_new_hash_is_not_accepted(mutation):
    value=row();body=value['payload']
    if mutation=='tenant':body['tenant']['orgId']='other'
    elif mutation=='row_scope':value['org_id']='other'
    elif mutation=='fence':body['dispatchSnapshot'][0]['operationFence']=False
    elif mutation=='operations':body['dispatchSnapshot'].pop()
    elif mutation=='request':body['request']['configRef']['revision']=2
    elif mutation=='executable':body['executable']=True
    elif mutation=='clock':body['createdAt']='not-a-time'
    elif mutation=='actor':body['actor']=''
    value['content_hash']='sha256:'+'0'*64 if mutation=='hash' else canonical_sha256(body)
    with pytest.raises(ValueError):check(value)
