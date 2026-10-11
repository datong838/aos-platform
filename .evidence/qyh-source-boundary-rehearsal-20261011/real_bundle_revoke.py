"""Generic unissued bundle revoke keeps the original initialization source fence."""
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
from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked, ProductionContractIdempotencyConflict, ProductionContractNotFound
from aos_api.tenant_scope import TenantScope

R, DB, ROLE, SCOPE = C.R, C.DB, C.ROLE, C.SCOPE
TABLES = {'aip_evidence_bundle_revision': 'SELECT', 'aip_license_source_issuance': 'SELECT',
          'aip_evidence_bundle_revoke_event': 'SELECT,INSERT', 'aip_production_contract_receipt': 'SELECT,INSERT'}
FUNCTION = 'public.aos_license_source_initialization_lock(text,text,text,bigint,text,boolean)'
HEAD_FUNCTION = 'public.aos_license_source_lock(text,text,text,bigint,text,boolean)'


def record(name, value):
    with (R / ('bundle-revoke-' + name + '.json')).open('x') as out:
        out.write(json.dumps(value, default=str, indent=2) + '\n')


def counts(conn):
    return {n: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(n))).fetchone()['n'] for n in [*TABLES, 'aip_license_source_initialization_fence', 'aip_license_source_head']}


def main():
    assert not (R / 'bundle-revoke-intent.json').exists(), 'Existing attempt: reconcile only'
    assert json.loads((R / 'evidence-control-verified.json').read_text())['temporaryRoleRemoved']
    ref = json.loads((R / 'eval-bundle-business-result.json').read_text())['bundleRef']
    frozen = json.loads((C.ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(C.S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', C.TARGET]))
    assert item['Id'] == frozen['container']['Id'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before, metadata = C.S.P.M.fingerprint(C.TARGET), C.S.D.metadata(C.TARGET)
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
        raise AssertionError('Contract operation used Plan factory')
    created_role = False
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB, user='aos_app', autocommit=True, row_factory=dict_row) as admin:
        assert admin.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == frozen['cloneIdentity']['cluster']
        assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        assert admin.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_159'
        bundle = admin.execute('SELECT * FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s', (*SCOPE.key, ref['resourceId'], ref['revision'])).fetchone()
        assert bundle and bundle['content_hash'] == ref['contentHash']
        assert not admin.execute('SELECT 1 FROM aip_license_source_issuance WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s', (*SCOPE.key, ref['resourceId'], ref['revision'])).fetchone()
        assert not admin.execute('SELECT 1 FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s AND revision=%s AND content_hash=%s', (ref['resourceId'], ref['revision'], ref['contentHash'])).fetchone()
        definition = admin.execute('SELECT pg_get_functiondef(%s::regprocedure) AS d', (FUNCTION,)).fetchone()['d']
        expected_hash = json.loads((R / 'bundle-revoke-dependency-readback.json').read_text())['functions'][0]['definitionHash']
        assert hashlib.sha256(definition.encode()).hexdigest() == expected_hash
        record('intent', {'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'], 'database': DB, 'role': ROLE, 'bundleRef': ref, 'unissuedSourceOnly': True, 'functionSignature': FUNCTION, 'functionHash': expected_hash, 'currentDatabaseTouched': False, 'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_bundle_revoke_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), plan_connect_factory=no_plan, contract_connect_factory=contract)
            body = RevokeEvidenceBundleRequest(expected_revision=ref['revision'], expected_content_hash=ref['contentHash'], reason='隔离副本普通未发行证据包撤销演练')
            assert not admin.execute('SELECT has_function_privilege(%s,%s,%s) AS allowed', (ROLE, FUNCTION, 'EXECUTE')).fetchone()['allowed']
            saved = counts(admin)
            try:
                store.revoke_evidence_bundle(SCOPE, 'clone:test', ref['resourceId'], 'qyh-bundle-denied', body)
            except ProductionContractDependencyBlocked as error:
                assert str(error) == 'LICENSE_SOURCE_FENCE_DENIED'
                cases.append('missing-exact-function-execute-original-fence-denied')
            else:
                raise AssertionError('Missing source lock permission accepted')
            assert counts(admin) == saved
            admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION ' + FUNCTION + ' TO {}').format(sql.Identifier(ROLE)))
            assert not admin.execute('SELECT has_function_privilege(%s,%s,%s) AS allowed', (ROLE, HEAD_FUNCTION, 'EXECUTE')).fetchone()['allowed']
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.revoke_evidence_bundle(SCOPE, 'clone:test', ref['resourceId'], 'qyh-bundle-drift', body.model_copy(update={'expected_content_hash': '0' * 64}))))
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.revoke_evidence_bundle(TenantScope('dev-org', 'dev-project'), 'clone:test', ref['resourceId'], 'qyh-bundle-canary', body)))
            admin.execute("CREATE FUNCTION qyh_bundle_revoke_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-bundle-rollback' THEN RAISE EXCEPTION 'QYH_CONTRACT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_bundle_revoke_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_bundle_revoke_rollback()')
            saved = counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.revoke_evidence_bundle(SCOPE, 'clone:test', ref['resourceId'], 'qyh-bundle-rollback', body), state='P0001'))
            assert counts(admin) == saved
            result = store.revoke_evidence_bundle(SCOPE, 'clone:test', ref['resourceId'], 'qyh-bundle-revoke', body)
            assert result.revoked
            assert store.revoke_evidence_bundle(SCOPE, 'clone:test', ref['resourceId'], 'qyh-bundle-revoke', body).revoked
            cases.append('original-unissued-bundle-revoke-and-replay-source-lock-kept')
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.revoke_evidence_bundle(SCOPE, 'clone:test', ref['resourceId'], 'qyh-bundle-revoke', body.model_copy(update={'reason': 'drift'}))))
            assert admin.execute('SELECT pg_get_functiondef(%s::regprocedure) AS d', (FUNCTION,)).fetchone()['d'] == definition
            assert admin.execute('SELECT * FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s', (*SCOPE.key, ref['resourceId'], ref['revision'])).fetchone() == bundle
            record('business-result', {'cases': cases, 'connections': connections, 'bundleRef': ref, 'functionHash': expected_hash, 'exactInitializationFunctionGrantOnly': True, 'headFunctionGrant': False, 'issuedSourcePathAccepted': False, 'bundleRevisionUnchanged': True, 'passwordOrOIDCAuthenticated': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_bundle_revoke_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    record('verified', {'originalClone647DataExact': True, 'allOriginalMetadataExact': True, 'temporaryRoleRemoved': True, 'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'originalSourceFenceKept': True, 'currentDatabaseTouched': False}))


if __name__ == '__main__':
    main()
