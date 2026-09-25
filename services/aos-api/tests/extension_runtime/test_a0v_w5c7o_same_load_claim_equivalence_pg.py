"""Negative contracts for repeated current claims; never optimize production guards."""

from functools import wraps

import pytest

from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.pipeline_snapshot_group_input_owner import PipelineSnapshotGroupInputOwner
from aos_api import pipeline_snapshot_group_input_owner as input_module


def test_two_loads_keep_each_member_parent_recheck_around_callback(prepared_case, monkeypatch):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    owner = PipelineSnapshotGroupInputOwner(claims=executor._claims)
    events = []
    original_load = PipelineSnapshotGroupInputOwner._load
    original_parent = input_module._bound_parent
    original_claim = PipelineSourceClaimOwner.read_current

    @wraps(original_load)
    def load(self, *items, **kwargs):
        events.append('load_enter')
        result = original_load(self, *items, **kwargs)
        events.append('load_exit')
        return result

    @wraps(original_parent)
    def parent(*items, **kwargs):
        events.append('parent')
        return original_parent(*items, **kwargs)

    @wraps(original_claim)
    def claim(self, *items, **kwargs):
        events.append('claim')
        return original_claim(self, *items, **kwargs)

    monkeypatch.setattr(PipelineSnapshotGroupInputOwner, '_load', load)
    monkeypatch.setattr(input_module, '_bound_parent', parent)
    monkeypatch.setattr(PipelineSourceClaimOwner, 'read_current', claim)
    with conn.transaction():
        current = owner.run_current(conn, **args,
            execute=lambda value: (events.append('callback'), value)[1])
    assert len(current.parents) == len(args['bindings']) == 2
    assert events.count('load_enter') == events.count('load_exit') == 2
    assert events.count('parent') == 2 * len(args['bindings'])
    first, callback, second = (events.index('load_enter'), events.index('callback'),
                               events.index('load_enter', events.index('callback')))
    assert first < events.index('load_exit') < callback < second
    assert events.count('claim') >= 2 * len(args['bindings'])
    assert state['calls'] == 1


def test_parent_rejection_after_group_claim_never_enters_consumer(prepared_case, monkeypatch):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    owner = PipelineSnapshotGroupInputOwner(claims=executor._claims)
    events = []
    original_claim = PipelineSourceClaimOwner.read_current

    @wraps(original_claim)
    def claim(self, *items, **kwargs):
        events.append('group_claim')
        return original_claim(self, *items, **kwargs)

    def reject_parent(*items, **kwargs):
        events.append('parent_reject')
        raise PermissionError('parent independent recheck denied')

    monkeypatch.setattr(PipelineSourceClaimOwner, 'read_current', claim)
    monkeypatch.setattr(input_module, '_bound_parent', reject_parent)
    with pytest.raises(PermissionError, match='parent independent recheck denied'), conn.transaction():
        owner.run_current(conn, **args, execute=lambda value: events.append('consumer'))
    assert events.count('group_claim') >= len(args['bindings'])
    assert events.count('parent_reject') == 1
    assert 'consumer' not in events
    assert state['calls'] == 1


def test_callback_loses_current_and_second_load_rejects(prepared_case, monkeypatch):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    owner = PipelineSnapshotGroupInputOwner(claims=executor._claims)
    events = []
    original_load = PipelineSnapshotGroupInputOwner._load

    @wraps(original_load)
    def load(self, *items, **kwargs):
        events.append('load')
        return original_load(self, *items, **kwargs)

    def callback(value):
        events.append('callback')
        state['deny'] = True
        return value

    monkeypatch.setattr(PipelineSnapshotGroupInputOwner, '_load', load)
    with pytest.raises((PermissionError, RuntimeError)), conn.transaction():
        owner.run_current(conn, **args, execute=callback)
    assert events == ['load', 'callback', 'load']
    assert state['calls'] == 1
