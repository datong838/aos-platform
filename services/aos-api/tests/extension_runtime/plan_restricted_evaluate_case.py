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
    registry=None, concurrent_revoke=False, evaluate_first=False,
    forged_available=False, paired_receipt=False, license_authority=False,
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
    license_id = "b69-license-" + suffix
    license_hash = "c" * 64
    if license_authority:
        scoped_tables += ("aip_evidence_bundle_revision",
                          "aip_evidence_bundle_revoke_event")
    license_check = sql.SQL("")
    if license_authority:
        license_check = sql.SQL("""IF NOT EXISTS (
            SELECT 1 FROM public.aip_evidence_bundle_revision e
             WHERE e.org_id=p_org AND e.project_id=p_project
               AND e.bundle_id={} AND e.revision=1
               AND e.content_hash={} AND e.lifecycle='frozen'
               AND e.license_summary<>'{{}}'::jsonb
               AND NOT EXISTS (
                 SELECT 1 FROM public.aip_evidence_bundle_revoke_event r
                  WHERE r.org_id=e.org_id AND r.project_id=e.project_id
                    AND r.bundle_id=e.bundle_id AND r.revision=e.revision
                    AND r.content_hash=e.content_hash))
          THEN RAISE EXCEPTION 'license evidence unavailable'
               USING ERRCODE='42501';
          END IF;""").format(sql.Literal(license_id), sql.Literal(license_hash))
    receipt_guards = None
    with psycopg.connect(get_dsn(), autocommit=True, row_factory=dict_row) as admin:
        admin.execute("""INSERT INTO aip_capability_binding(
            org_id,project_id,binding_id,capability_ref,secret_ref,health,
            network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
            status,version)
            VALUES('org-org','dev-project',%s,%s::jsonb,'secret://test-only',
                   'unknown','test-only','test-only',1000,1,'provisioning',1)""",
            (binding, json.dumps(binding_ref)))
        if license_authority:
            admin.execute("""INSERT INTO aip_evidence_bundle_revision
                (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
                 item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
                 license_summary,content_hash,lifecycle,created_by)
                VALUES(%s,%s,%s,1,'{}'::jsonb,'[]'::jsonb,NOW(),'[]'::jsonb,
                       'complete','[]'::jsonb,'[]'::jsonb,'[]'::jsonb,'fresh',
                       '{}'::jsonb,'{"license":"test-only"}'::jsonb,%s,
                       'frozen','test-only')""", (*scope.key, license_id, license_hash))
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
                        next_version bigint; existing record;
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
                  {}
                  digest := pg_catalog.md5(p_org||':'||p_project||':'||
                      p_installation::text||':'||p_etag::text||':'||p_binding||':'||
                      p_version::text||':'||p_key);
                  digest := digest||digest;
                  SELECT request_hash,result_ref INTO existing
                    FROM public.aip_agent_registry_receipt
                   WHERE org_id=p_org AND project_id=p_project
                     AND operation='capability_binding.evaluate'
                     AND idempotency_key=p_key;
                  IF FOUND THEN
                    IF existing.request_hash<>digest
                       OR existing.result_ref->>'resourceId'<>p_binding
                    THEN RAISE EXCEPTION 'evaluate idempotency conflict'
                         USING ERRCODE='42501';
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
                    sql.Literal(growth.content_hash), license_check))
            admin.execute(sql.SQL("ALTER FUNCTION {} OWNER TO {}")
                          .format(signature, sql.Identifier(definer)))
            admin.execute(sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC")
                          .format(signature))
            if paired_receipt:
                receipt_guards = _install_b67_receipt_guards(
                    admin=admin, suffix=suffix, definer=definer, role=role)
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
            if license_authority:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                        with limited.transaction():
                            limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                            limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                            "set_config('aos.project_id',%s,true)", scope.key)
                            limited.execute(call, (*scope.key, installation, etag,
                                                  binding, 1, key + "-no-license-acl"))
                assert admin.execute("SELECT version FROM aip_capability_binding "
                    "WHERE binding_id=%s", (binding,)).fetchone()["version"] == 1
                assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                    "WHERE idempotency_key=%s", (key + "-no-license-acl",)).fetchone()["n"] == 0
                for table in scoped_tables[-2:]:
                    admin.execute(sql.SQL("GRANT SELECT ON {} TO {}")
                                  .format(sql.Identifier(table), sql.Identifier(definer)))
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
            if paired_receipt:
                with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                    with limited.transaction():
                        limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                        limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                        "set_config('aos.project_id',%s,true)", scope.key)
                        assert limited.execute(call, (*scope.key, installation, etag,
                            binding, 1, key)).fetchone()["revision"] == 2
                        with pytest.raises(psycopg.errors.InsufficientPrivilege):
                            with limited.transaction():
                                limited.execute(call, (*scope.key, installation, etag,
                                    binding, 2, key))
                assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                    "WHERE operation='capability_binding.evaluate' AND idempotency_key=%s",
                    (key,)).fetchone()["n"] == 1
                fail_key = "b67-failed-" + suffix
                admin.execute("""INSERT INTO aip_agent_registry_receipt(
                    org_id,project_id,receipt_id,operation,idempotency_key,
                    request_hash,resource_ref,result_ref,status,created_by,created_at)
                    VALUES(%s,%s,%s,'agent_instance.create',%s,%s,
                    '{}'::jsonb,'{}'::jsonb,'applied','test-only',now())""",
                    (*scope.key, "b47-" + fail_key, fail_key + "-sentinel", "f" * 64))
                with pytest.raises(psycopg.errors.UniqueViolation):
                    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                        with limited.transaction():
                            limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                            limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                            "set_config('aos.project_id',%s,true)", scope.key)
                            limited.execute(call, (*scope.key, installation, etag,
                                                  binding, 2, fail_key))
                assert admin.execute("SELECT version FROM aip_capability_binding "
                    "WHERE binding_id=%s", (binding,)).fetchone()["version"] == 2
                assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                    "WHERE operation='capability_binding.evaluate' AND idempotency_key=%s",
                    (fail_key,)).fetchone()["n"] == 0
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                        with limited.transaction():
                            limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                            limited.execute("SELECT set_config('aos.org_id','dev-org',true),"
                                            "set_config('aos.project_id','dev-project',true)")
                            limited.execute(call, ("dev-org", "dev-project", installation,
                                                  etag, binding, 2, key + "-tenant"))
                assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                    "WHERE idempotency_key=%s", (key + "-tenant",)).fetchone()["n"] == 0
            if forged_available:
                _assert_ordinary_issuer_cannot_forge_available(
                    admin=admin, restricted_parts=restricted_parts,
                    scope=scope, binding=binding, key=key,
                )
            if paired_receipt:
                _assert_b67_ordinary_receipt_denied(
                    admin=admin, restricted_parts=restricted_parts,
                    scope=scope, binding=binding, key=key,
                )
            if license_authority:
                revoked_key = key + "-license-revoked"
                admin.execute("""INSERT INTO aip_evidence_bundle_revoke_event
                    (org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor)
                    VALUES(%s,%s,%s,%s,1,%s,'test-only','test-only')""",
                    (*scope.key, "b69-revoke-" + suffix, license_id, license_hash))
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                        with limited.transaction():
                            limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                            limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                            "set_config('aos.project_id',%s,true)", scope.key)
                            limited.execute(call, (*scope.key, installation, etag,
                                                  binding, 2, revoked_key))
                assert admin.execute("SELECT version FROM aip_capability_binding "
                    "WHERE binding_id=%s", (binding,)).fetchone()["version"] == 2
                assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                    "WHERE idempotency_key=%s", (revoked_key,)).fetchone()["n"] == 0
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
            elif evaluate_first:
                assert registry is not None
                _assert_evaluate_first_revoke_waits(
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
            if receipt_guards is not None:
                _drop_b67_receipt_guards(admin, receipt_guards)
            admin.execute(sql.SQL("DROP FUNCTION IF EXISTS {}") .format(signature))
            for table in scoped_tables:
                admin.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}")
                    .format(sql.Identifier(function + "_" + table),
                            sql.Identifier(table)))
            admin.execute(sql.SQL("DROP OWNED BY {}") .format(sql.Identifier(definer)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}") .format(sql.Identifier(definer)))
            assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",
                                 (definer,)).fetchone() is None


def _install_b67_receipt_guards(*, admin, suffix, definer, role):
    identity = "b67_receipt_identity_" + suffix
    paired = "b67_receipt_pair_" + suffix
    binding_pair = "b67_binding_pair_" + suffix
    admin.execute(sql.SQL("""CREATE FUNCTION public.{}() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
        BEGIN
          IF NEW.operation='capability_binding.evaluate'
             AND (session_user IS DISTINCT FROM {} OR current_user IS DISTINCT FROM {})
          THEN RAISE EXCEPTION 'CAPABILITY_EVALUATOR_RECEIPT_REQUIRED'
               USING ERRCODE='42501';
          END IF;
          RETURN NEW;
        END $$""").format(sql.Identifier(identity), sql.Literal(role), sql.Literal(definer)))
    admin.execute(sql.SQL("""CREATE FUNCTION public.{}() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE paired_count integer;
        BEGIN
          IF NEW.operation='capability_binding.evaluate' THEN
            SELECT count(*) INTO paired_count
              FROM public.aip_capability_binding b
             WHERE b.org_id=NEW.org_id AND b.project_id=NEW.project_id
               AND b.binding_id=NEW.result_ref->>'resourceId'
               AND b.version::text=NEW.result_ref->>'revision'
               AND b.xmin::text=pg_catalog.pg_current_xact_id()::text
               AND b.operational_readiness='blocked'
               AND b.last_evaluated_at IS NOT NULL;
            IF paired_count<>1
               OR NEW.resource_ref->>'resourceType'<>'CapabilityBinding'
               OR NEW.resource_ref->>'resourceId'<>NEW.result_ref->>'resourceId'
               OR NEW.result_ref->>'resourceType'<>'CapabilityBindingReadiness'
               OR NEW.created_by IS DISTINCT FROM session_user
            THEN RAISE EXCEPTION 'CAPABILITY_EVALUATE_RECEIPT_UNPAIRED'
                 USING ERRCODE='42501';
            END IF;
          END IF;
          RETURN NEW;
        END $$""").format(sql.Identifier(paired)))
    admin.execute(sql.SQL("ALTER FUNCTION public.{}() OWNER TO {}")
                  .format(sql.Identifier(paired), sql.Identifier(definer)))
    admin.execute(sql.SQL("""CREATE FUNCTION public.{}() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE receipt_count integer;
        BEGIN
          IF NEW.last_evaluated_at IS DISTINCT FROM OLD.last_evaluated_at THEN
            SELECT count(*) INTO receipt_count
              FROM public.aip_agent_registry_receipt r
             WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
               AND r.operation='capability_binding.evaluate'
               AND r.result_ref->>'resourceId'=NEW.binding_id
               AND r.result_ref->>'revision'=NEW.version::text
               AND r.xmin::text=pg_catalog.pg_current_xact_id()::text;
            IF receipt_count<>1
            THEN RAISE EXCEPTION 'CAPABILITY_BINDING_RECEIPT_REQUIRED'
                 USING ERRCODE='42501';
            END IF;
          END IF;
          RETURN NEW;
        END $$""").format(sql.Identifier(binding_pair)))
    admin.execute(sql.SQL("ALTER FUNCTION public.{}() OWNER TO {}")
                  .format(sql.Identifier(binding_pair), sql.Identifier(definer)))
    admin.execute(sql.SQL("REVOKE ALL ON FUNCTION public.{}() FROM PUBLIC")
                  .format(sql.Identifier(identity)))
    admin.execute(sql.SQL("REVOKE ALL ON FUNCTION public.{}() FROM PUBLIC")
                  .format(sql.Identifier(paired)))
    admin.execute(sql.SQL("REVOKE ALL ON FUNCTION public.{}() FROM PUBLIC")
                  .format(sql.Identifier(binding_pair)))
    admin.execute(sql.SQL("""CREATE TRIGGER {} BEFORE INSERT ON aip_agent_registry_receipt
        FOR EACH ROW EXECUTE FUNCTION public.{}()""")
                  .format(sql.Identifier(identity), sql.Identifier(identity)))
    admin.execute(sql.SQL("""CREATE CONSTRAINT TRIGGER {} AFTER INSERT
        ON aip_agent_registry_receipt DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.{}()""")
                  .format(sql.Identifier(paired), sql.Identifier(paired)))
    admin.execute(sql.SQL("""CREATE CONSTRAINT TRIGGER {} AFTER UPDATE
        ON aip_capability_binding DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.{}()""")
                  .format(sql.Identifier(binding_pair), sql.Identifier(binding_pair)))
    return identity, paired, binding_pair


def _drop_b67_receipt_guards(admin, names):
    for name, table in zip(names, ("aip_agent_registry_receipt",
                                   "aip_agent_registry_receipt",
                                   "aip_capability_binding")):
        admin.execute(sql.SQL("DROP TRIGGER {} ON {}")
                      .format(sql.Identifier(name), sql.Identifier(table)))
        admin.execute(sql.SQL("DROP FUNCTION public.{}()")
                      .format(sql.Identifier(name)))


def _assert_b67_ordinary_receipt_denied(
    *, admin, restricted_parts, scope, binding, key,
):
    issuer = "b67_issuer_" + secrets.token_hex(4)
    password = secrets.token_urlsafe(32)
    policy = "b67_policy_" + secrets.token_hex(4)
    admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                  .format(sql.Identifier(issuer), sql.Literal(password)))
    try:
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}")
                      .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT,INSERT ON aip_agent_registry_receipt TO {}")
                      .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT,UPDATE ON aip_capability_binding TO {}")
                      .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("CREATE POLICY {} ON aip_agent_registry_receipt TO {} "
                              "USING(org_id=current_setting('aos.org_id',true) AND "
                              "project_id=current_setting('aos.project_id',true)) "
                              "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                              "project_id=current_setting('aos.project_id',true))")
                      .format(sql.Identifier(policy), sql.Identifier(issuer)))
        admin.execute(sql.SQL("CREATE POLICY {} ON aip_capability_binding TO {} "
                              "USING(org_id=current_setting('aos.org_id',true) AND "
                              "project_id=current_setting('aos.project_id',true)) "
                              "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                              "project_id=current_setting('aos.project_id',true))")
                      .format(sql.Identifier(policy + "_binding"), sql.Identifier(issuer)))
        issuer_parts = dict(restricted_parts, user=issuer, password=password)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(**issuer_parts, row_factory=dict_row) as limited:
                limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                "set_config('aos.project_id',%s,true)", scope.key)
                limited.execute("""INSERT INTO aip_agent_registry_receipt(
                    org_id,project_id,receipt_id,operation,idempotency_key,
                    request_hash,resource_ref,result_ref,status,created_by,created_at)
                    VALUES(%s,%s,%s,'capability_binding.evaluate',%s,%s,
                    %s::jsonb,%s::jsonb,'applied',%s,clock_timestamp())""",
                    (*scope.key, "b67-" + key, "b67-" + key, "f" * 64,
                     json.dumps({"resourceType": "CapabilityBinding", "resourceId": binding}),
                     json.dumps({"resourceType": "CapabilityBindingReadiness",
                                 "resourceId": binding, "revision": "2"}), issuer))
        assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
            "WHERE idempotency_key=%s", ("b67-" + key,)).fetchone()["n"] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(**issuer_parts, row_factory=dict_row) as limited:
                limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                "set_config('aos.project_id',%s,true)", scope.key)
                limited.execute("""UPDATE aip_capability_binding SET
                    operational_readiness='blocked',
                    last_evaluated_at=clock_timestamp(),version=version+1
                    WHERE org_id=%s AND project_id=%s AND binding_id=%s
                      AND version=2""", (*scope.key, binding))
    finally:
        admin.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_agent_registry_receipt")
                      .format(sql.Identifier(policy)))
        admin.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_capability_binding")
                      .format(sql.Identifier(policy + "_binding")))
        admin.execute(sql.SQL("DROP OWNED BY {}") .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("DROP ROLE IF EXISTS {}") .format(sql.Identifier(issuer)))
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",
                             (issuer,)).fetchone() is None


def _assert_ordinary_issuer_cannot_forge_available(
    *, admin, restricted_parts, scope, binding, key,
):
    issuer = "b62b_issuer_" + secrets.token_hex(4)
    password = secrets.token_urlsafe(32)
    policy = "b62b_policy_" + secrets.token_hex(4)
    tables = ("aip_capability_binding", "aip_agent_registry_receipt")
    admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                  .format(sql.Identifier(issuer), sql.Literal(password)))
    try:
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}")
                      .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT,UPDATE ON aip_capability_binding TO {}")
                      .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT,INSERT ON aip_agent_registry_receipt TO {}")
                      .format(sql.Identifier(issuer)))
        for table in tables:
            admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} "
                "USING(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true))")
                .format(sql.Identifier(policy + table), sql.Identifier(table),
                        sql.Identifier(issuer)))
        issuer_parts = dict(restricted_parts, user=issuer, password=password)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(**issuer_parts, row_factory=dict_row) as limited:
                with limited.transaction():
                    limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                    "set_config('aos.project_id',%s,true)", scope.key)
                    limited.execute("""UPDATE aip_capability_binding SET
                        operational_readiness='available',
                        dependency_snapshot_hash=%s,
                        readiness_reasons='[]'::jsonb,
                        last_evaluated_at=clock_timestamp(),
                        readiness_expires_at=clock_timestamp()+interval '15 minutes',
                        version=version+1
                        WHERE org_id=%s AND project_id=%s AND binding_id=%s AND version=2""",
                        ("f" * 64, *scope.key, binding))
                    limited.execute("""INSERT INTO aip_agent_registry_receipt(
                        org_id,project_id,receipt_id,operation,idempotency_key,
                        request_hash,resource_ref,result_ref,status,created_by,created_at)
                        VALUES(%s,%s,%s,'capability_binding.evaluate',%s,%s,
                        %s::jsonb,%s::jsonb,'applied',%s,clock_timestamp())""",
                        (*scope.key, "b62b-" + key, "b62b-" + key, "f" * 64,
                         json.dumps({"resourceType": "CapabilityBinding", "resourceId": binding}),
                         json.dumps({"resourceType": "CapabilityBindingReadiness",
                                     "resourceId": binding, "revision": "3"}), issuer))
    finally:
        for table in tables:
            admin.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}")
                          .format(sql.Identifier(policy + table), sql.Identifier(table)))
        admin.execute(sql.SQL("DROP OWNED BY {}") .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("DROP ROLE IF EXISTS {}") .format(sql.Identifier(issuer)))
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",
                             (issuer,)).fetchone() is None


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


def _assert_evaluate_first_revoke_waits(
    *, admin, registry, restricted_parts, call, scope, installation, etag,
    growth, binding, key,
):
    first_key = key + "-first"
    after_key = key + "-after"

    def revoke():
        return registry.revoke(
            publisher=growth.publisher, bundle_id=growth.bundle_id,
            version=growth.version, actor="b50-test-only-revoker",
            roles={"asset-publisher"}, publisher_scopes={growth.publisher},
            reason="b50 restricted evaluate commits before Registry revoke",
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
            with limited.transaction():
                limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                "set_config('aos.project_id',%s,true)", scope.key)
                assert limited.execute(call, (*scope.key, installation, etag,
                                              binding, 2, first_key)).fetchone()["revision"] == 3
                assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                    "WHERE idempotency_key=%s", (first_key,)).fetchone()["n"] == 0
                revoked = pool.submit(revoke)
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    waiting = admin.execute("""SELECT count(*) AS n FROM pg_locks
                        WHERE locktype='advisory' AND classid=228 AND objid=1
                          AND NOT granted""").fetchone()["n"]
                    if waiting:
                        break
                    assert not revoked.done(), "revoke did not wait for evaluate"
                    time.sleep(0.025)
                else:
                    raise AssertionError("Registry revoke advisory wait not observed")
            assert revoked.result(timeout=10)["status"] == "revoked"
    assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
        "WHERE idempotency_key=%s", (first_key,)).fetchone()["n"] == 1
    assert admin.execute("SELECT version FROM aip_capability_binding "
        "WHERE binding_id=%s", (binding,)).fetchone()["version"] == 3
    with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
        with limited.transaction():
            limited.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            limited.execute("SELECT set_config('aos.org_id',%s,true),"
                            "set_config('aos.project_id',%s,true)", scope.key)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with limited.transaction():
                    limited.execute(call, (*scope.key, installation, etag,
                                           binding, 3, after_key))
    assert admin.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
        "WHERE idempotency_key=%s", (after_key,)).fetchone()["n"] == 0
    assert admin.execute("SELECT version FROM aip_capability_binding "
        "WHERE binding_id=%s", (binding,)).fetchone()["version"] == 3
