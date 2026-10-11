"""Original generic media ReviewIssue contract in a historical isolated copy."""
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import real_contract as C
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.aip_production_contracts import CreateReviewIssueRequest, ResolveReviewIssueRequest, ReturnReviewIssueRequest, ExactArtifactRef, ExactRevisionRef
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractConflict, ProductionContractDependencyBlocked, ProductionContractIdempotencyConflict, ProductionContractNotFound
from aos_api.tenant_scope import TenantScope

R, DB, ROLE, SCOPE = C.R, C.DB, C.ROLE, C.SCOPE
TABLES = {'aip_artifact': 'SELECT', 'aip_eval_report_revision': 'SELECT',
          'aip_review_rule_revision': 'SELECT', 'aip_review_issue': 'SELECT,INSERT,UPDATE',
          'aip_review_issue_event': 'SELECT,INSERT', 'aip_production_contract_receipt': 'SELECT,INSERT',
          'aip_task_run': 'SELECT', 'aip_task': 'SELECT', 'aip_plan_revision': 'SELECT',
          'aip_step_run': 'SELECT', 'aip_return_decision': 'SELECT'}


def record(name, value):
    with (R / ('review-issue-' + name + '.json')).open('x') as out:
        out.write(json.dumps(value, indent=2, default=str) + '\n')


def counts(conn):
    return {n: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(n))).fetchone()['n'] for n in TABLES}


def main():
    assert not (R / 'review-issue-intent.json').exists(), 'Existing attempt: reconcile only'
    previous = json.loads((R / 'artifact-family-business-result.json').read_text())
    frozen = json.loads((C.ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(C.S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', C.TARGET]))
    assert item['Id'] == frozen['container']['Id'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before, metadata = C.S.P.M.fingerprint(C.TARGET), C.S.D.metadata(C.TARGET)
    assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == before
    config = SourceIssuerDatabaseConfig('contract', BIIssuerDatabaseConfig('127.0.0.1', 18431, DB, (R / 'private/contract-identity/contract.pgpass').resolve()))
    connections, cases = [], []
    @contextmanager
    def contract(scope):
        with connect_source_issuer_write(config, scope) as conn:
            identity = conn.execute('SELECT session_user AS login,current_user AS role,current_database() AS db').fetchone()
            assert identity == {'login': ROLE, 'role': ROLE, 'db': DB}
            connections.append(identity)
            yield conn
    def no_plan(scope):
        raise AssertionError('Review operation used Plan factory')
    created_role = False
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB, user='aos_app', autocommit=True, row_factory=dict_row) as admin:
        assert admin.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == frozen['cloneIdentity']['cluster']
        assert admin.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_159'
        assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        report = admin.execute('SELECT * FROM aip_eval_report_revision WHERE org_id=%s AND project_id=%s ORDER BY report_id,revision LIMIT 1', SCOPE.key).fetchone()
        assert report
        report_ref = ExactRevisionRef(resource_type='EvalReportRevision', resource_id=report['report_id'], revision=report['revision'], content_hash=report['content_hash'])
        artifact_ref = ExactArtifactRef.model_validate(previous['fixtures'][1])
        artifact = admin.execute('SELECT * FROM aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_id=%s', (*SCOPE.key, artifact_ref.artifact_id)).fetchone()
        assert artifact['artifact_type'] == 'media_asset' and artifact['content_hash'] == artifact_ref.content_hash
        run = admin.execute('SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*SCOPE.key, previous['runId'])).fetchone()
        assert run['status'] == 'queued'
        assert admin.execute('SELECT count(*) AS n FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*SCOPE.key, run['run_id'])).fetchone()['n'] == 0
        rule = previous['rule']
        rule_ref = ExactRevisionRef(resource_type='EvalRuleRevision', resource_id=rule['ruleId'], revision=rule['revision'], content_hash=rule['contentHash'])
        body = CreateReviewIssueRequest(rule_ref=rule_ref, severity='warning', artifact_ref=artifact_ref, eval_report_ref=report_ref, location={'testOnly': True, 'businessDomain': 'ecommerce', 'path': 'metadata'}, suggested_fix='隔离合同兼容核验；不是本轮实际媒体评测', return_stage='fixture')
        record('intent', {'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'], 'database': DB, 'role': ROLE,
                         'head': 'da757eebe63c870c438cc4237041eb8282fe22e0', 'authority': 'AOS-001888', 'task': 'qyh-source-boundary-rehearsal-20261011',
                         'artifactRef': artifact_ref.model_dump(mode='json', by_alias=True), 'historicalEvalReportRef': report_ref.model_dump(mode='json', by_alias=True),
                         'existingExperimentalQueuedRun': run['run_id'], 'ordinaryMediaPathOnly': True, 'contentEvalSubjectAccepted': False,
                         'newEvaluationPerformed': False, 'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'currentDatabaseTouched': False})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_review_issue_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), contract_connect_factory=contract, plan_connect_factory=no_plan)
            saved = counts(admin)
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.create_review_issue(SCOPE, 'clone:test', 'qyh-review-hash-drift', body.model_copy(update={'artifact_ref': artifact_ref.model_copy(update={'content_hash': '0' * 64})}))))
            assert counts(admin) == saved
            made = store.create_review_issue(SCOPE, 'clone:test', 'qyh-review-create', body)
            assert made.status.value == 'open' and made.version == 1
            assert store.create_review_issue(SCOPE, 'clone:test', 'qyh-review-create', body).issue_id == made.issue_id
            cases.append('original-create-and-idempotency')
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.create_review_issue(SCOPE, 'clone:test', 'qyh-review-create', body.model_copy(update={'suggested_fix': 'drift'}))))
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.get_review_issue(TenantScope('dev-org', 'dev-project'), made.issue_id)))
            resolution_ref = ExactRevisionRef(resource_type='Artifact', resource_id=previous['fixtures'][2]['artifactId'], revision=1, content_hash=previous['fixtures'][2]['contentHash'])
            resolution = ResolveReviewIssueRequest(expected_version=1, reason='实际非空实验Artifact引用；非生产修复结论', resolution_refs=[resolution_ref])
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.resolve_review_issue(SCOPE, 'clone:test', made.issue_id, 'qyh-review-stale', resolution.model_copy(update={'expected_version': 2}))))
            resolved = store.resolve_review_issue(SCOPE, 'clone:test', made.issue_id, 'qyh-review-resolve', resolution)
            assert resolved.status.value == 'resolved' and resolved.version == 2
            assert store.resolve_review_issue(SCOPE, 'clone:test', made.issue_id, 'qyh-review-resolve', resolution).version == 2
            cases.append('original-resolve-nonempty-ref-and-idempotency')
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.resolve_review_issue(SCOPE, 'clone:test', made.issue_id, 'qyh-review-closed', resolution.model_copy(update={'expected_version': 2}))))
            opened = store.create_review_issue(SCOPE, 'clone:test', 'qyh-review-open-for-return', body)
            saved = counts(admin)
            return_body = ReturnReviewIssueRequest(expected_version=1, run_id=run['run_id'], target_stage='fixture', reason='不启动排队Run，验证原退回拒绝', attempt_idempotency_key='qyh-review-return-attempt')
            try:
                store.return_review_issue(SCOPE, 'clone:test', opened.issue_id, 'qyh-review-return-denied', return_body)
            except ProductionContractDependencyBlocked as error:
                assert str(error) == 'RETURN_TARGET_NOT_RUNNING'
                cases.append('original-return-denied-queued-run')
            else:
                raise AssertionError('Queued run accepted return')
            assert counts(admin) == saved
            admin.execute("CREATE FUNCTION qyh_review_issue_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-review-rollback' THEN RAISE EXCEPTION 'QYH_REVIEW_RECEIPT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_review_issue_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_review_issue_rollback()')
            saved = counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.create_review_issue(SCOPE, 'clone:test', 'qyh-review-rollback', body), state='P0001'))
            assert counts(admin) == saved
            assert admin.execute('SELECT * FROM aip_eval_report_revision WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s', (*SCOPE.key, report['report_id'], report['revision'])).fetchone() == report
            assert admin.execute('SELECT * FROM aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_id=%s', (*SCOPE.key, artifact_ref.artifact_id)).fetchone() == artifact
            assert admin.execute('SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*SCOPE.key, run['run_id'])).fetchone() == run
            record('business-result', {'cases': cases, 'connections': connections, 'resolved': resolved.model_dump(mode='json', by_alias=True), 'openForReturn': opened.model_dump(mode='json', by_alias=True), 'resolutionRefs': [resolution_ref.model_dump(mode='json', by_alias=True)], 'queuedRunUntouched': True, 'historicalReportAndArtifactUnchanged': True, 'ordinaryMediaPathOnly': True, 'contentEvalSubjectAccepted': False, 'returnPositiveAccepted': False, 'newEvaluationPerformed': False, 'passwordOrOIDCAuthenticated': False, 'fullRestorationAccepted': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_review_issue_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == before
    assert C.S.D.metadata('qyh-restored-pg-20261011') == metadata
    record('verified', {'originalAndCurrent647DataExact': True, 'allOriginalMetadataExact': True, 'temporaryRoleRemoved': True, 'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'currentDatabaseTouched': False}))


if __name__ == '__main__':
    main()
