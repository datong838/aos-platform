"""Completed-read gate with actual isolated journal rows; asset Owner is a named double."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from psycopg.types.json import Jsonb
from test_pipeline_controlled_ingress_journal_pg import prepared,claim_case,reserve,legacy_args,owner_case,ledger,database,pytestmark
from aos_api.ec_ingress_journal import IngressJournalConflict,_digest
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal


@pytest.fixture
def completed(prepared):
    case,journal=prepared;conn,owner,args,*_=case
    with conn.transaction():
        parent=journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(case))
        derived=journal.save_derived(conn,args['scope'],args['run_id'],())
    conn.execute('RESET ROLE')
    conn.execute("ALTER TABLE meta_schedule_run ADD COLUMN executor_id text")
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_007_ingress_dataset_receipt.py'
    spec=importlib.util.spec_from_file_location('completed_receipt_migration',path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    result=dict(parentHash=_digest(parent),derivedHash=_digest(derived),completion=dict(expected=0,projected=0,pending=0),
        dataset=dict(pipelineId=parent['pipelineId'],sourceId=parent['sourceId']),build=dict(status='success'))
    conn.execute('INSERT INTO ecommerce_ingress_dataset_receipt(org_id,project_id,run_id,payload_hash,payload) VALUES(%s,%s,%s,%s,%s)',
        (*args['scope'].key,args['run_id'],_digest(result),Jsonb(result)))
    conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_id='ec-live-v1',executor_stopped=true,finished_at=clock_timestamp()")
    conn.execute('SET ROLE aos_runtime')
    return case,journal


def test_completed_input_readable_without_reopening_write_gate(completed):
    case,old=completed;conn,owner,args,*_=case
    with conn.transaction():assert owner.read_completed_current(conn,**args).run_id==args['run_id']
    with pytest.raises(IngressJournalConflict),conn.transaction():owner.read_saved_current(conn,**args)
    journal=ControlledIngressJournal(claims=owner,completed_read=True,**args)
    with conn.transaction():journal.verify_running_schedule(conn,args['scope'],**legacy_args(case))
    with pytest.raises(PermissionError):journal.save_derived(conn,args['scope'],args['run_id'],())
    with pytest.raises(PermissionError),conn.transaction():journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(case))


@pytest.mark.parametrize('fault',['running','stopped','missing','hash'])
def test_completed_receipt_gate_rejects_incomplete_input(completed,fault):
    case,_=completed;conn,owner,args,*_=case
    conn.execute('RESET ROLE')
    if fault=='running':conn.execute("UPDATE meta_schedule_run SET status='running'")
    if fault=='stopped':conn.execute('UPDATE meta_schedule_run SET executor_stopped=false')
    # Table is immutable; test missing/corrupt reads with a scoped temporary view
    # is unnecessary. Mutate only the assertion lookup using a proxy below.
    conn.execute('SET ROLE aos_runtime')
    class Proxy:
        def __getattr__(self,name):return getattr(conn,name)
        def execute(self,query,params=()):
            cursor=conn.execute(query,params)
            if fault in ('missing','hash') and 'payload,payload_hash' in str(query):
                row=cursor.fetchone()
                return SimpleNamespace(fetchone=lambda:None if fault=='missing' else dict(row,payload_hash='bad'))
            return cursor
    with pytest.raises(IngressJournalConflict),conn.transaction():owner.read_completed_current(Proxy(),**args)


def test_completed_history_does_not_bypass_current_permission(completed):
    case,_=completed;conn,owner,args,_,_,selections=case
    def deny(*args):raise PermissionError('current denied')
    selections._guarded=deny
    with pytest.raises(PermissionError),conn.transaction():owner.read_completed_current(conn,**args)


def test_completed_and_recovery_modes_are_distinct(completed):
    case,_=completed;_,owner,args,*_=case
    with pytest.raises(ValueError):ControlledIngressJournal(claims=owner,completed_read=True,saved_recovery=True,**args)
