"""Original Eval revise/freeze with actual preserved publication dependencies."""
import hashlib
import json
from pathlib import Path
from contextlib import contextmanager
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import real_contract as C
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.aip_production_contracts import CreateEvalContractRequest, ReviseEvalContractRequest
from aos_api.aip_production_contract_store import (AipProductionContractStore,
    ProductionContractConflict, ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict, ProductionContractNotFound)
from aos_api.tenant_scope import TenantScope

R, DB, ROLE, SCOPE = C.R, C.DB, C.ROLE, C.SCOPE
OLD = 'eval-contract-eb2d228de06542d2a0ec'
TABLES = {'aip_eval_contract_head': 'SELECT,INSERT,UPDATE',
    'aip_eval_contract_revision': 'SELECT,INSERT',
    'aip_eval_suite_revision': 'SELECT', 'aip_publication_event': 'SELECT',
    'aip_release_gate_decision': 'SELECT', 'aip_production_contract_receipt': 'SELECT,INSERT'}

def record(name, body):
    with (R / ('eval-freeze-' + name + '.json')).open('x') as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2, default=str)
        stream.write('\n')

def counts(conn):
    return {t: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(t))).fetchone()['n']
        for t in ('aip_eval_contract_head', 'aip_eval_contract_revision',
                  'aip_production_contract_receipt', 'aip_task_run', 'aip_step_run')}

def main():
    assert not (R / 'eval-freeze-intent.json').exists(), 'Existing attempt: reconcile only'
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
        raise AssertionError('Eval operation used Plan factory')
    role_created = trigger_created = False
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB, user='aos_app', autocommit=True, row_factory=dict_row) as admin:
        assert admin.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == frozen['cloneIdentity']['cluster']
        assert admin.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_159'
        assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), contract_connect_factory=contract, plan_connect_factory=no_plan)
        historical = store.get_eval_contract(SCOPE, OLD, 2)
        assert historical.lifecycle.value == 'frozen' and historical.readiness.value == 'ready' and not historical.blockers
        trial = json.loads((R / 'eval-bundle-business-result.json').read_text())['evalContractId']
        existing = store.get_eval_contract(SCOPE, trial)
        assert existing.version == 2 and existing.revision == 2 and existing.lifecycle.value == 'draft'
        assert {b.code for b in existing.blockers} == {'EVAL_PUBLICATION_MISSING', 'EVAL_GATE_MISSING'}
        body = ReviseEvalContractRequest(**{k: getattr(historical, k) for k in CreateEvalContractRequest.model_fields}, expected_version=2)
        initial = counts(admin)
        original = admin.execute('SELECT * FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=2', (*SCOPE.key, OLD)).fetchone()
        record('intent', {'head': '9a5a8d0d6d3a8f18e99d47dcecb68ed83f9636b6', 'authority': 'AOS-001893',
            'task': 'qyh-source-boundary-rehearsal-20261011', 'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'],
            'database': DB, 'role': ROLE, 'historicalContractId': OLD, 'experimentalContractId': trial,
            'request': body.model_dump(mode='json', by_alias=True), 'initialCounts': initial,
            'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'historicalMetadataOnly': True})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            role_created = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_eval_freeze_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            assert not admin.execute('SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)', (ROLE,)).fetchone()
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.freeze_eval_contract(SCOPE, 'clone:test', trial, 2, 'qyh-eval-freeze-missing')))
            revised = store.revise_eval_contract(SCOPE, 'clone:test', trial, 'qyh-eval-freeze-revise', body)
            assert revised.version == 3 and revised.readiness.value == 'ready' and not revised.blockers
            cases.append('original-revise-real-historical-suite-publication-gate')
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.freeze_eval_contract(SCOPE, 'clone:test', trial, 2, 'qyh-eval-freeze-stale')))
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.freeze_eval_contract(TenantScope('dev-org', 'dev-project'), 'clone:test', trial, 3, 'qyh-eval-freeze-canary')))
            admin.execute("CREATE FUNCTION qyh_eval_freeze_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-eval-freeze-rollback' THEN RAISE EXCEPTION 'QYH_EVAL_FREEZE_RECEIPT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_eval_freeze_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_eval_freeze_rollback()')
            trigger_created = True
            saved = counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.freeze_eval_contract(SCOPE, 'clone:test', trial, 3, 'qyh-eval-freeze-rollback'), state='P0001'))
            assert counts(admin) == saved and store.get_eval_contract(SCOPE, trial).model_dump() == revised.model_dump()
            made = store.freeze_eval_contract(SCOPE, 'clone:test', trial, 3, 'qyh-eval-freeze-commit')
            assert made.revision == 4 and made.version == 4 and made.lifecycle.value == 'frozen' and made.readiness.value == 'ready'
            assert store.freeze_eval_contract(SCOPE, 'clone:test', trial, 3, 'qyh-eval-freeze-commit').model_dump() == made.model_dump()
            cases.append('original-freeze-commit-and-idempotency')
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.freeze_eval_contract(SCOPE, 'clone:test', trial, 4, 'qyh-eval-freeze-commit')))
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.freeze_eval_contract(SCOPE, 'clone:test', trial, 4, 'qyh-eval-freeze-frozen')))
            cases.append(C.expect_error(psycopg.Error, forge_runtime, state='42501'))
            final = counts(admin)
            assert final == dict(initial, aip_eval_contract_revision=initial['aip_eval_contract_revision']+2,
                aip_production_contract_receipt=initial['aip_production_contract_receipt']+2)
            assert admin.execute('SELECT * FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=2', (*SCOPE.key, OLD)).fetchone() == original
            record('business-result', {'cases': cases, 'connections': connections,
                'revised': revised.model_dump(mode='json', by_alias=True), 'frozen': made.model_dump(mode='json', by_alias=True),
                'finalCounts': final, 'noNewRunOrStep': True, 'historicalMetadataOnly': True,
                'formalLoginConnected': False, 'formalPublisherConnected': False, 'fullRestorationAccepted': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if trigger_created:
                admin.execute('DROP TRIGGER qyh_eval_freeze_rollback ON aip_production_contract_receipt')
            admin.execute('DROP FUNCTION IF EXISTS qyh_eval_freeze_rollback()')
            if role_created:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_eval_freeze_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before == C.S.P.M.fingerprint('qyh-restored-pg-20261011')
    assert C.S.D.metadata(C.TARGET) == metadata == C.S.D.metadata('qyh-restored-pg-20261011')
    record('verified', {'originalAndCurrent647DataExact': True, 'allOriginalMetadataExact': True,
        'temporaryRoleAndPoliciesRemoved': True, 'faultTriggerRemoved': True,
        'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'currentDatabaseTouched': False}))

def forge_runtime():
    with C.runtime(SCOPE, read_only=False) as conn:
        conn.execute("INSERT INTO aip_production_contract_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by) VALUES('org-org','dev-project','qyh-eval-freeze-forged','eval_contract.freeze','qyh-eval-freeze-forged',%s,'{}','clone:test')", ('a'*64,))

if __name__ == '__main__':
    main()
