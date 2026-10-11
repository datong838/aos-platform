"""Pure bounded calculation. Trusted source reading and admission stay in Host."""
from datetime import datetime, timedelta
import hashlib
import json
import re
from .product_source_event_window import _aware, _event_window_times


def _time(value):
    if type(value) is not str:
        raise ValueError('event window requires wire timestamps')
    try:
        return _aware(datetime.fromisoformat(value))
    except (ValueError, OverflowError):
        raise ValueError('event window timestamp invalid') from None


def calculate_windows(payload):
    if type(payload) is not dict or set(payload) != {'schemaVersion','effectiveFrom','effectiveUntil',
            'maxSourceAgeSeconds','recoveryWindowSeconds','events'}:
        raise ValueError('event window envelope invalid')
    if payload['schemaVersion'] != 'aos.product-event-window-request/v1':
        raise ValueError('event window schema invalid')
    start,end=_time(payload['effectiveFrom']),_time(payload['effectiveUntil'])
    if not timedelta(0)<end-start<=timedelta(days=1):
        raise ValueError('event window policy interval invalid')
    for name in ('maxSourceAgeSeconds','recoveryWindowSeconds'):
        if type(payload[name]) is not int or not 1<=payload[name]<=86400:
            raise ValueError('event window duration invalid')
    rows=payload['events']
    if type(rows) is not list or not 1<=len(rows)<=100:
        raise ValueError('event window batch invalid')
    seen=set();results=[]
    for row in rows:
        if type(row) is not dict or set(row)!={'eventKey','recordedAt','sourceUpdatedAt'}:
            raise ValueError('event window item invalid')
        key=row['eventKey']
        if type(key) is not str or re.fullmatch('[0-9a-f]{64}',key) is None or key in seen:
            raise ValueError('event window identity invalid')
        seen.add(key)
        _,_,deadline=_event_window_times(recorded_at=_time(row['recordedAt']),
            source_updated_at=row['sourceUpdatedAt'],effective_from=start,effective_until=end,
            max_source_age_seconds=payload['maxSourceAgeSeconds'],recovery_window_seconds=payload['recoveryWindowSeconds'])
        results.append(dict(eventKey=key,deadline=deadline.isoformat()))
    digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return dict(schemaVersion='aos.product-event-window-result/v1',requestHash='sha256:'+digest,events=results)
