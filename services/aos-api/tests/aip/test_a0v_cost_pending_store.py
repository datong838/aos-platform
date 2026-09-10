from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, BudgetReservationBlocked, BudgetReservationConflict
from aos_api.aip_budget_reservation_contracts import BudgetExactRef, exact_ref_payload
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')
USAGE = BudgetExactRef(resourceType='UsageReceipt',resourceId='u',revision=1,contentHash='sha256:'+'a'*64)


def make_store(state):
    events = []
    row = {'state':state,'invocation_id':'inv','usage_receipt_refs':[exact_ref_payload(USAGE)]}
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield SimpleNamespace(execute=lambda _: SimpleNamespace(fetchone=lambda: {'now':datetime.now(UTC)}))
    store = AipBudgetReservationStore(connect_factory=connect)
    store._reservation_by_id = lambda *a,**k: row
    store._view = lambda *a,**k: k['replayed']
    store._assert_provider_receipt_replay = lambda *a,**k: events.append('replay')
    store._require_deferred_cost_authority = lambda *a: events.append('authority')
    store._usage_authority = lambda *a,**k: events.append('usage')
    store._record_provider_receipt = lambda *a,**k: events.append('result') or USAGE
    store._transition_reservation = lambda *a,**k: events.append(k['state'])
    store._update_invocation_state = lambda *a: events.append('invocation')
    return store, events, row


def complete(store, **patch):
    args=dict(provider_result_hash='b'*64,usage_receipt_refs=(USAGE,),evidence_refs=(),actor='m1')
    return store.complete_cost_pending(SCOPE,'r',**(args|patch))


@pytest.mark.parametrize('state',['submitted','unknown'])
def test_deferral_checks_authority_and_usage_before_recording_result(state):
    store, events, _ = make_store(state)
    assert complete(store) is False
    assert events == ['authority','usage','result','cost_pending','invocation']


def test_pending_replay_does_not_write_or_reauthorize():
    store,events,row=make_store('cost_pending')
    assert complete(store) is True
    assert events==['replay']
    row['usage_receipt_refs']=[]
    with pytest.raises(BudgetReservationConflict): complete(store)


@pytest.mark.parametrize('state',['held','released','settled'])
def test_invalid_source_state_cannot_defer(state):
    store,events,_=make_store(state)
    with pytest.raises(BudgetReservationConflict): complete(store)
    assert events==[]


def test_authority_failure_does_not_record_completion():
    store,events,_=make_store('submitted')
    def blocked(*a): raise BudgetReservationBlocked('denied')
    store._require_deferred_cost_authority=blocked
    with pytest.raises(BudgetReservationBlocked): complete(store)
    assert events==[]
