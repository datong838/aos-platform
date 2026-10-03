"""Disposable full-schema proof for Tool receipt operation/session isolation."""

import json
import secrets

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from aos_api.db import get_dsn


def test_tool_receipt_requires_independent_login_and_pair_in_one_transaction():
    dsn = get_dsn()
    dbname = conninfo_to_dict(dsn)["dbname"]
    assert dbname.startswith("aos_test_") and dbname.endswith("_ti4_test")
    issuer = "s3owaob12_issuer_" + secrets.token_hex(4)
    runtime = "s3owaob12_runtime_" + secrets.token_hex(4)
    passwords = {name: secrets.token_urlsafe(24) for name in (issuer, runtime)}
    with psycopg.connect(dsn, autocommit=True) as owner:
        owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','formal') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO twa_workspace(org_id,project_id,name) "
                      "VALUES('org-org','dev-project','formal') ON CONFLICT DO NOTHING")
        for name, password in passwords.items():
            owner.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                          .format(sql.Identifier(name), sql.Literal(password)))
        try:
            for name in (issuer, runtime):
                owner.execute(sql.SQL("GRANT SELECT,INSERT ON aip_agent_registry_receipt TO {}")
                              .format(sql.Identifier(name)))
                owner.execute(sql.SQL("CREATE POLICY {} ON aip_agent_registry_receipt TO {} "
                    "USING(org_id=current_setting('aos.org_id',true) AND "
                    "project_id=current_setting('aos.project_id',true)) "
                    "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                    "project_id=current_setting('aos.project_id',true))")
                    .format(sql.Identifier(name + "_receipt"), sql.Identifier(name)))
            owner.execute(sql.SQL("GRANT SELECT,INSERT ON aip_tool_binding TO {}")
                          .format(sql.Identifier(issuer)))
            owner.execute(sql.SQL("CREATE POLICY {} ON aip_tool_binding TO {} "
                "USING(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true))")
                .format(sql.Identifier(issuer + "_binding"), sql.Identifier(issuer)))
            owner.execute(sql.SQL("""CREATE FUNCTION public.s3owaob12_receipt_guard()
                RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
                SET search_path=pg_catalog AS $$
                BEGIN
                  IF NEW.operation='tool_binding.upsert' THEN
                    IF session_user<>{} OR NEW.status<>'applied'
                       OR NEW.result_ref->>'resourceType'<>'ToolBinding'
                       OR NOT EXISTS (
                         SELECT 1 FROM public.aip_tool_binding b
                         WHERE b.org_id=NEW.org_id AND b.project_id=NEW.project_id
                           AND b.binding_id=NEW.result_ref->>'resourceId'
                           AND b.version::text=NEW.result_ref->>'revision'
                           AND b.xmin::text=pg_current_xact_id()::text) THEN
                      RAISE EXCEPTION 'TOOL_RECEIPT_UNPAIRED'
                        USING ERRCODE='42501';
                    END IF;
                  ELSIF session_user={} THEN
                    RAISE EXCEPTION 'TOOL_ISSUER_OPERATION_FORBIDDEN'
                      USING ERRCODE='42501';
                  END IF;
                  RETURN NEW;
                END $$""").format(sql.Literal(issuer), sql.Literal(issuer)))
            owner.execute("REVOKE ALL ON FUNCTION public.s3owaob12_receipt_guard() FROM PUBLIC")
            owner.execute("""CREATE TRIGGER s3owaob12_receipt_guard
                BEFORE INSERT ON aip_agent_registry_receipt FOR EACH ROW
                EXECUTE FUNCTION public.s3owaob12_receipt_guard()""")

            def login(name):
                return psycopg.connect(make_conninfo(dsn, user=name, password=passwords[name]))

            def receipt(conn, operation, key, binding="b12-tool", revision="1"):
                return conn.execute("""INSERT INTO aip_agent_registry_receipt(
                    org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
                    resource_ref,result_ref,status,created_by,created_at)
                    VALUES('org-org','dev-project',%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                           'applied','b12-test',now())""",
                    (key, operation, key, "f" * 64, "{}",
                     json.dumps({"resourceType": "ToolBinding", "resourceId": binding,
                                 "revision": revision})))

            with login(runtime) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                receipt(conn, "agent_instance.create", "b12-normal")
            with login(runtime) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "tool_binding.upsert", "b12-runtime-forgery")
                conn.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(sql.SQL("SET ROLE {}") .format(sql.Identifier(issuer)))
                conn.rollback()
            with login(issuer) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "tool_binding.upsert", "b12-unpaired")
                conn.rollback()
            with login(issuer) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "agent_instance.create", "b12-issuer-other")
                conn.rollback()
            with login(issuer) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                conn.execute("""INSERT INTO aip_tool_binding(
                    org_id,project_id,binding_id,tool_id,version,agent_instance_id,status)
                    VALUES('org-org','dev-project','b12-prior','test-only-tool',1,
                           'test-only-agent','disabled')""")
            with login(issuer) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "tool_binding.upsert", "b12-late-receipt", "b12-prior")
                conn.rollback()
            owner.execute(sql.SQL("""CREATE FUNCTION public.s3owaob12_binding_guard()
                RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
                SET search_path=pg_catalog AS $$
                BEGIN
                  IF session_user<>{} OR NOT EXISTS (
                      SELECT 1 FROM public.aip_agent_registry_receipt r
                       WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
                         AND r.operation='tool_binding.upsert'
                         AND r.result_ref->>'resourceType'='ToolBinding'
                         AND r.result_ref->>'resourceId'=NEW.binding_id
                         AND r.result_ref->>'revision'=NEW.version::text
                         AND r.xmin::text=pg_current_xact_id()::text) THEN
                    RAISE EXCEPTION 'TOOL_BINDING_UNRECEIPTED' USING ERRCODE='42501';
                  END IF;
                  RETURN NEW;
                END $$""").format(sql.Literal(issuer)))
            owner.execute("REVOKE ALL ON FUNCTION public.s3owaob12_binding_guard() FROM PUBLIC")
            owner.execute("""CREATE CONSTRAINT TRIGGER s3owaob12_binding_guard
                AFTER INSERT ON aip_tool_binding DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW EXECUTE FUNCTION public.s3owaob12_binding_guard()""")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                                 "set_config('aos.project_id','dev-project',true)")
                    conn.execute("""INSERT INTO aip_tool_binding(
                        org_id,project_id,binding_id,tool_id,version,agent_instance_id,status)
                        VALUES('org-org','dev-project','b12-no-receipt','test-only-tool',1,
                               'test-only-agent','disabled')""")
            with login(issuer) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                conn.execute("""INSERT INTO aip_tool_binding(
                    org_id,project_id,binding_id,tool_id,version,agent_instance_id,status)
                    VALUES('org-org','dev-project','b12-tool','test-only-tool',1,
                           'test-only-agent','disabled')""")
                pair = conn.execute("SELECT xmin::text,pg_current_xact_id()::text "
                                    "FROM aip_tool_binding WHERE binding_id='b12-tool'").fetchone()
                assert pair[0] == pair[1], pair
                receipt(conn, "tool_binding.upsert", "b12-paired")
            with login(issuer) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "tool_binding.upsert", "b12-wrong-version",
                            revision="2")
                conn.rollback()
                conn.execute("SELECT set_config('aos.org_id','dev-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "tool_binding.upsert", "b12-wrong-tenant")
                conn.rollback()
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "tool_binding.upsert", "b12-paired")
                conn.rollback()
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                conn.execute("""INSERT INTO aip_tool_binding(
                    org_id,project_id,binding_id,tool_id,version,agent_instance_id,status)
                    VALUES('org-org','dev-project','b12-rollback','test-only-tool',1,
                           'test-only-agent','disabled')""")
                receipt(conn, "tool_binding.upsert", "b12-rollback", "b12-rollback")
                conn.rollback()
            assert owner.execute("SELECT count(*) FROM aip_agent_registry_receipt "
                                 "WHERE org_id='org-org' AND project_id='dev-project' "
                                 "AND idempotency_key LIKE 'b12-%'").fetchone()[0] == 2
            assert owner.execute("SELECT count(*) FROM aip_tool_binding "
                                 "WHERE org_id='org-org' AND project_id='dev-project' "
                                 "AND binding_id='b12-rollback'").fetchone()[0] == 0
        finally:
            owner.execute("DROP TRIGGER IF EXISTS s3owaob12_binding_guard ON aip_tool_binding")
            owner.execute("DROP FUNCTION IF EXISTS public.s3owaob12_binding_guard()")
            owner.execute("DROP TRIGGER IF EXISTS s3owaob12_receipt_guard "
                          "ON aip_agent_registry_receipt")
            owner.execute("DROP FUNCTION IF EXISTS public.s3owaob12_receipt_guard()")
            for name in (issuer, runtime):
                owner.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_agent_registry_receipt")
                              .format(sql.Identifier(name + "_receipt")))
            owner.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_tool_binding")
                          .format(sql.Identifier(issuer + "_binding")))
            owner.execute(sql.SQL("REVOKE SELECT,INSERT ON aip_tool_binding FROM {}")
                          .format(sql.Identifier(issuer)))
            for name in (issuer, runtime):
                owner.execute(sql.SQL("REVOKE SELECT,INSERT ON aip_agent_registry_receipt FROM {}")
                              .format(sql.Identifier(name)))
                owner.execute(sql.SQL("DROP ROLE IF EXISTS {}") .format(sql.Identifier(name)))
