"""Complete original object/link/Projector chain in an isolated PostgreSQL schema."""
from contextlib import contextmanager
import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case
from test_snapshot_group_relationship_journal_pg import journal_case
from test_snapshot_group_object_executor_pg import object_case
from test_snapshot_group_link_command_pg import link_case
from aos_api.pipeline_snapshot_group_link_executor import ControlledSnapshotGroupLinkExecutor


@pytest.fixture
def link_executor_case(link_case):
    original, conn, args, state, _ = link_case
    executor = ControlledSnapshotGroupLinkExecutor(claims=original._claims, store=original._store,
        connect=original._single._ingress._connect, eng=original._single._eng)
    return executor, conn, args, state


def test_complete_group_candidates_apply_project_and_replay(link_executor_case):
    executor, conn, args, state = link_executor_case
    first = executor.execute(**args)
    again = executor.execute(**args)
    assert first['relationship_scope'] == 'current_candidates_only'
    assert first['relationships_applied'] and first['completion'] == {'expected': 1, 'projected': 1, 'pending': 0}
    assert again['replayed'] and again['projection']['projected'] == 0
    assert conn.execute('SELECT count(*) AS n FROM ecom_link').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n'] == 3
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='running'").fetchone()['n'] == 2
    assert state['calls'] == 1


def test_command_commit_ack_loss_stops_before_links(link_executor_case, monkeypatch):
    executor, conn, args, state = link_executor_case
    original = executor._transaction
    @contextmanager
    def lost(scope):
        with original(scope) as db: yield db
        raise RuntimeError('command commit ack lost')
    monkeypatch.setattr(executor, '_transaction', lost)
    with pytest.raises(RuntimeError, match='ack lost'): executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_link_command').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM ecom_link').fetchone()['n'] == 0
    monkeypatch.setattr(executor, '_transaction', original)
    assert executor.execute(**args)['relationships_applied']
    assert state['calls'] == 1


def test_link_commit_ack_loss_recovers_original_receipt(link_executor_case, monkeypatch):
    executor, conn, args, state = link_executor_case
    original = executor._store.apply_strict_link_batch
    def lost(command):
        original(command)
        raise RuntimeError('link commit ack lost')
    monkeypatch.setattr(executor._store, 'apply_strict_link_batch', lost)
    with pytest.raises(RuntimeError, match='ack lost'): executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM ecom_link').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n'] == 0
    monkeypatch.setattr(executor._store, 'apply_strict_link_batch', original)
    assert executor.execute(**args)['replayed']
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n'] == 3
    assert state['calls'] == 1


def test_projection_failure_rolls_back_graph_and_recovers(link_executor_case, monkeypatch):
    from aos_api import pipeline_controlled_projection as projection
    executor, conn, args, state = link_executor_case
    original = projection._project_link
    def fail(*a, **kw):
        original(*a, **kw)
        raise RuntimeError('after graph write')
    monkeypatch.setattr(projection, '_project_link', fail)
    with pytest.raises(RuntimeError, match='graph write'): executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n'] == 0
    assert conn.execute("SELECT count(*) AS n FROM projection_outbox WHERE change_kind='links_written' AND projected").fetchone()['n'] == 0
    monkeypatch.setattr(projection, '_project_link', original)
    assert executor.execute(**args)['completion']['pending'] == 0
    assert state['calls'] == 1


def test_current_revocation_between_prepare_and_apply_prevents_links(link_executor_case, monkeypatch):
    executor, conn, args, state = link_executor_case
    original = executor._transaction
    @contextmanager
    def revoke(scope):
        with original(scope) as db: yield db
        state['deny'] = True
    monkeypatch.setattr(executor, '_transaction', revoke)
    with pytest.raises(PermissionError): executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM ecom_link').fetchone()['n'] == 0
    assert state['calls'] == 1


@pytest.mark.parametrize('ordering', ['earlier', 'later'])
def test_unrelated_events_are_not_consumed_by_group(link_executor_case, monkeypatch, ordering):
    from aos_api.ec_ingress_journal import IngressJournalConflict
    from aos_api.ecom_core_models import BatchCommand
    from aos_api.ec_ot_writer import _build_batch_command
    executor, conn, args, state = link_executor_case
    with executor._transaction(args['scope']) as db:
        current = executor._commands._relationships._assessments.run_current(db, **args, execute=lambda v: v)
    original = BatchCommand.model_validate(current.input.parents[0]['command'])
    record = original.objects[0]
    unrelated = record.model_copy(update={'identity': record.identity.model_copy(update={'external_id': 'unrelated-fixture'})})
    unrelated_scope = original.scope.model_copy(update={'stream': 'unrelated-fixture'})
    other = _build_batch_command(sync_scope=unrelated_scope, objects=[unrelated], links=[],
                                pipeline_id=unrelated_scope.stream, store=executor._store)
    apply_links = executor._store.apply_strict_link_batch
    def interleave(command):
        if ordering == 'earlier': executor._store.apply_batch(other)
        result = apply_links(command)
        if ordering == 'later': executor._store.apply_batch(other)
        return result
    monkeypatch.setattr(executor._store, 'apply_strict_link_batch', interleave)
    if ordering == 'earlier':
        with pytest.raises(IngressJournalConflict, match='PROJECTION_ORDER_BLOCKED'): executor.execute(**args)
        assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n'] == 0
    else:
        assert executor.execute(**args)['completion']['pending'] == 0
        assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n'] == 1
    assert executor._store.read_batch_projection_completion(other, [])['pending'] == 1
    assert state['calls'] == 1
