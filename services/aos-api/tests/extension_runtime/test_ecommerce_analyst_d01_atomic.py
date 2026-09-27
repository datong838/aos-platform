"""Atomic natural D01 must bind the original chain to the canonical Owner."""
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest

import aos_api.ecommerce_analyst_d01_atomic as atomic_module
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
from test_ecommerce_analyst_d01_issuer import HASH, NOW, SCOPE, _packet, _request, _timeline

RECEIPT = {'resourceType': 'AnalysisRuntimeReceipt', 'resourceId': 'analysis-1',
           'revision': 1, 'contentHash': 'sha256:' + HASH, 'receiptId': 'receipt-analysis-1'}


def _harness(monkeypatch, *, original_run='run-1', original_plan='plan-1',
             cutoff=None, reject_origin=False, reject_sources=False,
             unknown_commit=False, task_selection='source-selection-1',
             original_selection='source-selection-1', task_selection_revision='1',
             reject_selection=False, mismatched_packet=False):
    calls = []
    class Connection:
        def commit(self):
            calls.append('commit')
            if unknown_commit:
                raise RuntimeError('commit result unknown')
    conn = Connection()
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        calls.append('connect')
        yield conn
    monkeypatch.setattr(atomic_module, 'connect_serializable', connect)
    def timeline(_self, scope, task_run_id):
        selected = _timeline()
        if task_selection is None:
            selected.task.selection_ref = None
        else:
            selected.task.selection_ref.resource_id = task_selection
            selected.task.selection_ref.revision = task_selection_revision
        return selected
    monkeypatch.setattr(atomic_module.AipTaskStore, 'timeline', timeline)
    def selected(_self, transaction, scope, task_run_id, plan_id, actor, occurred_at):
        calls.append('selection')
        if reject_selection:
            raise ValueError('approved D01 selection unavailable')
        assert scope == SCOPE and task_run_id == 'run-1' and plan_id == 'plan-1'
        assert actor == 'analyst-owner' and occurred_at == NOW
        packet = _packet()
        if mismatched_packet:
            packet = packet.model_copy(update={'max_bytes': packet.max_bytes - 1})
        return packet, {'resourceType': 'D01SourceSelectionApproval'}
    monkeypatch.setattr(atomic_module.D01SourceSelectionStore, 'read_current', selected)
    origin = object.__new__(AnalysisContinuationOrigin)
    origin.context = SimpleNamespace(analysis=SimpleNamespace(
        scope=SCOPE, source=SimpleNamespace(actor='analyst-owner')))
    def current(connection, *, receipt_ref, execute):
        assert connection is conn
        calls.append('origin')
        if reject_origin:
            raise PermissionError('original lineage revoked')
        return execute({'context': {'source': {'policy': {
            'sourceSelectionRef': {'resourceType': 'SourceSelectionRevision',
                'resourceId': original_selection, 'revision': 1,
                'contentHash': 'sha256:' + HASH}}}}, 'analysisReceipt': {
            'receiptRef': receipt_ref,
            'taskRunRef': {'resourceType': 'TaskRun', 'resourceId': original_run},
            'planRef': {'resourceType': 'PlanRevision', 'resourceId': original_plan},
            'cutoffAt': (cutoff or NOW).isoformat(),
            'phase': 'PREPARING',
        }})
    monkeypatch.setattr(origin, 'run_current', current)
    def source(transaction, scope, request, packet, actor, occurred_at):
        calls.append('sources')
        calls.append(transaction)
        assert scope == SCOPE and packet == _packet()
        if reject_sources:
            raise PermissionError('source revoked')
        return True
    monkeypatch.setattr(atomic_module, 'require_current_d01_sources_in_transaction', source)
    owner = AipAgentRunService()
    receipt = SimpleNamespace(
        receipt_id='receipt-1', operation='agent_run.create',
        idempotency_key='natural-d01:' + _request().agent_run_id,
        result_ref=SimpleNamespace(resource_type='AgentRun', resource_id=_request().agent_run_id),
    )
    def create(transaction, scope, request, *, idempotency_key, actor, occurred_at):
        calls.append('owner')
        assert transaction is calls[calls.index('sources') + 1]
        assert scope == SCOPE and idempotency_key == receipt.idempotency_key
        return SimpleNamespace(agent_run_id=request.agent_run_id, status='queued'), receipt
    monkeypatch.setattr(owner, '_create_in_transaction', create)
    monkeypatch.setattr(owner, '_receipt_row', lambda *_args: {'receipt_id': receipt.receipt_id})
    monkeypatch.setattr(owner, '_receipt_from_row', lambda *_args: receipt)
    return atomic_module.NaturalD01AtomicCoordinator(origin, owner), calls


def test_one_original_chain_commits_one_owner_receipt(monkeypatch):
    coordinator, calls = _harness(monkeypatch)
    result = coordinator.issue(SCOPE, 'run-1', _request(), _packet(),
                               receipt_ref=RECEIPT,
                               actor='analyst-owner', occurred_at=NOW)
    assert result[0].agent_run_id == _request().agent_run_id
    assert [item for item in calls if isinstance(item, str)] == [
        'connect', 'origin', 'selection', 'sources', 'owner', 'commit']


@pytest.mark.parametrize('drift', [
    {'reject_selection': True}, {'mismatched_packet': True},
])
def test_missing_or_mismatched_approved_selection_never_reaches_owner(monkeypatch, drift):
    coordinator, calls = _harness(monkeypatch, **drift)
    with pytest.raises(ValueError, match='approved D01 selection'):
        coordinator.issue(SCOPE, 'run-1', _request(), _packet(),
                          receipt_ref=RECEIPT, actor='analyst-owner', occurred_at=NOW)
    assert 'owner' not in calls and 'commit' not in calls


def test_different_actor_cannot_borrow_original_chain(monkeypatch):
    coordinator, calls = _harness(monkeypatch)
    with pytest.raises(PermissionError, match='original analysis actor'):
        coordinator.issue(SCOPE, 'run-1', _request(), _packet(),
                          receipt_ref=RECEIPT,
                          actor='another-member', occurred_at=NOW)
    assert calls == []


def test_missing_original_actor_fails_closed(monkeypatch):
    coordinator, calls = _harness(monkeypatch)
    del coordinator.origin.context.analysis.source.actor
    with pytest.raises(PermissionError, match='original analysis actor'):
        coordinator.issue(SCOPE, 'run-1', _request(), _packet(),
                          receipt_ref=RECEIPT,
                          actor='analyst-owner', occurred_at=NOW)
    assert calls == []


@pytest.mark.parametrize('selection,revision', [
    ('another-selection', '1'), (None, '1'), ('source-selection-1', '2'),
])
def test_task_source_selection_must_match_original_chain(monkeypatch, selection, revision):
    coordinator, calls = _harness(monkeypatch, task_selection=selection,
                                  task_selection_revision=revision)
    with pytest.raises(ValueError, match='source selection'):
        coordinator.issue(SCOPE, 'run-1', _request(), _packet(),
                          receipt_ref=RECEIPT,
                          actor='analyst-owner', occurred_at=NOW)
    assert 'owner' not in calls and 'commit' not in calls


@pytest.mark.parametrize('drift', [
    {'original_run': 'other-run'}, {'original_plan': 'other-plan'},
    {'cutoff': NOW + timedelta(seconds=1)},
    {'reject_origin': True}, {'reject_sources': True},
])
def test_original_or_source_drift_never_reaches_commit(monkeypatch, drift):
    coordinator, calls = _harness(monkeypatch, **drift)
    with pytest.raises((ValueError, PermissionError)):
        coordinator.issue(SCOPE, 'run-1', _request(), _packet(),
                          receipt_ref=RECEIPT,
                          actor='analyst-owner', occurred_at=NOW)
    assert 'owner' not in calls and 'commit' not in calls


def test_unknown_commit_propagates_without_a_second_owner_call(monkeypatch):
    coordinator, calls = _harness(monkeypatch, unknown_commit=True)
    with pytest.raises(RuntimeError, match='unknown'):
        coordinator.issue(SCOPE, 'run-1', _request(), _packet(),
                          receipt_ref=RECEIPT,
                          actor='analyst-owner', occurred_at=NOW)
    assert calls.count('owner') == 1 and calls.count('commit') == 1


def test_missing_independent_owner_receipt_readback_never_commits(monkeypatch):
    coordinator, calls = _harness(monkeypatch)
    monkeypatch.setattr(coordinator.owner, '_receipt_row', lambda *_args: None)
    with pytest.raises(ValueError, match='Receipt readback'):
        coordinator.issue(SCOPE, 'run-1', _request(), _packet(),
                          receipt_ref=RECEIPT, actor='analyst-owner', occurred_at=NOW)
    assert calls.count('owner') == 1 and 'commit' not in calls
