"""Current v2 policy and original PG records; package/source remain explicit fixtures."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import json
import psycopg
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
from test_snapshot_group_link_executor_pg import link_executor_case
from test_snapshot_group_relationship_audit_pg import audit_case, add_extra
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.pipeline_snapshot_group_retirement_journal import PipelineSnapshotGroupRetirementJournal


def migrate(conn):
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_048_snapshot_group_retirement.py'
    spec=importlib.util.spec_from_file_location('group_retirement_schema',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    conn.execute('RESET ROLE');module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')


@pytest.fixture
def retirement_case(assessment_case,request):
    parts=list(assessment_case);state=parts[3]
    document=json.loads(state['policy_raw'])
    document.update(schemaVersion='aos.snapshot-relationships/v2',retirement=dict(mode='present-rows-only',
        requireCompleteReferences=True,rejectNewerThanObservation=True,allowMissingRowDeletion=False))
    state['policy_raw']=json.dumps(document).encode()
    parts[5]=parts[5].model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['policy_raw']).hexdigest()})
    prepared=journal_case.__wrapped__(tuple(parts))
    generator=object_case.__wrapped__(prepared);original=next(generator)
    try:
        base=link_case.__wrapped__(original)
        executor,conn,args,state=link_executor_case.__wrapped__(base)
        migrate(conn);executor.execute(**args)
        if getattr(request,'param',True):add_extra(executor,args)
        journal=PipelineSnapshotGroupRetirementJournal(claims=executor._objects._claims,store=executor._store)
        yield executor,conn,args,state,journal
    finally:
        try:next(generator)
        except StopIteration:pass


def test_prepare_and_applied_receipt_replay_keep_original_command(retirement_case):
    executor,conn,args,state,journal=retirement_case
    with conn.transaction():first=journal.prepare(conn,**args)
    assert first.created and not first.applied and len(first.command.links)==1
    assert first.command.links[0].is_deleted
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n']==2
    executor._store.apply_strict_link_retirement_batch(first.command)
    with conn.transaction():replay=journal.prepare(conn,**args)
    with conn.transaction():read=journal.read_current(conn,**args)
    assert replay==read and replay.applied and not replay.created
    assert replay.command==first.command and replay.preparation_hash==first.preparation_hash
    assert state['calls']==1


def test_read_missing_never_creates_and_rollback_retries(retirement_case):
    _,conn,args,state,journal=retirement_case
    with pytest.raises(LookupError),conn.transaction():journal.read_current(conn,**args)
    with pytest.raises(RuntimeError,match='rollback'),conn.transaction():
        journal.prepare(conn,**args);raise RuntimeError('rollback')
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_retirement').fetchone()['n']==0
    with conn.transaction():assert journal.prepare(conn,**args).created
    assert state['calls']==1


def test_unapplied_prior_change_invalidates_saved_preparation(retirement_case):
    from datetime import timedelta
    from aos_api.ec_ot_writer import _build_batch_command
    executor,conn,args,_,journal=retirement_case
    with conn.transaction():saved=journal.prepare(conn,**args)
    old=saved.command.links[0]
    changed=old.model_copy(update={'is_deleted':False,'source_updated_at':old.source_updated_at+timedelta(seconds=1),
                                  'properties':{'fixture':'newer'}})
    command=_build_batch_command(sync_scope=old_scope(saved.command),objects=[],links=[changed],
                                 pipeline_id='newer-fixture',store=executor._store)
    executor._store.apply_batch(command)
    with pytest.raises(IngressJournalConflict),conn.transaction():journal.read_current(conn,**args)


def old_scope(command):return command.scope.model_copy(update={'stream':'newer-fixture'})


def test_regular_delete_receipt_cannot_replace_conditional_retirement(retirement_case):
    from aos_api.ecom_core_models import EcomConsistencyError
    executor,conn,args,_,journal=retirement_case
    with conn.transaction():saved=journal.prepare(conn,**args)
    executor._store.apply_strict_link_batch(saved.command)
    with pytest.raises(EcomConsistencyError,match='retirement precondition evidence'),conn.transaction():
        journal.read_current(conn,**args)


@pytest.mark.parametrize('retirement_case',[False],indirect=True)
def test_no_residual_has_null_command_without_fake_receipt(retirement_case):
    executor,conn,args,_,journal=retirement_case
    with conn.transaction():first=journal.prepare(conn,**args)
    with conn.transaction():replay=journal.read_current(conn,**args)
    assert first.command is None and replay.command is None
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n']==3


def test_retirement_history_is_immutable_and_tenant_isolated(retirement_case):
    _,conn,args,_,journal=retirement_case
    with conn.transaction():journal.prepare(conn,**args)
    for statement in ('UPDATE pipeline_snapshot_group_retirement SET audit_hash=audit_hash',
                      'DELETE FROM pipeline_snapshot_group_retirement','TRUNCATE pipeline_snapshot_group_retirement'):
        with pytest.raises(psycopg.Error),conn.transaction():conn.execute(statement)
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_retirement').fetchone()['n']==0


def test_v1_policy_does_not_enable_retirement(audit_case):
    executor,conn,args,_,_=audit_case
    migrate(conn);executor.execute(**args)
    journal=PipelineSnapshotGroupRetirementJournal(claims=executor._objects._claims,store=executor._store)
    with pytest.raises(PermissionError,match='retirement policy'),conn.transaction():journal.prepare(conn,**args)


def test_post_prepare_revocation_cannot_commit_when_caught(retirement_case,monkeypatch):
    executor,conn,args,state,journal=retirement_case
    original=executor._store.get_checkpoint
    def revoke(command):
        result=original(command);state['deny']=True;return result
    monkeypatch.setattr(executor._store,'get_checkpoint',revoke)
    with conn.transaction():
        with pytest.raises(PermissionError):journal.prepare(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_retirement').fetchone()['n']==0


@pytest.mark.parametrize('fault',['parent','assessment','count','active','time'])
def test_database_rejects_retirement_binding_drift(retirement_case,fault):
    from datetime import timedelta
    from psycopg.types.json import Jsonb
    _,conn,args,_,journal=retirement_case
    with pytest.raises(RuntimeError,match='fixture rollback'),conn.transaction():
        journal.prepare(conn,**args)
        row=conn.execute('SELECT * FROM pipeline_snapshot_group_retirement').fetchone()
        raise RuntimeError('fixture rollback')
    if fault=='parent':row['parent_command_hash']='sha256:'+'f'*64
    elif fault=='assessment':row['audit']['assessmentHash']='sha256:'+'f'*64
    elif fault=='count':row['audit']['cleanupCandidates']=[]
    elif fault=='active':row['command']['links'][0]['is_deleted']=False
    else:row['prepared_at']+=timedelta(seconds=1)
    with pytest.raises(psycopg.Error),conn.transaction():
        conn.execute('INSERT INTO pipeline_snapshot_group_retirement(org_id,project_id,group_id,parent_command_hash,audit_hash,audit,prepared_at,preparation_hash,command) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (*args['scope'].key,args['group_id'],row['parent_command_hash'],row['audit_hash'],Jsonb(row['audit']),row['prepared_at'],row['preparation_hash'],Jsonb(row['command'])))
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_retirement').fetchone()['n']==0


def test_shape_valid_forged_retirement_cannot_target_wanted_edge(retirement_case):
    from psycopg.types.json import Jsonb
    from aos_api.source_read_observation import observed_rows_hash
    from aos_api.pipeline_snapshot_group_retirement_journal import _envelope
    executor,conn,args,_,journal=retirement_case
    with pytest.raises(RuntimeError,match='fixture rollback'),conn.transaction():
        journal.prepare(conn,**args)
        row=conn.execute('SELECT * FROM pipeline_snapshot_group_retirement').fetchone()
        raise RuntimeError('fixture rollback')
    with executor._transaction(args['scope']) as db:parent=executor._commands.read_current(db,**args)
    wanted=parent.command.links[0]
    descriptor=row['audit']['cleanupCandidates'][0]
    descriptor['sourceId']=wanted.source.external_id
    descriptor['payloadHash']=wanted.payload_hash()
    row['audit_hash']=observed_rows_hash([row['audit']])
    link=row['command']['links'][0]
    link['source']=wanted.source.model_dump(mode='json')
    link['properties']['retirementExpectedPayloadHash']=wanted.payload_hash()
    link['properties']['retirementAuditHash']=row['audit_hash']
    row['command']['idempotency_key']=journal._key(args['group_id'],row['audit_hash'])
    row['preparation_hash']=observed_rows_hash([_envelope(row['parent_command_hash'],row['audit_hash'],row['audit'],row['prepared_at'],row['command'])])
    with conn.transaction():
        conn.execute('INSERT INTO pipeline_snapshot_group_retirement(org_id,project_id,group_id,parent_command_hash,audit_hash,audit,prepared_at,preparation_hash,command) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (*args['scope'].key,args['group_id'],row['parent_command_hash'],row['audit_hash'],Jsonb(row['audit']),row['prepared_at'],row['preparation_hash'],Jsonb(row['command'])))
    with pytest.raises(IngressJournalConflict,match='RETIREMENT_LINK_SCOPE_INVALID'),conn.transaction():
        journal.read_current(conn,**args)
