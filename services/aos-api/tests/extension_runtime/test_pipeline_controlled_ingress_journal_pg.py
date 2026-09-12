"""Controlled current gates with real saved batches/recovery; asset authority remains a named fake."""
import importlib.util
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case, reserve, legacy_args
from aos_api.ec_ingress_journal import IngressJournalConflict, _digest
from aos_api.ec_ingress_claim import claim_failed_run
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def prepared(claim_case):
    conn,owner,args,*_=claim_case
    reserve(claim_case)
    conn.execute('RESET ROLE')
    conn.execute('ALTER TABLE meta_schedule_run ADD COLUMN executor_stopped boolean, ADD COLUMN finished_at timestamptz')
    for filename in ('a0v_006_ingress_derived_journal.py','a0v_009_ingress_recovery_claim.py'):
        path=Path(__file__).resolve().parents[2]/'alembic/versions'/filename
        spec=importlib.util.spec_from_file_location(filename[:-3],path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    journal=ControlledIngressJournal(claims=owner,**args)
    return claim_case,journal


def test_controlled_original_and_derived_preparation_are_replayable(prepared):
    case,journal=prepared;conn,_,args,*_=case
    with conn.transaction():
        journal.lock_run(conn,args['scope'],args['run_id'])
        first=journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(case))
        derived=journal.save_derived(conn,args['scope'],args['run_id'],())
    with conn.transaction():
        assert journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(case))==first
        assert journal.save_derived(conn,args['scope'],args['run_id'],())==derived
    assert conn.execute('SELECT count(*) FROM ecommerce_ingress_command').fetchone()=={'count':1}
    assert conn.execute('SELECT count(*) FROM ecommerce_ingress_derived_command').fetchone()=={'count':1}


@pytest.mark.parametrize('stage',['lock','original','derived'])
def test_every_write_rechecks_current_permission(prepared,stage):
    case,journal=prepared;conn,_,args,_,_,selections=case
    with conn.transaction():journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(case))
    def deny(*a):raise PermissionError('current denied')
    selections._guarded=deny
    with pytest.raises(PermissionError),conn.transaction():
        if stage=='lock':journal.lock_run(conn,args['scope'],args['run_id'])
        elif stage=='original':journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(case))
        else:journal.save_derived(conn,args['scope'],args['run_id'],())
    assert conn.execute('SELECT count(*) FROM ecommerce_ingress_derived_command').fetchone()=={'count':0}


@pytest.mark.parametrize('kind',['run','tenant'])
def test_journal_cannot_change_fixed_target(prepared,kind):
    case,journal=prepared;conn,_,args,*_=case
    with pytest.raises((ValueError,PermissionError)),conn.transaction():
        journal.lock_run(conn,TenantScope('dev-org','dev-project') if kind=='tenant' else args['scope'],
            'run-two' if kind=='run' else args['run_id'])


def test_existing_recovery_owner_resumes_same_controlled_batch(prepared):
    case,journal=prepared;conn,_,args,*_=case
    with conn.transaction():parent=journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(case))
    conn.execute("UPDATE meta_schedule_run SET status='failed',executor_stopped=true,finished_at=clock_timestamp()")
    @contextmanager
    def connection(scope):
        assert scope==args['scope']
        yield conn
    claim_id=str(uuid4())
    assert claim_failed_run(connection,args['scope'],args['run_id'],claim_id,journal=journal) is True
    assert claim_failed_run(connection,args['scope'],args['run_id'],claim_id,journal=journal) is False
    assert _digest(journal.read(conn,args['scope'],args['run_id']))==_digest(parent)
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':1}
    assert conn.execute('SELECT status FROM meta_schedule_run WHERE id=%s',(args['run_id'],)).fetchone()=={'status':'running'}


def test_untrusted_gate_dependency_is_not_accepted():
    with pytest.raises(TypeError):ControlledIngressJournal(claims=SimpleNamespace(),scope=TenantScope('org-org','dev-project'),run_id='run',control_ref={},actor='actor')


def test_recovery_with_wrong_claim_actor_rolls_back(prepared):
    case,journal=prepared;conn,owner,args,*_=case
    with conn.transaction():journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(case))
    conn.execute("UPDATE meta_schedule_run SET status='failed',executor_stopped=true,finished_at=clock_timestamp()")
    wrong=ControlledIngressJournal(claims=owner,**(args|{'actor':'different-actor'}))
    @contextmanager
    def connection(scope):yield conn
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    with pytest.raises(RuntimeConflict,match='binding differs'):
        claim_failed_run(connection,args['scope'],args['run_id'],str(uuid4()),journal=wrong)
    assert conn.execute('SELECT count(*) FROM ecommerce_ingress_recovery_claim').fetchone()=={'count':0}
    assert conn.execute('SELECT status FROM meta_schedule_run WHERE id=%s',(args['run_id'],)).fetchone()=={'status':'failed'}
