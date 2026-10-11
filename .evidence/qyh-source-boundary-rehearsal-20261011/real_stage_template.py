"""Original StageTemplate lifecycle in the retained historical test copy only."""
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
from aos_api.aip_stage_template_authority import published_source_bundle_ref, resolve_stage_template_source
from aos_api.aip_production_contracts import CreateStageTemplateRequest, ReviseStageTemplateRequest
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractConflict, ProductionContractDependencyBlocked, ProductionContractIdempotencyConflict, ProductionContractNotFound
from aos_api.tenant_scope import TenantScope

R, DB, ROLE, SCOPE = C.R, C.DB, C.ROLE, C.SCOPE
TABLES = {'aip_stage_template_head': 'SELECT,INSERT,UPDATE',
          'aip_stage_template_revision': 'SELECT,INSERT',
          'aip_production_contract_receipt': 'SELECT,INSERT'}


def record(name, value):
    with (R / ('stage-lifecycle-' + name + '.json')).open('x') as out:
        out.write(json.dumps(value, indent=2, default=str) + '\n')


def counts(conn):
    return {n: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(n))).fetchone()['n'] for n in TABLES}


def main():
    assert not (R / 'stage-lifecycle-intent.json').exists(), 'Existing attempt: reconcile only'
    frozen = json.loads((C.ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(C.S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', C.TARGET]))
    assert item['Id'] == frozen['container']['Id'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before = C.S.P.M.fingerprint(C.TARGET)
    metadata = C.S.D.metadata(C.TARGET)
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
        raise AssertionError('Stage operation used Plan factory')
    created_role = False
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB, user='aos_app', autocommit=True, row_factory=dict_row) as admin:
        assert admin.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == frozen['cloneIdentity']['cluster']
        assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        assert admin.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_159'
        old = admin.execute('SELECT template_id,revision,content_hash,profile,stages FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s ORDER BY template_id,revision LIMIT 1', SCOPE.key).fetchone()
        assert old
        source = published_source_bundle_ref()
        assert resolve_stage_template_source(SCOPE, source)
        assert not resolve_stage_template_source(SCOPE, source.model_copy(update={'content_hash': '0' * 64}))
        body = CreateStageTemplateRequest(profile=old['profile'], source_bundle_ref=source, stages=old['stages'])
        record('intent', {'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'], 'database': DB,
                         'head': 'f0c5e5479c9065e94095667ae19f4d219582b397', 'authority': 'AOS-001887',
                         'task': 'qyh-source-boundary-rehearsal-20261011', 'role': ROLE,
                         'historicalStageRef': {k: old[k] for k in ('template_id', 'revision', 'content_hash')},
                         'sourceRef': source.model_dump(mode='json', by_alias=True), 'sourceIsLegacyStaticAllowlist': True,
                         'currentSignedInstallationVerified': False, 'currentDatabaseTouched': False,
                         'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_stage_lifecycle_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), stage_template_source_resolver=resolve_stage_template_source, contract_connect_factory=contract, plan_connect_factory=no_plan)
            made = store.create_stage_template(SCOPE, 'clone:test', 'qyh-stage-create', body)
            assert made.lifecycle.value == 'draft' and made.readiness.value == 'ready' and not made.blockers
            assert store.create_stage_template(SCOPE, 'clone:test', 'qyh-stage-create', body).template_id == made.template_id
            cases.append('original-create-and-idempotency')
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.create_stage_template(SCOPE, 'clone:test', 'qyh-stage-create', body.model_copy(update={'profile': 'ecommerce.drift'}))))
            revised_body = ReviseStageTemplateRequest(**body.model_dump(), expected_version=made.version)
            revised = store.revise_stage_template(SCOPE, 'clone:test', made.template_id, 'qyh-stage-revise', revised_body)
            assert revised.revision == 2 and revised.version == 2
            assert store.revise_stage_template(SCOPE, 'clone:test', made.template_id, 'qyh-stage-revise', revised_body).revision == 2
            cases.append('original-revise-and-idempotency')
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.revise_stage_template(SCOPE, 'clone:test', made.template_id, 'qyh-stage-stale', revised_body)))
            frozen_stage = store.freeze_stage_template(SCOPE, 'clone:test', made.template_id, revised.version, 'qyh-stage-freeze')
            assert frozen_stage.lifecycle.value == 'frozen' and frozen_stage.revision == 3 and frozen_stage.seal_hash
            assert store.freeze_stage_template(SCOPE, 'clone:test', made.template_id, revised.version, 'qyh-stage-freeze').seal_hash == frozen_stage.seal_hash
            cases.append('original-freeze-seal-and-idempotency')
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.revise_stage_template(SCOPE, 'clone:test', made.template_id, 'qyh-stage-frozen-revise', revised_body.model_copy(update={'expected_version': frozen_stage.version}))))
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.get_stage_template(TenantScope('dev-org', 'dev-project'), made.template_id)))
            drifted_body = body.model_copy(update={'source_bundle_ref': source.model_copy(update={'content_hash': '0' * 64})})
            drifted = store.create_stage_template(SCOPE, 'clone:test', 'qyh-stage-drift-create', drifted_body)
            assert drifted.readiness.value == 'blocked' and [x.code for x in drifted.blockers] == ['STAGE_SOURCE_MISSING_OR_DRIFTED']
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.freeze_stage_template(SCOPE, 'clone:test', drifted.template_id, drifted.version, 'qyh-stage-drift-freeze')))
            admin.execute("CREATE FUNCTION qyh_stage_lifecycle_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-stage-rollback' THEN RAISE EXCEPTION 'QYH_STAGE_RECEIPT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_stage_lifecycle_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_stage_lifecycle_rollback()')
            saved = counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.create_stage_template(SCOPE, 'clone:test', 'qyh-stage-rollback', body), state='P0001'))
            assert counts(admin) == saved
            cases.append(C.expect_error(psycopg.Error, lambda: forge_runtime(), state='42501'))
            assert admin.execute('SELECT template_id,revision,content_hash,profile,stages FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s AND template_id=%s AND revision=%s', (*SCOPE.key, old['template_id'], old['revision'])).fetchone() == old
            record('business-result', {'cases': cases, 'connections': connections, 'frozen': frozen_stage.model_dump(mode='json', by_alias=True), 'drifted': drifted.model_dump(mode='json', by_alias=True), 'sourceIsLegacyStaticAllowlist': True, 'actualSignedInstallationVerified': False, 'passwordOrOIDCAuthenticated': False, 'fullRestorationAccepted': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_stage_lifecycle_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == before
    assert C.S.D.metadata('qyh-restored-pg-20261011') == metadata
    record('verified', {'originalAndCurrent647DataExact': True, 'allOriginalMetadataExact': True, 'temporaryRoleRemoved': True, 'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'currentDatabaseTouched': False}))


def forge_runtime():
    with C.runtime(SCOPE, read_only=False) as conn:
        conn.execute("INSERT INTO aip_production_contract_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by) VALUES('org-org','dev-project','qyh-stage-forged','stage_template.create','qyh-stage-forged',%s,'{}','clone:test')", ('a' * 64,))


if __name__ == '__main__':
    main()
