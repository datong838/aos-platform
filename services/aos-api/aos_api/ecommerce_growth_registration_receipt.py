"""Integrity of stored registration history; not authorization to execute it."""
from copy import deepcopy
from datetime import datetime

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest, preview_registration
from aos_api.tenant_scope import TenantScope


def decode_registration_receipt(row, *, scope: TenantScope) -> dict:
    if type(scope) is not TenantScope:
        raise TypeError('trusted receipt scope required')
    try:
        body=row['payload']
        required={'schemaVersion','tenant','receiptId','installationId','generation','groupId',
                  'requestHash','idempotencyKey','actor','request','dispatchSnapshot','executable','createdAt'}
        if type(body) is not dict or set(body)!=required:
            raise ValueError()
        if ((row['org_id'],row['project_id'])!=scope.key
                or body['tenant']!=dict(orgId=scope.org_id,projectId=scope.project_id)
                or body['schemaVersion']!='aos.ecommerce.first-dispatch-registration-receipt/v1'
                or body['executable'] is not False or canonical_sha256(body)!=row['content_hash']):
            raise ValueError()
        for column,key in (('receipt_id','receiptId'),('installation_id','installationId'),
            ('generation','generation'),('group_id','groupId'),('idempotency_key','idempotencyKey'),('request_hash','requestHash')):
            if str(row[column])!=body[key]:raise ValueError()
        request=FirstDispatchRegistrationRequest.model_validate(body['request'])
        if (request.request_hash()!=body['requestHash']
            or request.installationRef.installation_id!=body['installationId']
            or request.generation!=body['generation'] or request.groupId!=body['groupId']
            or request.idempotencyKey!=body['idempotencyKey']
            or canonical_sha256(body['dispatchSnapshot'])!=canonical_sha256(preview_registration(request)['proposedDispatchSnapshot'])
            or type(body['actor']) is not str or not 1<=len(body['actor'])<=240
            or not body['actor'].isprintable() or body['actor'].strip()!=body['actor']
            or datetime.fromisoformat(body['createdAt']).utcoffset() is None):
            raise ValueError()
        return dict(deepcopy(body),contentHash=row['content_hash'])
    except (KeyError,TypeError,ValueError,OverflowError):
        raise ValueError('REGISTRATION_RECEIPT_INVALID') from None
