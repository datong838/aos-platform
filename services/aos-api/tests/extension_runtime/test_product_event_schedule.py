from copy import deepcopy
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'bundles/solutions/ecommerce-growth/backend'))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'packages/aos-extension-sdk/python'))
from ecommerce_growth.ecommerce_business_investigation_case import canonical_hash
from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy


def ref(kind, identity='test'):
    return dict(resourceType=kind, resourceId=identity, revision=1,
                contentHash='sha256:'+'a'*64, receiptId=None)


def seal(body):
    body['contentHash'] = canonical_hash({k:v for k,v in body.items() if k!='contentHash'})
    return body


@pytest.fixture
def body():
    return seal(dict(schemaVersion='aos.ecommerce.product-event-schedule-policy/v1',
        tenant=dict(orgId='org-org',projectId='dev-project'),schedulePolicyId='product-change',
        revision=1,priorRef=None,caseRef=ref('BusinessInvestigationCaseRevision'),
        sourceSelectionRef=ref('SourceSelectionRevision'),methodRef=ref('InvestigationProfileRevision'),
        platform='niushop',shopId='1',objectTypes=['Product','ProductSku'],
        effectiveFrom='2026-09-13T06:00:00+00:00',effectiveUntil='2026-09-13T07:00:00+00:00',
        maxSourceAgeSeconds=3600,recoveryWindowSeconds=600,
        createdBy='installer',createdAt='2026-09-13T05:00:00+00:00'))


def test_roundtrip_immutable_and_no_execution_grant(body):
    before=deepcopy(body)
    value=ProductEventSchedulePolicy.from_authority(body)
    assert value.authority_payload()==before
    assert value==ProductEventSchedulePolicy.from_authority(before)
    assert body==before
    body['objectTypes'].clear()
    assert value.object_types==('Product','ProductSku')
    assert not {'approved','enabled','executable'} & value.authority_payload().keys()


@pytest.mark.parametrize('key,value',[
    ('revision',True),('revision','1'),('revision',1.0),('revision',0),
    ('shopId',' '),('shopId','*'),('platform','niushop '),
    ('objectTypes',[]),('objectTypes',['Customer']),('objectTypes',['Product','Product']),
    ('objectTypes',['ProductSku','Product']),('maxSourceAgeSeconds',True),
    ('recoveryWindowSeconds',86401),('effectiveUntil','2026-09-13T06:00:00+00:00'),
    ('effectiveFrom','2026-09-13T06:00:00'),('createdAt','2026-09-13T08:00:00+00:00'),
    ('approved',True),('schemaVersion','other'),
])
def test_rehashed_invalid_policy_still_rejected(body,key,value):
    body[key]=value
    with pytest.raises(ValueError):ProductEventSchedulePolicy.from_authority(seal(body))


@pytest.mark.parametrize('key,value',[
    ('resourceType','Other'),('revision',True),('resourceId',' test'),('receiptId','receipt'),
    ('contentHash','bad'),('extra','unexpected'),
])
def test_strict_source_reference(body,key,value):
    body['sourceSelectionRef'][key]=value
    with pytest.raises(ValueError):ProductEventSchedulePolicy.from_authority(seal(body))


def test_hash_drift_rejected(body):
    body['shopId']='2'
    with pytest.raises(ValueError):ProductEventSchedulePolicy.from_authority(body)


def test_successor_requires_contiguous_exact_predecessor_and_same_case(body):
    first=ProductEventSchedulePolicy.from_authority(body)
    body['revision']=2
    body['priorRef']=ref('SchedulePolicyRevision','product-change')
    body['priorRef']['contentHash']=first.content_hash
    second=ProductEventSchedulePolicy.from_authority(seal(body))
    second.validate_successor(first)
    body['caseRef']['resourceId']='other'
    changed=ProductEventSchedulePolicy.from_authority(seal(body))
    with pytest.raises(ValueError):changed.validate_successor(first)
    body['caseRef']['resourceId']='test'
    body['priorRef']['contentHash']='sha256:'+'b'*64
    changed=ProductEventSchedulePolicy.from_authority(seal(body))
    with pytest.raises(ValueError):changed.validate_successor(first)


@pytest.mark.parametrize('key,value', [('createdAt','2026-09-12T05:00:00+00:00'),
                                       ('effectiveFrom','2026-09-13T05:00:00+00:00')])
def test_successor_cannot_backdate_authority(body,key,value):
    first=ProductEventSchedulePolicy.from_authority(body)
    body['revision']=2
    body['priorRef']=ref('SchedulePolicyRevision','product-change')
    body['priorRef']['contentHash']=first.content_hash
    body[key]=value
    second=ProductEventSchedulePolicy.from_authority(seal(body))
    with pytest.raises(ValueError):second.validate_successor(first)
