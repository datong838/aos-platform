from copy import deepcopy
import pytest
from test_product_source_event_window import timed_event, event, window, AT
from ecommerce_core import handle, register
from ecommerce_core.product_source_event_window_operation import calculate_windows


def request(row):
    return dict(schemaVersion='aos.product-event-window-request/v1',effectiveFrom=AT.isoformat(),
        effectiveUntil=AT.replace(hour=7).isoformat(),maxSourceAgeSeconds=3600,recoveryWindowSeconds=600,
        events=[dict(eventKey=row['event_key'],recordedAt=row['created_at'].isoformat(),
                     sourceUpdatedAt=row['payload']['record']['source_updated_at'])])


def test_registered_pure_calculation_matches_original_domain_rule(timed_event):
    payload=request(timed_event);before=deepcopy(payload)
    result=handle('ecommerce_core_product_event_windows',payload,None)
    assert result==calculate_windows(payload)
    assert result['events']==[dict(eventKey=timed_event['event_key'],deadline=window(timed_event).deadline.isoformat())]
    assert set(result)=={'schemaVersion','requestHash','events'}
    assert payload==before
    assert any(c['operationId']=='ecommerce_core_product_event_windows' for c in register(None)['contributions'])


@pytest.mark.parametrize('change',['extra','empty','duplicate','too_many','bool','naive','future','extra_event','hash','window'])
def test_malformed_window_request_rejected(timed_event,change):
    p=request(timed_event)
    if change=='extra':p['approved']=True
    if change=='empty':p['events']=[]
    if change=='duplicate':p['events']*=2
    if change=='too_many':p['events']*=101
    if change=='bool':p['maxSourceAgeSeconds']=True
    if change=='naive':p['events'][0]['recordedAt']='2026-09-13T06:00:00'
    if change=='future':p['events'][0]['sourceUpdatedAt']='2026-09-13T06:00:01+00:00'
    if change=='extra_event':p['events'][0]['payload']={}
    if change=='hash':p['events'][0]['eventKey']='bad'
    if change=='window':p['effectiveUntil']='2026-09-15T06:00:00+00:00'
    with pytest.raises(ValueError):calculate_windows(p)


def test_old_source_remains_expired_and_replay_fixed(timed_event):
    p=request(timed_event);p['events'][0]['sourceUpdatedAt']='2026-09-13T01:00:00+00:00'
    assert calculate_windows(p)['events'][0]['deadline']=='2026-09-13T02:00:00+00:00'
    assert calculate_windows(p)==calculate_windows(deepcopy(p))


def test_other_core_operation_stays_fenced():
    with pytest.raises(PermissionError):handle('ecommerce_core_object_describe',{},None)
