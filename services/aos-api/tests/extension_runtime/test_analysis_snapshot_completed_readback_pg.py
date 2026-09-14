"""Real original receipts; final schedule state is a named readback-only fixture.

This does not prove the completion writer (e6d2). No copied Task/Run state.
"""
import hashlib
import json

import pytest

from test_analysis_snapshot_native_projection_pg import (
    native_projection_case,private_database,stored,native_claims_case,native_input_case,
    host_case,control_governed,governed,service_case,pair,body,
)
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.pipeline_snapshot_group_retirement_executor import ControlledSnapshotGroupRetirementExecutor


@pytest.fixture
def completed_receipts_case(native_projection_case,request,monkeypatch):
    objects,conn,args,state = native_projection_case
    policy = json.loads(state['policy_raw'])
    policy.update(schemaVersion='aos.snapshot-relationships/v2',retirement=dict(mode='present-rows-only',
        requireCompleteReferences=True,rejectNewerThanObservation=True,allowMissingRowDeletion=False))
    state['policy_raw'] = json.dumps(policy).encode()
    args = args|{'policy_ref':args['policy_ref'].model_copy(update={
        'content_hash':'sha256:'+hashlib.sha256(state['policy_raw']).hexdigest()})}
    executor = ControlledSnapshotGroupRetirementExecutor(claims=objects._claims,store=objects._store,
        connect=objects._single._ingress._connect,eng=objects._single._eng)
    if getattr(request,'param',False):
        from test_snapshot_group_relationship_audit_pg import add_extra
        from aos_api import ecom_projector
        executor._links.execute(**args)
        add_extra(executor._links,args)
        monkeypatch.setattr(ecom_projector,'connect',executor._transaction)
        assert ecom_projector.project_pending(args['scope'])['pending'] == 0
    result = executor.execute(**args)
    assert result['reconciliation_status'] == 'complete'
    with executor._transaction(args['scope']) as db:
        prior = executor._retirement.read_current(db,**args)
    # Deliberately named terminal fixture only for readonly API validation.
    # e6d2 must replace this setup with the actual completion service.
    conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_id='ec-live-v1',executor_stopped=true,finished_at=clock_timestamp()")
    return executor,conn,args,state,prior


def test_completed_readback_keeps_original_receipts_without_writes(completed_receipts_case,monkeypatch):
    executor,conn,args,state,prior = completed_receipts_case
    retirement = executor._retirement
    audit = retirement._audit
    commands = retirement._commands
    relationship = commands._relationships
    tables = ('pipeline_snapshot_group_relationship','pipeline_snapshot_group_link_command',
        'pipeline_snapshot_group_retirement','ecom_ingest_receipt','projection_outbox',
        'ecommerce_ingress_dataset_receipt')
    def counts():
        return {table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in tables}
    before = counts()
    with executor._transaction(args['scope']) as db:
        assert retirement.read_completed_current(db,**args) == prior
        first = commands.read_completed_current(db,**args)
        assert first.created is False
        assert relationship.read_completed_current(db,**args).created is False
        current = audit.read_completed_current(db,**args)
        assert all(value['missingExpected'] == value['extraActive'] == value['uncertainReferences'] == 0
                   for value in current.counts.values())
    assert counts() == before and state['calls'] == 1


    # Completed state is never a new preparation grant.
    for owner in (relationship,commands,retirement):
        with pytest.raises(IngressJournalConflict),executor._transaction(args['scope']) as db:
            owner.prepare(db,**args)
    # A callback changing a current release cannot leak a successful read.
    with pytest.raises(PermissionError,match='named installed policy denied'),executor._transaction(args['scope']) as db:
        audit.run_completed_current(db,**args,execute=lambda value:state.update(denied=True))
    state['denied'] = False
    with pytest.raises((PermissionError,IngressJournalConflict)),executor._transaction(args['scope']) as db:
        db.execute("SELECT set_config('aos.org_id','dev-org',true)")
        retirement.read_completed_current(db,**args)
    # Missing immutable read is not permission to insert it again.
    from psycopg import sql
    from types import SimpleNamespace
    from contextlib import contextmanager
    class Missing:
        def __init__(self,db):
            self.db = db
        def __getattr__(self,name):
            return getattr(self.db,name)
        @contextmanager
        def cursor(self,*a,**kw):
            with self.db.cursor(*a,**kw) as cursor:
                def execute(query,params=()):
                    rendered = query.as_string(self.db) if isinstance(query,sql.Composable) else query
                    if isinstance(rendered,str) and rendered.startswith('SELECT parent_command_hash,audit_hash'):
                        return SimpleNamespace(fetchone=lambda:None)
                    return cursor.execute(query,params)
                yield SimpleNamespace(execute=execute)
    # Use actual runtime connection, only named final SELECT response is absent.
    with executor._transaction(args['scope']) as db:
        with pytest.raises(LookupError,match='original retirement preparation required'):
            retirement.read_completed_current(Missing(db),**args)
    assert counts() == before and state['calls'] == 1


@pytest.mark.parametrize('completed_receipts_case',[True],indirect=True)
def test_completed_nonempty_retirement_reads_actual_applied_receipt(completed_receipts_case):
    executor,conn,args,state,prior = completed_receipts_case
    assert prior.command is not None and prior.applied is True
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n'] == 1
    before = conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n']
    with executor._transaction(args['scope']) as db:
        assert executor._retirement.read_completed_current(db,**args) == prior
        assert executor._store.read_batch_projection_completion(prior.command,[]) == dict(expected=1,projected=1,pending=0)
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n'] == before
    assert state['calls'] == 1
