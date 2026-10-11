"""Original Artifact family APIs in the isolated historical test database only."""
import hashlib
import json
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

import real_contract as C
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_production_contracts import ExactArtifactRef, ExactRevisionRef, RegisterArtifactFamilyRequest, AttachArtifactFamilyMemberRequest, SelectArtifactFamilyCandidateRequest, CreateArtifactRelationRequest, RegisterReviewRuleRevisionRequest
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractConflict, ProductionContractDependencyBlocked, ProductionContractIdempotencyConflict, ProductionContractNotFound
from aos_api.tenant_scope import TenantScope

R, DB, ROLE, SCOPE = C.R, C.DB, C.ROLE, C.SCOPE
TABLES = {
    'aip_artifact': 'SELECT',
    'aip_artifact_family_head': 'SELECT,INSERT,UPDATE',
    'aip_artifact_relation': 'SELECT,INSERT',
    'aip_artifact_family_selection_revision': 'SELECT,INSERT',
    'aip_review_rule_revision': 'SELECT,INSERT',
    'aip_production_contract_receipt': 'SELECT,INSERT',
}


def record(name, value):
    with (R / ('artifact-family-' + name + '.json')).open('x') as out:
        json.dump(value, out, default=str, indent=2)
        out.write('\n')


def counts(conn):
    return {n: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(n))).fetchone()['n'] for n in TABLES}


def main():
    assert not (R / 'artifact-family-intent.json').exists(), 'Existing attempt: reconcile only'
    assert json.loads((R / 'eval-bundle-verified.json').read_text())['temporaryRoleRemoved']
    frozen = json.loads((C.ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    item = json.loads(C.S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', C.TARGET]))
    assert item['Id'] == frozen['container']['Id'] and item['Mounts'] == []
    assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    before = C.S.P.M.fingerprint(C.TARGET)
    metadata = C.S.D.metadata(C.TARGET)
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
        lineage = admin.execute('SELECT template_id,revision,content_hash FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s ORDER BY template_id,revision LIMIT 1', SCOPE.key).fetchone()
        assert lineage
        lineage_ref = ExactRevisionRef(resource_type='StageTemplateRevision', resource_id=lineage['template_id'], revision=lineage['revision'], content_hash=lineage['content_hash'])
        record('intent', {'containerId': item['Id'], 'cluster': frozen['cloneIdentity']['cluster'], 'database': DB, 'role': ROLE, 'currentDatabaseTouched': False, 'originalCloneDatabaseWrites': False, 'newQueuedRunOnly': True, 'lineageRef': lineage_ref.model_dump(mode='json', by_alias=True), 'scriptHash': hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest()})
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
            created_role = True
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, privileges in TABLES.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_artifact_' + table), sql.Identifier(table), sql.Identifier(ROLE)))
            for table in C.SOURCE_TABLES:
                assert not admin.execute('SELECT has_table_privilege(%s,%s,%s) AS writable', ('aos_runtime', table, 'INSERT')).fetchone()['writable']
            tasks = AipTaskStore(lambda scope: C.runtime(scope, read_only=False))
            task = tasks.create_task(SCOPE, 'clone:test', 'qyh-artifact-test-task', CreateTaskRequest(type='media', title='电商 栖月汇隔离协议夹具；不执行'))
            plan = tasks.create_plan(SCOPE, 'clone:test', task.id, 'qyh-artifact-test-plan', CreatePlanRevisionRequest(expected_task_version=task.version, steps=[PlanStep(step_key='fixture', title='仅测试元数据，不执行')]))
            planning = tasks.get_task(SCOPE, task.id)
            tasks.approve_plan(SCOPE, 'clone:test', task.id, plan.revision, planning.version, plan.content_hash)
            approved = tasks.get_task(SCOPE, task.id)
            run = tasks.create_run(SCOPE, 'clone:test', task.id, 'qyh-artifact-test-run', CreateTaskRunRequest(plan_revision_id=plan.id, expected_task_version=approved.version))
            assert run.status.value == 'queued'
            family_id = 'qyh-clone-protocol-family'
            fixtures = []
            for revision, role in [(1, 'family_manifest'), (2, 'master'), (3, 'master')]:
                token = f'qyh-isolated-test-only:{family_id}:{revision}:{role}'
                digest = hashlib.sha256(token.encode()).hexdigest()
                artifact_id = tasks.record_artifact(SCOPE, run.id, 'clone:test', 'artifact_family_manifest' if revision == 1 else 'media_asset', {'contentRef': 'memory://' + token, 'contentHash': digest, 'metadata': {'testOnly': True, 'businessDomain': 'ecommerce', 'artifactFamily': {'familyId': family_id, 'familyRevision': revision, 'role': role, 'profile': 'STANDARD', 'platform': 'ecommerce', 'renditionSpec': {'ratio': '9:16', 'codec': 'h264'}, 'lineageRefs': [lineage_ref.model_dump(mode='json', by_alias=True)]}}})
                fixtures.append(ExactArtifactRef(artifact_id=artifact_id, content_hash=digest))
            store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), plan_connect_factory=no_plan, contract_connect_factory=contract)
            body = RegisterArtifactFamilyRequest(family_id=family_id, manifest_artifact=fixtures[0])
            made = store.register_artifact_family(SCOPE, 'clone:test', 'qyh-family-register', body)
            assert store.register_artifact_family(SCOPE, 'clone:test', 'qyh-family-register', body).family_id == family_id
            cases.append('original-family-register-replay')
            for index in [1, 2]:
                attach = AttachArtifactFamilyMemberRequest(artifact_ref=fixtures[index], expected_family_version=made.version, reason='隔离协议夹具，不是生产成果')
                made = store.attach_artifact_family_member(SCOPE, 'clone:test', family_id, f'qyh-family-attach-{index}', attach)
            cases.append('original-two-master-members')
            cases.append(C.expect_error(ProductionContractConflict, lambda: store.attach_artifact_family_member(SCOPE, 'clone:test', family_id, 'qyh-family-stale', attach)))
            group = next(g for g in made.candidate_groups if g.status.value == 'conflict')
            rule = store.register_review_rule_revision(SCOPE, 'clone:test', 'qyh-family-rule', RegisterReviewRuleRevisionRequest(rule_id='qyh-clone-test-rule', revision=1, spec={'testOnly': True, 'businessDomain': 'ecommerce'}))
            policy = ExactRevisionRef(resource_type='TestOnlyPolicyRevision', resource_id='qyh-clone-test-policy', revision=1, content_hash=hashlib.sha256(b'qyh-test-only-policy').hexdigest())
            selection = SelectArtifactFamilyCandidateRequest(selection_key=group.selection_key, expected_family_version=made.version, candidate_refs=group.candidates, selected_ref=fixtures[2], policy_ref=policy, reason='仅候选协议验证，无正式政策授权')
            made = store.select_artifact_family_candidate(SCOPE, 'clone:test', family_id, 'qyh-family-select', selection)
            assert store.select_artifact_family_candidate(SCOPE, 'clone:test', family_id, 'qyh-family-select', selection).version == made.version
            cases.append('original-conflict-selection-replay-test-policy-only')
            cases.append(C.expect_error(ProductionContractIdempotencyConflict, lambda: store.select_artifact_family_candidate(SCOPE, 'clone:test', family_id, 'qyh-family-select', selection.model_copy(update={'reason': 'drift'}))))
            relation_body = CreateArtifactRelationRequest(relation_type='derived_from', from_artifact=fixtures[1], to_artifact=fixtures[2], reason='隔离测试关系')
            relation = store.create_artifact_relation(SCOPE, 'clone:test', 'qyh-family-relation', relation_body)
            cases.append('original-relation-and-rule-register')
            cases.append(C.expect_error(ProductionContractDependencyBlocked, lambda: store.create_artifact_relation(SCOPE, 'clone:test', 'qyh-family-cycle', relation_body.model_copy(update={'from_artifact': fixtures[2], 'to_artifact': fixtures[1]}))))
            cases.append(C.expect_error(ProductionContractNotFound, lambda: store.get_artifact_family(TenantScope('dev-org', 'dev-project'), family_id)))
            admin.execute("CREATE FUNCTION qyh_artifact_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-family-rollback' THEN RAISE EXCEPTION 'QYH_CONTRACT_ROLLBACK'; END IF; RETURN NEW; END $$")
            admin.execute('CREATE TRIGGER qyh_artifact_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_artifact_rollback()')
            saved = counts(admin)
            cases.append(C.expect_error(psycopg.Error, lambda: store.register_review_rule_revision(SCOPE, 'clone:test', 'qyh-family-rollback', RegisterReviewRuleRevisionRequest(rule_id='qyh-clone-failed-rule', revision=1, spec={'testOnly': True})), state='P0001'))
            assert counts(admin) == saved
            assert admin.execute('SELECT status FROM aip_task_run WHERE run_id=%s', (run.id,)).fetchone()['status'] == 'queued'
            assert admin.execute('SELECT count(*) AS n FROM aip_step_run WHERE run_id=%s', (run.id,)).fetchone()['n'] == 0
            record('business-result', {'cases': cases, 'connections': connections, 'familyId': family_id, 'runId': run.id, 'taskId': task.id, 'fixtures': [x.model_dump(mode='json', by_alias=True) for x in fixtures], 'familyVersion': made.version, 'rule': rule.model_dump(mode='json', by_alias=True), 'relation': relation.model_dump(mode='json', by_alias=True), 'formalPolicyVerified': False, 'renderedBusinessArtifacts': False, 'passwordOrOIDCAuthenticated': False, 'queuedRunNoSteps': True})
        except Exception as error:
            record('failure', {'errorType': type(error).__name__, 'sqlstate': getattr(error, 'sqlstate', None), 'completedCases': cases, 'unknownEffectReplayAllowed': False})
            raise
        finally:
            if created_role:
                for table in TABLES:
                    admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_artifact_' + table), sql.Identifier(table)))
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    assert C.S.P.M.fingerprint(C.TARGET) == before
    assert C.S.D.metadata(C.TARGET) == metadata
    record('verified', {'originalClone647DataExact': True, 'allOriginalMetadataExact': True, 'temporaryRoleRemoved': True, 'currentDatabaseTouched': False, 'wholeTaskAccepted': False})
    print(json.dumps({'cases': len(cases), 'connections': len(connections), 'newRunQueuedNoSteps': True, 'currentDatabaseTouched': False}))


if __name__ == '__main__':
    main()
