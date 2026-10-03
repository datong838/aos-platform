"""Original Plan Store under a disposable, nonowner signed-source issuer."""

import secrets
from contextlib import nullcontext

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractConflict,
    ProductionContractDependencyBlocked, ProductionContractIdempotencyConflict,
)
from aos_api.aip_production_contracts import ReviseResponsibilityPlanRequest
from aos_api.ecommerce_business_investigation_aip_authority import (
    build_responsibility_plan_request,
)
from aos_api.aip_responsibility_template_authority import ApprovedBIPreparationResolver
from aos_api.aip_business_investigation_responsibility_template import BI_ROLE_BLUEPRINTS
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope('org-org', 'dev-project')


def assert_original_plan_store_with_restricted_login(selected_template, signed, trust):
    dbname = conninfo_to_dict(get_dsn())['dbname']
    assert dbname.startswith('aos_test_') and dbname.endswith('_ti4_test')
    issuer = 's3owi_plan_' + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    resolver = ApprovedBIPreparationResolver(
        connect_factory=connect, registry_connect_factory=connect,
        release_root=signed['signed_tree'], trust_roots=trust,
        source_alias=signed['source_alias'],
    )
    request = build_responsibility_plan_request(
        {instance_id: 1 for _, _, instance_id, _, _ in BI_ROLE_BLUEPRINTS},
        template_ref=selected_template.template_ref,
    )
    assert resolver.resolve(SCOPE, selected_template.template_ref) is True
    assert resolver.resolve(TenantScope('dev-org', 'dev-project'),
                            selected_template.template_ref) is False
    assert resolver.resolve(SCOPE, selected_template.template_ref.model_copy(
        update={'content_hash': '0' * 64})) is False
    with psycopg.connect(get_dsn(), autocommit=True) as admin:
        admin.execute(sql.SQL('''CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
            PASSWORD {}''').format(sql.Identifier(issuer), sql.Literal(password)))
        try:
            for table, privileges in (
                ('aip_responsibility_plan_head', 'SELECT,INSERT,UPDATE'),
                ('aip_responsibility_plan_revision', 'SELECT,INSERT'),
                ('aip_production_contract_receipt', 'SELECT,INSERT'),
                ('aip_agent_instance', 'SELECT'),
                ('aip_skill_binding', 'SELECT'),
                ('aip_skill_template_revision', 'SELECT'),
                ('aip_agent_registry_receipt', 'SELECT'),
            ):
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(
                    sql.SQL(privileges), sql.Identifier(table), sql.Identifier(issuer)))
            for table in (
                'aip_responsibility_plan_head', 'aip_responsibility_plan_revision',
                'aip_production_contract_receipt', 'aip_agent_instance',
                'aip_skill_binding', 'aip_agent_registry_receipt',
            ):
                admin.execute(sql.SQL('''CREATE POLICY {} ON {} TO {}
                    USING(org_id=current_setting('aos.org_id',true)
                      AND project_id=current_setting('aos.project_id',true))
                    WITH CHECK(org_id=current_setting('aos.org_id',true)
                      AND project_id=current_setting('aos.project_id',true))''').format(
                          sql.Identifier('s3owi_' + table), sql.Identifier(table),
                          sql.Identifier(issuer)))
            admin.execute(sql.SQL('''CREATE FUNCTION s3owi_plan_receipt_guard() RETURNS trigger
                LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
                BEGIN
                  IF session_user<>{} OR current_user<>{}
                     OR NEW.operation NOT IN ('responsibility_plan.create',
                                             'responsibility_plan.revise',
                                             'responsibility_plan.freeze')
                     OR NEW.result_ref->>'resourceType'<>'ResponsibilityPlanRevision'
                     OR NOT EXISTS (
                       SELECT 1 FROM aip_responsibility_plan_head h
                       JOIN aip_responsibility_plan_revision r
                         ON r.org_id=h.org_id AND r.project_id=h.project_id
                        AND r.plan_id=h.plan_id AND r.revision=h.current_revision
                       WHERE h.org_id=NEW.org_id AND h.project_id=NEW.project_id
                         AND h.plan_id=NEW.result_ref->>'resourceId'
                         AND r.revision=(NEW.result_ref->>'revision')::bigint
                         AND r.content_hash=NEW.result_ref->>'contentHash') THEN
                    RAISE EXCEPTION 'PLAN_RECEIPT_UNPAIRED' USING ERRCODE='42501';
                  END IF;
                  IF NEW.idempotency_key='s3owi-forced-rollback' THEN
                    RAISE EXCEPTION 'PLAN_FORCED_ROLLBACK';
                  END IF;
                  RETURN NEW;
                END $$''').format(sql.Literal(issuer), sql.Literal(issuer)))
            admin.execute('''CREATE TRIGGER s3owi_plan_receipt_guard BEFORE INSERT
                ON aip_production_contract_receipt FOR EACH ROW
                EXECUTE FUNCTION s3owi_plan_receipt_guard()''')
            parts = conninfo_to_dict(get_dsn())
            with psycopg.connect(host=parts['host'], port=parts['port'], dbname=dbname,
                                 user=issuer, password=password, row_factory=dict_row) as writer:
                writer.execute("SELECT set_config('aos.org_id',%s,false)", (SCOPE.org_id,))
                writer.execute("SELECT set_config('aos.project_id',%s,false)", (SCOPE.project_id,))
                writer.commit()
                assert writer.execute('SELECT session_user,current_user').fetchone() == {
                    'session_user': issuer, 'current_user': issuer}
                store = AipProductionContractStore(
                    connect_factory=lambda _: nullcontext(writer),
                    responsibility_template_resolver=resolver.resolve,
                )
                issued = store.create_responsibility_plan(
                    SCOPE, 'test-author', 's3owi-original-create', request)
                assert issued.readiness.value == 'blocked'
                assert store.create_responsibility_plan(
                    SCOPE, 'test-author', 's3owi-original-create', request).plan_id == issued.plan_id
                with pytest.raises(ProductionContractIdempotencyConflict):
                    store.create_responsibility_plan(
                        SCOPE, 'test-author', 's3owi-original-create',
                        request.model_copy(update={'profile': 'other-isolated-profile'}))
                row = writer.execute('''SELECT h.current_revision,r.content_hash,p.result_ref
                    FROM aip_responsibility_plan_head h
                    JOIN aip_responsibility_plan_revision r USING(org_id,project_id,plan_id)
                    JOIN aip_production_contract_receipt p
                      ON p.org_id=h.org_id AND p.project_id=h.project_id
                     AND p.operation='responsibility_plan.create'
                     AND p.idempotency_key='s3owi-original-create'
                    WHERE h.org_id=%s AND h.project_id=%s AND h.plan_id=%s''',
                    (*SCOPE.key, issued.plan_id)).fetchone()
                assert row['current_revision'] == 1
                assert row['result_ref']['resourceId'] == issued.plan_id
                assert row['result_ref']['contentHash'] == row['content_hash']
                revised_request = ReviseResponsibilityPlanRequest(
                    **request.model_dump(mode='json', by_alias=True),
                    expectedVersion=issued.version,
                )
                revised = store.revise_responsibility_plan(
                    SCOPE, 'test-author', issued.plan_id, 's3owi-original-revise',
                    revised_request)
                assert revised.revision == 2 and revised.version == 2
                assert store.revise_responsibility_plan(
                    SCOPE, 'test-author', issued.plan_id, 's3owi-original-revise',
                    revised_request).revision == 2
                with pytest.raises(ProductionContractConflict,
                                   match='stale responsibility plan version'):
                    store.revise_responsibility_plan(
                        SCOPE, 'test-author', issued.plan_id, 's3owi-stale-revise',
                        revised_request)
                with pytest.raises(ProductionContractDependencyBlocked,
                                   match='RESPONSIBILITY_PLAN_NOT_READY'):
                    store.freeze_responsibility_plan(
                        SCOPE, 'test-author', issued.plan_id, revised.version,
                        's3owi-closed-freeze')
                assert writer.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                    WHERE operation='responsibility_plan.freeze'
                      AND idempotency_key='s3owi-closed-freeze' ''').fetchone()['n'] == 0
                before = writer.execute('SELECT count(*) AS n FROM aip_responsibility_plan_head').fetchone()['n']
                revisions_before = writer.execute(
                    'SELECT count(*) AS n FROM aip_responsibility_plan_revision').fetchone()['n']
                with pytest.raises(psycopg.Error, match='PLAN_FORCED_ROLLBACK'):
                    store.create_responsibility_plan(
                        SCOPE, 'test-author', 's3owi-forced-rollback', request)
                writer.rollback()
                assert writer.execute('SELECT count(*) AS n FROM aip_responsibility_plan_head').fetchone()['n'] == before
                assert writer.execute(
                    'SELECT count(*) AS n FROM aip_responsibility_plan_revision').fetchone()['n'] == revisions_before
                assert writer.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                    WHERE idempotency_key='s3owi-forced-rollback' ''').fetchone()['n'] == 0
                with pytest.raises(psycopg.errors.InsufficientPrivilege), writer.transaction():
                    writer.execute('''INSERT INTO aip_responsibility_plan_head
                        (org_id,project_id,plan_id,current_revision,version)
                        VALUES('dev-org','dev-project','s3owi-cross-tenant',1,1)''')
                with pytest.raises(psycopg.errors.InsufficientPrivilege,
                                   match='PLAN_RECEIPT_UNPAIRED'), writer.transaction():
                    writer.execute('''INSERT INTO aip_production_contract_receipt
                        (org_id,project_id,receipt_id,operation,idempotency_key,
                         request_hash,result_ref,created_by)
                        VALUES(%s,%s,'s3owi-unpaired','responsibility_plan.create',
                          's3owi-unpaired',%s,%s::jsonb,'test-author')''',
                        (*SCOPE.key, 'a' * 64,
                         '{"resourceType":"ResponsibilityPlanRevision",'
                         '"resourceId":"missing","revision":1,"contentHash":"' + 'b' * 64 + '"}'))
        finally:
            admin.execute('''DROP TRIGGER IF EXISTS s3owi_plan_receipt_guard
                ON aip_production_contract_receipt''')
            admin.execute('DROP FUNCTION IF EXISTS s3owi_plan_receipt_guard()')
            admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(issuer)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(issuer)))
