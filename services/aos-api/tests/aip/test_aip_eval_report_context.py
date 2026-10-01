"""Metadata integrity only; signed fixtures do not prove a real stage evaluation."""
from datetime import UTC, datetime, timedelta, timezone
import json
import os
import secrets
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb
import pytest

from aos_api.aip_eval_contracts import EvalReportRevision
from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_report_proof_reader import read_verified_skill_eval_report
from aos_api.aip_eval_runner import AipEvalRunner, compute_eval_report_hash
from aos_api.aip_eval_writer_atomic import persist_signed_skill_eval_report
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope
from test_aip_eval_execution_authority import INPUT_HASH, _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_writer_atomic import _presented, _seed_source, _source_objects
from test_aip_eval_writer_transaction import _grant_isolated

SCOPE = TenantScope('org-org', 'dev-project')
FIELDS = ('eval_contract_ref', 'subject_artifact_ref', 'stage_attempt_ref',
          'gate_policy_ref', 'evidence_cutoff_at')


def context():
    return dict(
        evalContractRef=dict(resourceType='EvalContractRevision', resourceId='fixture-contract',
                             revision=1, contentHash='a'*64),
        subjectArtifactRef=dict(resourceType='Artifact', resourceId='fixture-text', contentHash='b'*64),
        stageAttemptRef=dict(resourceType='StepRunAttempt', runId='fixture-task-run',
                             stepKey='diagnosis', stepRunId='fixture-step', attempt=1, inputHash='c'*64),
        gatePolicyRef=dict(resourceType='EvalContractRevision', resourceId='fixture-contract',
                           revision=1, contentHash='a'*64),
        evidenceCutoffAt=datetime(2026, 9, 29, tzinfo=UTC),
    )


def bound_report(base, mode='stage'):
    payload = base.model_dump(mode='python', by_alias=True)
    values = context()
    if mode == 'contract':
        values = {'evalContractRef': values['evalContractRef']}
    if mode != 'none':
        payload.update(values)
    value = EvalReportRevision.model_validate(payload)
    return value.model_copy(update={'content_hash': compute_eval_report_hash(value)})


def row_context(report):
    return {name: (value.model_dump(mode='json', by_alias=True)
                  if hasattr(value, 'model_dump') else value)
            for name in FIELDS for value in [getattr(report, name)]}


def drifted_context_value(report, field):
    value = getattr(report, field)
    if field == 'evidence_cutoff_at':
        return value + timedelta(seconds=1)
    return value.model_copy(update={
        'run_id' if field == 'stage_attempt_ref' else 'resource_id': 'different-source'})


@pytest.mark.parametrize('mode', ['none', 'contract', 'stage'])
def test_exact_existing_context_shapes(mode):
    from aos_api.aip_eval_report_context import require_same_eval_context
    _, base = _source_objects()
    report = bound_report(base, mode)
    require_same_eval_context(report, row_context(report))


@pytest.mark.parametrize('field', FIELDS)
def test_missing_context_is_not_a_wildcard(field):
    from aos_api.aip_eval_report_context import require_same_eval_context
    _, base = _source_objects()
    report = bound_report(base)
    row = row_context(report)
    row[field] = None
    with pytest.raises(EvalExecutionRejected, match='context'):
        require_same_eval_context(report, row)


def test_context_preserves_json_types_and_requires_aware_cutoff():
    from aos_api.aip_eval_report_context import require_same_eval_context
    _, base = _source_objects()
    report = bound_report(base)
    for name in ('eval_contract_ref', 'gate_policy_ref', 'stage_attempt_ref'):
        row = row_context(report)
        row[name]['attempt' if name == 'stage_attempt_ref' else 'revision'] = True
        with pytest.raises(EvalExecutionRejected, match='context'):
            require_same_eval_context(report, row)
    row = row_context(report)
    row['evidence_cutoff_at'] = report.evidence_cutoff_at.replace(tzinfo=None)
    with pytest.raises(EvalExecutionRejected, match='context'):
        require_same_eval_context(report, row)
    row['evidence_cutoff_at'] = report.evidence_cutoff_at.astimezone(timezone(timedelta(hours=8)))
    require_same_eval_context(report, row)


def test_incomplete_report_context_is_rejected():
    from aos_api.aip_eval_report_context import require_same_eval_context
    _, base = _source_objects()
    report = bound_report(base)
    for field in FIELDS:
        candidate = report.model_copy(update={field: None})
        with pytest.raises(EvalExecutionRejected, match='context'):
            require_same_eval_context(candidate, row_context(candidate))


@pytest.fixture()
def writer(tmp_path, monkeypatch):
    """Real independent login; all authority rows are explicitly test fixtures."""
    admin_dsn = os.environ['AOS_DATABASE_URL']
    parts = conninfo_to_dict(admin_dsn)
    database = parts['dbname']
    assert database.startswith('aos_test_') and database.endswith('_ti4_test')
    login = 'eval_context_' + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    suite, base = _source_objects()
    with connect() as admin:
        admin.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated fixture') ON CONFLICT DO NOTHING")
        admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated fixture') ON CONFLICT DO NOTHING")
        at = admin.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        root, target, judge = _signed_pair(at - timedelta(seconds=2), suite_ref=base.suite_ref)
        _seed_source(admin, suite)
        _seed(admin, root, target, judge, stage='identities', suite_ref=base.suite_ref)
        report = bound_report(base.model_copy(update={
            'created_at': admin.execute('SELECT clock_timestamp() AS now').fetchone()['now']}))
        values = row_context(report)
        admin.execute('''UPDATE aip_eval_run SET status='succeeded',target_ref=%s,
            dataset_ref=%s,judge_ref=%s,eval_contract_ref=%s,subject_artifact_ref=%s,
            stage_attempt_ref=%s,gate_policy_ref=%s,evidence_cutoff_at=%s
            WHERE org_id=%s AND project_id=%s AND run_id=%s''', (
                Jsonb(report.target.model_dump(mode='json', by_alias=True)),
                Jsonb(report.dataset.model_dump(mode='json', by_alias=True)),
                Jsonb(report.judge.model_dump(mode='json', by_alias=True)),
                *(Jsonb(values[name]) for name in FIELDS[:-1]), values[FIELDS[-1]],
                *SCOPE.key, report.run_id))
        _grant_isolated(admin)
        admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION PASSWORD {}').format(
            sql.Identifier(login), sql.Literal(password)))
        admin.execute(sql.SQL('GRANT aos_aip_eval_writer TO {}').format(sql.Identifier(login)))
        admin.commit()
    identity = tmp_path/'writer.json'
    identity.write_text(json.dumps(dict(schemaVersion='aos.aip.eval-writer-identity/v1',
        dsn=make_conninfo(admin_dsn, user=login, password=password), role='aos_aip_eval_writer')))
    identity.chmod(0o600)
    monkeypatch.setenv('AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE', str(identity))
    try:
        yield database, report, target, judge
    finally:
        monkeypatch.delenv('AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE')
        identity.unlink()
        with connect() as admin:
            admin.execute(sql.SQL('REVOKE aos_aip_eval_writer FROM {}').format(sql.Identifier(login)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(login)))
            admin.commit()
        # Disposable session database owns all fixture rows and temporary grants.


def test_real_writer_roundtrip_keeps_exact_report_context(writer):
    database, report, target, judge = writer
    proof = _presented(target, judge)
    for field in FIELDS:
        changed = drifted_context_value(report, field)
        candidate = report.model_copy(update={field: changed})
        candidate = candidate.model_copy(update={'content_hash': compute_eval_report_hash(candidate)})
        with pytest.raises(EvalExecutionRejected, match='context'):
            persist_signed_skill_eval_report(expected_database=database, report=candidate,
                expected_input_hashes={'case-1': INPUT_HASH}, presented=proof)
        with connect() as conn:
            for table in ('aip_eval_execution_receipt', 'aip_eval_report_revision', 'aip_eval_case_execution_proof'):
                assert conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(table))).fetchone()['n'] == 0
    result = persist_signed_skill_eval_report(expected_database=database, report=report,
        expected_input_hashes={'case-1': INPUT_HASH}, presented=proof)
    assert result.report_hash == report.content_hash
    reread = AipEvalRunner().get_report(SCOPE, report.report_id)
    assert reread == report
    assert compute_eval_report_hash(reread) == report.content_hash
    with connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id','org-org',true)")
        conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
        at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        verified = read_verified_skill_eval_report(conn, report=report, evaluated_at=at,
            expected_input_hashes={'case-1': INPUT_HASH}, presented=proof)
        assert verified.report_hash == report.content_hash
    for field in FIELDS:
        with connect() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            changed = drifted_context_value(report, field)
            value = Jsonb(changed.model_dump(mode='json', by_alias=True)) if hasattr(changed, 'model_dump') else changed
            conn.execute(sql.SQL('UPDATE aip_eval_run SET {}=%s WHERE org_id=%s AND project_id=%s AND run_id=%s').format(
                sql.Identifier(field)), (value, *SCOPE.key, report.run_id))
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute("SELECT set_config('aos.org_id','org-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            with pytest.raises(EvalExecutionRejected, match='context'):
                read_verified_skill_eval_report(conn, report=report, evaluated_at=at,
                    expected_input_hashes={'case-1': INPUT_HASH}, presented=proof)
            conn.rollback()
