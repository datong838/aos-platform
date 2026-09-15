"""Complete event dependency profile with real isolated core invocation proof."""
import hashlib
import json
from build_ecommerce_current_candidates import load_builder as previous_builder

METHOD='ecommerce_core_product_event_windows'
PAYLOAD=dict(schemaVersion='aos.product-event-window-request/v1',
    effectiveFrom='2026-09-16T00:00:00+00:00',effectiveUntil='2026-09-16T00:15:00+00:00',
    maxSourceAgeSeconds=3600,recoveryWindowSeconds=600,
    events=[dict(eventKey='a'*64,recordedAt='2026-09-16T00:01:00+00:00',sourceUpdatedAt='2026-09-16T00:00:00+00:00')])


def digest(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


async def probe(session):
    payload=json.loads(json.dumps(PAYLOAD))
    expected=dict(schemaVersion='aos.product-event-window-result/v1',requestHash=digest(payload),
        events=[dict(eventKey='a'*64,deadline='2026-09-16T00:11:00+00:00')])
    result=await session.invoke(METHOD,payload)
    if result!=expected:raise ValueError('installed core event window computation differs')
    return dict(method=METHOD,payloadHash=digest(PAYLOAD),resultHash=digest(result),
                executionAllowed=False,evidence='qualification-fixture-only')


def load_builder():
    builder=previous_builder()
    replacements={
        ('domain.ecommerce.core/1.3.0','domain.ecommerce.core','1.3.0','ecommerce_core'):
        ('domain.ecommerce.core/1.4.0','domain.ecommerce.core','1.4.0','ecommerce_core'),
        ('solution.ecommerce.growth/1.9.0','solution.ecommerce.growth','1.9.0','ecommerce_growth'):
        ('solution.ecommerce.growth/1.10.0','solution.ecommerce.growth','1.10.0','ecommerce_growth')}
    if builder.EXPECTED_RUNTIME_OPERATION_COUNT!=14 or any(builder.RUNTIME_CASES.count(k)!=1 for k in replacements):
        raise ValueError('previous event profile drifted')
    builder.RUNTIME_CASES=tuple(replacements.get(x,x) for x in builder.RUNTIME_CASES)
    builder.ALL_CASES=tuple(replacements.get(x,x) for x in builder.ALL_CASES)
    builder.EXPECTED_RUNTIME_OPERATION_COUNT=15
    previous=builder._qualify_session
    def qualify_session(**kwargs):
        methods=[c.get('operationId') if isinstance(c,dict) else getattr(c,'operation_id',None) for c in kwargs['contributions']]
        if METHOD in methods:return previous(**kwargs,probe=probe)
        return previous(**kwargs)
    builder._qualify_session=qualify_session
    return builder


if __name__=='__main__':raise SystemExit(load_builder().main())
