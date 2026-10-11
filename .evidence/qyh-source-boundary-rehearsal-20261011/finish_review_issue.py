"""Continue only the reconciled zero-effect review lock/rollback probes."""
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import real_review_issue as Q
import real_contract as C
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.aip_production_contracts import CreateReviewIssueRequest, ReturnReviewIssueRequest
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked

R, DB, ROLE, SCOPE = Q.R, Q.DB, Q.ROLE, Q.SCOPE


def record(name, value):
    with (R / ('review-issue-finish-' + name + '.json')).open('x') as out:
        out.write(json.dumps(value, indent=2, default=str) + '\n')


def main():
    assert not (R / 'review-issue-finish-intent.json').exists(), 'Existing attempt: reconcile only'
    failure = json.loads((R / 'review-issue-failure.json').read_text())
    assert failure['errorType'] == 'InsufficientPrivilege' and failure['sqlstate'] == '42501'
    assert len(failure['completedCases']) == 7
    intent = json.loads((R / 'review-issue-intent.json').read_text())
    assert intent['scriptHash'] == hashlib.sha256((R / 'real_review_issue.py').read_bytes()).hexdigest()
    frozen = json.loads((C.ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(C.S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', C.TARGET]))
    assert item['Id'] == frozen['container']['Id'] == intent['containerId'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before, metadata = C.S.P.M.fingerprint(C.TARGET), C.S.D.metadata(C.TARGET)
    assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == before
    reader = lambda scope: C.runtime(scope, read_only=True)
    with reader(SCOPE) as conn:
        receipts = conn.execute('SELECT operation,idempotency_key,result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key LIKE %s ORDER BY idempotency_key', (*SCOPE.key, 'qyh-review-%')).fetchall()
        assert {x['idempotency_key'] for x in receipts} == {'qyh-review-create', 'qyh-review-open-for-return', 'qyh-review-resolve'}
        rows = {x['idempotency_key']: x for x in receipts}
        store = AipProductionContractStore(reader)
        resolved = store.get_review_issue(SCOPE, rows['qyh-review-resolve']['result_ref']['resourceId'], conn=conn)
        opened = store.get_review_issue(SCOPE, rows['qyh-review-open-for-return']['result_ref']['resourceId'], conn=conn)
        assert resolved.status.value == 'resolved' and resolved.version == 2
        assert opened.status.value == 'open' and opened.version == 1
    connections, cases = [], list(failure['completedCases'])
    config = SourceIssuerDatabaseConfig('contract', BIIssuerDatabaseConfig('127.0.0.1', 18431, DB, (R / 'private/contract-identity/contract.pgpass').resolve()))
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
        assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        run = admin.execute('SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*SCOPE.key, intent['existingExperimentalQueuedRun'])).fetchone()
        task = admin.execute('SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s', (*SCOPE.key, run['task_id'])).fetchone()
        assert run['status'] == 'queued'
        assert admin.execute('SELECT count(*) AS n FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*SCOPE.key, run['run_id'])).fetchone()['n'] == 0
        body = CreateReviewIssueRequest(**{k: getattr(opened, k) for k in CreateReviewIssueRequest.model_fields})
        record('intent', {'originalFailure': failure, 'oldIntentHash': hashlib.sha256((R / 'review-issue-intent.json').read_bytes()).hexdigest(), 'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'], 'database': DB, 'sourceScriptHash': intent['scriptHash'], 'finishScriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'completedReceiptsReplayed': False, 'queuedRunId': run['run_id'], 'lockColumnsOnly': ['aip_task_run.updated_at', 'aip_task.updated_at'], 'timestampWriteExposureRemains': True, 'currentDatabaseTouched': False})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in Q.TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_review_finish_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            for table in ('aip_task_run', 'aip_task'):
                admin.execute(sql.SQL('GRANT UPDATE(updated_at) ON {} TO {}').format(sql.Identifier(table), sql.Identifier(ROLE)))
                for column in ('status', 'version'):
                    assert not admin.execute('SELECT has_column_privilege(%s,%s,%s,%s) AS allowed', (ROLE, table, column, 'UPDATE')).fetchone()['allowed']
                def deny_state(table=table):
                    with contract(SCOPE) as conn:
                        conn.execute(sql.SQL('UPDATE {} SET status=status WHERE org_id=%s AND project_id=%s').format(sql.Identifier(table)), SCOPE.key)
                cases.append(C.expect_error(psycopg.Error, deny_state, state='42501'))
            store = AipProductionContractStore(reader, contract_connect_factory=contract, plan_connect_factory=no_plan)
            saved = Q.counts(admin)
            return_body = ReturnReviewIssueRequest(expected_version=1, run_id=run['run_id'], target_stage='fixture', reason='补最小锁列后仍不启动排队Run', attempt_idempotency_key='qyh-review-return-lock-attempt')
            try:
                store.return_review_issue(SCOPE, 'clone:test', opened.issue_id, 'qyh-review-return-lock-denied', return_body)
            except ProductionContractDependencyBlocked as error:
                assert str(error) == 'RETURN_TARGET_NOT_RUNNING'
                cases.append('original-return-business-denial-after-column-lock-grant')
            else:
                raise AssertionError('Queued run accepted return')
            assert Q.counts(admin) == saved
            admin.execute("CREATE FUNCTION qyh_review_issue_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-review-rollback' THEN RAISE EXCEPTION 'QYH_REVIEW_RECEIPT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_review_issue_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_review_issue_rollback()')
            saved = Q.counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.create_review_issue(SCOPE, 'clone:test', 'qyh-review-rollback', body), state='P0001'))
            assert Q.counts(admin) == saved
            assert admin.execute('SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*SCOPE.key, run['run_id'])).fetchone() == run
            assert admin.execute('SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s', (*SCOPE.key, task['task_id'])).fetchone() == task
            record('business-result', {'cases': cases, 'finishConnections': connections, 'resolved': resolved.model_dump(mode='json', by_alias=True), 'openForReturn': opened.model_dump(mode='json', by_alias=True), 'sourceReportRef': intent['historicalEvalReportRef'], 'queuedRunUntouched': True, 'timestampWriteExposureRemains': True, 'ordinaryMediaPathOnly': True, 'contentEvalSubjectAccepted': False, 'returnPositiveAccepted': False, 'newEvaluationPerformed': False, 'completedReceiptsReplayed': False, 'fullRestorationAccepted': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in Q.TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_review_finish_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == before
    assert C.S.D.metadata('qyh-restored-pg-20261011') == metadata
    record('verified', {'originalAndCurrent647DataExact': True, 'allOriginalMetadataExact': True, 'temporaryRoleRemoved': True, 'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'casesIncludingOriginalCompleted': len(cases), 'finishConnections': len(connections), 'completedWritesReplayed': False, 'currentDatabaseTouched': False}))


if __name__ == '__main__':
    main()
