"""Disposable PG contract for an atomic, fail-closed restricted evaluate command."""

import json
import secrets

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
import pytest

from aos_api.db import get_dsn


def test_restricted_evaluate_command_denies_direct_writes_and_is_atomic():
    dsn = get_dsn()
    dbname = conninfo_to_dict(dsn)["dbname"]
    assert dbname.startswith("aos_test_") and dbname.endswith("_ti4_test")
    suffix = secrets.token_hex(4)
    issuer = "b46_issuer_" + suffix
    definer = "b46_definer_" + suffix
    function = "b46_blocked_evaluate_" + suffix
    binding = "b46-binding-" + suffix
    key = "b46-first-" + suffix
    password = secrets.token_urlsafe(24)
    function_name = sql.Identifier("public", function)
    signature = sql.SQL("{}(text,text,text,bigint,text)").format(function_name)
    call = sql.SQL("SELECT {}(%s,%s,%s,%s,%s) AS revision").format(function_name)
    ref = {"assetType": "CapabilityRevision", "assetId": "b46-test-only",
           "revision": 1, "contentHash": "a" * 64}

    def login():
        return psycopg.connect(make_conninfo(dsn, user=issuer, password=password),
                               row_factory=dict_row)

    def scope(conn, org="org-org"):
        conn.execute("SELECT set_config('aos.org_id',%s,true),"
                     "set_config('aos.project_id','dev-project',true)", (org,))

    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as owner:
        owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') "
                      "ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO twa_workspace(org_id,project_id,name) "
                      "VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
        owner.execute("""INSERT INTO aip_capability_binding(
            org_id,project_id,binding_id,capability_ref,secret_ref,health,
            network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
            status,version)
            VALUES('org-org','dev-project',%s,%s::jsonb,'secret://test-only',
                   'unknown','test-only','test-only',1000,1,'provisioning',1)""",
            (binding, json.dumps(ref)))
        owner.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS "
                              "PASSWORD {}").format(sql.Identifier(issuer),
                                                    sql.Literal(password)))
        owner.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS")
                      .format(sql.Identifier(definer)))
        try:
            with login() as conn:
                scope(conn)
                assert conn.execute("SELECT session_user,current_user").fetchone() == {
                    "session_user": issuer, "current_user": issuer,
                }
                for table, privilege in (("aip_capability_binding", "UPDATE"),
                                         ("aip_agent_registry_receipt", "INSERT")):
                    assert not conn.execute("SELECT has_table_privilege("
                        "session_user,%s,%s) AS allowed", (table, privilege)
                    ).fetchone()["allowed"]
                with pytest.raises(psycopg.errors.UndefinedFunction):
                    conn.execute(call, ("org-org", "dev-project", binding, 1, key))
                conn.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute("UPDATE aip_capability_binding SET version=2 "
                                 "WHERE binding_id=%s", (binding,))
                conn.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute("""INSERT INTO aip_agent_registry_receipt(
                        org_id,project_id,receipt_id,operation,idempotency_key,
                        request_hash,resource_ref,result_ref,status,created_by,created_at)
                        VALUES('org-org','dev-project','b46-direct',
                        'capability_binding.evaluate','b46-direct',%s,'{}','{}',
                        'applied','test-only',now())""", ("f" * 64,))
                conn.rollback()

            owner.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}")
                          .format(sql.Identifier(definer)))
            owner.execute(sql.SQL("GRANT SELECT,UPDATE ON aip_capability_binding TO {}")
                          .format(sql.Identifier(definer)))
            owner.execute(sql.SQL("GRANT SELECT,INSERT ON aip_agent_registry_receipt TO {}")
                          .format(sql.Identifier(definer)))
            for table in ("aip_capability_binding", "aip_agent_registry_receipt"):
                owner.execute(sql.SQL("CREATE POLICY {} ON {} TO {} "
                    "USING(org_id=current_setting('aos.org_id',true) AND "
                    "project_id=current_setting('aos.project_id',true)) "
                    "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                    "project_id=current_setting('aos.project_id',true))")
                    .format(sql.Identifier(function + "_" + table),
                            sql.Identifier(table), sql.Identifier(definer)))
            owner.execute(sql.SQL("""CREATE FUNCTION {}(
                p_org text,p_project text,p_binding text,p_version bigint,p_key text)
                RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
                SET search_path=pg_catalog AS $$
                DECLARE existing record; next_version bigint; digest text;
                BEGIN
                  IF session_user <> {} OR p_org <> 'org-org'
                     OR p_project <> 'dev-project' OR p_key IS NULL OR p_key = ''
                     OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
                  THEN RAISE EXCEPTION 'restricted evaluate unavailable'
                       USING ERRCODE='42501';
                  END IF;
                  PERFORM pg_catalog.pg_advisory_xact_lock(227,
                      pg_catalog.hashtext(p_org||':'||p_project||':'||p_key));
                  digest := pg_catalog.md5(p_org||':'||p_project||':'||p_binding||':'||
                      p_version::text||':'||p_key);
                  digest := digest||digest;
                  SELECT request_hash,result_ref INTO existing
                    FROM public.aip_agent_registry_receipt
                    WHERE org_id=p_org AND project_id=p_project
                      AND operation='capability_binding.evaluate'
                      AND idempotency_key=p_key;
                  IF FOUND THEN
                    IF existing.request_hash <> digest THEN
                      RAISE EXCEPTION 'idempotency identity changed' USING ERRCODE='42501';
                    END IF;
                    RETURN (existing.result_ref->>'revision')::bigint;
                  END IF;
                  UPDATE public.aip_capability_binding SET
                    operational_readiness='blocked',
                    readiness_reasons='["TRUSTED_EVALUATOR_PENDING"]'::jsonb,
                    dependency_snapshot_hash=NULL,readiness_expires_at=NULL,
                    last_evaluated_at=pg_catalog.clock_timestamp(),
                    version=version+1,updated_at=pg_catalog.clock_timestamp()
                    WHERE org_id=p_org AND project_id=p_project
                      AND binding_id=p_binding AND version=p_version
                      AND status='provisioning'
                    RETURNING version INTO next_version;
                  IF NOT FOUND THEN
                    RAISE EXCEPTION 'binding version unavailable' USING ERRCODE='42501';
                  END IF;
                  INSERT INTO public.aip_agent_registry_receipt(
                    org_id,project_id,receipt_id,operation,idempotency_key,
                    request_hash,resource_ref,result_ref,status,created_by,created_at)
                  VALUES(p_org,p_project,'b46-'||p_key,
                    'capability_binding.evaluate',p_key,digest,
                    pg_catalog.jsonb_build_object('resourceType','CapabilityBinding',
                        'resourceId',p_binding),
                    pg_catalog.jsonb_build_object('resourceType',
                        'CapabilityBindingReadiness','resourceId',p_binding,
                        'revision',next_version::text),
                    'applied',session_user,pg_catalog.clock_timestamp());
                  RETURN next_version;
                END $$""").format(function_name, sql.Literal(issuer)))
            owner.execute(sql.SQL("ALTER FUNCTION {} OWNER TO {}")
                          .format(signature, sql.Identifier(definer)))
            owner.execute(sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC")
                          .format(signature))
            with login() as conn:
                scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(call, ("org-org", "dev-project", binding, 1, key))
                conn.rollback()
            owner.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}")
                          .format(signature, sql.Identifier(issuer)))

            for org, expected, key in (("dev-org", 1, "cross"),
                                       ("org-org", 2, "wrong-version")):
                with login() as conn:
                    scope(conn, org)
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        conn.execute(call, (org, "dev-project", binding, expected, key))
            with login() as conn:
                assert conn.execute("SELECT session_user").fetchone()["session_user"] == issuer
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(call, ("org-org", "dev-project", binding, 1, "no-guc"))
            with login() as conn:
                scope(conn)
                assert not conn.execute("SELECT has_table_privilege(session_user,"
                    "'aip_capability_binding','UPDATE') AS allowed").fetchone()["allowed"]
                assert conn.execute(call, ("org-org", "dev-project", binding, 1,
                                           key)).fetchone()["revision"] == 2
            with login() as conn:
                scope(conn)
                assert conn.execute(call, ("org-org", "dev-project", binding, 1,
                                           key)).fetchone()["revision"] == 2
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(call, ("org-org", "dev-project", binding, 2, key))
                conn.rollback()
            fail_key = "b46-failure-" + suffix
            owner.execute("""INSERT INTO aip_agent_registry_receipt(
                org_id,project_id,receipt_id,operation,idempotency_key,
                request_hash,resource_ref,result_ref,status,created_by,created_at)
                VALUES('org-org','dev-project',%s,'agent_instance.create',%s,
                       %s,'{}','{}','applied','b46-test-only',now())""",
                ("b46-" + fail_key, fail_key + "-sentinel", "f" * 64))
            with login() as conn:
                scope(conn)
                with pytest.raises(psycopg.errors.UniqueViolation):
                    conn.execute(call, ("org-org", "dev-project", binding, 2,
                                        fail_key))
            row = owner.execute("SELECT version,status,operational_readiness,"
                "dependency_snapshot_hash,readiness_expires_at,readiness_reasons "
                "FROM aip_capability_binding WHERE binding_id=%s", (binding,)).fetchone()
            assert row == {"version": 2, "status": "provisioning",
                           "operational_readiness": "blocked",
                           "dependency_snapshot_hash": None,
                           "readiness_expires_at": None,
                           "readiness_reasons": ["TRUSTED_EVALUATOR_PENDING"]}
            assert owner.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                "WHERE idempotency_key=%s", (key,)).fetchone()["n"] == 1
            assert owner.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                "WHERE operation='capability_binding.evaluate' AND idempotency_key=%s",
                (fail_key,)).fetchone()["n"] == 0
        finally:
            owner.execute(sql.SQL("DROP FUNCTION IF EXISTS {}").format(signature))
            for table in ("aip_capability_binding", "aip_agent_registry_receipt"):
                owner.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}")
                    .format(sql.Identifier(function + "_" + table),
                            sql.Identifier(table)))
            owner.execute(sql.SQL("REVOKE SELECT,UPDATE ON aip_capability_binding FROM {}")
                          .format(sql.Identifier(definer)))
            owner.execute(sql.SQL("REVOKE SELECT,INSERT ON aip_agent_registry_receipt FROM {}")
                          .format(sql.Identifier(definer)))
            owner.execute(sql.SQL("REVOKE USAGE ON SCHEMA public FROM {}")
                          .format(sql.Identifier(definer)))
            owner.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(issuer)))
            owner.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(definer)))
            assert owner.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname IN (%s,%s)",
                                 (issuer, definer)).fetchone()["n"] == 0
