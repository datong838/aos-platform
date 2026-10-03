"""Disposable full-schema RED for independently logged-in Capability receipt forgery."""

import json
import secrets

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from aos_api.db import get_dsn


@pytest.mark.xfail(strict=True, reason="shared Receipt lacks Capability operation/session guard")
def test_capability_receipt_requires_real_issuer_and_binding_pair():
    dsn = get_dsn()
    dbname = conninfo_to_dict(dsn)["dbname"]
    assert dbname.startswith("aos_test_") and dbname.endswith("_ti4_test")
    runtime = "s3owaob22_runtime_" + secrets.token_hex(4)
    password = secrets.token_urlsafe(24)
    with psycopg.connect(dsn, autocommit=True) as owner:
        owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','formal') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO twa_workspace(org_id,project_id,name) "
                      "VALUES('org-org','dev-project','formal') ON CONFLICT DO NOTHING")
        owner.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                      .format(sql.Identifier(runtime), sql.Literal(password)))
        try:
            owner.execute(sql.SQL("GRANT SELECT,INSERT ON aip_agent_registry_receipt TO {}")
                          .format(sql.Identifier(runtime)))
            owner.execute(sql.SQL("CREATE POLICY {} ON aip_agent_registry_receipt TO {} "
                "USING(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true))")
                .format(sql.Identifier(runtime + "_receipt"), sql.Identifier(runtime)))
            with psycopg.connect(make_conninfo(dsn, user=runtime, password=password)) as conn:
                conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                             "set_config('aos.project_id','dev-project',true)")
                assert conn.execute("SELECT session_user,current_user").fetchone() == (runtime, runtime)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute("""INSERT INTO aip_agent_registry_receipt(
                        org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
                        resource_ref,result_ref,status,created_by,created_at)
                        VALUES('org-org','dev-project','b22-unpaired',
                        'capability_binding.create','b22-unpaired',%s,%s::jsonb,%s::jsonb,
                        'applied','b22-test',now())""",
                        ("f" * 64, json.dumps({"resourceType": "Capability", "resourceId": "test-only"}),
                         json.dumps({"resourceType": "CapabilityBinding", "resourceId": "absent"})))
        finally:
            owner.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_agent_registry_receipt")
                          .format(sql.Identifier(runtime + "_receipt")))
            owner.execute(sql.SQL("REVOKE SELECT,INSERT ON aip_agent_registry_receipt FROM {}")
                          .format(sql.Identifier(runtime)))
            owner.execute(sql.SQL("DROP ROLE IF EXISTS {}") .format(sql.Identifier(runtime)))


def test_clone_only_capability_operation_guard_preserves_normal_receipts():
    dsn = get_dsn()
    dbname = conninfo_to_dict(dsn)["dbname"]
    assert dbname.startswith("aos_test_") and dbname.endswith("_ti4_test")
    issuer = "s3owaob22_issuer_" + secrets.token_hex(4)
    runtime = "s3owaob22_runtime_" + secrets.token_hex(4)
    passwords = {name: secrets.token_urlsafe(24) for name in (issuer, runtime)}

    def login(name):
        return psycopg.connect(make_conninfo(dsn, user=name, password=passwords[name]))

    def set_scope(conn, org="org-org"):
        conn.execute("SELECT set_config('aos.org_id',%s,true),"
                     "set_config('aos.project_id','dev-project',true)", (org,))

    def receipt(conn, operation, key, *, binding="b22-binding", revision="1"):
        result_type = ("CapabilityBindingReadiness" if operation == "capability_binding.evaluate"
                       else "CapabilityBinding")
        source_type = "Capability" if operation == "capability_binding.create" else "CapabilityBinding"
        return conn.execute("""INSERT INTO aip_agent_registry_receipt(
            org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
            resource_ref,result_ref,status,created_by,created_at)
            VALUES('org-org','dev-project',%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                   'applied','b22-test',now())""",
            (key, operation, key, "f" * 64,
             json.dumps({"resourceType": source_type, "resourceId": binding}),
             json.dumps({"resourceType": result_type, "resourceId": binding,
                         "revision": revision})))

    def insert_binding(conn, binding):
        conn.execute("""INSERT INTO aip_capability_binding(
            org_id,project_id,binding_id,capability_ref,secret_ref,health,
            network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
            status,version)
            VALUES('org-org','dev-project',%s,'{}'::jsonb,'secret://test-only',
                   'unknown','test-only','test-only',1000,1,'provisioning',1)""", (binding,))

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
            owner.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE ON aip_capability_binding TO {}")
                          .format(sql.Identifier(issuer)))
            owner.execute(sql.SQL("CREATE POLICY {} ON aip_capability_binding TO {} "
                "USING(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true))")
                .format(sql.Identifier(issuer + "_binding"), sql.Identifier(issuer)))
            owner.execute(sql.SQL("""CREATE FUNCTION public.s3owaob22_receipt_guard()
                RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
                SET search_path=pg_catalog AS $$
                BEGIN
                  IF NEW.operation LIKE 'capability_binding.%' THEN
                    IF NEW.operation NOT IN ('capability_binding.create',
                        'capability_binding.update','capability_binding.evaluate')
                       OR session_user<>{} OR NEW.status<>'applied'
                       OR NEW.result_ref->>'resourceId' IS NULL
                       OR NEW.result_ref->>'revision' IS NULL
                       OR NOT EXISTS (
                         SELECT 1 FROM public.aip_capability_binding b
                         WHERE b.org_id=NEW.org_id AND b.project_id=NEW.project_id
                           AND b.binding_id=NEW.result_ref->>'resourceId'
                           AND b.version::text=NEW.result_ref->>'revision'
                           AND b.xmin::text=pg_current_xact_id()::text
                           AND ((NEW.operation='capability_binding.create'
                                 AND NEW.result_ref->>'resourceType'='CapabilityBinding'
                                 AND NEW.resource_ref->>'resourceType'='Capability')
                             OR (NEW.operation='capability_binding.update'
                                 AND NEW.result_ref->>'resourceType'='CapabilityBinding'
                                 AND NEW.resource_ref->>'resourceType'='CapabilityBinding')
                             OR (NEW.operation='capability_binding.evaluate'
                                 AND NEW.result_ref->>'resourceType'='CapabilityBindingReadiness'
                                 AND NEW.resource_ref->>'resourceType'='CapabilityBinding')))
                    THEN RAISE EXCEPTION 'CAPABILITY_RECEIPT_UNPAIRED' USING ERRCODE='42501';
                    END IF;
                  ELSIF session_user={} THEN
                    RAISE EXCEPTION 'CAPABILITY_ISSUER_OPERATION_FORBIDDEN' USING ERRCODE='42501';
                  END IF;
                  RETURN NEW;
                END $$""").format(sql.Literal(issuer), sql.Literal(issuer)))
            owner.execute("REVOKE ALL ON FUNCTION public.s3owaob22_receipt_guard() FROM PUBLIC")
            owner.execute("""CREATE TRIGGER s3owaob22_receipt_guard
                BEFORE INSERT ON aip_agent_registry_receipt FOR EACH ROW
                EXECUTE FUNCTION public.s3owaob22_receipt_guard()""")
            owner.execute(sql.SQL("""CREATE FUNCTION public.s3owaob22_binding_guard()
                RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
                SET search_path=pg_catalog AS $$
                DECLARE expected_operation text;
                BEGIN
                  IF TG_OP='INSERT' THEN
                    expected_operation := 'capability_binding.create';
                  ELSIF NEW.status IS DISTINCT FROM OLD.status
                     OR NEW.health IS DISTINCT FROM OLD.health THEN
                    expected_operation := 'capability_binding.update';
                  ELSE
                    expected_operation := 'capability_binding.evaluate';
                  END IF;
                  IF session_user<>{} OR NOT EXISTS (
                      SELECT 1 FROM public.aip_agent_registry_receipt r
                       WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
                         AND r.operation=expected_operation
                         AND r.result_ref->>'resourceId'=NEW.binding_id
                         AND r.result_ref->>'revision'=NEW.version::text
                         AND r.xmin::text=pg_current_xact_id()::text)
                  THEN RAISE EXCEPTION 'CAPABILITY_BINDING_UNRECEIPTED' USING ERRCODE='42501';
                  END IF;
                  RETURN NEW;
                END $$""").format(sql.Literal(issuer)))
            owner.execute("REVOKE ALL ON FUNCTION public.s3owaob22_binding_guard() FROM PUBLIC")
            owner.execute("""CREATE CONSTRAINT TRIGGER s3owaob22_binding_guard
                AFTER INSERT OR UPDATE ON aip_capability_binding
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
                EXECUTE FUNCTION public.s3owaob22_binding_guard()""")

            with login(runtime) as conn:
                set_scope(conn)
                receipt(conn, "agent_instance.create", "b22-normal")
            with login(runtime) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-runtime-forgery")
                conn.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(sql.SQL("SET ROLE {}") .format(sql.Identifier(issuer)))
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-unpaired")
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "agent_instance.create", "b22-issuer-other")
                conn.rollback()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    insert_binding(conn, "b22-no-receipt")
            with login(issuer) as conn:
                set_scope(conn)
                insert_binding(conn, "b22-binding")
                receipt(conn, "capability_binding.create", "b22-created")
            with login(issuer) as conn:
                set_scope(conn)
                conn.execute("""UPDATE aip_capability_binding SET status='suspended',
                    version=version+1 WHERE binding_id='b22-binding'""")
                receipt(conn, "capability_binding.update", "b22-updated", revision="2")
            with login(issuer) as conn:
                set_scope(conn)
                conn.execute("""UPDATE aip_capability_binding SET version=version+1,
                    operational_readiness='blocked',dependency_snapshot_hash=%s,
                    last_evaluated_at=now(),readiness_expires_at=now()+interval '15 minutes'
                    WHERE binding_id='b22-binding'""", ("b" * 64,))
                receipt(conn, "capability_binding.evaluate", "b22-evaluated", revision="3")
            with login(issuer) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-created")
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-late")
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                insert_binding(conn, "b22-wrong-version")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-wrong-version", revision="2",
                            binding="b22-wrong-version")
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn, "dev-org")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-cross-tenant")
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                insert_binding(conn, "b22-rollback")
                receipt(conn, "capability_binding.create", "b22-rollback",
                        binding="b22-rollback")
                conn.rollback()
            assert owner.execute("SELECT count(*) FROM aip_agent_registry_receipt "
                                 "WHERE idempotency_key LIKE 'b22-%'").fetchone()[0] == 4
            assert owner.execute("SELECT count(*) FROM aip_capability_binding "
                                 "WHERE binding_id LIKE 'b22-%'").fetchone()[0] == 1
        finally:
            owner.execute("DROP TRIGGER IF EXISTS s3owaob22_binding_guard ON aip_capability_binding")
            owner.execute("DROP FUNCTION IF EXISTS public.s3owaob22_binding_guard()")
            owner.execute("DROP TRIGGER IF EXISTS s3owaob22_receipt_guard "
                          "ON aip_agent_registry_receipt")
            owner.execute("DROP FUNCTION IF EXISTS public.s3owaob22_receipt_guard()")
            owner.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_capability_binding")
                          .format(sql.Identifier(issuer + "_binding")))
            owner.execute(sql.SQL("REVOKE SELECT,INSERT,UPDATE ON aip_capability_binding FROM {}")
                          .format(sql.Identifier(issuer)))
            for name in (issuer, runtime):
                owner.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_agent_registry_receipt")
                              .format(sql.Identifier(name + "_receipt")))
                owner.execute(sql.SQL("REVOKE SELECT,INSERT ON aip_agent_registry_receipt FROM {}")
                              .format(sql.Identifier(name)))
                owner.execute(sql.SQL("DROP ROLE IF EXISTS {}") .format(sql.Identifier(name)))
