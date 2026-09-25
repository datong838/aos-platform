"""Frozen original attempt: exact dual Receipt evidence without replay or writes."""

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import os
from types import SimpleNamespace as NS

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

from aos_api.data_requirement_outbox_store import DataRequirementOutboxStore
from aos_api.ecommerce_analysis_data_requirement_route import AnalysisDataRequirementRouteReader
from aos_api.ecommerce_analysis_original_attempt_receipt_resolver import (
    OriginalAttemptReceiptFrozen, OriginalAttemptReceiptResolver,
)
from aos_api.ecommerce_analysis_snapshot_coordinator import AnalysisSnapshotCoordinator
from aos_api.ecommerce_analysis_snapshot_policy_set import AnalysisSnapshotPolicySetOwner
from aos_api.tenant_scope import TenantScope


def _factory(conn, *, read_only):
    dsn = os.environ['AOS_DATABASE_URL']
    assert psycopg.conninfo.conninfo_to_dict(dsn)['dbname'] == conn.info.dbname
    identity = conn.execute('SELECT session_user AS name').fetchone()['name']
    conn.rollback()

    @contextmanager
    def connect(scope):
        with psycopg.connect(dsn, row_factory=dict_row) as current:
            current.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(identity)))
            current.execute('SET ROLE aos_runtime')
            current.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)", scope.key)
            current.commit()
            current.read_only = read_only
            current.isolation_level = (psycopg.IsolationLevel.REPEATABLE_READ if read_only
                else psycopg.IsolationLevel.SERIALIZABLE)
            yield current

    return connect


def test_frozen_original_attempt_receipts_are_read_only_and_exact(chain_case):
    conn, state, analysis, _prepared_session, _root, _requirement = chain_case
    conn.rollback()
    writer = _factory(conn, read_only=False)
    reader = _factory(conn, read_only=True)
    analysis.connect = writer
    claim = DataRequirementOutboxStore(writer).claim_next(analysis.scope,
        topic='data.requirement.request', worker_id='w5c8d-test',
        lease_token='w5c8d-original-token', lease_seconds=300)
    assert claim is not None
    route = AnalysisDataRequirementRouteReader(
        claims=analysis.source.reader._journal._claims, connect_factory=writer,
    ).read(analysis.scope, claim)
    artifacts = analysis.source.reader._journal._claims._controls._selections._artifacts
    old_record = artifacts.load_record
    documents = {path: artifacts.read_artifact(None, path, 256 * 1024)
        for _, path in AnalysisSnapshotPolicySetOwner.POLICIES}
    indexed = [dict(relativePath=path, digest='sha256:' + hashlib.sha256(raw).hexdigest(),
        size=len(raw), mediaType='application/json') for path, raw in documents.items()]
    artifacts.load_record = lambda selected: NS(manifest=old_record(selected).manifest, artifacts=indexed)
    result = AnalysisSnapshotCoordinator(analysis=analysis,
        completion=state['completion'], store=state['completion']._store).run(route=route)
    assert result['phase'] == 'RUNNING' and state['calls'] == 1
    DataRequirementOutboxStore(writer).mark_unknown(analysis.scope,
        claim.outbox_id, claim.lease_token, reason_code='W5C8D_DIAGNOSTIC_UNKNOWN')
    resolver = OriginalAttemptReceiptResolver(reader)
    evidence = resolver.resolve(analysis.scope, claim)
    assert evidence.state == 'unknown' and evidence.attempt == claim.attempt
    assert evidence.analysis_ref.receipt_id == result['receiptRef'].get('receiptId')
    assert evidence.fulfillment_ref.receipt_id == result['fulfillmentRef']['receiptId']
    assert state['calls'] == 1
    with pytest.raises(OriginalAttemptReceiptFrozen, match='ORIGINAL_ATTEMPT_DRIFT'):
        resolver.resolve(analysis.scope, replace(claim, attempt=claim.attempt + 1))
    with pytest.raises(OriginalAttemptReceiptFrozen, match='ORIGINAL_ATTEMPT_DRIFT'):
        resolver.resolve(analysis.scope, replace(claim, lease_token='wrong-token'))
    wrong_requirement = replace(claim, requirement_id='wrong-w5c8d-requirement',
        payload={**claim.payload, 'requirementId': 'wrong-w5c8d-requirement'})
    with pytest.raises(OriginalAttemptReceiptFrozen, match='ORIGINAL_ATTEMPT_DRIFT'):
        resolver.resolve(analysis.scope, wrong_requirement)
    with pytest.raises(OriginalAttemptReceiptFrozen, match='OUTBOX_NOT_FOUND'):
        resolver.resolve(TenantScope(org_id='dev-org', project_id='dev-project'), claim)
    with pytest.raises(OriginalAttemptReceiptFrozen, match='READ_ONLY_TENANT_BOUNDARY_REQUIRED'):
        OriginalAttemptReceiptResolver(writer).resolve(analysis.scope, claim)

    dsn = os.environ['AOS_DATABASE_URL']
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE data_requirement_outbox_delivery SET state='claimed',
            lease_expires_at=clock_timestamp()-INTERVAL '1 second'
            WHERE org_id=%s AND project_id=%s AND outbox_id=%s''',
            (*analysis.scope.key, claim.outbox_id))
    with reader(analysis.scope) as current:
        expired = current.execute('''SELECT lease_expires_at FROM data_requirement_outbox_delivery
            WHERE org_id=%s AND project_id=%s AND outbox_id=%s''',
            (*analysis.scope.key, claim.outbox_id)).fetchone()['lease_expires_at']
    expired_claim = replace(claim, lease_expires_at=expired)
    assert resolver.resolve(analysis.scope, expired_claim).state == 'claimed'
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE ecommerce_growth_runtime_command_receipt
            SET idempotency_key=idempotency_key||'-missing'
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND target_receipt_ref=%s::jsonb''',
            (*analysis.scope.key, Jsonb(result['receiptRef'])))
    with pytest.raises(OriginalAttemptReceiptFrozen, match='ANALYSIS_RECEIPT_MISSING'):
        resolver.resolve(analysis.scope, expired_claim)
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE ecommerce_growth_runtime_command_receipt
            SET idempotency_key=left(idempotency_key,length(idempotency_key)-length('-missing'))
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND target_receipt_ref=%s::jsonb''',
            (*analysis.scope.key, Jsonb(result['receiptRef'])))
    assert resolver.resolve(analysis.scope, expired_claim).state == 'claimed'
    missing_fulfillment = dict(result['fulfillmentRef'], resourceId='missing-w5c8d',
        receiptId='missing-w5c8d')
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE ecommerce_growth_runtime_command_receipt
            SET response=jsonb_set(response,'{fulfillmentRef}',%s::jsonb)
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND target_receipt_ref=%s::jsonb''',
            (Jsonb(missing_fulfillment), *analysis.scope.key, Jsonb(result['receiptRef'])))
    with pytest.raises(OriginalAttemptReceiptFrozen, match='FULFILLMENT_LINEAGE_DRIFT'):
        resolver.resolve(analysis.scope, expired_claim)
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE ecommerce_growth_runtime_command_receipt
            SET response=jsonb_set(response,'{fulfillmentRef}',%s::jsonb)
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND target_receipt_ref=%s::jsonb''',
            (Jsonb(result['fulfillmentRef']), *analysis.scope.key, Jsonb(result['receiptRef'])))
    assert resolver.resolve(analysis.scope, expired_claim).state == 'claimed'
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE ecommerce_growth_runtime_command_receipt
            SET response=jsonb_set(response,'{runRef,resourceId}','"wrong-w5c8d-run"'::jsonb)
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND target_receipt_ref=%s::jsonb''',
            (*analysis.scope.key, Jsonb(result['receiptRef'])))
    with pytest.raises(OriginalAttemptReceiptFrozen, match='ANALYSIS_LINEAGE_DRIFT'):
        resolver.resolve(analysis.scope, expired_claim)
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE ecommerce_growth_runtime_command_receipt
            SET response=jsonb_set(response,'{runRef}',%s::jsonb)
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND target_receipt_ref=%s::jsonb''',
            (Jsonb(result['runRef']), *analysis.scope.key, Jsonb(result['receiptRef'])))
    assert resolver.resolve(analysis.scope, expired_claim).state == 'claimed'
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE ecommerce_growth_runtime_command_receipt
            SET response=jsonb_set(response,'{phase}','"PREPARING"'::jsonb)
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND target_receipt_ref=%s::jsonb''',
            (*analysis.scope.key, Jsonb(result['receiptRef'])))
    with pytest.raises(OriginalAttemptReceiptFrozen, match='ANALYSIS_LINEAGE_DRIFT'):
        resolver.resolve(analysis.scope, expired_claim)
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''UPDATE ecommerce_growth_runtime_command_receipt
            SET response=jsonb_set(response,'{phase}','"RUNNING"'::jsonb)
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND target_receipt_ref=%s::jsonb''',
            (*analysis.scope.key, Jsonb(result['receiptRef'])))
        admin.execute('''INSERT INTO ecommerce_growth_runtime_command_receipt(
            org_id,project_id,operation_id,idempotency_key,request_hash,dispatch_revision,
            installation_id,generation,execution_epoch,cutover_group_id,cutover_group_revision,
            runtime_revision,response,target_receipt_ref,actor,occurred_at)
            SELECT org_id,project_id,operation_id,idempotency_key||'-duplicate',request_hash,
                   dispatch_revision,installation_id,generation,execution_epoch,cutover_group_id,
                   cutover_group_revision,runtime_revision,
                   jsonb_set(response,'{receiptRef,resourceId}','"duplicate-w5c8d"'::jsonb),
                   jsonb_set(target_receipt_ref,'{resourceId}','"duplicate-w5c8d"'::jsonb),
                   actor,occurred_at
            FROM ecommerce_growth_runtime_command_receipt
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'
              AND response->>'phase'='PREPARING' AND response->'requirementRef'='null'::jsonb''',
            analysis.scope.key)
    with pytest.raises(OriginalAttemptReceiptFrozen, match='ORIGINAL_SOURCE_RECEIPT_NOT_UNIQUE'):
        resolver.resolve(analysis.scope, expired_claim)
    assert state['calls'] == 1
