"""Actual Eval and nonempty Evidence build on the retained historical test copy."""
import hashlib
import json
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

import real_contract as C
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contracts import CreateEvalContractRequest, ReviseEvalContractRequest, ExactRevisionRef, BuildEvidenceBundleRequest
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractConflict, ProductionContractDependencyBlocked, ProductionContractIdempotencyConflict, ProductionContractNotFound
from aos_api.evidence_bundle_provenance import read_build_provenance
from aos_api.tenant_scope import TenantScope

R, DB, ROLE, SCOPE = C.R, C.DB, C.ROLE, C.SCOPE
TABLES = {
    'aip_eval_contract_head': 'SELECT,INSERT,UPDATE',
    'aip_eval_contract_revision': 'SELECT,INSERT',
    'aip_eval_suite_revision': 'SELECT',
    'aip_production_contract_receipt': 'SELECT,INSERT',
    'aip_task_brief_head': 'SELECT', 'aip_task_brief_revision': 'SELECT',
    'aip_evidence': 'SELECT', 'aip_evidence_revoke_event': 'SELECT',
    'aip_evidence_bundle_revision': 'SELECT,INSERT',
    'aip_evidence_bundle_build_provenance': 'SELECT,INSERT',
    'aip_evidence_bundle_revoke_event': 'SELECT',
}


def record(name, value):
    with (R / ('eval-bundle-' + name + '.json')).open('x') as out:
        json.dump(value, out, default=str, indent=2)
        out.write('\n')


def counts(conn):
    names = ('aip_eval_contract_head', 'aip_eval_contract_revision',
             'aip_evidence_bundle_revision', 'aip_evidence_bundle_build_provenance',
             'aip_production_contract_receipt')
    return {n: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(n))).fetchone()['n'] for n in names}


def main():
    assert not (R / 'eval-bundle-intent.json').exists(), 'Existing attempt: reconcile only'
    previous = json.loads((R / 'contract-r2-verified.json').read_text())
    assert previous['experimentalDatabaseRetained'] == DB and previous['temporaryRoleRemoved']
    frozen = json.loads((C.ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(C.S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', C.TARGET]))
    assert item['Id'] == frozen['container']['Id'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before = C.S.P.M.fingerprint(C.TARGET)
    metadata = C.S.D.metadata(C.TARGET)
    config = SourceIssuerDatabaseConfig('contract', BIIssuerDatabaseConfig('127.0.0.1', 18431, DB, (R / 'private/contract-identity/contract.pgpass').resolve()))
    connections = []
    @contextmanager
    def contract(scope):
        with connect_source_issuer_write(config, scope) as conn:
            identity = conn.execute('SELECT session_user AS login,current_user AS role,current_database() AS db').fetchone()
            assert identity == {'login': ROLE, 'role': ROLE, 'db': DB}
            connections.append(identity)
            yield conn
    def no_plan(scope):
        raise AssertionError('Contract operation used Plan factory')
    cases = []
    created_role = False
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB, user='aos_app', autocommit=True, row_factory=dict_row) as admin:
        assert admin.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == frozen['cloneIdentity']['cluster']
        assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        assert admin.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_159'
        guard = admin.execute("SELECT pg_get_functiondef('public.s3owe_guard()'::regprocedure) AS definition").fetchone()['definition']
        assert ROLE in guard and 'session_user' in guard and 'current_user' in guard
        record('intent', {'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'], 'database': DB,
                          'guardHash': hashlib.sha256(guard.encode()).hexdigest(), 'role': ROLE,
                          'currentDatabaseTouched': False, 'originalCloneDatabaseWrites': False,
                          'historicalCutoffOnly': True})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_eval_bundle_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            for table in C.SOURCE_TABLES:
                assert not admin.execute('SELECT has_table_privilege(%s,%s,%s) AS writable', ('aos_runtime', table, 'INSERT')).fetchone()['writable']
            store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), plan_connect_factory=no_plan, contract_connect_factory=contract)
            suite = admin.execute('SELECT suite_id,revision,content_hash FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s ORDER BY suite_id,revision LIMIT 1', SCOPE.key).fetchone()
            assert suite
            body = CreateEvalContractRequest(suite_ref=ExactRevisionRef(resource_type='EvalSuiteRevision', resource_id=suite['suite_id'], revision=suite['revision'], content_hash=suite['content_hash']), artifact_schema_ref=ResourceRef(resource_type='Schema', resource_id='ecommerce.analysis', revision='1', authority='aip'), severity_thresholds={'critical': 1.0}, gate_policy={'mode': 'all'}, return_mapping={'critical': 'draft'}, override_policy={'allowed': False})
            made = store.create_eval_contract(SCOPE, 'clone:test', 'qyh-eval-create', body)
            assert made.readiness.value == 'blocked'
            assert {b.code for b in made.blockers} == {'EVAL_PUBLICATION_MISSING', 'EVAL_GATE_MISSING'}
            assert store.create_eval_contract(SCOPE, 'clone:test', 'qyh-eval-create', body).contract_id == made.contract_id
            cases.append('actual-retained-suite-create-replay-original-blockers')
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.create_eval_contract(SCOPE, 'clone:test', 'qyh-eval-create', body.model_copy(update={'severity_thresholds': {'critical': .9}}))))
            revised_body = ReviseEvalContractRequest(**body.model_dump(), expected_version=made.version)
            revised = store.revise_eval_contract(SCOPE, 'clone:test', made.contract_id, 'qyh-eval-revise', revised_body)
            assert (revised.revision, revised.version) == (2, 2)
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.revise_eval_contract(SCOPE, 'clone:test', made.contract_id, 'qyh-eval-stale', revised_body)))
            saved = counts(admin)
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.freeze_eval_contract(SCOPE, 'clone:test', made.contract_id, revised.version, 'qyh-eval-closed-freeze')))
            assert counts(admin) == saved
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.get_eval_contract(TenantScope('dev-org', 'dev-project'), made.contract_id)))
            brief_row = admin.execute("SELECT brief_id,revision,content_hash FROM aip_task_brief_revision WHERE org_id=%s AND project_id=%s AND created_by='clone:test' AND lifecycle='frozen' ORDER BY brief_id LIMIT 1", SCOPE.key).fetchone()
            assert brief_row
            evidence_rows = admin.execute('''SELECT evidence_id,content_hash,payload,freshness_at FROM aip_evidence e
                WHERE org_id=%s AND project_id=%s AND freshness_at IS NOT NULL
                AND NOT EXISTS(SELECT 1 FROM aip_evidence_revoke_event r WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id AND r.revision=1 AND r.content_hash=e.content_hash)
                ORDER BY evidence_id''', SCOPE.key).fetchall()
            evidence = next(x for x in evidence_rows if store._evidence_fact_ids(x['payload']))
            facts = store._evidence_fact_ids(evidence['payload'])
            request = BuildEvidenceBundleRequest(brief_ref=ExactRevisionRef(resource_type='TaskBriefRevision', resource_id=brief_row['brief_id'], revision=brief_row['revision'], content_hash=brief_row['content_hash']), subject_refs=[], cutoff_at=evidence['freshness_at'], item_refs=[ExactRevisionRef(resource_type='Evidence', resource_id=evidence['evidence_id'], revision=1, content_hash=evidence['content_hash'])], required_fact_ids=facts)
            bundle = store.build_evidence_bundle(SCOPE, 'clone:test', 'qyh-evidence-build', request)
            assert bundle.coverage.value == 'complete' and bundle.freshness.value == 'fresh'
            assert store.build_evidence_bundle(SCOPE, 'clone:test', 'qyh-evidence-build', request).bundle_id == bundle.bundle_id
            ref = ExactRevisionRef(resource_type='EvidenceBundleRevision', resource_id=bundle.bundle_id, revision=bundle.revision, content_hash=bundle.content_hash)
            with contract(SCOPE) as conn:
                provenance = read_build_provenance(conn, SCOPE, ref)
                assert provenance.required_fact_ids == tuple(facts)
            cases.append('nonempty-historical-evidence-build-replay-exact-provenance')
            drifted = request.model_copy(update={'item_refs': [request.item_refs[0].model_copy(update={'content_hash': '0' * 64})]})
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.build_evidence_bundle(SCOPE, 'clone:test', 'qyh-evidence-drift', drifted)))
            admin.execute("CREATE FUNCTION qyh_eval_bundle_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key IN ('qyh-eval-rollback','qyh-evidence-rollback') THEN RAISE EXCEPTION 'QYH_CONTRACT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_eval_bundle_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_eval_bundle_rollback()')
            for key, action in [('qyh-eval-rollback', lambda: store.create_eval_contract(SCOPE, 'clone:test', 'qyh-eval-rollback', body)), ('qyh-evidence-rollback', lambda: store.build_evidence_bundle(SCOPE, 'clone:test', 'qyh-evidence-rollback', request))]:
                saved = counts(admin)
                cases.append(C.expect_error(psycopg.Error, action, state='P0001'))
                assert counts(admin) == saved
            record('business-result', {'cases': cases, 'connections': connections, 'suiteRef': body.suite_ref.model_dump(mode='json', by_alias=True),
                                      'evalContractId': made.contract_id, 'bundleRef': ref.model_dump(mode='json', by_alias=True),
                                      'historicalEvidenceCutoff': request.cutoff_at, 'requiredFacts': facts,
                                      'originalBuildProvenanceVerified': True, 'originalEvalFreezeRemainsBlocked': True,
                                      'all29OperationsOrNaturalFirstChainAccepted': False, 'passwordOrOIDCAuthenticated': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_eval_bundle_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    record('verified', {'originalClone647DataExact': True, 'allOriginalMetadataExact': True, 'temporaryRoleRemoved': True,
                        'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'actualNonemptyHistoricalBuild': True, 'currentDatabaseTouched': False}))


if __name__ == '__main__':
    main()
