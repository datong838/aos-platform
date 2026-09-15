"""One original route drives the fixed snapshot fulfillment coordinator."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
from types import SimpleNamespace as NS
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

pytest_plugins = ('test_analysis_snapshot_resume_chain_pg',)
pytestmark = [
    pytest.mark.parametrize('startup_case', ['defer-host'], indirect=True),
    pytest.mark.parametrize('stored', ['qualified-runtime'], indirect=True),
]

from aos_api.data_requirement_outbox_store import DataRequirementOutboxStore
from aos_api.ecommerce_analysis_data_requirement_route import AnalysisDataRequirementRouteReader
from aos_api.ecommerce_analysis_snapshot_coordinator import AnalysisSnapshotCoordinator
from aos_api.ecommerce_analysis_snapshot_policy_set import AnalysisSnapshotPolicySetOwner


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


def test_claim_route_is_the_only_input_to_fixed_coordinator(chain_case):
    conn, state, analysis, _prepared_session, root, requirement = chain_case
    conn.rollback()
    factory = _runtime_connect(conn)
    analysis.connect = factory
    claim = DataRequirementOutboxStore(factory).claim_next(analysis.scope,
        topic='data.requirement.request', worker_id='snapshot-coordinator-test',
        lease_token='snapshot-coordinator-test-token', lease_seconds=300)
    assert claim is not None
    route = AnalysisDataRequirementRouteReader(
        claims=analysis.source.reader._journal._claims, connect_factory=factory).read(analysis.scope, claim)

    artifacts = analysis.source.reader._journal._claims._controls._selections._artifacts
    old_record = artifacts.load_record
    documents = {path: artifacts.read_artifact(None, path, 256 * 1024)
        for _, path in AnalysisSnapshotPolicySetOwner.POLICIES}
    indexed = [dict(relativePath=path, digest='sha256:' + hashlib.sha256(raw).hexdigest(),
        size=len(raw), mediaType='application/json') for path, raw in documents.items()]
    artifacts.load_record = lambda selected: NS(manifest=old_record(selected).manifest, artifacts=indexed)

    coordinator = AnalysisSnapshotCoordinator(analysis=analysis,
        completion=state['completion'], store=state['completion']._store)
    result = coordinator.run(route=route)
    assert result['phase'] == 'RUNNING'
    assert result['requirementRef']['resourceId'] == requirement.requirement_id
    assert result['receiptRef'] != root['receiptRef']
    before = {table: conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in (
        'aip_evidence', 'source_readiness_receipt', 'data_fulfillment_receipt',
        'ecommerce_growth_runtime_command_receipt', 'ecom_ingest_receipt')}
    assert coordinator.run(route=route) == result
    assert before == {table: conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in before}
    assert state['calls'] == 1

    changed = replace(route, generation=str(uuid4()))
    with pytest.raises(ValueError, match='route differs'):
        coordinator.run(route=changed)
    assert before == {table: conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in before}

    state['denied'] = True
    with pytest.raises(PermissionError, match='policy denied'):
        coordinator.run(route=route)
    assert before == {table: conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in before}
