"""Runtime service uses real current Owners and saved recovery facts in PG."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_controlled_schedule_guard_pg import bound_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_pipeline_schedule_control_binding_pg import binding_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database, pytestmark
from aos_api.pipeline_control_service import PipelineControlServices
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict


@pytest.fixture
def runtime_case(bound_case, monkeypatch):
    import aos_api.pipeline_controlled_runtime as module
    bound, original, conn, args, state, owner, bind_args, binding = bound_case
    service = PipelineControlServices(args['scope'], original._claims._controls._selections,
        original._claims._controls, original._claims)
    monkeypatch.setattr(module, 'runtime_worker_connection', original._connect)
    monkeypatch.setattr(module, 'consumer_connection', lambda connect, scope: original._transaction(args['scope']))
    @contextmanager
    def store(): yield original._store
    monkeypatch.setattr(module, '_authoritative_store', store)
    execution = module.ControlledScheduleExecution(service, binding, object(), recovery=True)
    return execution, bound, original, conn, args, state, owner, bind_args, binding


@pytest.mark.parametrize('change', ['disabled','denied','rebound'])
def test_service_rechecks_current_authority_and_plan(runtime_case, change):
    execution, _, original, conn, args, state, owner, bind_args, binding = runtime_case
    execution.validate_current()
    if change == 'disabled': conn.execute('UPDATE meta_schedule SET enabled=false')
    elif change == 'denied': state['deny'] = True
    else:
        with original._transaction(args['scope']) as db:
            owner.bind(db, **bind_args, idempotency_key='rebind', previous_ref=binding.ref)
    with pytest.raises((RuntimeConflict, RuntimeRevisionConflict, PermissionError)):
        execution.validate_current()
    assert state['calls'] == 0


@pytest.mark.parametrize('stopped', [False, True])
def test_service_recovery_claim_keeps_original_input_and_stopped_gate(runtime_case, stopped):
    execution, bound, _, conn, args, state, _, _, _ = runtime_case
    bound.prepare(**args)
    assert state['calls'] == 1
    conn.execute('RESET ROLE')
    conn.execute('ALTER TABLE meta_schedule_run ADD COLUMN finished_at timestamptz')
    path = Path(__file__).resolve().parents[2]/'alembic/versions/a0v_009_ingress_recovery_claim.py'
    spec = importlib.util.spec_from_file_location('runtime_recovery_migration', path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=conn.execute); migration.upgrade()
    conn.execute("UPDATE meta_schedule_run SET status='failed',executor_stopped=%s,finished_at=now()", (stopped,))
    conn.execute('SET ROLE aos_runtime')
    claim_id = str(uuid4())
    if stopped:
        assert execution.claim_recovery(run_id=args['run_id'], claim_id=claim_id) is True
        assert execution.claim_recovery(run_id=args['run_id'], claim_id=claim_id) is False
        assert conn.execute('SELECT count(*) FROM ecommerce_ingress_recovery_claim').fetchone()=={'count':1}
    else:
        with pytest.raises(IngressJournalConflict, match='STOPPED'):
            execution.claim_recovery(run_id=args['run_id'], claim_id=claim_id)
        assert conn.execute('SELECT count(*) FROM ecommerce_ingress_recovery_claim').fetchone()=={'count':0}
    assert state['calls'] == 1
