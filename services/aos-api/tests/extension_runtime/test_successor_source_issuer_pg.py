"""Actual successor COMMIT in a disposable current full-schema database."""
import json
import os
import secrets
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest

from aos_api import aip_source_issuer_wiring as wiring
from aos_api.aip_production_contracts import AssigneeRef, ExactRevisionRef
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.aip_responsibility_assignment import CreateResponsibilitySuccessorRequest
from aos_api.aip_responsibility_assignment_store import (
    AipResponsibilityAssignmentStore, ResponsibilityAssignmentConflict,
    ResponsibilityAssignmentNotFound,
)
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(os.getenv('AOS_SOURCE_ISSUER_PG_TEST') != '1', reason='isolated issuer opt-in required')
SCOPE = TenantScope('org-org', 'dev-project')
ROLE = 'aos_bi_plan_issuer'


def _policy(admin, table):
    admin.execute(sql.SQL("CREATE POLICY isolated_successor_source ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier(table), sql.Identifier(ROLE)))


def _dependencies(admin):
    for table, privileges in [('aip_responsibility_successor', 'SELECT,INSERT'), ('aip_assignee_resolution_receipt', 'SELECT'), ('aip_task_run', 'SELECT')]:
        admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
        _policy(admin, table)


@pytest.fixture
def successor_case(tmp_path, monkeypatch):
    dsn = get_dsn()
    parts = conninfo_to_dict(dsn)
    database = parts['dbname']
    assert database.startswith('aos_test_') and database.endswith('_ti4_test')
    assert (parts['host'], int(parts['port']), parts['user']) == ('127.0.0.1', 18431, 'aos_app')
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.execute('SELECT version_num FROM alembic_version').fetchone()[0] == 'a0v_161'
        assert admin.execute('SELECT count(*) FROM pg_roles WHERE rolname=%s', (ROLE,)).fetchone()[0] == 0
        admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated successor') ON CONFLICT DO NOTHING")
        suffix = uuid4().hex[:12]
        task_id, plan_id, resolution_id = ('isolated-task-' + suffix, 'isolated-plan-' + suffix, 'isolated-resolution-' + suffix)
        admin.execute("INSERT INTO aip_task(org_id,project_id,task_id,task_type,title,status,idempotency_key,request_hash,created_by) VALUES('org-org','dev-project',%s,'isolated','isolated successor','pending',%s,'seed','isolated')", (task_id, 'isolated-seed-' + suffix))
        payload = {'profile': 'STANDARD', 'templateRef': {'resourceType': 'ResponsibilityTemplateRevision', 'resourceId': 'isolated-template', 'revision': 1, 'contentHash': '1' * 64},
                   'slots': [{'slotId': 'operator', 'responsibilityType': 'execution', 'requiredCapabilityIds': ['isolated.execute'], 'inputSchemaRef': {'resourceType': 'Schema', 'resourceId': 'isolated-in'}, 'outputSchemaRef': {'resourceType': 'Schema', 'resourceId': 'isolated-out'}, 'gateRefs': [], 'returnStage': 'execute', 'assignee': {'kind': 'human_principal', 'resourceId': 'isolated-old', 'version': 1}}], 'mergeDecisions': []}
        digest = canonical_hash(payload)
        admin.execute("INSERT INTO aip_responsibility_plan_head(org_id,project_id,plan_id,current_revision,version) VALUES('org-org','dev-project',%s,1,1)", (plan_id,))
        admin.execute("INSERT INTO aip_responsibility_plan_revision(org_id,project_id,plan_id,revision,profile,template_ref,slots,merge_decisions,content_hash,lifecycle,created_by) VALUES('org-org','dev-project',%s,1,%s,%s::jsonb,%s::jsonb,'[]',%s,'frozen','isolated')", (plan_id, payload['profile'], json.dumps(payload['templateRef']), json.dumps(payload['slots']), digest))
        admin.execute("INSERT INTO aip_assignee_resolution_receipt(org_id,project_id,receipt_id,subject_id,kind,resource_id,version,status,actor,content_hash) VALUES('org-org','dev-project',%s,'isolated-new','human_principal','isolated-new',1,'resolved','isolated',%s)", (resolution_id, '2' * 64))
        password = secrets.token_urlsafe(24)
        admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}').format(sql.Identifier(ROLE), sql.Literal(password)))
        private = tmp_path / 'private'
        private.mkdir(mode=0o700)
        passfile = private / 'issuer.pgpass'
        passfile.write_text(f'127.0.0.1:18431:{database}:{ROLE}:{password}' + chr(10))
        passfile.chmod(0o600)
        config = private / 'issuer.json'
        config.write_text(json.dumps({'schemaVersion': 'aos.source-issuer-database/v1', 'purpose': 'plan', 'host': '127.0.0.1', 'port': 18431, 'database': database, 'passfile': str(passfile)}))
        config.chmod(0o600)
        monkeypatch.setenv('AOS_PLAN_SOURCE_ISSUER_CONFIG', str(config))
        try:
            for table, privileges in [('aip_responsibility_plan_head', 'SELECT,INSERT,UPDATE'), ('aip_responsibility_plan_revision', 'SELECT,INSERT'), ('aip_production_contract_receipt', 'SELECT,INSERT')]:
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(ROLE)))
                _policy(admin, table)
            factory = wiring.configured_source_issuer_factory('plan')
            body = CreateResponsibilitySuccessorRequest(task_id=task_id, source_plan_ref=ExactRevisionRef(resource_type='ResponsibilityPlanRevision', resource_id=plan_id, revision=1, content_hash=digest), expected_source_version=1, slot_id='operator', target_assignee=AssigneeRef(kind='human_principal', resource_id='isolated-new', version=1), resolution_receipt_id=resolution_id, reason_code='OPERATOR_REASSIGNED')
            yield admin, factory, body
        finally:
            admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))


def test_original_successor_commits_and_replays_with_minimal_source_issuer(successor_case):
    admin, factory, body = successor_case
    _dependencies(admin)
    store = AipResponsibilityAssignmentStore(plan_connect_factory=factory)
    receipt = store.create_successor(SCOPE, body, actor='isolated', idempotency_key='isolated-successor-create')
    assert store.create_successor(SCOPE, body, actor='isolated', idempotency_key='isolated-successor-create') == receipt
    with pytest.raises(ResponsibilityAssignmentConflict):
        store.create_successor(SCOPE, body.model_copy(update={'reason_code': 'OTHER_ISOLATED_REASON'}),
                               actor='isolated', idempotency_key='isolated-successor-create')
    row = admin.execute('SELECT current_revision,version FROM aip_responsibility_plan_head WHERE org_id=%s AND project_id=%s AND plan_id=%s', (*SCOPE.key, receipt.successor_plan_ref.resource_id)).fetchone()
    assert row == (1, 1)
    assert admin.execute('SELECT count(*) FROM aip_responsibility_successor WHERE org_id=%s AND project_id=%s AND successor_id=%s', (*SCOPE.key, receipt.successor_id)).fetchone()[0] == 1


def test_missing_successor_dependency_rejects_without_plan_changes(successor_case):
    admin, factory, body = successor_case
    before = _counts(admin)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        AipResponsibilityAssignmentStore(plan_connect_factory=factory).create_successor(
            SCOPE, body, actor='isolated', idempotency_key='isolated-missing-dependency')
    assert _counts(admin) == before


def test_late_successor_insert_failure_rolls_back_both_plan_tables(successor_case):
    admin, factory, body = successor_case
    _dependencies(admin)
    before = _counts(admin)
    admin.execute("""CREATE FUNCTION isolated_late_successor_failure() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'ISOLATED_LATE_FAILURE'; END $$""")
    admin.execute("""CREATE TRIGGER isolated_late_successor_failure BEFORE INSERT
        ON aip_responsibility_successor FOR EACH ROW
        EXECUTE FUNCTION isolated_late_successor_failure()""")
    with pytest.raises(psycopg.Error, match='ISOLATED_LATE_FAILURE'):
        AipResponsibilityAssignmentStore(plan_connect_factory=factory).create_successor(
            SCOPE, body, actor='isolated', idempotency_key='isolated-late-failure')
    assert _counts(admin) == before


def _counts(admin):
    return tuple(admin.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                 for table in ('aip_responsibility_plan_head', 'aip_responsibility_plan_revision', 'aip_responsibility_successor'))


@pytest.mark.parametrize('wrong_scope', [TenantScope('dev-org', 'dev-project'), TenantScope('org-org', 'other-project')])
def test_original_source_plan_is_invisible_cross_tenant(successor_case, wrong_scope):
    admin, factory, body = successor_case
    _dependencies(admin)
    before = _counts(admin)
    with pytest.raises(ResponsibilityAssignmentNotFound):
        AipResponsibilityAssignmentStore(plan_connect_factory=factory).create_successor(
            wrong_scope, body, actor='isolated', idempotency_key='isolated-cross-tenant')
    assert _counts(admin) == before
