"""Original event -> DataRequirement Outbox -> lifecycle worker -> unified resume."""
import asyncio
from contextlib import contextmanager
import hashlib
from types import SimpleNamespace

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

pytest_plugins = ('test_analysis_snapshot_resume_chain_pg',)
pytestmark = [
    pytest.mark.parametrize('startup_case', ['defer-host'], indirect=True),
    pytest.mark.parametrize('stored', ['qualified-runtime'], indirect=True),
    pytest.mark.parametrize('chain_case', ['natural-worker'], indirect=True),
]

from aos_api.ecommerce_analysis_data_requirement_worker import AnalysisDataRequirementWorker
from aos_api.ecommerce_analysis_snapshot_policy_set import AnalysisSnapshotPolicySetOwner
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.tenant_scope import TenantScope


CANARY = TenantScope('dev-org', 'dev-project')


def _runtime_connect(conn):
    dsn = conn.info.dsn
    identity = conn.execute('SELECT session_user AS name').fetchone()['name']
    conn.rollback()
    @contextmanager
    def factory(scope):
        with psycopg.connect(dsn, row_factory=dict_row,
                options='-c default_transaction_isolation=serializable') as current:
            current.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(identity)))
            current.execute('SET ROLE aos_runtime')
            current.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)", scope.key)
            yield current
    return factory


def _install_policy_index(analysis, state):
    artifacts = analysis.source.reader._journal._claims._controls._selections._artifacts
    original = artifacts.load_record
    documents = state['policy_documents']
    indexed = [dict(relativePath=path, digest='sha256:' + hashlib.sha256(raw).hexdigest(),
        size=len(raw), mediaType='application/json') for _, path in AnalysisSnapshotPolicySetOwner.POLICIES
        for raw in (documents[path],)]
    artifacts.load_record = lambda selected: SimpleNamespace(
        manifest=original(selected).manifest, artifacts=indexed)


def _build_worker(monkeypatch, conn, state, analysis):
    import aos_api.ecommerce_analysis_data_requirement_worker as worker_module
    connect_factory = _runtime_connect(conn)
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_DATABASE_URL', conn.info.dsn)
    analysis.connect = connect_factory
    factory = object.__new__(PipelineControlServiceFactory)
    claims = analysis.source.reader._journal._claims
    monkeypatch.setattr(PipelineControlServiceFactory, 'build',
        lambda self, scope: SimpleNamespace(claims=claims))
    monkeypatch.setattr(PipelineControlServiceFactory, 'build_event_analysis',
        lambda self, scope, **kwargs: analysis)
    directory = LivePreparedJobDirectory()
    target = (analysis.scope, analysis.invoker.installation_id, analysis.invoker.generation)
    monkeypatch.setattr(directory, 'current_targets', lambda: (target,))
    def resolve(**kwargs):
        assert kwargs == dict(scope=analysis.scope,
            installation_id=str(analysis.invoker.installation_id),
            generation=str(analysis.invoker.generation))
        return object()
    monkeypatch.setattr(directory, 'resolve', resolve)
    monkeypatch.setattr(worker_module, 'connect_serializable', connect_factory)
    @contextmanager
    def store():
        yield state['completion']._store
    monkeypatch.setattr(worker_module, '_authoritative_store', store)
    worker = AnalysisDataRequirementWorker(factory, directory)
    monkeypatch.setattr(worker, '_markings', lambda scope, actor: ('internal',))
    return worker


def _business_state(conn, analysis, root):
    conn.rollback()
    tables = ('aip_evidence', 'aip_evidence_bundle_revision', 'source_readiness_receipt',
        'data_fulfillment_receipt', 'ecommerce_growth_runtime_command_receipt',
        'ecom_ingest_receipt')
    counts = {table: conn.execute(
        f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND "
        f"{'workspace_id' if table == 'ecom_ingest_receipt' else 'project_id'}=%s",
        analysis.scope.key).fetchone()['n'] for table in tables}
    task = conn.execute('''SELECT status,version FROM aip_task_run
        WHERE org_id=%s AND project_id=%s AND run_id=%s''',
        (*analysis.scope.key, root['taskRunRef']['resourceId'])).fetchone()
    run = conn.execute('''SELECT lifecycle,current_version AS version,content_hash
        FROM ecommerce_investigation_run_state_head
        WHERE org_id=%s AND project_id=%s AND run_id=%s''',
        (*analysis.scope.key, root['runRef']['resourceId'])).fetchone()
    return counts, dict(task), dict(run)


def _delivery(conn, analysis):
    conn.rollback()
    return conn.execute('''SELECT state,attempt,lease_token,lease_expires_at,
               completion_fulfillment_ref,completion_analysis_ref
        FROM data_requirement_outbox_delivery WHERE org_id=%s AND project_id=%s''',
        analysis.scope.key).fetchone()


def _assert_canary_empty(conn):
    conn.rollback()
    for table in ('data_requirement_outbox_delivery', 'data_requirement_head',
                  'ecommerce_investigation_run_state_head', 'aip_evidence'):
        assert conn.execute(f'SELECT count(*) AS n FROM {table} WHERE org_id=%s AND project_id=%s',
            CANARY.key).fetchone()['n'] == 0


def test_original_event_naturally_resumes_through_worker_and_second_tick_is_idle(
        chain_case, monkeypatch):
    conn, state, analysis, session, root, _requirement = chain_case
    assert session is None
    _install_policy_index(analysis, state)
    worker = _build_worker(monkeypatch, conn, state, analysis)
    before = _business_state(conn, analysis, root)
    assert before[1]['status'] == 'paused' and before[2]['lifecycle'] == 'WAITING_DATA'

    first = asyncio.run(worker.tick())
    assert first['scopesChecked'] == 1 and first['completed'] == 1, first
    delivered = _delivery(conn, analysis)
    assert delivered['state'] == 'acked'
    assert delivered['completion_fulfillment_ref']['resourceType'] == 'DataFulfillmentReceipt'
    assert delivered['completion_analysis_ref']['resourceType'] == 'AnalysisRuntimeReceipt'
    after = _business_state(conn, analysis, root)
    assert after[1]['status'] == 'running' and after[2]['lifecycle'] == 'PREPARING'

    second = asyncio.run(worker.tick())
    assert second == {'scopesChecked': 1, 'completed': 0, 'replayed': 0,
                      'unknown': 0, 'failed': 0}
    assert _business_state(conn, analysis, root) == after
    assert _delivery(conn, analysis) == delivered
    _assert_canary_empty(conn)


def test_unknown_after_coordination_reconciles_after_worker_rebuild_and_expired_lease(
        chain_case, monkeypatch):
    conn, state, analysis, session, root, _requirement = chain_case
    assert session is None
    _install_policy_index(analysis, state)
    first_worker = _build_worker(monkeypatch, conn, state, analysis)
    monkeypatch.setattr(first_worker._outbox, 'complete', lambda *args, **kwargs:
        (_ for _ in ()).throw(TimeoutError('completion result unavailable')))

    first = asyncio.run(first_worker.tick())
    assert first['unknown'] == 1
    unknown = _delivery(conn, analysis)
    assert unknown['state'] == 'unknown' and unknown['completion_fulfillment_ref'] is None
    committed = _business_state(conn, analysis, root)
    assert committed[1]['status'] == 'running' and committed[2]['lifecycle'] == 'PREPARING'

    with psycopg.connect(conn.info.dsn) as admin:
        admin.execute('''UPDATE data_requirement_outbox_delivery
            SET lease_expires_at=clock_timestamp()-INTERVAL '1 second'
            WHERE org_id=%s AND project_id=%s''', analysis.scope.key)
    rebuilt = _build_worker(monkeypatch, conn, state, analysis)
    reconciled = asyncio.run(rebuilt.tick())
    assert reconciled['completed'] == 1, reconciled
    delivered = _delivery(conn, analysis)
    assert delivered['state'] == 'acked' and delivered['attempt'] == unknown['attempt']
    assert delivered['lease_token'] == unknown['lease_token']
    assert delivered['completion_fulfillment_ref'] is not None
    assert delivered['completion_analysis_ref'] is not None
    assert _business_state(conn, analysis, root) == committed

    idle = asyncio.run(rebuilt.tick())
    assert idle == {'scopesChecked': 1, 'completed': 0, 'replayed': 0,
                    'unknown': 0, 'failed': 0}
    assert _business_state(conn, analysis, root) == committed
    _assert_canary_empty(conn)
