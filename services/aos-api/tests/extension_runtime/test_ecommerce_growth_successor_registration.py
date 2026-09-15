from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest, preview_registration
from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest, decode_successor_receipt
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_registration_contracts import payload


def request_payload():
    return dict(schemaVersion='aos.ecommerce.successor-dispatch-registration/v1',
        registration=payload(), expectedGroupRevision=5,
        predecessorDetachReceiptRef=dict(resourceType='DispatchDisableDetachReceipt',resourceId=str(uuid4()),
                                         revision=1,contentHash='sha256:'+'a'*64))


def receipt_row():
    raw=request_payload();request=SuccessorDispatchRegistrationRequest.model_validate(raw)
    registration=request.registration
    snapshot=preview_registration(registration)['proposedDispatchSnapshot']
    for item in snapshot:item.update(revision=5,cutoverGroupRevision=5)
    body=dict(schemaVersion='aos.ecommerce.successor-dispatch-registration-receipt/v1',
        tenant=dict(orgId='org-org',projectId='dev-project'),receiptId=str(uuid4()),
        installationId=registration.installationRef.installation_id,generation=registration.generation,
        groupId=registration.groupId,requestHash=request.request_hash(),idempotencyKey=registration.idempotencyKey,
        actor='operator',request=raw,dispatchSnapshot=snapshot,executable=False,createdAt=datetime.now(timezone.utc).isoformat())
    row=dict(org_id='org-org',project_id='dev-project',payload=body,content_hash=canonical_sha256(body))
    for col,key in [('receipt_id','receiptId'),('installation_id','installationId'),('generation','generation'),
                    ('group_id','groupId'),('idempotency_key','idempotencyKey'),('request_hash','requestHash')]:row[col]=body[key]
    return row


def test_successor_preserves_original_request_bytes_and_full_hash_binding():
    raw=request_payload();first=FirstDispatchRegistrationRequest.model_validate(raw['registration'])
    successor=SuccessorDispatchRegistrationRequest.model_validate(raw)
    assert successor.registration.request_hash()==first.request_hash()
    for key in ('expectedGroupRevision','predecessorDetachReceiptRef'):
        changed=deepcopy(raw)
        if key=='expectedGroupRevision':changed[key]+=1
        else:changed[key]['contentHash']='sha256:'+'b'*64
        assert SuccessorDispatchRegistrationRequest.model_validate(changed).request_hash()!=successor.request_hash()


def test_successor_receipt_is_nonexecuting_and_detached_copy():
    row=receipt_row();result=decode_successor_receipt(row,scope=TenantScope('org-org','dev-project'))
    assert result['executable'] is False
    result['dispatchSnapshot'][0]['revision']=90
    assert row['payload']['dispatchSnapshot'][0]['revision']==5


@pytest.mark.parametrize('fault',['tenant','hash','request','actor','group','fence','operation','revision','execution'])
def test_successor_receipt_rejects_tamper_even_when_outer_hash_is_recomputed(fault):
    row=receipt_row();body=row['payload']
    if fault=='tenant':body['tenant']['orgId']='dev-org'
    elif fault=='hash':row['content_hash']='sha256:'+'f'*64
    elif fault=='request':body['request']['predecessorDetachReceiptRef']['contentHash']='sha256:'+'b'*64
    elif fault=='actor':body['actor']=' operator'
    elif fault=='group':body['dispatchSnapshot'][0]['cutoverGroupRevision']=4
    elif fault=='fence':body['dispatchSnapshot'][0]['operationFence']=False
    elif fault=='operation':body['dispatchSnapshot'].pop()
    elif fault=='revision':body['dispatchSnapshot'][0]['revision']=True
    else:body['executable']=True
    if fault!='hash':row['content_hash']=canonical_sha256(body)
    with pytest.raises(ValueError,match='SUCCESSOR_REGISTRATION_RECEIPT_INVALID'):
        decode_successor_receipt(row,scope=TenantScope('org-org','dev-project'))


def test_successor_origin_uses_explicit_reference_type_and_exact_snapshot():
    from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef, verify_registration_origin
    row=receipt_row();body=row['payload'];inner=body['request']['registration']
    args=dict(row=row,scope=TenantScope('org-org','dev-project'),dispatch_snapshot=body['dispatchSnapshot'],
        installation_id=body['installationId'],generation=body['generation'],execution_epoch=inner['executionEpoch'],
        binding_revision=inner['bindingRevision'])
    ref=RegistrationReceiptRef(resourceType='SuccessorDispatchRegistrationReceipt',resourceId=body['receiptId'],
                               revision=1,contentHash=row['content_hash'])
    assert verify_registration_origin(receipt_ref=ref,**args).request_hash()==FirstDispatchRegistrationRequest.model_validate(inner).request_hash()
    wrong=RegistrationReceiptRef(**{**ref.model_dump(),'resourceType':'FirstDispatchRegistrationReceipt'})
    with pytest.raises(ValueError,match='REGISTRATION_ORIGIN_INVALID'):
        verify_registration_origin(receipt_ref=wrong,**args)
