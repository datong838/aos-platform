"""Nonexecuting successor provenance; current authority belongs to the Owner."""
from copy import deepcopy
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.tenant_scope import TenantScope


class PredecessorDetachReceiptRef(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              hide_input_in_errors=True, revalidate_instances='always')
    resourceType: Literal['DispatchDisableDetachReceipt']
    resourceId: str
    revision: StrictInt = Field(ge=1, le=1)
    contentHash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')

    @field_validator('resourceId')
    @classmethod
    def canonical_identity(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical detach identity required')
        return value


class SuccessorDispatchRegistrationRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              hide_input_in_errors=True, revalidate_instances='always')
    schemaVersion: Literal['aos.ecommerce.successor-dispatch-registration/v1']
    registration: FirstDispatchRegistrationRequest
    expectedGroupRevision: StrictInt = Field(ge=1, le=2**63-1)
    predecessorDetachReceiptRef: PredecessorDetachReceiptRef

    def request_hash(self):
        checked=type(self).model_validate(self.model_dump(mode='python',by_alias=True))
        return canonical_sha256(checked.model_dump(mode='json',by_alias=True))


def require_successor_snapshot(snapshot, request):
    if type(request) is not SuccessorDispatchRegistrationRequest or type(snapshot) is not list:
        raise ValueError('strict successor request and snapshot required')
    expected=sorted(ECOMMERCE_GROWTH_OPERATIONS)
    if len(snapshot)!=len(expected):
        raise ValueError('exact nine legacy entries required')
    keys={'operationId','handlerKind','installationId','generation','executionEpoch',
          'operationFence','revision','cutoverGroupId','cutoverGroupRevision'}
    for operation,item in zip(expected,snapshot):
        if (type(item) is not dict or set(item)!=keys or item['operationId']!=operation
            or item['handlerKind']!='legacy' or item['operationFence'] is not True
            or any(item[k] is not None for k in ('installationId','generation','executionEpoch'))
            or type(item['revision']) is not int or not 1<=item['revision']<=2**63-1
            or type(item['cutoverGroupRevision']) is not int
            or item['cutoverGroupRevision']!=request.expectedGroupRevision
            or item['cutoverGroupId']!=request.registration.groupId):
            raise ValueError('successor legacy snapshot differs')


def decode_successor_receipt(row, *, scope):
    if type(scope) is not TenantScope:
        raise TypeError('trusted successor tenant required')
    try:
        body=row['payload']
        keys={'schemaVersion','tenant','receiptId','installationId','generation','groupId',
              'requestHash','idempotencyKey','actor','request','dispatchSnapshot','executable','createdAt'}
        if (type(body) is not dict or set(body)!=keys
            or body['schemaVersion']!='aos.ecommerce.successor-dispatch-registration-receipt/v1'
            or (row['org_id'],row['project_id'])!=scope.key
            or body['tenant']!=dict(orgId=scope.org_id,projectId=scope.project_id)
            or body['executable'] is not False or canonical_sha256(body)!=row['content_hash']):
            raise ValueError()
        for column,key in (('receipt_id','receiptId'),('installation_id','installationId'),
            ('generation','generation'),('group_id','groupId'),('idempotency_key','idempotencyKey'),('request_hash','requestHash')):
            if str(row[column])!=body[key]:raise ValueError()
        if str(UUID(body['receiptId']))!=body['receiptId']:raise ValueError()
        request=SuccessorDispatchRegistrationRequest.model_validate(body['request'])
        registration=request.registration
        if (request.request_hash()!=body['requestHash']
            or registration.installationRef.installation_id!=body['installationId']
            or registration.generation!=body['generation'] or registration.groupId!=body['groupId']
            or registration.idempotencyKey!=body['idempotencyKey']
            or type(body['actor']) is not str or not 1<=len(body['actor'])<=240
            or not body['actor'].isprintable() or body['actor'].strip()!=body['actor']
            or datetime.fromisoformat(body['createdAt']).utcoffset() is None):
            raise ValueError()
        require_successor_snapshot(body['dispatchSnapshot'],request)
        return dict(deepcopy(body),contentHash=row['content_hash'])
    except (KeyError,TypeError,ValueError,OverflowError):
        raise ValueError('SUCCESSOR_REGISTRATION_RECEIPT_INVALID') from None
