"""One original route drives the fixed snapshot fulfillment coordinator."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import os
from types import SimpleNamespace as NS
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

pytest_plugins = ('test_analysis_snapshot_resume_chain_pg',)
pytestmark = [
    pytest.mark.parametrize('startup_case', ['defer-host'], indirect=True),
    pytest.mark.parametrize('stored', ['qualified-runtime'], indirect=True),
]

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_outbox_store import (
    DataRequirementOutboxConflict,
    DataRequirementOutboxStore,
)
from aos_api.ecommerce_analysis_data_requirement_route import AnalysisDataRequirementRouteReader
from aos_api.ecommerce_analysis_snapshot_coordinator import AnalysisSnapshotCoordinator
from aos_api.ecommerce_analysis_snapshot_policy_set import AnalysisSnapshotPolicySetOwner
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.pipeline_control_service import PipelineControlServiceFactory


def _private_dsn(conn):
    dsn = os.environ['AOS_DATABASE_URL']
    assert psycopg.conninfo.conninfo_to_dict(dsn)['dbname'] == conn.info.dbname
    return dsn


def _runtime_connect(conn):
    dsn = _private_dsn(conn)
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


@pytest.mark.parametrize('completion_path', ['complete', 'reconcile-completed'])
def test_claim_route_is_the_only_input_to_fixed_coordinator(chain_case, completion_path):
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

    outbox = DataRequirementOutboxStore(factory)
    fulfillment_ref = InvestigationExactRef.model_validate(result['fulfillmentRef'])
    analysis_ref = InvestigationExactRef.model_validate(result['receiptRef'])
    diagnostic = conn.execute('''SELECT
        f.status, f.authority_data->'tenant' AS fulfillment_tenant,
        f.authority_data->'requirementRef' AS fulfillment_requirement,
        f.authority_data->>'receiptId' AS authority_receipt_id,
        f.authority_data->>'contentHash' AS authority_content_hash,
        a.request_hash, a.response->>'requestHash' AS response_request_hash,
        a.response->>'phase' AS phase, a.response->'completed' AS completed,
        a.target_receipt_ref=%s::jsonb AS target_matches,
        a.response->'receiptRef'=a.target_receipt_ref AS response_target_matches,
        a.response->'requirementRef'=%s::jsonb AS analysis_requirement_matches,
        a.response->'fulfillmentRef'=%s::jsonb AS analysis_fulfillment_matches,
        a.response->'runRef'=q.run_ref-'receiptId' AS analysis_run_matches,
        q.run_ref->'receiptId'='null'::jsonb AS stored_run_null_receipt,
        q.run_ref, a.response->'runRef' AS analysis_run_ref
      FROM data_requirement_outbox o
      JOIN data_requirement_revision q ON q.org_id=o.org_id AND q.project_id=o.project_id
        AND q.requirement_id=o.requirement_id AND q.revision=o.requirement_revision
      JOIN data_fulfillment_receipt f ON f.org_id=o.org_id AND f.project_id=o.project_id
        AND f.receipt_id=%s
      JOIN ecommerce_growth_runtime_command_receipt a ON a.org_id=o.org_id
        AND a.project_id=o.project_id AND a.operation_id='ecommerce_growth_analysis_advance'
        AND a.target_receipt_ref=%s::jsonb
      WHERE o.org_id=%s AND o.project_id=%s AND o.outbox_id=%s''', (
        Jsonb(result['receiptRef']), Jsonb(result['requirementRef']),
        Jsonb(result['fulfillmentRef']), fulfillment_ref.receipt_id,
        Jsonb(result['receiptRef']), *analysis.scope.key, claim.outbox_id)).fetchone()
    assert diagnostic is not None, 'dual Receipt diagnostic join is empty'
    expected_fulfillment_requirement = dict(result['requirementRef'], receiptId=None)
    assert (
        diagnostic['status'] == 'fulfilled'
        and diagnostic['fulfillment_tenant'] == dict(orgId=analysis.scope.org_id,
            projectId=analysis.scope.project_id)
        and diagnostic['fulfillment_requirement'] == expected_fulfillment_requirement
        and diagnostic['authority_receipt_id'] == fulfillment_ref.receipt_id
        and diagnostic['authority_content_hash'] == fulfillment_ref.content_hash
        and diagnostic['request_hash'] == diagnostic['response_request_hash']
        and diagnostic['phase'] == 'RUNNING'
        and diagnostic['completed'] is False
        and diagnostic['target_matches']
        and diagnostic['response_target_matches']
        and diagnostic['analysis_requirement_matches']
        and diagnostic['analysis_fulfillment_matches']
        and diagnostic['analysis_run_matches']
        and diagnostic['stored_run_null_receipt']
    ), diagnostic
    wrong_attempt = replace(claim, attempt=claim.attempt + 1)
    wrong_token = replace(claim, lease_token='wrong-completion-token')
    missing_fulfillment = InvestigationExactRef(
        resource_type='DataFulfillmentReceipt', resource_id='missing-fulfillment-receipt',
        revision=1, content_hash='sha256:' + '0' * 64,
        receipt_id='missing-fulfillment-receipt')
    preparing_analysis = InvestigationExactRef.model_validate(route.analysis_receipt_ref)
    for attempted_claim, attempted_fulfillment, attempted_analysis in (
        (wrong_attempt, fulfillment_ref, analysis_ref),
        (wrong_token, fulfillment_ref, analysis_ref),
        (claim, missing_fulfillment, analysis_ref),
        (claim, fulfillment_ref, preparing_analysis),
    ):
        with pytest.raises(DataRequirementOutboxConflict):
            outbox.complete(analysis.scope, attempted_claim,
                attempted_fulfillment, attempted_analysis)
    if completion_path == 'complete':
        with psycopg.connect(_private_dsn(conn)) as admin:
            admin.execute('''UPDATE data_requirement_outbox_delivery
                SET lease_expires_at=clock_timestamp()-INTERVAL '1 second'
                WHERE org_id=%s AND project_id=%s AND outbox_id=%s''',
                (*analysis.scope.key, claim.outbox_id))
        with pytest.raises(DataRequirementOutboxConflict):
            outbox.complete(analysis.scope, claim, fulfillment_ref, analysis_ref)
        with psycopg.connect(_private_dsn(conn)) as admin:
            admin.execute('''UPDATE data_requirement_outbox_delivery
                SET lease_expires_at=clock_timestamp()+INTERVAL '300 seconds'
                WHERE org_id=%s AND project_id=%s AND outbox_id=%s''',
                (*analysis.scope.key, claim.outbox_id))
        completed = outbox.complete(analysis.scope, claim, fulfillment_ref, analysis_ref)
    else:
        unknown = outbox.mark_unknown(analysis.scope, claim.outbox_id, claim.lease_token,
            reason_code='COMMIT_RESULT_UNKNOWN')
        assert unknown.state == 'unknown'
        for attempted_claim, attempted_fulfillment, attempted_analysis in (
            (wrong_attempt, fulfillment_ref, analysis_ref),
            (wrong_token, fulfillment_ref, analysis_ref),
            (claim, missing_fulfillment, analysis_ref),
            (claim, fulfillment_ref, preparing_analysis),
        ):
            with pytest.raises(DataRequirementOutboxConflict):
                outbox.reconcile_completed(analysis.scope, attempted_claim,
                    attempted_fulfillment, attempted_analysis)
        with psycopg.connect(_private_dsn(conn)) as admin:
            admin.execute('''UPDATE data_requirement_outbox_delivery
                SET lease_expires_at=clock_timestamp()-INTERVAL '1 second'
                WHERE org_id=%s AND project_id=%s AND outbox_id=%s''',
                (*analysis.scope.key, claim.outbox_id))
        completed = outbox.reconcile_completed(
            analysis.scope, claim, fulfillment_ref, analysis_ref)

    # Treat the returned completion as lost: a separate runtime connection must
    # identify the committed original attempt and both exact Receipts by SELECT.
    with factory(analysis.scope) as reader:
        readback = reader.execute('''SELECT state,attempt,lease_token,
                completion_fulfillment_ref,completion_analysis_ref
            FROM data_requirement_outbox_delivery
            WHERE org_id=%s AND project_id=%s AND outbox_id=%s''',
            (*analysis.scope.key, claim.outbox_id)).fetchone()
    assert readback == dict(state='acked', attempt=claim.attempt,
        lease_token=claim.lease_token,
        completion_fulfillment_ref=result['fulfillmentRef'],
        completion_analysis_ref=result['receiptRef'])
    with factory(type(analysis.scope)(org_id='dev-org', project_id='dev-project')) as reader:
        assert reader.execute('''SELECT state FROM data_requirement_outbox_delivery
            WHERE org_id=%s AND project_id=%s AND outbox_id=%s''',
            (*analysis.scope.key, claim.outbox_id)).fetchone() is None

    replay = (outbox.complete if completion_path == 'complete' else outbox.reconcile_completed)(
        analysis.scope, claim, fulfillment_ref, analysis_ref)
    assert completed.state == 'acked' and not completed.replayed
    assert replay.state == 'acked' and replay.replayed

    conn.rollback()
    row = conn.execute('''SELECT state,completion_fulfillment_ref,completion_analysis_ref
        FROM data_requirement_outbox_delivery
        WHERE org_id=%s AND project_id=%s AND outbox_id=%s''',
        (*analysis.scope.key, claim.outbox_id)).fetchone()
    assert row['state'] == 'acked'
    assert row['completion_fulfillment_ref'] == result['fulfillmentRef']
    assert row['completion_analysis_ref'] == result['receiptRef']

    with pytest.raises(DataRequirementOutboxConflict):
        outbox.complete(type(analysis.scope)(org_id='dev-org', project_id='dev-project'),
            claim, fulfillment_ref, analysis_ref)
    with factory(analysis.scope) as runtime:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute('''UPDATE data_requirement_outbox_delivery SET state='failed'
                WHERE outbox_id=%s''', (claim.outbox_id,))
        runtime.rollback()


def test_production_factory_composes_coordinator_from_original_analysis(chain_case, monkeypatch):
    conn, state, analysis, _prepared_session, _root, _requirement = chain_case
    conn.rollback()
    connect_factory = _runtime_connect(conn)
    claim = DataRequirementOutboxStore(connect_factory).claim_next(analysis.scope,
        topic='data.requirement.request', worker_id='factory-composition-test',
        lease_token='factory-composition-token', lease_seconds=300)
    route = AnalysisDataRequirementRouteReader(
        claims=analysis.source.reader._journal._claims,
        connect_factory=connect_factory).read(analysis.scope, claim)
    factory = object.__new__(PipelineControlServiceFactory)
    monkeypatch.setattr(PipelineControlServiceFactory, 'build_event_analysis',
        lambda self, scope, **kwargs: analysis)
    coordinator = factory.build_analysis_snapshot_coordinator(analysis.scope,
        route=route, live_directory=LivePreparedJobDirectory(), markings=('internal',),
        store=state['completion']._store)
    assert type(coordinator) is AnalysisSnapshotCoordinator
    assert coordinator.analysis is analysis
    assert coordinator.completion._claims is analysis.source.reader._journal._claims
    assert coordinator.store is state['completion']._store
