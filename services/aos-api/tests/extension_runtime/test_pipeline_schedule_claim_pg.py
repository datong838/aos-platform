"""Real row-lock claim guards; package and source are explicit fixtures."""
import pytest
from test_controlled_snapshot_ingress_pg import executor_case
from test_pipeline_schedule_control_binding_pg import binding_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database, pytestmark
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner


@pytest.fixture
def claiming(executor_case, binding_case, monkeypatch):
    import aos_api.pipeline_schedule_claim as module
    original, conn, args, state = executor_case
    monkeypatch.setattr(module, '_connection', original._transaction)
    conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_stopped=true")
    owner = PipelineScheduleControlOwner(controls=original._claims._controls)
    bind_args = dict(scope=args['scope'], schedule_id='schedule', control_ref=args['control_ref'],
        actor=args['actor'], idempotency_key='initial')
    return module, original, conn, args, owner, bind_args


def test_first_binding_after_discovery_blocks_legacy_claim(claiming):
    module, original, conn, args, owner, bind_args = claiming
    assert module.read_schedule_binding(args['scope'], 'schedule') is None
    with original._transaction(args['scope']) as db:
        binding = owner.bind(db, **bind_args)
    with pytest.raises(RuntimeRevisionConflict):
        with module.schedule_claim_connection(args['scope'], schedule_id='schedule'):
            pytest.fail('legacy claim must not be reached')
    with module.schedule_claim_connection(args['scope'], schedule_id='schedule', binding=binding) as db:
        db.execute("UPDATE meta_schedule_run SET status='running',executor_stopped=false WHERE id=%s", (args['run_id'],))
    assert conn.execute('SELECT status FROM meta_schedule_run WHERE id=%s', (args['run_id'],)).fetchone()['status']=='running'


def test_legacy_claim_before_first_binding_prevents_cutover(claiming):
    module, original, conn, args, owner, bind_args = claiming
    with module.schedule_claim_connection(args['scope'], schedule_id='schedule') as db:
        db.execute("UPDATE meta_schedule_run SET status='running',executor_stopped=false WHERE id=%s", (args['run_id'],))
    with pytest.raises(RuntimeConflict, match='stopped'):
        with original._transaction(args['scope']) as db:
            owner.bind(db, **bind_args)
    assert module.read_schedule_binding(args['scope'], 'schedule') is None


def test_disabled_schedule_cannot_claim_even_after_discovery(claiming):
    module, _, conn, args, _, _ = claiming
    assert module.read_schedule_binding(args['scope'], 'schedule') is None
    conn.execute('UPDATE meta_schedule SET enabled=false')
    with pytest.raises(RuntimeConflict, match='enabled'):
        with module.schedule_claim_connection(args['scope'], schedule_id='schedule'):
            pytest.fail('disabled claim must not be reached')


def test_claim_and_binding_serialize_on_same_real_row_lock(claiming):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    module, original, conn, args, owner, bind_args = claiming
    entered = Event()
    def bind_concurrently():
        with original._transaction(args['scope']) as db:
            entered.set()
            return owner.bind(db, **bind_args)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with module.schedule_claim_connection(args['scope'], schedule_id='schedule') as db:
            future = pool.submit(bind_concurrently)
            assert entered.wait(5)
            db.execute("UPDATE meta_schedule_run SET status='running',executor_stopped=false WHERE id=%s", (args['run_id'],))
        with pytest.raises(RuntimeConflict, match='stopped'):
            future.result(timeout=5)
    assert module.read_schedule_binding(args['scope'], 'schedule') is None
