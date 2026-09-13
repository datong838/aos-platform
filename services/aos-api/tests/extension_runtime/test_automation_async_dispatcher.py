import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.automation_dispatcher import dispatch_one_occurrence_async
from aos_api.automation_occurrence_store import ClaimTarget
from aos_api.tenant_scope import TenantScope


def test_async_dispatch_uses_exact_target_and_completion_time():
    events = []
    started = datetime.now(UTC)
    completed = started + timedelta(minutes=6)
    times = iter([started, completed])
    target = ClaimTarget('analysis', uuid4(), uuid4())
    claim = SimpleNamespace(occurrence_id=uuid4())
    store = SimpleNamespace(
        reconcile_expired_claims=lambda scope, **kw: events.append(('reconcile', kw)),
        claim_next=lambda scope, **kw: (events.append(('claim', kw)), claim)[1],
        record_target_receipt=lambda scope, **kw: events.append(('receipt', kw)),
    )
    async def handler(value):
        assert value is claim
        await asyncio.sleep(0)
        return {'resourceId': 'receipt'}
    assert asyncio.run(dispatch_one_occurrence_async(TenantScope('org-org', 'dev-project'),
        owner='worker', target=target, handler=handler, store=store, clock=lambda: next(times)))
    assert events[1][1]['target'] == target
    assert events[-1][1]['occurred_at'] == completed


@pytest.mark.parametrize('outcome', ['timeout', 'empty', 'cancel', 'receipt-error', 'no-claim'])
def test_async_dispatch_does_not_retry_unknown_outcome(outcome):
    calls = []
    claim = SimpleNamespace(occurrence_id=uuid4())
    def record(*args, **kwargs):
        calls.append('record')
        raise RuntimeError('receipt unavailable')
    store = SimpleNamespace(
        reconcile_expired_claims=lambda *args, **kw: None,
        claim_next=lambda *args, **kw: None if outcome == 'no-claim' else claim,
        mark_needs_attention=lambda *args, **kw: calls.append('attention'),
        record_target_receipt=record,
    )
    async def handler(value):
        calls.append('handler')
        if outcome == 'cancel': raise asyncio.CancelledError()
        if outcome == 'timeout': raise TimeoutError()
        return {} if outcome == 'empty' else {'resourceId': 'receipt'}
    def run():
        return asyncio.run(dispatch_one_occurrence_async(TenantScope('org-org', 'dev-project'),
            owner='worker', target=ClaimTarget('analysis', uuid4(), uuid4()), handler=handler, store=store))
    if outcome == 'cancel':
        with pytest.raises(asyncio.CancelledError): run()
        assert calls == ['handler']
    elif outcome == 'receipt-error':
        with pytest.raises(RuntimeError): run()
        assert calls == ['handler', 'record']
    else:
        assert run() is False
        assert calls == ([] if outcome == 'no-claim' else ['handler', 'attention'])
