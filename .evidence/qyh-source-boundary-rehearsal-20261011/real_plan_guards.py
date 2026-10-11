"""Preserve original Plan authority and successor gates on retained history."""
import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

import real_contract as C
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.aip_production_contracts import CreateResponsibilityPlanRequest, ReviseResponsibilityPlanRequest, ExactRevisionRef
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked, ProductionContractConflict, ProductionContractNotFound
from aos_api.aip_responsibility_template_authority import InstalledProductionProfileResolver, ApprovedBIPreparationResolver
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.aip_responsibility_assignment import CreateResponsibilitySuccessorRequest
from aos_api.aip_responsibility_assignment_store import AipResponsibilityAssignmentStore, ResponsibilityAssignmentBlocked
from aos_api.tenant_scope import TenantScope

R, DB, SCOPE = C.R, C.DB, C.SCOPE
ROLE = 'aos_bi_plan_issuer'
TABLES = {'aip_responsibility_plan_head': 'SELECT,INSERT,UPDATE', 'aip_responsibility_plan_revision': 'SELECT,INSERT', 'aip_production_contract_receipt': 'SELECT,INSERT', 'aip_agent_instance': 'SELECT', 'aip_skill_binding': 'SELECT', 'aip_agent_registry_receipt': 'SELECT', 'aip_capability_binding': 'SELECT', 'aip_assignee_resolution_receipt': 'SELECT', 'aip_task_run': 'SELECT', 'aip_responsibility_successor': 'SELECT'}


def record(name, value):
    with (R / ('plan-guards-' + name + '.json')).open('x') as out:
        out.write(json.dumps(value, default=str, indent=2) + '\n')


def counts(conn):
    return {n: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(n))).fetchone()['n'] for n in TABLES}


def main():
    assert not (R / 'plan-guards-intent.json').exists(), 'Existing attempt: reconcile only'
    assert json.loads((R / 'bundle-revoke-verified.json').read_text())['temporaryRoleRemoved']
    frozen = json.loads((C.ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(C.S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', C.TARGET]))
    assert item['Id'] == frozen['container']['Id'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before, metadata = C.S.P.M.fingerprint(C.TARGET), C.S.D.metadata(C.TARGET)
    connections, cases = [], []
    created_role = False
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=DB, user='aos_app', autocommit=True, row_factory=dict_row) as admin:
        assert admin.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == frozen['cloneIdentity']['cluster']
        assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()
        historical = admin.execute("SELECT r.*,h.version FROM aip_responsibility_plan_revision r JOIN aip_responsibility_plan_head h USING(org_id,project_id,plan_id) WHERE r.org_id=%s AND r.project_id=%s AND r.lifecycle='frozen' AND r.revision=h.current_revision ORDER BY r.plan_id LIMIT 1", SCOPE.key).fetchone()
        assert historical and not historical['template_ref']['resourceId'].startswith('bundle://')
        task = admin.execute("SELECT task_id FROM aip_task_brief_revision b WHERE org_id=%s AND project_id=%s AND created_by='clone:test' AND NOT EXISTS(SELECT 1 FROM aip_task_run r WHERE r.org_id=b.org_id AND r.project_id=b.project_id AND r.task_id=b.task_id) LIMIT 1", SCOPE.key).fetchone()
        assert task
        root = C.ROOT / '.evidence/qyh-full-system-restoration-20261011/selected-public-bundles'
        trust = FileTrustRootProvider(C.ROOT / '.evidence/qyh-full-system-restoration-20261011/restoration-public-trust-roots.json')
        reader = lambda scope: C.runtime(scope, read_only=True)
        resolver = InstalledProductionProfileResolver(reader, release_root=root)
        ref = ExactRevisionRef.model_validate(historical['template_ref'])
        assert not resolver.resolve(SCOPE, ref)
        preparer = ApprovedBIPreparationResolver(reader, registry_connect_factory=lambda: C.runtime(SCOPE, read_only=True), release_root=root, trust_roots=trust, source_alias='a0v-canonical', registry_prepared_transaction=True)
        assert len(preparer._approved_rows(SCOPE)) == 0 and preparer.select(SCOPE) is None
        record('intent', {'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'], 'database': DB, 'role': ROLE, 'historicalPlanId': historical['plan_id'], 'historicalTemplateRef': historical['template_ref'], 'signedApprovedCandidateCount': 0, 'currentDatabaseTouched': False, 'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        private = R / 'private/plan-identity'
        private.mkdir(mode=0o700)
        passfile = private / 'plan.pgpass'
        fd = os.open(passfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(f'127.0.0.1:18431:{DB}:{ROLE}:{secrets.token_urlsafe(32)}\n')
        config = SourceIssuerDatabaseConfig('plan', BIIssuerDatabaseConfig('127.0.0.1', 18431, DB, passfile.resolve()))
        @contextmanager
        def plan(scope):
            with connect_source_issuer_write(config, scope) as conn:
                identity = conn.execute('SELECT session_user AS login,current_user AS role,current_database() AS db').fetchone()
                assert identity == {'login': ROLE, 'role': ROLE, 'db': DB}
                connections.append(identity)
                yield conn
        def no_contract(scope):
            raise AssertionError('Plan call used Contract factory')
        saved = counts(admin)
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_plan_guards_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            admin.execute(sql.SQL('GRANT SELECT ON aip_skill_template_revision TO {}').format(sql.Identifier(ROLE)))
            store = AipProductionContractStore(reader, responsibility_template_resolver=resolver.resolve, plan_connect_factory=plan, contract_connect_factory=no_contract)
            with plan(SCOPE) as conn:
                read = store.get_responsibility_plan(SCOPE, historical['plan_id'], conn=conn)
                assert read.lifecycle.value == 'frozen' and read.readiness.value == 'blocked' and len(read.slots) == 6
            cases.append('original-historical-six-slot-frozen-plan-read-current-blockers')
            body = CreateResponsibilityPlanRequest(profile=historical['profile'], template_ref=ref, slots=historical['slots'], merge_decisions=historical['merge_decisions'])
            try:
                store.create_responsibility_plan(SCOPE, 'clone:test', 'qyh-plan-source-denied', body)
            except ProductionContractDependencyBlocked as error:
                assert str(error) == 'RESPONSIBILITY_TEMPLATE_MISSING_OR_DRIFTED'
                cases.append('original-historical-template-not-signed-source-denied')
            else:
                raise AssertionError('Historical source accepted without current signed installation')
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.get_responsibility_plan(TenantScope('dev-org', 'dev-project'), historical['plan_id'])))
            revised = ReviseResponsibilityPlanRequest(**body.model_dump(), expected_version=historical['version'])
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.revise_responsibility_plan(SCOPE, 'clone:test', historical['plan_id'], 'qyh-plan-frozen-revise', revised)))
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.freeze_responsibility_plan(SCOPE, 'clone:test', historical['plan_id'], historical['version'], 'qyh-plan-frozen-freeze')))
            successor = CreateResponsibilitySuccessorRequest(task_id=task['task_id'], source_plan_ref=ExactRevisionRef(resource_type='ResponsibilityPlanRevision', resource_id=historical['plan_id'], revision=historical['revision'], content_hash=historical['content_hash']), expected_source_version=historical['version'], slot_id=read.slots[0].slot_id, target_assignee=read.slots[0].assignee, resolution_receipt_id='qyh-unavailable-resolution', reason_code='ISOLATED_GUARD_CHECK')
            assignment = AipResponsibilityAssignmentStore(reader, plan_connect_factory=plan)
            try:
                assignment.create_successor(SCOPE, successor, actor='clone:test', idempotency_key='qyh-plan-successor-denied')
            except ResponsibilityAssignmentBlocked as error:
                assert str(error) == 'ASSIGNEE_RESOLUTION_MISSING'
                cases.append('original-successor-missing-resolution-no-write')
            else:
                raise AssertionError('Missing successor resolution accepted')
            def forge_contract():
                with plan(SCOPE) as conn:
                    store._receipt(conn, SCOPE, 'task_brief.create', 'qyh-plan-contract-forgery', 'a' * 64, {'resourceType': 'TaskBriefRevision', 'resourceId': 'qyh-invalid', 'revision': 1, 'contentHash': 'b' * 64}, 'clone:test')
            cases.append(C.expect_error(psycopg.Error, forge_contract, state='42501'))
            assert counts(admin) == saved
            actual = admin.execute("SELECT r.*,h.version FROM aip_responsibility_plan_revision r JOIN aip_responsibility_plan_head h USING(org_id,project_id,plan_id) WHERE r.org_id=%s AND r.project_id=%s AND r.plan_id=%s AND r.revision=%s", (*SCOPE.key, historical['plan_id'], historical['revision'])).fetchone()
            assert actual == historical
            record('business-result', {'cases': cases, 'connections': connections, 'historicalPlanId': historical['plan_id'], 'historicalRevision': historical['revision'], 'historicalHash': historical['content_hash'], 'historicalVersion': historical['version'], 'originalBlockers': [x.code for x in read.blockers], 'allRelatedTableCountsUnchanged': True, 'originalHistoricalPlanUnchanged': True, 'signedApprovedCandidateCount': 0, 'genericBISuccessorPositiveAccepted': False, 'passwordOrOIDCAuthenticated': False})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_plan_guards_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    record('verified', {'originalClone647DataExact': True, 'allOriginalMetadataExact': True, 'temporaryRoleRemoved': True, 'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'historicalSourceRecoveryGapVerified': True, 'currentDatabaseTouched': False}))


if __name__ == '__main__':
    main()
