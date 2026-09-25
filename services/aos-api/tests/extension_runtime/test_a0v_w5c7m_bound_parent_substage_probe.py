"""Test-only timing transparency and parent failure contracts; no live source reads."""

from types import SimpleNamespace

import pytest

from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict
from aos_api.ec_ingress_recovery import _bound_parent
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from test_snapshot_schedule_runtime_pg import _install_bound_parent_substage_probe


def test_substage_probe_counts_only_active_calls_and_preserves_return_and_error(monkeypatch):
    events = []

    def envelope(*args):
        events.append('envelope')
        return {'runId': 'r'}

    def claim(*args, **kwargs):
        events.append('claim')
        return 'current'

    def reject(*args, **kwargs):
        events.append('binding')
        raise PermissionError('original binding rejection')

    monkeypatch.setattr(ControlledIngressJournal, 'read', envelope)
    monkeypatch.setattr(PipelineSourceClaimOwner, 'read_current', claim)
    monkeypatch.setattr(IngressJournal, 'verify_schedule_binding', reject)
    stages = {}
    active = _install_bound_parent_substage_probe(monkeypatch, stages)
    assert ControlledIngressJournal.read(None, None, None, 'r') == {'runId': 'r'}
    assert stages['parent_envelope_read'][0] == 0
    token = active.set(True)
    try:
        assert ControlledIngressJournal.read(None, None, None, 'r') == {'runId': 'r'}
        assert PipelineSourceClaimOwner.read_current(None, None) == 'current'
        with pytest.raises(PermissionError, match='original binding rejection'):
            IngressJournal.verify_schedule_binding(None, None, None)
    finally:
        active.reset(token)
    assert events == ['envelope', 'envelope', 'claim', 'binding']
    assert [stages[key][0] for key in (
        'parent_envelope_read', 'parent_claim_current', 'parent_running_binding')] == [1, 1, 1]
    assert stages['parent_claim_completed'][0] == 0
    assert stages['parent_completed_binding'][0] == 0
    assert all(count >= 0 and seconds >= 0 for count, seconds in stages.values())


def test_bound_parent_missing_envelope_stops_before_schedule():
    events = []

    class Journal:
        def read(self, *args):
            events.append('read')
            return None

        def verify_running_schedule(self, *args, **kwargs):
            events.append('verify')

    with pytest.raises(IngressJournalConflict, match='INGRESS_PARENT_REQUIRED'):
        _bound_parent(None, None, 'r', Journal())
    assert events == ['read']


def test_bound_parent_binding_rejection_is_not_retried():
    events = []
    parent = dict(pipelineId='p', sourceId='s', sourceRevision=2, pipelineHash='h')

    class Journal:
        def read(self, *args):
            events.append('read')
            return parent

        def verify_running_schedule(self, *args, **kwargs):
            events.append('verify')
            raise PermissionError('current claim lost')

    with pytest.raises(PermissionError, match='current claim lost'):
        _bound_parent(None, None, 'r', Journal())
    assert events == ['read', 'verify']


@pytest.mark.parametrize('completed', [False, True])
def test_controlled_journal_selects_exact_current_and_binding_mode(monkeypatch, completed):
    events = []
    journal = object.__new__(ControlledIngressJournal)
    journal._completed_read = completed
    journal._saved_recovery = False
    journal._run_id = 'r'
    journal._ref = 'ref'
    journal._actor = 'actor'
    journal._claims = SimpleNamespace(
        read_current=lambda *args, **kwargs: events.append('current'),
        read_completed_current=lambda *args, **kwargs: events.append('completed'),
        read_saved_current=lambda *args, **kwargs: events.append('saved'))
    monkeypatch.setattr(ControlledIngressJournal, '_fixed', lambda *args: None)
    monkeypatch.setattr(IngressJournal, 'verify_schedule_binding',
                        lambda *args, **kwargs: events.append('running_binding'))
    monkeypatch.setattr(IngressJournal, 'verify_completed_schedule_binding',
                        lambda *args, **kwargs: events.append('completed_binding'))
    journal.verify_running_schedule(None, None, run_id='r')
    assert events == (['completed', 'completed_binding'] if completed
                      else ['current', 'running_binding'])
