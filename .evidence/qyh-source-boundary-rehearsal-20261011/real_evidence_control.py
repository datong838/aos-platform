"""Original revoke and denied-disclosure transactions on the historical clone."""
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
from aos_api.aip_production_contracts import RevokeEvidenceRequest, ResolveEvidenceDisclosureRequest, EvidenceExactRevisionRef
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked, ProductionContractIdempotencyConflict, ProductionContractNotFound
from aos_api.tenant_scope import TenantScope

R, DB, ROLE, SCOPE = C.R, C.DB, C.ROLE, C.SCOPE
TABLES = {'aip_evidence': 'SELECT', 'aip_evidence_revoke_event': 'SELECT,INSERT',
          'aip_evidence_bundle_revision': 'SELECT', 'aip_evidence_bundle_revoke_event': 'SELECT',
          'aip_evidence_disclosure_decision': 'SELECT,INSERT', 'aip_production_contract_receipt': 'SELECT,INSERT'}


def record(name, value):
    with (R / ('evidence-control-' + name + '.json')).open('x') as out:
        out.write(json.dumps(value, default=str, indent=2) + '\n')


def counts(conn):
    return {n: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(n))).fetchone()['n'] for n in TABLES}


def main():
    assert not (R / 'evidence-control-intent.json').exists(), 'Existing attempt: reconcile only'
    assert json.loads((R / 'artifact-family-verified.json').read_text())['temporaryRoleRemoved']
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
        evidence = admin.execute("""SELECT evidence_id,content_hash,payload FROM aip_evidence e WHERE org_id=%s AND project_id=%s
            AND NOT (payload ? 'evidencePolicyVersion') AND source_type <> 'aip-metric-query'
            AND NOT EXISTS(SELECT 1 FROM aip_evidence_revoke_event r WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id AND r.revision=1 AND r.content_hash=e.content_hash)
            ORDER BY evidence_id LIMIT 1""", SCOPE.key).fetchone()
        assert evidence
        evidence_ref = EvidenceExactRevisionRef(resource_type='Evidence', resource_id=evidence['evidence_id'], revision=1, content_hash=evidence['content_hash'])
        record('intent', {'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'], 'database': DB, 'role': ROLE, 'currentDatabaseTouched': False, 'originalCloneDatabaseWrites': False, 'evidenceRef': evidence_ref.model_dump(mode='json', by_alias=True), 'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_evidence_control_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            for table in C.SOURCE_TABLES:
                assert not admin.execute('SELECT has_table_privilege(%s,%s,%s) AS writable', ('aos_runtime', table, 'INSERT')).fetchone()['writable']
            store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), plan_connect_factory=no_plan, contract_connect_factory=contract)
            body = RevokeEvidenceRequest(expected_content_hash=evidence['content_hash'], reason='仅隔离历史副本撤销演练，不修改原栖月汇证据')
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.revoke_evidence(SCOPE, 'clone:test', evidence['evidence_id'], 'qyh-revoke-drift', body.model_copy(update={'expected_content_hash': '0' * 64}))))
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.revoke_evidence(TenantScope('dev-org', 'dev-project'), 'clone:test', evidence['evidence_id'], 'qyh-revoke-canary', body)))
            admin.execute("CREATE FUNCTION qyh_evidence_control_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key IN ('qyh-revoke-rollback','qyh-disclosure-rollback') THEN RAISE EXCEPTION 'QYH_CONTRACT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_evidence_control_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_evidence_control_rollback()')
            saved = counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.revoke_evidence(SCOPE, 'clone:test', evidence['evidence_id'], 'qyh-revoke-rollback', body), state='P0001'))
            assert counts(admin) == saved
            revoked = store.revoke_evidence(SCOPE, 'clone:test', evidence['evidence_id'], 'qyh-revoke-create', body)
            assert store.revoke_evidence(SCOPE, 'clone:test', evidence['evidence_id'], 'qyh-revoke-create', body).event_id == revoked.event_id
            cases.append('original-revoke-exact-event-and-replay')
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.revoke_evidence(SCOPE, 'clone:test', evidence['evidence_id'], 'qyh-revoke-create', body.model_copy(update={'reason': 'drift'}))))
            disclosure = ResolveEvidenceDisclosureRequest(evidence_ref=evidence_ref, purpose='summary', requested_level='l1')
            decision = store.resolve_evidence_disclosure(SCOPE, 'clone:test', 'qyh-disclosure-create', disclosure, markings=['public'])
            assert 'EVIDENCE_REVOKED' in decision.reasons
            assert decision.granted_level is None and decision.display_payload == {}
            assert not decision.redaction_receipt['bodyReturned']
            replay = store.resolve_evidence_disclosure(SCOPE, 'clone:test', 'qyh-disclosure-create', disclosure, markings=['public'])
            assert replay.decision_id == decision.decision_id and replay.granted_level is None
            cases.append('original-denied-disclosure-and-replay-no-body')
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.resolve_evidence_disclosure(SCOPE, 'clone:test', 'qyh-disclosure-create', disclosure.model_copy(update={'purpose': type(disclosure.purpose)('preview')}), markings=['public'])))
            saved = counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.resolve_evidence_disclosure(SCOPE, 'clone:test', 'qyh-disclosure-rollback', disclosure, markings=['public']), state='P0001'))
            assert counts(admin) == saved
            assert admin.execute('SELECT payload FROM aip_evidence WHERE evidence_id=%s', (evidence['evidence_id'],)).fetchone()['payload'] == evidence['payload']
            record('business-result', {'cases': cases, 'connections': connections, 'evidenceRef': evidence_ref.model_dump(mode='json', by_alias=True), 'revokeEventId': revoked.event_id, 'decisionId': decision.decision_id, 'status': decision.status.value, 'reasons': decision.reasons, 'noBodyOrGrantedLevel': True, 'originalEvidencePayloadUnchanged': True, 'actualDisclosureAuthorization': False, 'passwordOrOIDCAuthenticated': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_evidence_control_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    record('verified', {'originalClone647DataExact': True, 'allOriginalMetadataExact': True, 'temporaryRoleRemoved': True, 'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'originalDisclosureDenied': True, 'currentDatabaseTouched': False}))


if __name__ == '__main__':
    main()
