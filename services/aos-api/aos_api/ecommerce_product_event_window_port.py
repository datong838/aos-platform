"""One installed core calculation; no source authority, retries or writes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker


def _time(value):
    if type(value) is not str:
        raise ValueError('event window timestamp required')
    try:
        result=datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError('timezone required')
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError('event window timestamp invalid') from None


def _request(payload):
    if type(payload) is not dict or set(payload)!={'schemaVersion','effectiveFrom','effectiveUntil',
            'maxSourceAgeSeconds','recoveryWindowSeconds','events'}:
        raise ValueError('event window request invalid')
    canonical_json(payload)
    if payload['schemaVersion']!='aos.product-event-window-request/v1':
        raise ValueError('event window request schema invalid')
    start,end=_time(payload['effectiveFrom']),_time(payload['effectiveUntil'])
    if not timedelta(0)<end-start<=timedelta(days=1):
        raise ValueError('event window policy interval invalid')
    for name in ('maxSourceAgeSeconds','recoveryWindowSeconds'):
        if type(payload[name]) is not int or not 1<=payload[name]<=86400:
            raise ValueError('event window duration invalid')
    rows=payload['events']
    if type(rows) is not list or not 1<=len(rows)<=100:
        raise ValueError('bounded event window batch required')
    ceilings=[];seen=set()
    for row in rows:
        if type(row) is not dict or set(row)!={'eventKey','sourceUpdatedAt','recordedAt'}:
            raise ValueError('event window metadata invalid')
        key=row['eventKey']
        if type(key) is not str or re.fullmatch('[0-9a-f]{64}',key) is None or key in seen:
            raise ValueError('event window keys invalid')
        seen.add(key)
        source,recorded=_time(row['sourceUpdatedAt']),_time(row['recordedAt'])
        if not start<=recorded<end or source>recorded:
            raise ValueError('event window source time invalid')
        try:
            ceilings.append(min(end,source+timedelta(seconds=payload['maxSourceAgeSeconds']),
                recorded+timedelta(seconds=payload['recoveryWindowSeconds'])))
        except OverflowError:
            raise ValueError('event window ceiling invalid') from None
    return ceilings


class InstalledProductEventWindowPort:
    def __init__(self,invoker):
        if type(invoker) is not CurrentInstalledPackageInvoker:
            raise TypeError('exact installed package invoker required')
        if invoker.package_id!='domain.ecommerce.core':
            raise ValueError('event windows require current core package')
        self._invoker=invoker

    async def calculate(self,payload):
        ceilings=_request(payload)
        snapshot=deepcopy(payload)
        digest=canonical_sha256(snapshot)
        if self._invoker.package_id!='domain.ecommerce.core':
            raise ValueError('event window package changed')
        result=await self._invoker('ecommerce_core_product_event_windows',deepcopy(snapshot))
        if self._invoker.package_id!='domain.ecommerce.core':
            raise ValueError('event window package changed')
        if (type(result) is not dict or set(result)!={'schemaVersion','requestHash','events'}
                or result['schemaVersion']!='aos.product-event-window-result/v1'
                or result['requestHash']!=digest or type(result['events']) is not list
                or len(result['events'])!=len(snapshot['events'])):
            raise ValueError('event window result differs')
        canonical_json(result)
        for row,original,ceiling in zip(result['events'],snapshot['events'],ceilings):
            if type(row) is not dict or set(row)!={'eventKey','deadline'} or row['eventKey']!=original['eventKey']:
                raise ValueError('event window result identity differs')
            deadline=_time(row['deadline'])
            if deadline.microsecond or deadline.isoformat()!=row['deadline'] or deadline>ceiling:
                raise ValueError('event window result exceeds fixed bound')
        return deepcopy(result)
