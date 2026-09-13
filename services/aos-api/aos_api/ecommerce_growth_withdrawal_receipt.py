"""Strict immutable withdrawal readback, without current execution authority."""
from copy import deepcopy
from datetime import datetime
from uuid import UUID
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_registration_receipt import decode_registration_receipt
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest
from aos_api.tenant_scope import TenantScope


def decode_withdrawal_receipt(row, *, registration_row, scope: TenantScope):
    if type(scope) is not TenantScope:
        raise TypeError('trusted withdrawal receipt scope required')
    try:
        origin=decode_registration_receipt(registration_row,scope=scope)
        body=row['payload']
        fields={'schemaVersion','tenant','receiptId','registrationReceiptRef','installationId','generation',
            'groupId','idempotencyKey','requestHash','actor','request','oldDispatchSnapshot',
            'releasedOperationCount','executable','createdAt'}
        if (type(body) is not dict or set(body)!=fields or (row['org_id'],row['project_id'])!=scope.key
                or body['tenant']!=dict(orgId=scope.org_id,projectId=scope.project_id)
                or body['schemaVersion']!='aos.ecommerce.first-dispatch-withdrawal-receipt/v1'
                or body['executable'] is not False or type(body['releasedOperationCount']) is not int
                or body['releasedOperationCount']!=9 or canonical_sha256(body)!=row['content_hash']
                or type(body['receiptId']) is not str or str(UUID(body['receiptId']))!=body['receiptId']):raise ValueError()
        for column,key in (('receipt_id','receiptId'),('idempotency_key','idempotencyKey'),('request_hash','requestHash')):
            if str(row[column])!=body[key]:raise ValueError()
        request=RegistrationWithdrawalRequest.model_validate(body['request'])
        ref=dict(resourceType='FirstDispatchRegistrationReceipt',resourceId=origin['receiptId'],revision=1,contentHash=origin['contentHash'])
        if (str(row['registration_receipt_id'])!=origin['receiptId']
                or canonical_sha256(body['registrationReceiptRef'])!=canonical_sha256(ref)
                or request.registrationReceiptRef.model_dump(mode='json')!=ref
                or request.request_hash()!=body['requestHash'] or request.idempotencyKey!=body['idempotencyKey']
                or any(body[k]!=origin[k] for k in ('installationId','generation','groupId'))
                or canonical_sha256(body['oldDispatchSnapshot'])!=canonical_sha256(origin['dispatchSnapshot'])
                or type(body['actor']) is not str or not 1<=len(body['actor'])<=240
                or not body['actor'].isprintable() or body['actor'].strip()!=body['actor']
                or datetime.fromisoformat(body['createdAt']).utcoffset() is None):raise ValueError()
        return dict(deepcopy(body),contentHash=row['content_hash'])
    except (KeyError,TypeError,ValueError,OverflowError):
        raise ValueError('WITHDRAWAL_RECEIPT_INVALID') from None
