"""Stored hold replay must bind both canonical row bytes and approved request."""
from copy import deepcopy
from uuid import UUID, uuid4
import pytest
from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore, ModelEvalBudgetBlocked
from aos_api.aip_budget_reservation_store import canonical_hash

@pytest.fixture
def hold():
    fields={'reservationId':'reservation_id','requestId':'request_id','requestHash':'request_hash','proposalId':'proposal_id','proposalHash':'proposal_hash','approvalEventId':'approval_event_id','budgetPolicyRef':'budget_policy_ref','budgetRevisionRef':'budget_revision_ref','priceRef':'price_ref','currency':'currency','upperBoundMinor':'upper_bound_minor','state':'state'}
    payload={'reservationId':str(uuid4()),'requestId':'request','requestHash':'a'*64,'proposalId':'proposal','proposalHash':'b'*64,'approvalEventId':'approval','budgetPolicyRef':{'assetId':'policy'},'budgetRevisionRef':{'resourceId':'budget'},'priceRef':{'resourceId':'price'},'currency':'CNY','upperBoundMinor':10,'state':'held'}
    row={column:deepcopy(payload[key]) for key,column in fields.items()};row['content_hash']=canonical_hash(payload,prefixed=True)
    return row,payload,fields

def test_exact_hold_preserves_uuid_and_payload(hold):
    row,payload,_=hold;row['reservation_id']=UUID(row['reservation_id'])
    before=deepcopy(row);AipModelEvalBudgetReservationStore._require_exact_hold(row,payload);assert row==before

@pytest.mark.parametrize('field',['content_hash','price_ref','budget_revision_ref','budget_policy_ref','currency','proposal_id','request_id','approval_event_id','upper_bound_minor','state'])
def test_hold_rejects_stored_fact_drift(hold,field):
    row,payload,_=hold;row[field]=999 if field=='upper_bound_minor' else 'drift'
    with pytest.raises(ModelEvalBudgetBlocked,match='hash'):AipModelEvalBudgetReservationStore._require_exact_hold(row,payload)

def test_coherently_rehashed_wrong_price_cannot_replay(hold):
    row,payload,_=hold;forged=deepcopy(payload);forged['priceRef']={'resourceId':'another-price'}
    row['price_ref']=forged['priceRef'];row['content_hash']=canonical_hash(forged,prefixed=True)
    with pytest.raises(ModelEvalBudgetBlocked,match='hash'):AipModelEvalBudgetReservationStore._require_exact_hold(row,payload)

@pytest.mark.parametrize('missing',['content_hash','price_ref','reservation_id'])
def test_missing_immutable_field_is_domain_rejection(hold,missing):
    row,payload,_=hold;row.pop(missing)
    with pytest.raises(ModelEvalBudgetBlocked,match='hash'):AipModelEvalBudgetReservationStore._require_exact_hold(row,payload)
