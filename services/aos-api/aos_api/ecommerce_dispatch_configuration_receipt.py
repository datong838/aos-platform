"""Decode immutable maintenance history; current authority is checked separately."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID
import json

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_dispatch_configuration_contracts import DispatchConfigurationRefreshRequest


def _uuid(value):
    if type(value) not in (str,UUID) or str(UUID(str(value)))!=str(value):
        raise ValueError('canonical receipt identity required')
    return str(value)


def receipt_body(row):
    created=row['created_at']
    if not isinstance(created,datetime) or created.utcoffset() is None:
        raise ValueError('aware receipt time required')
    return dict(schemaVersion='aos.ecommerce.dispatch-configuration-refresh-receipt/v1',
        receiptId=_uuid(row['receipt_id']),revision=row['revision'],
        activationOperationId=_uuid(row['activation_operation_id']),
        activationResumeReceiptId=_uuid(row['activation_resume_receipt_id']),actor=row['actor'],
        request=deepcopy(row['request']),requestHash=row['request_hash'],
        createdAt=created.astimezone(timezone.utc).isoformat())


def decode_receipt(row):
    """No callback, connection, permission grant or dispatch mutation."""
    try:
        revision=row['revision']
        if type(revision) is not int or not 1<=revision<2**63:
            raise ValueError('positive receipt revision required')
        request=DispatchConfigurationRefreshRequest.model_validate_json(json.dumps(row['request'],allow_nan=False))
        actor=row['actor']
        if type(actor) is not str or not 1<=len(actor)<=240 or actor!=actor.strip() or not actor.isprintable():
            raise ValueError('canonical receipt actor required')
        if (request.wire()!=row['request'] or request.request_hash()!=row['request_hash']
            or (request.org_id,request.project_id)!=(row['org_id'],row['project_id'])
            or request.cutover_group_id!=_uuid(row['cutover_group_id'])
            or request.generation!=_uuid(row['generation'])
            or request.installation_ref.installation_id!=_uuid(row['installation_id'])
            or request.idempotency_key!=row['idempotency_key']):
            raise ValueError('receipt request projection differs')
        previous=request.source_authority_ref
        if revision==1:
            if (row['previous_receipt_id'] is not None or row['previous_hash'] is not None
                or previous.resource_type!='CutoverResumeReceipt' or previous.revision!=1
                or previous.resource_id!=_uuid(row['activation_resume_receipt_id'])):
                raise ValueError('initial receipt must retain original resume')
        elif (previous.resource_type!='DispatchConfigurationRefreshReceipt' or previous.revision!=revision-1
              or previous.resource_id!=_uuid(row['previous_receipt_id']) or previous.content_hash!=row['previous_hash']):
            raise ValueError('refresh receipt predecessor differs')
        body=receipt_body(row)
        if body!=row['body'] or canonical_sha256(body)!=row['content_hash']:
            raise ValueError('receipt body or content hash differs')
        return dict(ref=dict(resourceType='DispatchConfigurationRefreshReceipt',resourceId=_uuid(row['receipt_id']),
                    revision=revision,contentHash=row['content_hash']),body=body,request=request.wire())
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('configuration refresh receipt malformed') from exc
