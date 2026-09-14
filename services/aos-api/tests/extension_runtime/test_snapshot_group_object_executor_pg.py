"""Actual PG object, projection and dataset Owners; source and release are fixtures."""
from contextlib import contextmanager
import pytest
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case
from test_snapshot_group_relationship_journal_pg import journal_case
from test_controlled_executor_integration_pg import integrated
from aos_api.pipeline_snapshot_group_object_executor import ControlledSnapshotGroupObjectExecutor

@pytest.fixture
def object_case(journal_case):
    conn,args,state,journal,source=journal_case
    generator=integrated.__wrapped__((source,conn,args,state))
    single,conn,_,_,eng=next(generator)
    executor=ControlledSnapshotGroupObjectExecutor(claims=source._claims,store=single._store,connect=source._connect,eng=eng)
    try:yield executor,conn,args,state
    finally:
        try:next(generator)
        except StopIteration:pass


def test_real_group_objects_project_and_dataset_replay_without_source(object_case):
    executor,conn,args,state=object_case
    first=executor.execute(**args);again=executor.execute(**args)
    assert len(first['members'])==2 and first['relationships_applied'] is False
    assert all(m['completion']['pending']==0 for m in first['members'])
    assert all(m['completed_replay'] for m in again['members'])
    for table in ('ecom_object','ecom_ingest_receipt','obj_instance','meta_dataset','meta_dataset_history','ecommerce_ingress_dataset_receipt'):
        assert conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']==2
    assert conn.execute('SELECT count(*) AS n FROM ecom_link').fetchone()['n']==0
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='running'").fetchone()['n']==2
    assert state['calls']==1


def test_interrupted_first_member_recovers_all_original_receipts(object_case,monkeypatch):
    executor,conn,args,state=object_case;resume=executor._single.resume_saved;calls=0
    def interrupt(**kwargs):
        nonlocal calls
        result=resume(**kwargs);calls+=1
        if calls==1:raise RuntimeError('after first member')
        return result
    monkeypatch.setattr(executor._single,'resume_saved',interrupt)
    with pytest.raises(RuntimeError,match='first member'):executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM obj_instance').fetchone()['n']==1
    monkeypatch.setattr(executor._single,'resume_saved',resume)
    result=executor.execute(**args)
    assert len(result['members'])==2 and any(m['completed_replay'] for m in result['members'])
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n']==2
    assert state['calls']==1


def test_preparation_commit_ack_loss_never_starts_application(object_case,monkeypatch):
    executor,conn,args,state=object_case;original=executor._transaction;calls=0
    @contextmanager
    def interrupted(scope):
        nonlocal calls
        with original(scope) as db:yield db
        calls+=1
        if calls==1:raise RuntimeError('preparation commit ack lost')
    monkeypatch.setattr(executor,'_transaction',interrupted)
    with pytest.raises(RuntimeError,match='ack lost'):executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM ecom_object').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_relationship').fetchone()['n']==1
    monkeypatch.setattr(executor,'_transaction',original)
    executor.execute(**args)
    assert state['calls']==1


def test_current_denial_prevents_any_object_write(object_case):
    executor,conn,args,state=object_case;state['deny']=True
    with pytest.raises(PermissionError):executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM ecom_object').fetchone()['n']==0
    assert state['calls']==1


def test_historical_dataset_success_cannot_hide_superseded_object(object_case):
    from datetime import timedelta
    from aos_api.ecom_core_models import BatchCommand,EcomConsistencyError
    from aos_api.ec_ot_writer import _build_batch_command
    executor,conn,args,state=object_case;executor.execute(**args)
    with executor._transaction(args['scope']) as db:
        current=executor._journal._assessments.run_current(db,**args,execute=lambda v:v)
    original=BatchCommand.model_validate(current.input.parents[0]['command']);record=original.objects[0]
    later=record.source_updated_at+timedelta(seconds=1)
    newer=record.model_copy(update={'source_updated_at':later,'properties':record.properties|{'name':'newer-fixture','updatedAt':later.isoformat()}})
    command=_build_batch_command(sync_scope=original.scope,objects=[newer],links=[],pipeline_id=original.scope.stream,store=executor._store)
    executor._store.apply_batch(command)
    with pytest.raises(EcomConsistencyError,match='missing or has been superseded'):executor.execute(**args)
    assert state['calls']==1


@pytest.mark.parametrize('missing_endpoint', [False, True])
def test_strict_group_candidate_links_commit_or_rollback(object_case, missing_endpoint, monkeypatch):
    from aos_api.ecom_core_models import BatchCommand, EcomConsistencyError
    from aos_api.ec_ot_writer import _normalize_rows, _build_batch_command
    executor, conn, args, state = object_case
    executor.execute(**args)
    with executor._transaction(args['scope']) as db:
        current = executor._journal._assessments.run_current(db, **args, execute=lambda v: v)
    original = BatchCommand.model_validate(current.input.parents[0]['command'])
    sync_scope = original.scope.model_copy(update={'stream': 'fixture-group-relationships'})
    _, links = _normalize_rows(list(current.assessment.candidate_links), sync_scope)
    assert len(links) == 1
    if missing_endpoint:
        missing = links[0].model_copy(update={
            'target': links[0].target.model_copy(update={'external_id': 'niushop:1:999999'}),
            'cursor_external_id': 'missing-fixture-endpoint',
        })
        links.append(missing)
    command = _build_batch_command(sync_scope=sync_scope, objects=[], links=links,
                                  pipeline_id=sync_scope.stream, store=executor._store)
    if missing_endpoint:
        with pytest.raises(EcomConsistencyError, match='original base record'):
            executor._store.apply_strict_link_batch(command)
        assert executor._store.read_committed_batch(command) is None
        assert executor._store.get_checkpoint(command) is None
        assert conn.execute('SELECT count(*) AS n FROM ecom_link').fetchone()['n'] == 0
        assert conn.execute("SELECT count(*) AS n FROM projection_outbox WHERE change_kind='links_written'").fetchone()['n'] == 0
    else:
        from sqlalchemy import text
        from sqlalchemy.exc import OperationalError
        from aos_api.ecom_consistency_store import _apply_transaction_scope
        original_reconcile = executor._store._reconcile_base_events
        probes = []
        def reconcile(db, original_command, receipt):
            result = original_reconcile(db, original_command, receipt)
            with pytest.raises(OperationalError) as failure:
                with executor._store._engine.begin() as competing:
                    _apply_transaction_scope(competing, org_id=sync_scope.org_id,
                                             workspace_id=sync_scope.workspace_id)
                    competing.execute(text("SET LOCAL lock_timeout='100ms'"))
                    competing.execute(text('UPDATE ecom_object SET updated_at=updated_at'))
            assert failure.value.orig.sqlstate == '55P03'
            probes.append(True)
            return result
        monkeypatch.setattr(executor._store, '_reconcile_base_events', reconcile)
        assert executor._store.apply_strict_link_batch(command).links_written == 1
        assert executor._store.apply_strict_link_batch(command).replayed
        assert len(probes) == 2
        monkeypatch.setattr(executor._store, '_reconcile_base_events', original_reconcile)
        assert executor._store.read_committed_batch_revision(command) > 0
        assert conn.execute('SELECT count(*) AS n FROM ecom_link').fetchone()['n'] == 1
    assert state['calls'] == 1
