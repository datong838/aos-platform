from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from tests.test_ecommerce_business_investigation_case import case_payload,successor
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision,BusinessInvestigationCaseStore,BusinessInvestigationCaseLifecycle
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.tenant_scope import TenantScope
import aos_api.ecommerce_product_event_host_service as service


def active():
    return successor(BusinessInvestigationCaseRevision.model_validate(case_payload()),'ACTIVE')

@pytest.mark.parametrize('fault',[None,'title','timestamp','hash','unknown'])
def test_stored_datetime_representation_is_normalized_but_tampering_rejected(fault):
    model=active();value=model.model_dump(mode='json',by_alias=True)
    value['createdAt']=model.created_at.isoformat()
    if fault=='title':value['title']='tampered'
    elif fault=='timestamp':value['createdAt']='2020-01-01T00:00:00Z'
    elif fault=='hash':value['contentHash']='sha256:'+'0'*64
    elif fault=='unknown':value['approved']=True
    if fault:
        with pytest.raises(ValueError):service._current_case_authority(value)
    else:
        checked=service._current_case_authority(value)
        assert checked==model.model_dump(mode='json',by_alias=True)
        assert checked['contentHash']==canonical_hash({k:v for k,v in checked.items() if k!='contentHash'},prefixed=True)


def test_transition_writes_the_same_canonical_payload_that_was_hashed(monkeypatch):
    previous=BusinessInvestigationCaseRevision.model_validate(case_payload())
    captured=[]
    class Connection:
        def execute(self,query,args):
            if 'SELECT case_id,expected_version,authority_data' in query:return SimpleNamespace(fetchone=lambda:None)
            payload=args[-1].obj;captured.append(deepcopy(payload))
            return SimpleNamespace(fetchone=lambda:dict(authority_data=payload,replayed=False))
        def commit(self):pass
    @contextmanager
    def connect(scope):yield Connection()
    store=BusinessInvestigationCaseStore(connect)
    monkeypatch.setattr(store,'get',lambda *args:previous)
    store.transition(TenantScope('org-org','dev-project'),previous.case_id,BusinessInvestigationCaseLifecycle.ACTIVE,
        expected_version=1,idempotency_key='canonical-date-test',actor='owner',occurred_at=datetime(2026,9,16,tzinfo=timezone.utc))
    assert len(captured)==1
    payload=captured[0]
    assert payload['createdAt']=='2026-09-16T00:00:00Z'
    assert payload['contentHash']==canonical_hash({k:v for k,v in payload.items() if k!='contentHash'},prefixed=True)
