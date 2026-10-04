"""Test-only composition of an installation lock and blocked Binding receipt."""

import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from aos_api.db import get_dsn


def assert_restricted_blocked_evaluate_composes_lock(
    *, scope, role, restricted_parts, lock_function, installation, etag, growth,
    registry=None, concurrent_revoke=False,
):
    suffix = secrets.token_hex(4)
    definer = "b47_definer_" + suffix
    function = "b47_blocked_evaluate_" + suffix
    binding = "b47-binding-" + suffix
    key = "b47-first-" + suffix
    signature = sql.SQL("public.{}(text,text,uuid,bigint,text,bigint,text)").format(
        sql.Identifier(function))
    call = sql.SQL("SELECT public.{}(%s,%s,%s,%s,%s,%s,%s) AS revision").format(
        sql.Identifier(function))
    binding_ref = {"assetType": "CapabilityRevision", "assetId": "b47-test-only",
                   "revision": 1, "contentHash": "a" * 64}
    scoped_tables = ("bundle_installation", "bundle_installation_revision",
                     "bundle_composition_lock", "aip_capability_binding",
                     "aip_agent_registry_receipt")
    with psycopg.connect(get_dsn(), autocommit=True, row_factory=dict_row) as admin:
        admin.execute("""INSERT INTO aip_capability_binding(
            org_id,project_id,binding_id,capability_ref,secret_ref,health,
            network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
            status,version)
            VALUES('org-org','dev-project',%s,%s::jsonb,'secret://test-only',
                   'unknown','test-only','test-only',1000,1,'provisioning',1)""",
            (binding, json.dumps(binding_ref)))
        admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS")
                      .format(sql.Identifier(definer)))
        try:
            admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}")
                          .format(sql.Identifier(definer)))
            for table in scoped_tables[:3]:
                admin.execute(sql.SQL("GRANT SELECT ON {} TO {}")
                              .format(sql.Identifier(table), sql.Identifier(definer)))
            for table in ("asset_bundle", "asset_bundle_version"):
                admin.execute(sql.SQL("GRANT SELECT ON {} TO {}")
                              .format(sql.Identifier(table), sql.Identifier(definer)))
            admin.execute(sql.SQL("GRANT UPDATE(status) ON asset_bundle_version TO {}")
                          .format(sql.Identifier(definer)))
            admin.execute(sql.SQL("GRANT SELECT,UPDATE ON aip_capability_binding TO {}")
                          .format(sql.Identifier(definer)))
            admin.execute(sql.SQL("GRANT SELECT,INSERT ON aip_agent_registry_receipt TO {}")
                          .format(sql.Identifier(definer)))
            admin.execute(sql.SQL("GRANT EXECUTE ON FUNCTION public.{}(text,text,uuid,bigint) "
                                  "TO {}").format(sql.Identifier(lock_function),
                                                  sql.Identifier(definer)))
            for table in scoped_tables:
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} "
                    "USING(org_id=current_setting('aos.org_id',true) AND "
                    "project_id=current_setting('aos.project_id',true)) "
                    "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                    "project_id=current_setting('aos.project_id',true))")
                    .format(sql.Identifier(function + "_" + table),
                            sql.Identifier(table), sql.Identifier(definer)))
            admin.execute(sql.SQL("""CREATE FUNCTION public.{}(
                p_org text,p_project text,p_installation uuid,p_etag bigint,
                p_binding text,p_version bigint,p_key text)
                RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
                SET search_path=pg_catalog AS $$
                DECLARE locked_pk uuid; release_pk uuid; source_count integer;
                        next_version bigint;
                        digest text;
                BEGIN
                  IF session_user IS DISTINCT FROM {}
                     OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
                     OR current_setting('transaction_isolation') <> 'serializable'
                     OR p_key IS NULL OR p_key = '' THEN
                    RAISE EXCEPTION 'restricted source unavailable' USING ERRCODE='42501';
                  END IF;
                  SELECT public.{}(p_org,p_project,p_installation,p_etag)
                    INTO locked_pk;
                  PERFORM pg_catalog.pg_advisory_xact_lock(228,1);
                  SELECT count(*) INTO source_count
                    FROM public.bundle_installation i
                    JOIN public.bundle_installation_revision r
                      ON r.org_id=i.org_id AND r.project_id=i.project_id
                     AND r.installation_pk=i.installation_pk
                     AND r.revision=i.current_revision
                    JOIN public.bundle_composition_lock l
                      ON l.org_id=r.org_id AND l.project_id=r.project_id
                     AND l.composition_pk=r.composition_pk
                     AND l.revision=r.lock_revision
                    CROSS JOIN LATERAL
                      pg_catalog.jsonb_array_elements(l.lock_payload->'resolved') member
                   WHERE i.org_id=p_org AND i.project_id=p_project
                     AND i.installation_pk=locked_pk
                     AND i.active_revision=i.current_revision AND r.state='active'
                     AND member->>'kind'='SolutionPack'
                     AND member->>'publisher'={}
                     AND member->>'id'={}
                     AND member->>'version'={}
                     AND member->>'contentHash'={};
                  IF source_count <> 1 THEN
                    RAISE EXCEPTION 'signed source unavailable' USING ERRCODE='42501';
                  END IF;
                  SELECT v.version_pk INTO release_pk
                    FROM public.asset_bundle_version v
                    JOIN public.asset_bundle b ON b.bundle_pk=v.bundle_pk
                   WHERE b.publisher={}
                     AND b.bundle_id={}
                     AND v.version={}
                     AND v.content_hash={}
                     AND v.status='published'
                     FOR SHARE OF v;
                  IF release_pk IS NULL THEN
                    RAISE EXCEPTION 'current release unavailable' USING ERRCODE='42501';
                  END IF;
                  digest := pg_catalog.md5(p_org||':'||p_project||':'||p_binding||':'||
                      p_version::text||':'||p_key);
                  digest := digest||digest;
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
                  VALUES(p_org,p_project,'b47-'||p_key,
                    'capability_binding.evaluate',p_key,digest,
                    pg_catalog.jsonb_build_object('resourceType','CapabilityBinding',
                        'resourceId',p_binding),
                    pg_catalog.jsonb_build_object('resourceType',
                        'CapabilityBindingReadiness','resourceId',p_binding,
                        'revision',next_version::text),
                    'applied',session_user,pg_catalog.clock_timestamp());
                  RETURN next_version;
                END $$""").format(
                    sql.Identifier(function), sql.Literal(role),
                    sql.Identifier(lock_function), sql.Literal(growth.publisher),
                    sql.Literal(growth.bundle_id), sql.Literal(growth.version),
                    sql.Literal(growth.content_hash), sql.Literal(growth.publisher),
                    sql.Literal(growth.bundle_id), sql.Literal(growth.version),
                    sql.Literal(growth.content_hash)))
            admin.execute(sql.SQL("ALTER FUNCTION {} OWNER TO {}")
                          .format(signature, sql.Identifier(definer)))
            admin.execute(sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC")
                          .format(signature))
            with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                with limited.transaction():
                    limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                    "set_config('aos.project_id',%s,true)", scope.key)
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        with limited.transaction():
                            limited.execute(call, (*scope.key, installation, etag,
                                                   binding, 1, key))
            admin.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}")
                          .format(signature, sql.Identifier(role)))
            with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                with limited.transaction():
                    limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                    "set_config('aos.project_id',%s,true)", scope.key)
                    assert limited.execute("SELECT has_table_privilege(session_user,"
                        "'aip_capability_binding','UPDATE') AS writable").fetchone()["writable"] is False
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        with limited.transaction():
                            limited.execute("""UPDATE aip_capability_binding
                                SET operational_readiness='available'
                                WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                                (*scope.key, binding))
                    assert limited.execute(call, (*scope.key, installation, etag,
                                                  binding, 1, key)).fetchone()["revision"] == 2
                    with psycopg.connect(get_dsn(), autocommit=True) as contender:
                        contender.execute("SET lock_timeout='250ms'")
                        assert contender.execute(
                            "SELECT count(*) FROM aip_agent_registry_receipt "
                            "WHERE operation='capability_binding.evaluate' "
                            "AND idempotency_key=%s", (key,),
                        ).fetchone()[0] == 0
                        with pytest.raises(psycopg.errors.LockNotAvailable):
                            contender.execute("SELECT 1 FROM bundle_installation "
                                "WHERE org_id=%s AND project_id=%s AND installation_id=%s "
                                "FOR UPDATE", (*scope.key, installation))
                        with pytest.raises(psycopg.errors.LockNotAvailable):
                            contender.execute("SELECT pg_advisory_xact_lock(228,1)")
            row = admin.execute("SELECT version,status,operational_readiness,"
                "dependency_snapshot_hash FROM aip_capability_binding WHERE binding_id=%s",
                (binding,)).fetchone()
            assert row == {"version": 2, "status": "provisioning",
                           "operational_readiness": "blocked",
                           "dependency_snapshot_hash": None}
            assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                "WHERE operation='capability_binding.evaluate' AND idempotency_key=%s",
                (key,)).fetchone()["n"] == 1
            with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                with limited.transaction():
                    limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                    "set_config('aos.project_id',%s,true)", scope.key)
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        with limited.transaction():
                            limited.execute(call, (*scope.key, uuid4(), etag,
                                                   binding, 2, key + "-wrong"))
            assert admin.execute("SELECT version FROM aip_capability_binding WHERE "
                "binding_id=%s", (binding,)).fetchone()["version"] == 2
            if concurrent_revoke:
                assert registry is not None
                _assert_concurrent_revoke_fails_closed(
                    admin=admin, registry=registry, restricted_parts=restricted_parts,
                    call=call, scope=scope, installation=installation, etag=etag,
                    growth=growth, binding=binding, key=key,
                )
            elif registry is not None:
                revoked = registry.revoke(
                    publisher=growth.publisher, bundle_id=growth.bundle_id,
                    version=growth.version, actor="b48-test-only-revoker",
                    roles={"asset-publisher"},
                    publisher_scopes={growth.publisher},
                    reason="b48 committed revoke versus restricted evaluate",
                )
                assert revoked["status"] == "revoked"
                with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                    with limited.transaction():
                        limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                        limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                        "set_config('aos.project_id',%s,true)", scope.key)
                        with pytest.raises(psycopg.errors.InsufficientPrivilege):
                            with limited.transaction():
                                limited.execute(call, (*scope.key, installation, etag,
                                                       binding, 2, key + "-revoked"))
                assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                    "WHERE idempotency_key=%s", (key + "-revoked",)).fetchone()["n"] == 0
                assert admin.execute("SELECT version FROM aip_capability_binding "
                    "WHERE binding_id=%s", (binding,)).fetchone()["version"] == 2
        finally:
            admin.execute(sql.SQL("DROP FUNCTION IF EXISTS {}") .format(signature))
            for table in scoped_tables:
                admin.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}")
                    .format(sql.Identifier(function + "_" + table),
                            sql.Identifier(table)))
            admin.execute(sql.SQL("DROP OWNED BY {}") .format(sql.Identifier(definer)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}") .format(sql.Identifier(definer)))
            assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",
                                 (definer,)).fetchone() is None


def _assert_concurrent_revoke_fails_closed(
    *, admin, registry, restricted_parts, call, scope, installation, etag,
    growth, binding, key,
):
    release = admin.execute("""SELECT v.version_pk FROM asset_bundle_version v
        JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
        WHERE b.publisher=%s AND b.bundle_id=%s AND v.version=%s
          AND v.content_hash=%s AND v.status='published'""",
        (growth.publisher, growth.bundle_id, growth.version,
         growth.content_hash)).fetchone()
    assert release is not None
    blocker = psycopg.connect(get_dsn(), autocommit=True)
    pids = Queue()

    def revoke():
        return registry.revoke(
            publisher=growth.publisher, bundle_id=growth.bundle_id,
            version=growth.version, actor="b49-test-only-revoker",
            roles={"asset-publisher"}, publisher_scopes={growth.publisher},
            reason="b49 concurrent revoke versus restricted evaluate",
        )

    def evaluate():
        with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
            with limited.transaction():
                limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                limited.execute("SET statement_timeout='10s'")
                limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                "set_config('aos.project_id',%s,true)", scope.key)
                pids.put(limited.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
                try:
                    limited.execute(call, (*scope.key, installation, etag,
                                           binding, 2, key + "-race"))
                except psycopg.Error as exc:
                    return exc.sqlstate
                return "applied"

    def await_lock(*, granted, pid=None):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            count = admin.execute("""SELECT count(*) AS n FROM pg_locks
                WHERE locktype='advisory' AND classid=228 AND objid=1
                  AND granted=%s AND (%s::int IS NULL OR pid=%s::int)""",
                (granted, pid, pid)).fetchone()["n"]
            if count:
                return
            time.sleep(0.025)
        raise AssertionError("expected advisory lock phase not observed")

    try:
        blocker.execute("BEGIN")
        blocker.execute("SELECT 1 FROM asset_bundle_version WHERE version_pk=%s "
                        "FOR UPDATE", (release["version_pk"],))
        with ThreadPoolExecutor(max_workers=2) as pool:
            revoked = pool.submit(revoke)
            await_lock(granted=True)
            evaluated = pool.submit(evaluate)
            limited_pid = pids.get(timeout=8)
            await_lock(granted=False, pid=limited_pid)
            blocker.execute("COMMIT")
            assert revoked.result(timeout=10)["status"] == "revoked"
            outcome = evaluated.result(timeout=10)
        assert outcome in {"42501", "40001"}, outcome
        assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
            "WHERE idempotency_key=%s", (key + "-race",)).fetchone()["n"] == 0
        assert admin.execute("SELECT version FROM aip_capability_binding "
            "WHERE binding_id=%s", (binding,)).fetchone()["version"] == 2
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
