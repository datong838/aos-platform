from copy import deepcopy
import pytest

from test_product_event_schedule import body, seal, ref
from tests.test_ecommerce_business_investigation_schedule import case as host_case
from ecommerce_growth.ecommerce_business_investigation_case import BusinessInvestigationCase, canonical_hash
from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy
from ecommerce_growth.ecommerce_product_event_binding import prepare_event_case_binding


@pytest.fixture
def pair(body):
    raw=host_case().model_dump(by_alias=True,mode='json')
    for key,value in raw.items():
        if key.endswith('Ref') and isinstance(value,dict):value['receiptId']=None
    raw['contentHash']=canonical_hash({k:v for k,v in raw.items() if k!='contentHash'})
    current=BusinessInvestigationCase.from_authority(raw)
    body['caseRef']=ref('BusinessInvestigationCaseRevision',current.case_id)
    body['caseRef'].update(revision=current.revision,contentHash=current.content_hash)
    body['methodRef']=raw['investigationProfileRef']
    return current,ProductEventSchedulePolicy.from_authority(seal(body))


def test_binding_is_deterministic_and_changes_only_schedule_link(pair):
    current,policy=pair
    result=prepare_event_case_binding(current,policy)
    assert result==prepare_event_case_binding(current,policy)
    assert result.case.revision==current.revision+1
    changed={'revision','version','priorRef','schedulePolicyRef','createdBy','createdAt','contentHash'}
    assert {k:v for k,v in result.case.authority_payload().items() if k not in changed}=={
        k:v for k,v in current.authority_payload().items() if k not in changed}
    assert result.case.prior_ref.content_hash==current.content_hash
    assert result.case.schedule_policy_ref.content_hash==policy.content_hash
    assert result.request_hash.startswith('sha256:')


@pytest.mark.parametrize('field', ['caseRef','methodRef','tenant'])
def test_rehashed_wrong_authority_is_rejected(pair,field):
    current,policy=pair; raw=deepcopy(policy.authority_payload())
    if field=='tenant':raw[field]['orgId']='another'
    else:raw[field]['contentHash']='sha256:'+'b'*64
    changed=ProductEventSchedulePolicy.from_authority(seal(raw))
    with pytest.raises(ValueError):prepare_event_case_binding(current,changed)


def test_successor_binds_both_current_case_and_previous_policy(pair):
    current,policy=pair; first=prepare_event_case_binding(current,policy)
    raw=policy.authority_payload();raw['revision']=2
    raw['priorRef']=ref('SchedulePolicyRevision',policy.policy_id)
    raw['priorRef']['contentHash']=policy.content_hash
    raw['caseRef'].update(revision=first.case.revision,contentHash=first.case.content_hash)
    successor=ProductEventSchedulePolicy.from_authority(seal(raw))
    result=prepare_event_case_binding(first.case,successor,previous_policy=policy)
    assert result.case.revision==current.revision+2
    with pytest.raises(ValueError):prepare_event_case_binding(first.case,successor)
    with pytest.raises(ValueError):prepare_event_case_binding(first.case,policy)


@pytest.mark.parametrize('change', ['closed','time'])
def test_closed_case_or_time_regression_is_rejected(pair,change):
    current,policy=pair; raw=current.authority_payload()
    if change=='closed':raw['lifecycle']='CLOSED'
    else:raw['createdAt']='2026-09-13T05:01:00Z'
    raw['contentHash']=canonical_hash({k:v for k,v in raw.items() if k!='contentHash'})
    changed=BusinessInvestigationCase.from_authority(raw)
    p=policy.authority_payload();p['caseRef']['contentHash']=changed.content_hash
    with pytest.raises(ValueError):prepare_event_case_binding(changed,ProductEventSchedulePolicy.from_authority(seal(p)))
