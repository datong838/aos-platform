import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from threading import Event
from time import sleep

import pytest

from aos_api.data_requirement_outbox_store import (
    DataRequirementOutboxClaim,
    DataRequirementOutboxTransition,
)
from aos_api.ecommerce_analysis_data_requirement_worker import AnalysisDataRequirementWorker
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope('org-org', 'dev-project')


def _claim(suffix='1'):
    return DataRequirementOutboxClaim(
        outbox_id='outbox-' + suffix, requirement_id='requirement-' + suffix,
        requirement_revision=1, event_id='event-' + suffix,
        topic='data.requirement.request',
        payload={'eventId': 'event-' + suffix, 'requirementId': 'requirement-' + suffix,
                 'revision': 1, 'contentHash': 'sha256:' + 'a' * 64},
        content_hash='sha256:' + 'a' * 64, attempt=1,
        lease_token='lease-' + suffix,
        lease_expires_at=datetime(2026, 9, 15, tzinfo=UTC),
    )


def _worker(monkeypatch):
    factory = object.__new__(PipelineControlServiceFactory)
    directory = LivePreparedJobDirectory()
    worker = AnalysisDataRequirementWorker(factory, directory)
    route = SimpleNamespace(
        installation_id='00000000-0000-0000-0000-000000000001',
        generation='00000000-0000-0000-0000-000000000002', actor='operator',
    )
    monkeypatch.setattr(worker, '_route', lambda scope, claim, reconcile: route)
    monkeypatch.setattr(directory, 'resolve', lambda **kwargs: object())
    monkeypatch.setattr(worker, '_markings', lambda scope, actor: ('internal',))
    return worker, factory, directory, route


class Outbox:
    def __init__(self, *, unknown=None, claimed=None, complete_error=False):
        self.unknown, self.claimed = unknown, claimed
        self.complete_error = complete_error
        self.calls = []

    def read_ambiguous_next(self, scope, *, topic):
        self.calls.append(('read_ambiguous', scope, topic))
        return self.unknown

    def claim_pending_next(self, scope, **kwargs):
        self.calls.append(('claim_pending', scope, kwargs))
        return self.claimed

    def complete(self, scope, claim, fulfillment, analysis):
        self.calls.append(('complete', claim, fulfillment, analysis))
        if self.complete_error:
            raise TimeoutError('commit result unavailable')
        return DataRequirementOutboxTransition('acked', False)

    def reconcile_completed(self, scope, claim, fulfillment, analysis):
        self.calls.append(('reconcile', claim, fulfillment, analysis))
        return DataRequirementOutboxTransition('acked', False)

    def fail(self, scope, outbox_id, lease_token, *, reason_code):
        self.calls.append(('fail', outbox_id, lease_token, reason_code))
        return DataRequirementOutboxTransition('failed', False)

    def mark_unknown(self, scope, outbox_id, lease_token, *, reason_code):
        self.calls.append(('mark_unknown', outbox_id, lease_token, reason_code))
        return DataRequirementOutboxTransition('unknown', False)


def _coordinator(monkeypatch, factory, *, error=False):
    import aos_api.ecommerce_analysis_data_requirement_worker as module
    @contextmanager
    def store():
        yield object()
    monkeypatch.setattr(module, '_authoritative_store', store)
    class Coordinator:
        def run(self, *, route):
            if error:
                raise TimeoutError('coordination result unavailable')
            return {
                'fulfillmentRef': {'resourceType': 'DataFulfillmentReceipt',
                    'resourceId': 'fulfillment', 'revision': 1,
                    'contentHash': 'sha256:' + 'b' * 64, 'receiptId': 'fulfillment'},
                'receiptRef': {'resourceType': 'AnalysisRuntimeReceipt',
                    'resourceId': 'analysis', 'revision': 1,
                    'contentHash': 'sha256:' + 'c' * 64, 'receiptId': 'analysis'},
            }
    monkeypatch.setattr(PipelineControlServiceFactory, 'build_analysis_snapshot_coordinator',
                        lambda self, scope, **kwargs: Coordinator())


def test_empty_live_directory_is_no_effect(monkeypatch):
    worker, _, _, _ = _worker(monkeypatch)
    worker._outbox = SimpleNamespace(read_ambiguous_next=lambda *args, **kwargs:
                                     (_ for _ in ()).throw(AssertionError('must not read')))
    assert asyncio.run(worker.tick()) == {
        'scopesChecked': 0, 'completed': 0, 'replayed': 0, 'unknown': 0, 'failed': 0,
    }


def test_normal_claim_uses_only_coordinator_dual_receipts(monkeypatch):
    worker, factory, _, _ = _worker(monkeypatch)
    worker._outbox = outbox = Outbox(claimed=_claim())
    _coordinator(monkeypatch, factory)
    assert worker.run_scope_once(SCOPE) == 'completed'
    assert [call[0] for call in outbox.calls] == ['read_ambiguous', 'claim_pending', 'complete']
    assert outbox.calls[-1][2].resource_type == 'DataFulfillmentReceipt'
    assert outbox.calls[-1][3].resource_type == 'AnalysisRuntimeReceipt'


def test_ambiguous_delivery_is_frozen_before_any_new_claim_or_coordinator(monkeypatch):
    worker, factory, _, _ = _worker(monkeypatch)
    worker._outbox = outbox = Outbox(unknown=_claim('unknown'), claimed=_claim('new'))
    _coordinator(monkeypatch, factory)
    assert worker.run_scope_once(SCOPE) == 'unknown'
    assert [call[0] for call in outbox.calls] == ['read_ambiguous']


def test_pre_coordination_rejection_is_deterministically_failed(monkeypatch):
    worker, _, _, _ = _worker(monkeypatch)
    worker._outbox = outbox = Outbox(claimed=_claim())
    monkeypatch.setattr(worker, '_route', lambda *args, **kwargs:
                        (_ for _ in ()).throw(PermissionError('revoked')))
    assert worker.run_scope_once(SCOPE) == 'failed'
    assert [call[0] for call in outbox.calls] == ['read_ambiguous', 'claim_pending', 'fail']
    assert outbox.calls[-1][-1] == 'CURRENT_ROUTE_REJECTED'


@pytest.mark.parametrize('stage', ['coordinator', 'complete'])
def test_any_post_coordination_uncertainty_becomes_unknown(monkeypatch, stage):
    worker, factory, _, _ = _worker(monkeypatch)
    worker._outbox = outbox = Outbox(claimed=_claim(), complete_error=stage == 'complete')
    _coordinator(monkeypatch, factory, error=stage == 'coordinator')
    assert worker.run_scope_once(SCOPE) == 'unknown'
    assert outbox.calls[-1][0] == 'mark_unknown'
    assert outbox.calls[-1][-1] == (
        'COORDINATION_RESULT_UNKNOWN' if stage == 'coordinator'
        else 'OUTBOX_COMPLETION_RESULT_UNKNOWN')


def test_unknown_never_reenters_coordinator_even_if_it_would_fail(monkeypatch):
    worker, factory, _, _ = _worker(monkeypatch)
    worker._outbox = outbox = Outbox(unknown=_claim('unknown'))
    _coordinator(monkeypatch, factory, error=True)
    assert worker.run_scope_once(SCOPE) == 'unknown'
    assert [call[0] for call in outbox.calls] == ['read_ambiguous']


def test_tick_is_bounded_and_rotates_scopes(monkeypatch):
    worker, _, _, _ = _worker(monkeypatch)
    scopes = tuple(TenantScope('org', f'project-{n}') for n in range(5))
    monkeypatch.setattr(worker, '_scopes', lambda: scopes)
    seen = []
    monkeypatch.setattr(worker, 'run_scope_once', lambda scope: seen.append(scope) or 'idle')
    asyncio.run(worker.tick()); asyncio.run(worker.tick())
    assert seen == [*scopes[:4], scopes[4], *scopes[:3]]


def test_cancellation_waits_for_inflight_thread(monkeypatch):
    worker, _, _, _ = _worker(monkeypatch)
    entered, finished = Event(), Event()
    monkeypatch.setattr(worker, '_scopes', lambda: (SCOPE,))
    def slow(scope):
        entered.set(); sleep(.05); finished.set(); return 'idle'
    monkeypatch.setattr(worker, 'run_scope_once', slow)
    async def run():
        task = asyncio.create_task(worker.tick())
        assert await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
    asyncio.run(run())


def test_worker_is_owned_by_active_application_lifecycle(monkeypatch):
    from test_runtime_startup_composition import _quiet_startup
    from aos_api import main
    import aos_api.asset_registry.control_wiring as wiring
    import aos_api.ecommerce_product_event_worker as event_module
    import aos_api.ecommerce_analysis_data_requirement_worker as analysis_module
    _quiet_startup(monkeypatch)
    monkeypatch.setattr(wiring, 'build_runtime_control_plane', lambda **kw: object())
    monkeypatch.setattr(event_module, 'build_product_event_worker', lambda plane: None)
    entered, stopped = asyncio.Event(), asyncio.Event()
    class Host:
        async def serve(self, stop):
            await stop.wait()
    class Worker:
        async def serve(self, stop, *, host_ready):
            assert host_ready(); entered.set()
            try:
                await stop.wait()
            finally:
                stopped.set()
    monkeypatch.setattr(wiring, 'build_production_runtime_host_selection',
        lambda **kw: SimpleNamespace(host=Host(), status='ACTIVE', error_code=None))
    monkeypatch.setattr(analysis_module, 'build_analysis_data_requirement_worker', lambda plane: Worker())
    async def run():
        async with main.lifespan(main.app):
            await asyncio.wait_for(entered.wait(), 1)
            assert {task.get_name() for task in main.app.state.runtime_background_tasks} == {
                'extension-runtime-host', 'analysis-data-requirement'}
        assert stopped.is_set()
    asyncio.run(run())
