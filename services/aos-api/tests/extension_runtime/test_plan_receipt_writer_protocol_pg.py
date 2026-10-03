"""Disposable SQL protocol for separate Plan and content issuers.

This does not install a production migration or provision formal credentials.
"""

import ast
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.tenant_scope import TenantScope
from current_configuration_sources_case import _migration, source_case
from test_lifecycle_pg import database


SCOPE = TenantScope('org-org', 'dev-project')
PLAN_OPERATIONS = (
    'responsibility_plan.create', 'responsibility_plan.revise',
    'responsibility_plan.freeze', 'bi_responsibility_plan.prepare',
    'bi_responsibility_plan.rebind', 'bi_responsibility_plan.freeze',
)
CONTRACT_OPERATIONS = (
    'eval_contract.create', 'eval_contract.revise', 'eval_contract.freeze',
    'impact_preview.create', 'impact_preview.revise', 'impact_preview.freeze',
    'stage_template.create', 'stage_template.revise', 'stage_template.freeze',
    'stage_template.compile', 'artifact_relation.create',
    'artifact_family.register', 'artifact_family.member.attach',
    'artifact_family.candidate.select', 'media_gate_profile.register',
    'media_contract_migration.create', 'media_gate_set.assemble',
    'review_rule.register', 'review_issue.create', 'review_issue.resolve',
    'review_issue.return', 'task_brief.create', 'task_brief.revise',
    'task_brief.freeze', 'evidence_bundle.build', 'evidence_bundle.create',
    'evidence_bundle.revoke', 'evidence.revoke',
    'evidence_disclosure.resolve', 'production_context.freeze',
)


@pytest.fixture
def protocol(source_case, database):
    conn, _ = source_case
    _, _, schema = database
    plan_role = 's3owe_plan_' + uuid4().hex[:12]
    content_role = 's3owe_content_' + uuid4().hex[:12]
    contract_role = 's3owg_contract_' + uuid4().hex[:12]
    plan_operation_sql = sql.SQL(',').join(
        sql.Literal(operation) for operation in PLAN_OPERATIONS).as_string(conn)
    contract_operation_sql = sql.SQL(',').join(
        sql.Literal(operation) for operation in CONTRACT_OPERATIONS).as_string(conn)
    conn.execute('RESET ROLE')
    conn.execute('''CREATE TABLE aip_task(
        org_id text NOT NULL, project_id text NOT NULL, task_id text NOT NULL,
        PRIMARY KEY(org_id,project_id,task_id))''')
    _migration(conn, 'w2_001_brief_evidence.py', 's3owe_original_receipt')
    try:
        for role in (plan_role, content_role, contract_role):
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS').format(
                sql.Identifier(role)))
            conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(
                sql.Identifier(schema), sql.Identifier(role)))
        conn.execute('''REVOKE INSERT,UPDATE,DELETE ON aip_responsibility_plan_head
            FROM aos_runtime''')
        conn.execute('''REVOKE INSERT,UPDATE,DELETE ON aip_responsibility_plan_revision
            FROM aos_runtime''')
        conn.execute('''REVOKE INSERT,UPDATE,DELETE ON aip_production_contract_receipt
            FROM aos_runtime''')
        for table, privileges, role in (
            ('aip_responsibility_plan_head', 'SELECT,INSERT,UPDATE', plan_role),
            ('aip_responsibility_plan_revision', 'SELECT,INSERT', plan_role),
            ('aip_production_contract_receipt', 'SELECT,INSERT', plan_role),
            ('aip_production_contract_receipt', 'SELECT,INSERT', content_role),
            ('aip_production_contract_receipt', 'SELECT,INSERT', contract_role),
        ):
            conn.execute(sql.SQL('GRANT {} ON {} TO {}').format(
                sql.SQL(privileges), sql.Identifier(table), sql.Identifier(role)))
        for table, role, suffix in (
            ('aip_responsibility_plan_head', plan_role, 'head'),
            ('aip_responsibility_plan_revision', plan_role, 'revision'),
            ('aip_production_contract_receipt', plan_role, 'plan_receipt'),
            ('aip_production_contract_receipt', content_role, 'content_receipt'),
            ('aip_production_contract_receipt', contract_role, 'contract_receipt'),
        ):
            conn.execute(sql.SQL('''CREATE POLICY {} ON {} TO {}
                USING(org_id=current_setting('aos.org_id',true)
                  AND project_id=current_setting('aos.project_id',true))
                WITH CHECK(org_id=current_setting('aos.org_id',true)
                  AND project_id=current_setting('aos.project_id',true))''').format(
                    sql.Identifier('s3owe_' + suffix), sql.Identifier(table),
                    sql.Identifier(role)))
        conn.execute(f'''CREATE FUNCTION s3owe_guard() RETURNS trigger
            LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
            DECLARE tenant_org text; tenant_project text; plan_id text; issuer text;
            BEGIN
              IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'PLAN_DELETE_FORBIDDEN' USING ERRCODE='42501';
              END IF;
              tenant_org:=NEW.org_id; tenant_project:=NEW.project_id;
              IF TG_TABLE_NAME='aip_production_contract_receipt' THEN
                IF NEW.operation IN ({plan_operation_sql}) THEN
                  issuer:='{plan_role}';
                ELSIF NEW.operation='content_draft.register' THEN
                  issuer:='{content_role}';
                ELSIF NEW.operation IN ({contract_operation_sql}) THEN
                  issuer:='{contract_role}';
                ELSE
                  RAISE EXCEPTION 'RECEIPT_OPERATION_UNMAPPED' USING ERRCODE='42501';
                END IF;
              ELSE
                issuer:='{plan_role}';
                plan_id:=NEW.plan_id;
              END IF;
              IF session_user<>issuer OR current_user<>issuer
                 OR tenant_org IS DISTINCT FROM current_setting('aos.org_id',true)
                 OR tenant_project IS DISTINCT FROM current_setting('aos.project_id',true)
                 OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user
                   AND (rolsuper OR rolbypassrls OR rolinherit OR NOT rolcanlogin)) THEN
                RAISE EXCEPTION 'SEPARATE_ISSUER_REQUIRED' USING ERRCODE='42501';
              END IF;
              IF plan_id IS NOT NULL THEN
                PERFORM pg_advisory_xact_lock(hashtextextended(
                  'aos-plan:' || jsonb_build_array(tenant_org,tenant_project,plan_id)::text,0));
              END IF;
              RETURN NEW;
            END $$''')
        conn.execute('''CREATE TRIGGER s3owe_head BEFORE INSERT OR UPDATE OR DELETE
            ON aip_responsibility_plan_head FOR EACH ROW EXECUTE FUNCTION s3owe_guard()''')
        conn.execute('''CREATE TRIGGER s3owe_revision BEFORE INSERT
            ON aip_responsibility_plan_revision FOR EACH ROW EXECUTE FUNCTION s3owe_guard()''')
        conn.execute('''CREATE TRIGGER s3owe_receipt BEFORE INSERT
            ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION s3owe_guard()''')
        yield conn, schema, plan_role, content_role, contract_role
    finally:
        conn.execute('RESET SESSION AUTHORIZATION')
        conn.execute('RESET ROLE')
        for role in (contract_role, content_role, plan_role):
            conn.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            conn.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
        conn.execute('SET ROLE aos_runtime')


@contextmanager
def _identity(conn, role):
    conn.execute('RESET ROLE')
    conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(role)))
    try:
        conn.execute("SELECT set_config('aos.org_id',%s,false)", (SCOPE.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,false)", (SCOPE.project_id,))
        identity = conn.execute('SELECT session_user,current_user').fetchone()
        assert identity == (role, role)
        yield conn
    finally:
        conn.execute('RESET SESSION AUTHORIZATION')
        conn.execute('SET ROLE aos_runtime')


def test_separate_issuers_keep_runtime_readonly_and_content_receipt_writable(protocol):
    conn, _, plan_role, content_role, _ = protocol
    for table in ('aip_responsibility_plan_head', 'aip_responsibility_plan_revision',
                  'aip_production_contract_receipt'):
        assert conn.execute('SELECT has_table_privilege(%s,%s,%s)',
                            ('aos_runtime', table, 'SELECT')).fetchone()[0]
        for privilege in ('INSERT', 'UPDATE', 'DELETE'):
            assert not conn.execute('SELECT has_table_privilege(%s,%s,%s)',
                                    ('aos_runtime', table, privilege)).fetchone()[0]
    with _identity(conn, 'aos_runtime'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute('''INSERT INTO aip_responsibility_plan_head
                (org_id,project_id,plan_id,current_revision,version)
                VALUES(%s,%s,'forged',1,1)''', SCOPE.key)
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            _receipt(conn, 'responsibility_plan.create', 'forged')
    with _identity(conn, content_role):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            _receipt(conn, 'responsibility_plan.create', 'content-forgery')
        with conn.transaction():
            _content_receipt(conn, 'content-ok')
    with _identity(conn, plan_role):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            _content_receipt(conn, 'plan-forgery')
        with conn.transaction():
            conn.execute('''INSERT INTO aip_responsibility_plan_head
                (org_id,project_id,plan_id,current_revision,version)
                VALUES(%s,%s,'issued',1,1)''', SCOPE.key)
            _receipt(conn, 'responsibility_plan.create', 'issued')
    with _identity(conn, 'aos_runtime'):
        assert conn.execute('''SELECT count(*) FROM aip_production_contract_receipt
            WHERE org_id=%s AND project_id=%s''', SCOPE.key).fetchone()[0] == 2
        assert conn.execute('''SELECT version FROM aip_responsibility_plan_head
            WHERE org_id=%s AND project_id=%s AND plan_id='issued' ''',
            SCOPE.key).fetchone()[0] == 1


def test_plan_revision_and_head_mutations_require_exact_issuer_and_tenant(protocol):
    conn, _, plan_role, content_role, _ = protocol
    with _identity(conn, 'aos_runtime'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            _clone_revision(conn, 'unissued-revision')
    with _identity(conn, content_role):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            _clone_revision(conn, 'content-forgery')
    with _identity(conn, plan_role):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute('''INSERT INTO aip_responsibility_plan_head
                (org_id,project_id,plan_id,current_revision,version)
                VALUES('dev-org','dev-project','cross-tenant',1,1)''')
        with conn.transaction():
            conn.execute('''INSERT INTO aip_responsibility_plan_head
                (org_id,project_id,plan_id,current_revision,version)
                VALUES(%s,%s,'issued-revision',1,1)''', SCOPE.key)
            _clone_revision(conn, 'issued-revision')
            conn.execute('''UPDATE aip_responsibility_plan_head SET version=version+1
                WHERE org_id=%s AND project_id=%s AND plan_id='issued-revision' ''', SCOPE.key)
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute('''DELETE FROM aip_responsibility_plan_head
                WHERE org_id=%s AND project_id=%s AND plan_id='issued-revision' ''', SCOPE.key)
    with _identity(conn, 'aos_runtime'):
        assert conn.execute('''SELECT version FROM aip_responsibility_plan_head
            WHERE org_id=%s AND project_id=%s AND plan_id='issued-revision' ''',
            SCOPE.key).fetchone()[0] == 2
        assert conn.execute('''SELECT count(*) FROM aip_responsibility_plan_revision
            WHERE org_id=%s AND project_id=%s AND plan_id='issued-revision' ''',
            SCOPE.key).fetchone()[0] == 1


def test_select_only_reader_stabilizes_original_plan_against_issuer_update(protocol):
    conn, schema, plan_role, _, _ = protocol
    with psycopg.connect(host='127.0.0.1', port=18432, user='postgres',
                         dbname='postgres', autocommit=True) as writer:
        writer.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        writer.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(plan_role)))
        writer.execute("SELECT set_config('aos.org_id',%s,false)", (SCOPE.org_id,))
        writer.execute("SELECT set_config('aos.project_id',%s,false)", (SCOPE.project_id,))
        writer.execute("SET statement_timeout='250ms'")
        with _identity(conn, 'aos_runtime'):
            with conn.transaction():
                conn.execute('''SELECT pg_advisory_xact_lock(hashtextextended(
                    'aos-plan:' || jsonb_build_array(%s::text,%s::text,%s::text)::text,0))''',
                    (*SCOPE.key, 'qyh-runtime-roles'))
                assert conn.execute('''SELECT version FROM aip_responsibility_plan_head
                    WHERE org_id=%s AND project_id=%s AND plan_id='qyh-runtime-roles' ''',
                    SCOPE.key).fetchone()[0] == 1
                with pytest.raises(psycopg.errors.QueryCanceled):
                    writer.execute('''UPDATE aip_responsibility_plan_head
                        SET version=version+1 WHERE org_id=%s AND project_id=%s
                        AND plan_id='qyh-runtime-roles' ''', SCOPE.key)
        writer.execute('''UPDATE aip_responsibility_plan_head SET version=version+1
            WHERE org_id=%s AND project_id=%s AND plan_id='qyh-runtime-roles' ''', SCOPE.key)
    assert conn.execute('''SELECT version FROM aip_responsibility_plan_head
        WHERE org_id=%s AND project_id=%s AND plan_id='qyh-runtime-roles' ''',
        SCOPE.key).fetchone()[0] == 2


def test_fixed_contract_operations_match_original_store():
    path = Path(__file__).resolve().parents[2] / 'aos_api/aip_production_contract_store.py'
    tree = ast.parse(path.read_text())
    operations = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == '_receipt'):
            operation = node.args[2]
            if isinstance(operation, ast.Constant) and isinstance(operation.value, str):
                operations.append(operation.value)
    assert len(operations) == len(CONTRACT_OPERATIONS) == 30
    assert set(operations) == set(CONTRACT_OPERATIONS)


def test_original_fixed_contract_operation_has_separate_issuer(protocol):
    conn, _, _, _, contract_role = protocol
    with _identity(conn, contract_role):
        with conn.transaction():
            _receipt(conn, 'eval_contract.create', 'contract-issued',
                     result={'resourceType': 'EvalContractRevision',
                             'resourceId': 'eval-contract-isolated',
                             'revision': 1, 'contentHash': 'b' * 64})
    with _identity(conn, 'aos_runtime'):
        assert conn.execute('''SELECT count(*) FROM aip_production_contract_receipt
            WHERE org_id=%s AND project_id=%s AND operation='eval_contract.create' ''',
            SCOPE.key).fetchone()[0] == 1


def test_all_mapped_receipt_operations_have_one_exact_issuer(protocol):
    conn, _, plan_role, content_role, contract_role = protocol
    assert len(set(PLAN_OPERATIONS + CONTRACT_OPERATIONS + ('content_draft.register',))) == 37
    for role, operations in (
        (plan_role, PLAN_OPERATIONS),
        (contract_role, CONTRACT_OPERATIONS),
    ):
        with _identity(conn, role):
            for operation in operations:
                with conn.transaction():
                    _receipt(conn, operation, role + '-' + operation)
    with _identity(conn, content_role):
        with conn.transaction():
            _content_receipt(conn, 'all-operations-content')
    with _identity(conn, 'aos_runtime'):
        assert conn.execute('''SELECT count(*) FROM aip_production_contract_receipt
            WHERE org_id=%s AND project_id=%s''', SCOPE.key).fetchone()[0] == 37
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            _receipt(conn, 'eval_contract.create', 'runtime-forgery')
    for role, forbidden in (
        (plan_role, 'eval_contract.create'),
        (plan_role, 'responsibility_plan.unknown'),
        (content_role, 'eval_contract.create'),
        (contract_role, 'responsibility_plan.create'),
        (contract_role, 'content_draft.register'),
        (contract_role, 'eval_contract.unknown'),
    ):
        with _identity(conn, role):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                _receipt(conn, forbidden, role + '-' + forbidden)
    with _identity(conn, contract_role):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute('''INSERT INTO aip_production_contract_receipt
                (org_id,project_id,receipt_id,operation,idempotency_key,
                 request_hash,result_ref,created_by)
                VALUES('dev-org','dev-project','cross-tenant-contract',
                  'eval_contract.create','cross-tenant-key',%s,'{}'::jsonb,'isolated')''',
                ('a' * 64,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute('''INSERT INTO aip_responsibility_plan_head
                (org_id,project_id,plan_id,current_revision,version)
                VALUES(%s,%s,'contract-cannot-issue-plan',1,1)''', SCOPE.key)


def _receipt(conn, operation, key, *, result=None):
    store = object.__new__(AipProductionContractStore)
    store._receipt(conn, SCOPE, operation, key, 'a' * 64,
                   result or {'resourceType': 'ResponsibilityPlanRevision',
                              'resourceId': 'issued', 'revision': 1,
                              'contentHash': 'b' * 64}, 'isolated')


def _content_receipt(conn, key):
    # The shared-table INSERT shape used by AipContentDraftStore.register.
    conn.execute('''INSERT INTO aip_production_contract_receipt
        (org_id,project_id,receipt_id,operation,idempotency_key,
         request_hash,result_ref,created_by,created_at)
        VALUES(%s,%s,%s,'content_draft.register',%s,%s,%s::jsonb,'isolated',now())''',
        (*SCOPE.key, 'content-receipt-' + key, key, 'a' * 64, '{}'))


def _clone_revision(conn, plan_id):
    conn.execute('''INSERT INTO aip_responsibility_plan_revision
        (org_id,project_id,plan_id,revision,profile,template_ref,slots,merge_decisions,
         profile_recommendation_ref,profile_confirmation_id,merge_policy_ref,
         merge_decision_receipt_ids,content_hash,lifecycle,created_by,created_at)
        SELECT org_id,project_id,%s,revision,profile,template_ref,slots,merge_decisions,
         profile_recommendation_ref,profile_confirmation_id,merge_policy_ref,
         merge_decision_receipt_ids,content_hash,lifecycle,created_by,created_at
        FROM aip_responsibility_plan_revision
        WHERE org_id=%s AND project_id=%s AND plan_id='qyh-runtime-roles' AND revision=1''',
        (plan_id, *SCOPE.key))
