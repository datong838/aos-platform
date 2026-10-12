"""Default Skill dependency snapshot must consume an original signed fixture proof."""
from datetime import UTC, datetime
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from aos_api.aip_eval_report_proof_reader import read_verified_skill_eval_report_from_persistence
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_skill_binding_readiness_service import AipSkillBindingReadinessService
from aos_api.tenant_scope import TenantScope
from test_aip_eval_execution_authority import _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_report_proof_reader import _seed_report, _seed_sidecar
from test_aip_eval_writer_atomic import _seed_source, _source_objects


def _exercise_default_dependency_reader():
    parts = conninfo_to_dict(os.environ['AOS_DATABASE_URL'])
    assert (parts['host'], parts['port']) == ('127.0.0.1', '18431')
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    suite, original = _source_objects()
    now = datetime.now(UTC)
    report = original.model_copy(update={'created_at': now})
    report = report.model_copy(update={'content_hash': compute_eval_report_hash(report)})
    root, target, judge = _signed_pair(now, suite_ref=report.suite_ref)
    # Original, test-only signed sources in the session-owned database; no
    # historical business Task/Run is changed or retrospectively certified.
    with psycopg.connect(os.environ['AOS_DATABASE_URL'], row_factory=dict_row) as admin:
        assert admin.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == '7695416748450308141'
        admin.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated') ON CONFLICT DO NOTHING")
        admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated') ON CONFLICT DO NOTHING")
        _seed_source(admin, suite)
        _seed(admin, root, target, judge, suite_ref=report.suite_ref)
        _seed_report(admin, report)
        _seed_sidecar(admin, target, judge)
        admin.commit()
    service = AipSkillBindingReadinessService()
    with service._connect_factory(TenantScope('org-org','dev-project')) as conn:
        proof = read_verified_skill_eval_report_from_persistence(conn, report=report, evaluated_at=now)
        assert proof.report_hash == report.content_hash and len(proof.cases) == 1
        identity = conn.execute("SELECT current_user AS role,current_setting('transaction_isolation') AS isolation,current_setting('transaction_read_only') AS readonly").fetchone()
        assert identity == {'role':'aos_runtime','isolation':'repeatable read','readonly':'on'}


def test_default_dependency_reader_consumes_real_signed_report_snapshot(monkeypatch):
    # The default factory opens an independent connection, so fixture inputs
    # must be committed. Confine them to a second owned database, preventing
    # these immutable fixed helper IDs from leaking into neighboring tests.
    original_dsn = os.environ['AOS_DATABASE_URL']
    parts = conninfo_to_dict(original_dsn)
    assert (parts['host'], parts['port']) == ('127.0.0.1', '18431')
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    database = 'aos_test_' + uuid4().hex[:12] + '_ti4_test'
    with psycopg.connect(original_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database), sql.Identifier(parts['dbname'])))
        try:
            monkeypatch.setenv('AOS_DATABASE_URL', make_conninfo(**{**parts, 'dbname': database}))
            _exercise_default_dependency_reader()
        finally:
            monkeypatch.setenv('AOS_DATABASE_URL', original_dsn)
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))
