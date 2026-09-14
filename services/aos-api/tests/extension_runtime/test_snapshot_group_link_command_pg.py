"""Original PG group/current-input and canonical Store; release/source are fixtures."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
import psycopg
from psycopg.types.json import Jsonb
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
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.pipeline_snapshot_group_link_command import PipelineSnapshotGroupLinkCommandJournal


@pytest.fixture
def link_case(object_case):
    executor, conn, args, state = object_case
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_047_snapshot_group_link_command.py'
    spec = importlib.util.spec_from_file_location('group_link_command_schema', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    conn.execute('RESET ROLE')
    module.op = SimpleNamespace(execute=conn.execute); module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    journal = PipelineSnapshotGroupLinkCommandJournal(claims=executor._claims, store=executor._store)
    return executor, conn, args, state, journal


def test_original_command_prepare_and_checkpoint_stable_replay(link_case, monkeypatch):
    executor, conn, args, state, journal = link_case
    executor.execute(**args)
    with conn.transaction(): first = journal.prepare(conn, **args)
    assert first.created and first.command is not None and len(first.command.links) == 1
    assert first.command.objects == []
    assert first.command.expected_checkpoint_version == 0
    executor._store.apply_strict_link_batch(first.command)
    def forbidden(*a, **kw): raise AssertionError('must not reconstruct checkpoint on replay')
    monkeypatch.setattr(executor._store, 'get_checkpoint', forbidden)
    with conn.transaction(): replay = journal.prepare(conn, **args)
    with conn.transaction(): read = journal.read_current(conn, **args)
    assert not replay.created and replay == read
    assert replay.command == first.command and replay.command_hash == first.command_hash
    assert state['calls'] == 1


def test_missing_relationship_preparation_never_starts_objects(link_case):
    executor, conn, args, state, journal = link_case
    with pytest.raises(LookupError), conn.transaction(): journal.prepare(conn, **args)
    assert conn.execute('SELECT count(*) AS n FROM ecom_object').fetchone()['n'] == 0
    assert state['calls'] == 1


def test_unapplied_original_objects_cannot_prepare_link_command(link_case):
    executor, conn, args, _, journal = link_case
    with conn.transaction(): executor._journal.prepare(conn, **args)
    with pytest.raises(IngressJournalConflict, match='INGRESS_DERIVED_PREPARATION_REQUIRED'), conn.transaction(): journal.prepare(conn, **args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_link_command').fetchone()['n'] == 0


def test_missing_command_read_does_not_create(link_case):
    executor, conn, args, _, journal = link_case
    executor.execute(**args)
    with pytest.raises(LookupError), conn.transaction(): journal.read_current(conn, **args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_link_command').fetchone()['n'] == 0


def test_rollback_retry_and_current_denial(link_case):
    executor, conn, args, state, journal = link_case
    executor.execute(**args)
    with pytest.raises(RuntimeError), conn.transaction():
        journal.prepare(conn, **args)
        raise RuntimeError('rollback')
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_link_command').fetchone()['n'] == 0
    with conn.transaction(): assert journal.prepare(conn, **args).created
    state['deny'] = True
    with pytest.raises(PermissionError), conn.transaction(): journal.read_current(conn, **args)
    assert state['calls'] == 1


def test_link_command_history_is_immutable_and_tenant_isolated(link_case):
    executor, conn, args, _, journal = link_case
    executor.execute(**args)
    with conn.transaction(): journal.prepare(conn, **args)
    for statement in ('UPDATE pipeline_snapshot_group_link_command SET command_hash=command_hash',
                      'DELETE FROM pipeline_snapshot_group_link_command',
                      'TRUNCATE pipeline_snapshot_group_link_command'):
        with pytest.raises(psycopg.Error), conn.transaction(): conn.execute(statement)
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_link_command').fetchone()['n'] == 0


@pytest.mark.parametrize('fault', ['assessment', 'tenant', 'count', 'objects'])
def test_database_rejects_unbound_link_command(link_case, fault):
    executor, conn, args, _, journal = link_case
    executor.execute(**args)
    with pytest.raises(RuntimeError, match='fixture rollback'), conn.transaction():
        saved = journal.prepare(conn, **args)
        payload = deepcopy(saved.command.model_dump(mode='json'))
        digest = saved.assessment_hash
        count = len(saved.command.links)
        raise RuntimeError('fixture rollback')
    with pytest.raises(psycopg.Error), conn.transaction():
        if fault == 'assessment': digest = 'sha256:' + 'f' * 64
        elif fault == 'tenant': payload['scope']['org_id'] = 'other'
        elif fault == 'count': count += 1
        else: payload['objects'] = [{}]
        conn.execute('INSERT INTO pipeline_snapshot_group_link_command(org_id,project_id,group_id,assessment_hash,link_count,command_hash,command) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                     (*args['scope'].key, args['group_id'], digest, count, saved.command_hash, Jsonb(payload)))


def test_caught_post_prepare_denial_rolls_back_command(link_case, monkeypatch):
    executor, conn, args, state, journal = link_case
    executor.execute(**args)
    original = executor._store.get_checkpoint
    def revoke(command):
        result = original(command)
        state['deny'] = True
        return result
    monkeypatch.setattr(executor._store, 'get_checkpoint', revoke)
    with conn.transaction():
        with pytest.raises(PermissionError): journal.prepare(conn, **args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_link_command').fetchone()['n'] == 0


def test_valid_shape_but_wrong_link_cannot_be_replayed(link_case):
    from aos_api.source_read_observation import observed_rows_hash
    executor, conn, args, _, journal = link_case
    executor.execute(**args)
    with pytest.raises(RuntimeError, match='fixture rollback'), conn.transaction():
        saved = journal.prepare(conn, **args)
        raise RuntimeError('fixture rollback')
    link = saved.command.links[0]
    wrong = link.model_copy(update={'target': link.target.model_copy(update={'external_id': 'niushop:1:9999'})})
    body = saved.command.model_copy(update={'links': [wrong]}).model_dump(mode='json')
    with conn.transaction():
        conn.execute('INSERT INTO pipeline_snapshot_group_link_command(org_id,project_id,group_id,assessment_hash,link_count,command_hash,command) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                     (*args['scope'].key, args['group_id'], saved.assessment_hash, 1,
                      observed_rows_hash([{'command': body}]), Jsonb(body)))
    with pytest.raises(IngressJournalConflict, match='GROUP_LINK_COMMAND_DRIFT'), conn.transaction():
        journal.read_current(conn, **args)


def test_empty_original_group_has_no_fake_command_or_receipt(assessment_case):
    assessment_case[3]['empty'] = True
    prepared = journal_case.__wrapped__(assessment_case)
    generator = object_case.__wrapped__(prepared)
    original = next(generator)
    try:
        executor, conn, args, state, journal = link_case.__wrapped__(original)
        executor.execute(**args)
        with conn.transaction(): first = journal.prepare(conn, **args)
        with conn.transaction(): replay = journal.read_current(conn, **args)
        assert first.command is None and replay.command is None
        assert first.command_hash == replay.command_hash
        assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n'] == 0
        assert state['calls'] == 1
    finally:
        try: next(generator)
        except StopIteration: pass
