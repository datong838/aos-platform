"""No-effect natural analyst discovery; never authorizes a model call."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_analyst_stage_runtime import (
    AnalystStageReadinessWorker, _classify,
)
from aos_api.ecommerce_growth_runtime_adapters import _analysis_command_hash
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope('org-org', 'dev-project')


def _row(**changes):
    body = dict(requestHash='sha256:' + 'a' * 64,
                taskRunRef=dict(resourceType='TaskRun', resourceId='run-1'),
                phase='RUNNING', completed=False)
    ref = dict(resourceType='AnalysisRuntimeReceipt', resourceId='receipt-1',
               revision=1, contentHash=_analysis_command_hash(body))
    row = dict(response={**body, 'receiptRef': ref},
               request_hash=body['requestHash'], target_receipt_ref=ref,
               installation_id='install-1', generation='generation-1', execution_epoch=2,
               dispatch_revision=3, handler_kind='extension',
               current_installation='install-1', current_generation='generation-1',
               current_epoch=2, current_dispatch_revision=3, dispatch_fence=False,
               desired_state='enabled', observed_state='ready', enabled=True,
               runtime_fence=False, task_run_status='running', task_status='executing',
               plan_revision_id='plan-1', current_plan_revision_id='plan-1',
               has_agent_run=False)
    row.update(changes)
    return row


def _directory():
    return SimpleNamespace(resolve=lambda **_kw: object())


def test_current_original_is_only_awaiting_more_authority():
    assert _classify(_row(), SCOPE, _directory()) == 'awaiting-authority'


@pytest.mark.parametrize('drift', [
    {'current_generation': 'old'}, {'current_epoch': 4},
    {'dispatch_fence': True}, {'runtime_fence': True},
    {'desired_state': 'disabled'}, {'task_run_status': 'paused'},
    {'task_run_status': 'succeeded'}, {'task_status': 'paused'},
    {'current_plan_revision_id': 'other'},
])
def test_stale_or_nonrunning_authority_is_blocked(drift):
    assert _classify(_row(**drift), SCOPE, _directory()) == 'blocked'


def test_unknown_or_existing_agent_run_requires_reconciliation():
    assert _classify(_row(has_agent_run=True), SCOPE, _directory()) == 'reconcile'
    response = dict(_row()['response'])
    response['phase'] = 'RECONCILING'
    assert _classify(_row(response=response), SCOPE, _directory()) == 'reconcile'
    assert _classify(_row(target_receipt_ref={'different': True}), SCOPE,
                     _directory()) == 'reconcile'


def test_live_directory_must_own_the_exact_generation():
    missing = SimpleNamespace(resolve=lambda **_kw: (_ for _ in ()).throw(LookupError()))
    assert _classify(_row(), SCOPE, missing) == 'blocked'


def test_worker_reads_only_scoped_bounded_receipt_metadata():
    seen = []
    class Connection:
        def execute(self, query, params):
            seen.append((query, params))
            return SimpleNamespace(fetchall=lambda: [_row()])
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    directory = LivePreparedJobDirectory()
    directory.resolve = lambda **_kw: object()
    worker = AnalystStageReadinessWorker(directory, connect=connect)
    assert worker.scan_scope(SCOPE) == dict(blocked=0, reconcile=0,
                                             awaitingAuthority=1, overflow=0)
    assert seen[0][1] == SCOPE.key
    assert 'LIMIT 101' in seen[0][0]
    assert 'ecommerce_growth_runtime_command_receipt' in seen[0][0]
    assert 'mall' not in seen[0][0].lower()


def test_overflow_fails_closed_without_classifying_any_candidate():
    class Connection:
        def execute(self, _query, _params):
            return SimpleNamespace(fetchall=lambda: [_row()] * 101)
    @contextmanager
    def connect(_scope):
        yield Connection()
    worker = AnalystStageReadinessWorker(LivePreparedJobDirectory(), connect=connect)
    assert worker.scan_scope(SCOPE) == dict(blocked=0, reconcile=0,
                                             awaitingAuthority=0, overflow=1)


def test_duplicate_original_task_receipts_are_reconciliation_not_authority():
    class Connection:
        def execute(self, _query, _params):
            return SimpleNamespace(fetchall=lambda: [_row(), _row()])
    @contextmanager
    def connect(_scope):
        yield Connection()
    directory = LivePreparedJobDirectory()
    directory.resolve = lambda **_kw: object()
    worker = AnalystStageReadinessWorker(directory, connect=connect)
    assert worker.scan_scope(SCOPE) == dict(blocked=0, reconcile=2,
                                             awaitingAuthority=0, overflow=0)
