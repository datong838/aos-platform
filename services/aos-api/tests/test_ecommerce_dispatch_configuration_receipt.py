"""Synthetic receipt integrity cases are not current execution authorization."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID
import pytest
from tests.test_ecommerce_dispatch_configuration_contracts import request
from aos_api.ecommerce_dispatch_configuration_contracts import DispatchConfigurationRefreshRequest
from aos_api.ecommerce_dispatch_configuration_receipt import receipt_body, decode_receipt
from aos_api.asset_registry.canonical_json import canonical_sha256
import json


def row():
    req=DispatchConfigurationRefreshRequest.model_validate_json(json.dumps(request())).wire()
    value=dict(org_id=req['orgId'],project_id=req['projectId'],cutover_group_id=UUID(req['cutoverGroupId']),
        receipt_id=UUID('00000000-0000-4000-8000-000000000009'),revision=1,
        activation_operation_id=UUID('00000000-0000-4000-8000-000000000010'),
        activation_resume_receipt_id=UUID(req['sourceAuthorityRef']['resourceId']),
        installation_id=UUID(req['installationRef']['installationId']),generation=UUID(req['generation']),
        previous_receipt_id=None,previous_hash=None,actor='fixture-admin',idempotency_key=req['idempotencyKey'],
        request=req,request_hash=canonical_sha256(req),created_at=datetime(2026,9,16,tzinfo=timezone.utc))
    value['body']=receipt_body(value);value['content_hash']=canonical_sha256(value['body'])
    return value


def test_valid_immutable_receipt_roundtrip_without_execution_claim():
    value=row();result=decode_receipt(value)
    assert result['ref']['resourceType']=='DispatchConfigurationRefreshReceipt'
    assert result['body']==value['body'] and result['request']==value['request']
    result['body']['actor']='edited'
    assert value['body']['actor']=='fixture-admin'


@pytest.mark.parametrize('field,value',[
    ('org_id','dev-org'),('revision',2),('idempotency_key','other'),('actor','another'),
    ('request_hash','sha256:'+'f'*64),('content_hash','sha256:'+'e'*64),
    ('generation',UUID('00000000-0000-4000-8000-000000000099')),
])
def test_column_or_hash_drift_is_rejected(field,value):
    saved=row();saved[field]=value
    with pytest.raises(ValueError):decode_receipt(saved)


def test_rehashing_mixed_request_does_not_hide_column_drift():
    saved=row();saved['request']['orgId']='dev-org'
    saved['request_hash']=canonical_sha256(saved['request'])
    saved['body']=receipt_body(saved);saved['content_hash']=canonical_sha256(saved['body'])
    with pytest.raises(ValueError):decode_receipt(saved)
