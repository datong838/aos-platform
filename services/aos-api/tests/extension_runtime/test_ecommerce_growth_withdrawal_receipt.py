from copy import deepcopy
from uuid import uuid4
import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest
from aos_api.ecommerce_growth_withdrawal_receipt import decode_withdrawal_receipt
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_registration_receipt import row as registration_row


def inputs():
    original=registration_row();o=deepcopy(original['payload'])
    ref=dict(resourceType='FirstDispatchRegistrationReceipt',resourceId=o['receiptId'],revision=1,contentHash=original['content_hash'])
    req=RegistrationWithdrawalRequest(registrationReceiptRef=ref,expectedInstallationEtag=5,idempotencyKey='withdraw-key')
    body=dict(schemaVersion='aos.ecommerce.first-dispatch-withdrawal-receipt/v1',tenant=o['tenant'],
        receiptId=str(uuid4()),registrationReceiptRef=ref,installationId=o['installationId'],generation=o['generation'],
        groupId=o['groupId'],idempotencyKey=req.idempotencyKey,requestHash=req.request_hash(),actor='actor',
        request=req.model_dump(mode='json'),oldDispatchSnapshot=o['dispatchSnapshot'],releasedOperationCount=9,
        executable=False,createdAt='2026-09-13T01:00:00+00:00')
    value=dict(org_id='org-a',project_id='project-a',receipt_id=body['receiptId'],registration_receipt_id=o['receiptId'],
        idempotency_key=body['idempotencyKey'],request_hash=body['requestHash'],payload=body,content_hash=canonical_sha256(body))
    return dict(row=value,registration_row=original,scope=TenantScope('org-a','project-a'))


def test_exact_historical_readback_detached():
    args=inputs();before=deepcopy(args);result=decode_withdrawal_receipt(**args)
    result['oldDispatchSnapshot'][0]['revision']=99
    assert args==before


@pytest.mark.parametrize('change',['hash','tenant','ref','float_ref','origin','snapshot','count','actor','clock','etag','extra','executable'])
def test_rehashed_corruption_rejected(change):
    args=inputs();row=args['row'];body=row['payload']
    if change=='hash':row['content_hash']='sha256:'+'0'*64
    elif change=='tenant':row['org_id']='other'
    elif change=='ref':body['registrationReceiptRef']['contentHash']='sha256:'+'0'*64
    elif change=='float_ref':body['registrationReceiptRef']['revision']=1.0
    elif change=='origin':row['registration_receipt_id']=str(uuid4())
    elif change=='snapshot':body['oldDispatchSnapshot'][0]['revision']=2
    elif change=='count':body['releasedOperationCount']=9.0
    elif change=='actor':body['actor']=' '
    elif change=='clock':body['createdAt']='2026-09-13T01:00:00'
    elif change=='etag':body['request']['expectedInstallationEtag']=6
    elif change=='executable':body['executable']=True
    else:body['extra']='unexpected'
    if change!='hash':row['content_hash']=canonical_sha256(body)
    with pytest.raises(ValueError):decode_withdrawal_receipt(**args)
