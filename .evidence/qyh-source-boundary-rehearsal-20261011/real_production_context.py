"""Original production-context transaction using preserved historical exact refs."""
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
from aos_api.aip_production_contracts import FreezeProductionContextRequest
from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict, ProductionContractNotFound)
from aos_api.tenant_scope import TenantScope

R, DB, ROLE, SCOPE = C.R, C.DB, C.ROLE, C.SCOPE
TABLES = {'aip_task_brief_revision': 'SELECT', 'aip_evidence_bundle_revision': 'SELECT',
          'aip_evidence_bundle_revoke_event': 'SELECT', 'aip_eval_contract_revision': 'SELECT',
          'aip_responsibility_plan_revision': 'SELECT',
          'aip_production_context_revision': 'SELECT,INSERT',
          'aip_production_contract_receipt': 'SELECT,INSERT'}
OLD = 'ctx-daeec3f5a06049a08783'

def record(name, body):
    with (R / ('production-context-' + name + '.json')).open('x') as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2, default=str)
        stream.write('\n')

def counts(conn):
    return {t: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(t))).fetchone()['n']
            for t in ('aip_production_context_revision', 'aip_production_contract_receipt', 'aip_task_run', 'aip_step_run')}

def main():
    assert not (R / 'production-context-intent.json').exists(), 'Existing attempt: reconcile only'
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
        raise AssertionError('Context operation used Plan factory')
    role_created = False
    trigger_created = False
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB, user='aos_app', autocommit=True, row_factory=dict_row) as admin:
        assert admin.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == frozen['cloneIdentity']['cluster']
        assert admin.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_159'
        assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        old = admin.execute('SELECT * FROM aip_production_context_revision WHERE org_id=%s AND project_id=%s AND context_id=%s', (*SCOPE.key, OLD)).fetchone()
        assert old and old['lifecycle'] == 'frozen' and old['readiness'] == 'ready'
        assert old['production_profile_ref'] is None and old['preparation_ref'] is None
        body = FreezeProductionContextRequest(task_id=old['task_id'], profile=old['profile'],
            brief_ref=old['brief_ref'], evidence_bundle_ref=old['evidence_bundle_ref'],
            eval_contract_ref=old['eval_contract_ref'], responsibility_plan_ref=old['responsibility_plan_ref'])
        guard = admin.execute("SELECT pg_get_functiondef('public.s3owe_guard()'::regprocedure) AS definition").fetchone()['definition']
        assert ROLE in guard and 'session_user' in guard and 'current_user' in guard
        initial = counts(admin)
        record('intent', {'head': 'daaf9e19ce45b6d6576d6507a5cd801f85ba0d84', 'authority': 'AOS-001892',
            'task': 'qyh-source-boundary-rehearsal-20261011', 'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'],
            'database': DB, 'role': ROLE, 'historicalContextId': OLD, 'request': body.model_dump(mode='json', by_alias=True),
            'initialCounts': initial, 'historicalStoredFreshnessOnly': True, 'currentSignedInstallationVerified': False,
            'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'guardHash': hashlib.sha256(guard.encode()).hexdigest()})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            role_created = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_context_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            assert not admin.execute('SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)', (ROLE,)).fetchone()
            store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), contract_connect_factory=contract, plan_connect_factory=no_plan)
            made = store.freeze_production_context(SCOPE, 'clone:test', 'qyh-context-freeze', body)
            assert made.lifecycle.value == 'frozen' and made.readiness.value == 'ready'
            assert made.production_profile_ref is None and made.preparation_ref is None
            replay = store.freeze_production_context(SCOPE, 'clone:test', 'qyh-context-freeze', body)
            assert replay.model_dump(mode='json') == made.model_dump(mode='json')
            cases.append('original-context-freeze-commit-and-idempotency')
            drift = body.model_copy(update={'brief_ref': body.brief_ref.model_copy(update={'content_hash': '0' * 64})})
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.freeze_production_context(SCOPE, 'clone:test', 'qyh-context-freeze', drift)))
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.freeze_production_context(SCOPE, 'clone:test', 'qyh-context-drift', drift)))
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.freeze_production_context(TenantScope('dev-org', 'dev-project'), 'clone:test', 'qyh-context-canary', body)))
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.get_production_context(TenantScope('dev-org', 'dev-project'), made.context_id)))
            admin.execute("CREATE FUNCTION qyh_context_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-context-rollback' THEN RAISE EXCEPTION 'QYH_CONTEXT_RECEIPT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_context_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_context_rollback()')
            trigger_created = True
            saved = counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.freeze_production_context(SCOPE, 'clone:test', 'qyh-context-rollback', body), state='P0001'))
            assert counts(admin) == saved
            cases.append(C.expect_error(psycopg.Error, forge_runtime, state='42501'))
            final = counts(admin)
            assert final['aip_production_context_revision'] == initial['aip_production_context_revision'] + 1
            assert final['aip_production_contract_receipt'] == initial['aip_production_contract_receipt'] + 1
            assert final['aip_task_run'] == initial['aip_task_run'] and final['aip_step_run'] == initial['aip_step_run']
            assert admin.execute('SELECT * FROM aip_production_context_revision WHERE org_id=%s AND project_id=%s AND context_id=%s', (*SCOPE.key, OLD)).fetchone() == old
            record('business-result', {'cases': cases, 'connections': connections, 'context': made.model_dump(mode='json', by_alias=True),
                'finalCounts': final, 'historicalStoredFreshnessOnly': True, 'noNewRunOrStep': True,
                'currentSignedInstallationVerified': False, 'formalIdentityVerified': False, 'fullRestorationAccepted': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if trigger_created:
                admin.execute('DROP TRIGGER qyh_context_rollback ON aip_production_contract_receipt')
            admin.execute('DROP FUNCTION IF EXISTS qyh_context_rollback()')
            if role_created:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_context_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == before
    assert C.S.D.metadata('qyh-restored-pg-20261011') == metadata
    record('verified', {'originalAndCurrent647DataExact': True, 'allOriginalMetadataExact': True,
        'temporaryRoleAndPoliciesRemoved': True, 'faultTriggerRemoved': True, 'currentDatabaseTouched': False,
        'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'currentDatabaseTouched': False}))

def forge_runtime():
    with C.runtime(SCOPE, read_only=False) as conn:
        conn.execute("INSERT INTO aip_production_contract_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by) VALUES('org-org','dev-project','qyh-context-forged','production_context.freeze','qyh-context-forged',%s,'{}','clone:test')", ('a' * 64,))

if __name__ == '__main__':
    main()
