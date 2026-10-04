"""Test-only composition of an installation lock and blocked Binding receipt."""

import json
import secrets
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from aos_api.db import get_dsn, connect
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest


def assert_restricted_blocked_evaluate_composes_lock(
    *, scope, role, restricted_parts, lock_function, installation, etag, growth,
    registry=None, concurrent_revoke=False, evaluate_first=False,
    forged_available=False, paired_receipt=False, license_authority=False,
    license_revoke_first=False, license_evaluate_first=False,
    license_epoch_fence=False, license_replay_probe=False,
    license_transaction_probe=False, license_receipt_guard=False,
    license_db_fence_probe=False, license_db_trigger_candidate=False,
    license_lock_entry_probe=False, license_lock_entry_candidate=False,
    license_composition_probe=False, license_pre_replay_lock=False,
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
    fence_table = 'b71_license_epoch_' + suffix if license_epoch_fence else None
    if license_authority:
        scoped_tables += ("aip_evidence_bundle_revision",
                          "aip_evidence_bundle_revoke_event")
    if fence_table:
        scoped_tables += (fence_table,)
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
        if fence_table:
            license_check = sql.SQL("""PERFORM 1 FROM public.{}
                WHERE org_id=p_org AND project_id=p_project AND bundle_id={}
                  AND revision=1 AND content_hash={} FOR SHARE;
                IF NOT FOUND THEN RAISE EXCEPTION 'license epoch unavailable'
                  USING ERRCODE='42501'; END IF;""").format(
                    sql.Identifier(fence_table), sql.Literal(license_id),
                    sql.Literal(license_hash)) + license_check
    receipt_guards = None
    with psycopg.connect(get_dsn(), autocommit=True, row_factory=dict_row) as admin:
        if fence_table:
            admin.execute(sql.SQL("""CREATE TABLE public.{}(
                org_id text NOT NULL, project_id text NOT NULL, bundle_id text NOT NULL,
                revision bigint NOT NULL, content_hash text NOT NULL, epoch bigint NOT NULL,
                PRIMARY KEY(org_id,project_id,bundle_id,revision,content_hash))""").format(
                    sql.Identifier(fence_table)))
            admin.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(fence_table)))
            admin.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(fence_table)))
            admin.execute(sql.SQL('REVOKE ALL ON {} FROM PUBLIC,aos_runtime').format(sql.Identifier(fence_table)))
            admin.execute(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,1,%s,0)').format(
                sql.Identifier(fence_table)), (*scope.key, license_id, license_hash))
            admin.execute(sql.SQL('GRANT SELECT,UPDATE(epoch) ON {} TO aos_runtime').format(
                sql.Identifier(fence_table)))
            admin.execute(sql.SQL("CREATE POLICY b71_writer ON {} TO aos_runtime "
                "USING(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true))").format(sql.Identifier(fence_table)))
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
            if license_revoke_first or license_evaluate_first:
                admin.execute("""UPDATE aip_evidence_bundle_revision
                    SET brief_ref=%s::jsonb, marking='[]'::jsonb
                    WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=1""",
                    (json.dumps({'resourceType': 'TaskBriefRevision',
                                 'resourceId': 'b70-test-only', 'revision': 1,
                                 'contentHash': 'd' * 64}), *scope.key, license_id))
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
                for table in ("aip_evidence_bundle_revision", "aip_evidence_bundle_revoke_event"):
                    admin.execute(sql.SQL("GRANT SELECT ON {} TO {}")
                                  .format(sql.Identifier(table), sql.Identifier(definer)))
                if fence_table:
                    admin.execute(sql.SQL('GRANT SELECT,UPDATE(epoch) ON {} TO {}').format(
                        sql.Identifier(fence_table), sql.Identifier(definer)))
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
                if license_transaction_probe:
                    _assert_license_transaction_contract(
                        admin=admin, scope=scope, fence_table=fence_table,
                        template_license=license_id, license_hash=license_hash,
                        receipt_guard=license_receipt_guard, db_fence_probe=license_db_fence_probe,
                        db_trigger_candidate=license_db_trigger_candidate,
                        lock_entry_probe=license_lock_entry_probe,
                        lock_entry_candidate=license_lock_entry_candidate,
                        composition_probe=license_composition_probe, pre_replay_lock=license_pre_replay_lock,
                        race_args=dict(admin=admin, restricted_parts=restricted_parts, call=call,
                            scope=scope, installation=installation, etag=etag, binding=binding,
                            key=key, license_id=license_id, license_hash=license_hash,
                            evaluate_first=license_evaluate_first, fence_table=fence_table)
                            if license_composition_probe else None,
                    )
                    if license_composition_probe:
                        return
                if license_revoke_first or license_evaluate_first:
                    _assert_license_race(
                        admin=admin, restricted_parts=restricted_parts, call=call,
                        scope=scope, installation=installation, etag=etag,
                        binding=binding, key=key, license_id=license_id,
                        license_hash=license_hash, evaluate_first=license_evaluate_first,
                        fence_table=fence_table, replay_probe=license_replay_probe,
                    )
                    return
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
            if fence_table:
                admin.execute(sql.SQL('DROP TABLE {}').format(sql.Identifier(fence_table)))


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


def _assert_license_race(
    *, admin, restricted_parts, call, scope, installation, etag,
    binding, key, license_id, license_hash, evaluate_first,
    fence_table=None, replay_probe=False, writer_lock_function=None, event_driven=False,
):
    """Probe the real Evidence writer; no direct revoke INSERT or current DB."""
    writer_pids = Queue()
    evaluator_pids = Queue()
    revoke_key = key + '-b70-revoke'
    evaluate_key = key + '-b70-evaluate'

    selected_writer_key = [revoke_key]

    @contextmanager
    def writer_connection(selected_scope):
        with connect(selected_scope) as conn:
            conn.execute("SET LOCAL statement_timeout='10s'")
            conn.execute("SET LOCAL lock_timeout='8s'")
            writer_pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            if writer_lock_function:
                conn.execute(sql.SQL('SELECT public.{}(%s,%s,%s,1,%s)').format(sql.Identifier(writer_lock_function)),
                             (*selected_scope.key, license_id, license_hash))
            if fence_table and replay_probe:
                assert conn.execute(sql.SQL('SELECT epoch FROM {} WHERE org_id=%s '
                    'AND project_id=%s AND bundle_id=%s AND revision=1 AND content_hash=%s '
                    'FOR UPDATE').format(sql.Identifier(fence_table)),
                    (*scope.key, license_id, license_hash)).fetchone() is not None
                replay = conn.execute('SELECT 1 FROM aip_production_contract_receipt '
                    "WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.revoke' "
                    'AND idempotency_key=%s', (*scope.key, selected_writer_key[0])).fetchone()
            else:
                replay = None
            if fence_table and not replay and not event_driven:
                updated = conn.execute(sql.SQL('UPDATE {} SET epoch=epoch+1 '
                    'WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=1 '
                    'AND content_hash=%s').format(sql.Identifier(fence_table)),
                    (*scope.key, license_id, license_hash))
                assert updated.rowcount == 1, 'exact epoch source missing'
            yield conn

    def revoke():
        return AipProductionContractStore(connect_factory=writer_connection).revoke_evidence_bundle(
            scope, 'b70-test-only-revoker', license_id, revoke_key,
            RevokeEvidenceBundleRequest(expected_revision=1,
                                        expected_content_hash=license_hash,
                                        reason='b70 isolated concurrent revoke'),
        )

    def evaluate():
        try:
            with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                with limited.transaction():
                    limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                    limited.execute("SET LOCAL statement_timeout='10s'")
                    limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                    "set_config('aos.project_id',%s,true)", scope.key)
                    evaluator_pids.put(limited.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
                    limited.execute(call, (*scope.key, installation, etag,
                                          binding, 2, evaluate_key))
            return 'applied'
        except psycopg.Error as exc:
            return exc.sqlstate

    if not evaluate_first:
        with psycopg.connect(get_dsn(), autocommit=True) as blocker:
            blocker.execute('BEGIN')
            try:
                blocker_pid = blocker.execute('SELECT pg_backend_pid()').fetchone()[0]
                blocker.execute('SELECT 1 FROM bundle_installation WHERE org_id=%s '
                                'AND project_id=%s AND installation_id=%s FOR UPDATE',
                                (*scope.key, installation))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    evaluated = pool.submit(evaluate)
                    pid = evaluator_pids.get(timeout=8)
                    try:
                        deadline = time.monotonic() + 8
                        while time.monotonic() < deadline:
                            blocked = admin.execute('SELECT %s=ANY(pg_blocking_pids(%s)) AS waiting',
                                                    (blocker_pid, pid)).fetchone()['waiting']
                            if blocked:
                                break
                            assert not evaluated.done(), 'evaluate did not reach Installation wait'
                            time.sleep(0.025)
                        else:
                            raise AssertionError('exact Installation lock wait not observed')
                        assert revoke().revoked is True
                        assert admin.execute('SELECT count(*) AS n FROM aip_production_contract_receipt '
                            "WHERE operation='evidence_bundle.revoke' AND idempotency_key=%s",
                            (revoke_key,)).fetchone()['n'] == 1
                    finally:
                        blocker.execute('ROLLBACK')
                    outcome = evaluated.result(timeout=12)
                receipts = admin.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt '
                    'WHERE idempotency_key=%s', (evaluate_key,)).fetchone()['n']
                version = admin.execute('SELECT version FROM aip_capability_binding WHERE binding_id=%s',
                                        (binding,)).fetchone()['version']
                assert (outcome, receipts, version) in {('42501', 0, 2), ('40001', 0, 2)}, (
                    'B70_STALE_SNAPSHOT_AFTER_COMMITTED_LICENSE_REVOKE', outcome, receipts, version)
                if fence_table:
                    assert outcome == '40001', 'epoch fence must reject the stale serializable snapshot'
            finally:
                blocker.execute('ROLLBACK')
    else:
        waiting = False
        with ThreadPoolExecutor(max_workers=1) as pool:
            with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
                with limited.transaction():
                    limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                    limited.execute("SET LOCAL statement_timeout='10s'")
                    limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                    "set_config('aos.project_id',%s,true)", scope.key)
                    limited_pid = limited.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                    assert limited.execute(call, (*scope.key, installation, etag,
                        binding, 2, evaluate_key)).fetchone()['revision'] == 3
                    assert admin.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt '
                        'WHERE idempotency_key=%s', (evaluate_key,)).fetchone()['n'] == 0
                    revoked = pool.submit(revoke)
                    writer_pid = writer_pids.get(timeout=8)
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        waiting = admin.execute('SELECT %s=ANY(pg_blocking_pids(%s)) AS waiting',
                                                (limited_pid, writer_pid)).fetchone()['waiting']
                        if waiting or revoked.done():
                            break
                        time.sleep(0.025)
                result = revoked.result(timeout=12)
            assert result.revoked is True
        assert waiting, 'B70_LICENSE_WRITER_COMMITTED_BEFORE_EVALUATOR_WITHOUT_COMMON_LOCK'
        assert admin.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt '
            'WHERE idempotency_key=%s', (evaluate_key,)).fetchone()['n'] == 1
        with psycopg.connect(**restricted_parts, row_factory=dict_row) as limited:
            with limited.transaction():
                limited.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                limited.execute("SELECT set_config('aos.org_id',%s,true),"
                                "set_config('aos.project_id',%s,true)", scope.key)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with limited.transaction():
                        limited.execute(call, (*scope.key, installation, etag,
                                              binding, 3, evaluate_key + '-after'))
        assert admin.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt '
            'WHERE idempotency_key=%s', (evaluate_key + '-after',)).fetchone()['n'] == 0

    if replay_probe:
        def snapshot():
            epoch = admin.execute(sql.SQL('SELECT epoch FROM {} WHERE org_id=%s '
                'AND project_id=%s AND bundle_id=%s AND revision=1 AND content_hash=%s').format(
                sql.Identifier(fence_table)), (*scope.key, license_id, license_hash)).fetchone()['epoch']
            events = admin.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event '
                'WHERE org_id=%s AND project_id=%s AND bundle_id=%s',
                (*scope.key, license_id)).fetchone()['n']
            receipts = admin.execute('SELECT count(*) AS n FROM aip_production_contract_receipt '
                "WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.revoke' "
                'AND idempotency_key=%s', (*scope.key, revoke_key)).fetchone()['n']
            return epoch, events, receipts
        before = snapshot()
        assert before == (1, 1, 1)
        assert revoke().revoked is True
        assert snapshot() == before, 'B72_SAME_KEY_REPLAY_ADVANCED_EPOCH'

        from aos_api.aip_production_contract_store import ProductionContractDependencyBlocked
        selected_writer_key[0] = revoke_key + '-wrong-hash'
        with pytest.raises(ProductionContractDependencyBlocked):
            AipProductionContractStore(connect_factory=writer_connection).revoke_evidence_bundle(
                scope, 'b72-test-only', license_id, revoke_key + '-wrong-hash',
                RevokeEvidenceBundleRequest(expected_revision=1,
                    expected_content_hash='e' * 64, reason='b72 wrong hash rollback'))
        assert snapshot() == before
        assert admin.execute('SELECT count(*) AS n FROM aip_production_contract_receipt '
            'WHERE idempotency_key=%s', (revoke_key + '-wrong-hash',)).fetchone()['n'] == 0

        class CommitFailure:
            def __init__(self, conn):
                self.conn = conn
            def __getattr__(self, name):
                return getattr(self.conn, name)
            def commit(self):
                raise RuntimeError('b72 forced precommit rollback')

        @contextmanager
        def failing_connection(selected_scope):
            with writer_connection(selected_scope) as conn:
                yield CommitFailure(conn)

        selected_writer_key[0] = revoke_key + '-forced-error'
        with pytest.raises(RuntimeError, match='b72 forced precommit rollback'):
            AipProductionContractStore(connect_factory=failing_connection).revoke_evidence_bundle(
                scope, 'b72-test-only', license_id, revoke_key + '-forced-error',
                RevokeEvidenceBundleRequest(expected_revision=1,
                    expected_content_hash=license_hash, reason='b72 forced rollback'))
        assert snapshot() == before
        assert admin.execute('SELECT count(*) AS n FROM aip_production_contract_receipt '
            'WHERE idempotency_key=%s', (revoke_key + '-forced-error',)).fetchone()['n'] == 0


def _assert_license_transaction_contract(
    *, admin, scope, fence_table, template_license, license_hash, receipt_guard,
    db_fence_probe=False, db_trigger_candidate=False, lock_entry_probe=False, lock_entry_candidate=False,
    composition_probe=False, pre_replay_lock=False, race_args=None,
):
    """Fresh source, independent writer closures, real Store and bounded PID waits."""
    from aos_api.aip_production_contract_store import ProductionContractIdempotencyConflict

    bundle = 'b73-license-' + secrets.token_hex(6)
    key = bundle + '-revoke'
    pids = Queue()
    admin.execute("""INSERT INTO aip_evidence_bundle_revision
        (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
         item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
         license_summary,content_hash,lifecycle,created_by)
        SELECT org_id,project_id,%s,revision,brief_ref,subject_refs,cutoff_at,
         item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
         license_summary,content_hash,lifecycle,created_by
        FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s
          AND bundle_id=%s AND revision=1""", (bundle, *scope.key, template_license))
    admin.execute(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,1,%s,0)').format(
        sql.Identifier(fence_table)), (*scope.key, bundle, license_hash))

    def snapshot():
        epoch = admin.execute(sql.SQL('SELECT epoch FROM {} WHERE org_id=%s '
            'AND project_id=%s AND bundle_id=%s AND revision=1 AND content_hash=%s').format(
            sql.Identifier(fence_table)), (*scope.key, bundle, license_hash)).fetchone()['epoch']
        event = admin.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event '
            'WHERE org_id=%s AND project_id=%s AND bundle_id=%s',
            (*scope.key, bundle)).fetchone()['n']
        receipts = admin.execute('SELECT count(*) AS n FROM aip_production_contract_receipt '
            "WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.revoke' "
            "AND result_ref->>'resourceId'=%s", (*scope.key, bundle)).fetchone()['n']
        return epoch, event, receipts

    def invoke(request_key, *, reason='b73 concurrent same body', fail_commit=False, unwrapped=False):
        @contextmanager
        def connection(selected_scope):
            with connect(selected_scope) as conn:
                conn.execute("SET LOCAL statement_timeout='10s'")
                conn.execute("SET LOCAL lock_timeout='8s'")
                pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
                if receipt_guard and not unwrapped:
                    assert conn.execute(sql.SQL('SELECT epoch FROM {} WHERE org_id=%s '
                        'AND project_id=%s AND bundle_id=%s AND revision=1 AND content_hash=%s '
                        'FOR UPDATE').format(sql.Identifier(fence_table)),
                        (*selected_scope.key, bundle, license_hash)).fetchone() is not None
                    replay = conn.execute('SELECT 1 FROM aip_production_contract_receipt '
                        "WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.revoke' "
                        'AND idempotency_key=%s', (*selected_scope.key, request_key)).fetchone()
                else:
                    replay = None
                if not replay and not unwrapped:
                    assert conn.execute(sql.SQL('UPDATE {} SET epoch=epoch+1 WHERE org_id=%s '
                        'AND project_id=%s AND bundle_id=%s AND revision=1 AND content_hash=%s').format(
                        sql.Identifier(fence_table)),
                        (*selected_scope.key, bundle, license_hash)).rowcount == 1
                if fail_commit:
                    class CommitFailure:
                        def __getattr__(self, name):
                            return getattr(conn, name)
                        def commit(self):
                            # Real writer has inserted its event and receipt in this transaction.
                            assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event '
                                'WHERE org_id=%s AND project_id=%s AND bundle_id=%s',
                                (*selected_scope.key, bundle)).fetchone()['n'] == 1
                            assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt '
                                "WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.revoke' "
                                'AND idempotency_key=%s',
                                (*selected_scope.key, request_key)).fetchone()['n'] == 1
                            raise RuntimeError('b73 forced first-event precommit rollback')
                    yield CommitFailure()
                else:
                    yield conn
        return AipProductionContractStore(connect_factory=connection).revoke_evidence_bundle(
            scope, 'b73-test-only', bundle, request_key,
            RevokeEvidenceBundleRequest(expected_revision=1,
                expected_content_hash=license_hash, reason=reason))

    assert snapshot() == (0, 0, 0)
    if db_trigger_candidate:
        _assert_license_db_trigger(admin=admin, scope=scope, fence_table=fence_table,
            template_license=template_license, license_hash=license_hash, bundle=bundle,
            lock_entry_probe=lock_entry_probe, lock_entry_candidate=lock_entry_candidate,
            composition_probe=composition_probe, pre_replay_lock=pre_replay_lock, race_args=race_args)
        return
    if db_fence_probe:
        assert invoke(key, unwrapped=True).revoked is True
        assert snapshot() == (1, 1, 1), ('B74_REAL_STORE_BYPASSED_EPOCH_FENCE', snapshot())
        return
    with pytest.raises(RuntimeError, match='b73 forced first-event precommit rollback'):
        invoke(key + '-failure', fail_commit=True)
    assert snapshot() == (0, 0, 0), 'B73_FIRST_EVENT_ROLLBACK_LEAK'
    pids.get(timeout=1)  # Discard completed failure PID before the two concurrent writers.
    with psycopg.connect(get_dsn(), autocommit=True) as blocker:
        blocker.execute('BEGIN')
        blocker_pid = blocker.execute('SELECT pg_backend_pid()').fetchone()[0]
        blocker.execute(sql.SQL('SELECT epoch FROM {} WHERE org_id=%s AND project_id=%s '
            'AND bundle_id=%s AND revision=1 AND content_hash=%s FOR UPDATE').format(
            sql.Identifier(fence_table)), (*scope.key, bundle, license_hash))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke, key) for _ in range(2)]
            try:
                writer_pids = [pids.get(timeout=8) for _ in range(2)]
                assert len(set(writer_pids)) == 2
                deadline = time.monotonic() + 6
                while time.monotonic() < deadline:
                    graph = {pid: admin.execute('SELECT pg_blocking_pids(%s) AS blockers',
                        (pid,)).fetchone()['blockers'] for pid in writer_pids}
                    def reaches_blocker(pid, seen=None):
                        seen = set() if seen is None else seen
                        if pid == blocker_pid:
                            return True
                        if pid in seen:
                            return False
                        return any(reaches_blocker(parent, seen | {pid})
                                   for parent in graph.get(pid, []))
                    if all(reaches_blocker(pid) for pid in writer_pids):
                        break
                    assert not any(f.done() for f in futures), 'writer escaped exact epoch blocker'
                    time.sleep(0.025)
                else:
                    raise AssertionError(('two exact writer PIDs did not wait on epoch blocker', graph))
            finally:
                blocker.execute('ROLLBACK')
            assert all(f.result(timeout=12).revoked for f in futures)
    assert snapshot() == (1, 1, 1), ('B73_DUPLICATE_KEY_EPOCH_DRIFT', snapshot())
    with pytest.raises(ProductionContractIdempotencyConflict):
        invoke(key, reason='b73 conflicting body')
    assert snapshot() == (1, 1, 1), 'B73_CONFLICT_CHANGED_AUTHORITY'


def _assert_license_db_trigger(*, admin, scope, fence_table, template_license, license_hash, bundle,
                              lock_entry_probe=False, lock_entry_candidate=False,
                              composition_probe=False, pre_replay_lock=False, race_args=None):
    suffix = secrets.token_hex(5)
    owner = 'b75_owner_' + suffix
    function = 'b75_fence_' + suffix
    lock_function = function + '_lock'
    policy = 'b75_tenant_' + suffix
    event_table = 'aip_evidence_bundle_revoke_event'
    source_table = 'aip_evidence_bundle_revision'
    created_policies = []
    admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(owner)))
    try:
        admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(owner)))
        for table in (source_table, fence_table):
            admin.execute(sql.SQL('GRANT SELECT ON public.{} TO {}').format(sql.Identifier(table), sql.Identifier(owner)))
            admin.execute(sql.SQL("CREATE POLICY {} ON public.{} TO {} USING ("
                "org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(
                sql.Identifier(policy), sql.Identifier(table), sql.Identifier(owner)))
            created_policies.append(table)
        admin.execute(sql.SQL('GRANT UPDATE(epoch) ON public.{} TO {}').format(sql.Identifier(fence_table), sql.Identifier(owner)))
        admin.execute(sql.SQL('REVOKE UPDATE(epoch) ON public.{} FROM aos_runtime').format(sql.Identifier(fence_table)))
        admin.execute(sql.SQL("""CREATE FUNCTION public.{}() RETURNS trigger
            LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $f$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM public.aip_evidence_bundle_revision
                WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND bundle_id=NEW.bundle_id
                  AND revision=NEW.revision AND content_hash=NEW.content_hash AND lifecycle='frozen')
                THEN RAISE EXCEPTION 'exact source unavailable' USING ERRCODE='42501'; END IF;
              UPDATE public.{} SET epoch=epoch+1 WHERE org_id=NEW.org_id AND project_id=NEW.project_id
                AND bundle_id=NEW.bundle_id AND revision=NEW.revision AND content_hash=NEW.content_hash;
              IF NOT FOUND THEN RAISE EXCEPTION 'exact epoch unavailable' USING ERRCODE='42501'; END IF;
              RETURN NEW;
            END $f$""").format(sql.Identifier(function), sql.Identifier(fence_table)))
        admin.execute(sql.SQL('ALTER FUNCTION public.{}() OWNER TO {}').format(sql.Identifier(function), sql.Identifier(owner)))
        admin.execute(sql.SQL('REVOKE ALL ON FUNCTION public.{}() FROM PUBLIC,aos_runtime').format(sql.Identifier(function)))
        condition = sql.SQL('') if composition_probe else sql.SQL('WHEN (NEW.bundle_id LIKE {}) ').format(sql.Literal(bundle + '%'))
        admin.execute(sql.SQL('CREATE TRIGGER {} BEFORE INSERT ON public.{} FOR EACH ROW {}EXECUTE FUNCTION public.{}()').format(
            sql.Identifier(function), sql.Identifier(event_table), condition, sql.Identifier(function)))
        if composition_probe:
            assert admin.execute('SELECT tgqual IS NULL AS unfiltered FROM pg_trigger WHERE tgname=%s',
                                 (function,)).fetchone()['unfiltered']
        writer_pids = Queue()
        attrs = admin.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=%s', (owner,)).fetchone()
        assert not any(attrs.values())
        proc = admin.execute('SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner '
            'FROM pg_proc WHERE oid=%s::regprocedure', ('public.' + function + '()',)).fetchone()
        assert proc['prosecdef'] and proc['owner'] == owner
        assert proc['proconfig'] == ['search_path=pg_catalog, public']
        assert not admin.execute("SELECT has_function_privilege('aos_runtime',%s,'EXECUTE') AS permitted",
            ('public.' + function + '()',)).fetchone()['permitted']
        flags = admin.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class '
            'WHERE oid=%s::regclass', ('public.' + fence_table,)).fetchone()
        assert all(flags.values())
        assert admin.execute("SELECT has_column_privilege('aos_runtime',%s,'epoch','UPDATE') AS permitted",
            ('public.' + fence_table,)).fetchone()['permitted'] is False

        def fresh(name, head=True):
            source = bundle + '-' + name
            admin.execute("""INSERT INTO aip_evidence_bundle_revision
                (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
                 item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
                 license_summary,content_hash,lifecycle,created_by)
                SELECT org_id,project_id,%s,revision,brief_ref,subject_refs,cutoff_at,
                 item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
                 license_summary,content_hash,lifecycle,created_by
                FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s
                AND bundle_id=%s AND revision=1""", (source, *scope.key, template_license))
            if head:
                admin.execute(sql.SQL('INSERT INTO public.{} VALUES(%s,%s,%s,1,%s,0)').format(sql.Identifier(fence_table)),
                              (*scope.key, source, license_hash))
            return source

        def state(source):
            row = admin.execute(sql.SQL('SELECT epoch FROM public.{} WHERE org_id=%s AND project_id=%s AND bundle_id=%s').format(
                sql.Identifier(fence_table)), (*scope.key, source)).fetchone()
            event = admin.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s', (source,)).fetchone()['n']
            receipts = admin.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE result_ref->>'resourceId'=%s", (source,)).fetchone()['n']
            return row['epoch'] if row else None, event, receipts

        def store(source, key, fail=False, concurrent=False, reason='b75 event fence'):
            @contextmanager
            def connection(selected_scope):
                with connect(selected_scope) as conn:
                    conn.execute("SET LOCAL statement_timeout='10s'")
                    conn.execute("SET LOCAL lock_timeout='8s'")
                    if concurrent:
                        writer_pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
                    if pre_replay_lock:
                        conn.execute(sql.SQL('SELECT public.{}(%s,%s,%s,1,%s)').format(sql.Identifier(lock_function)),
                                     (*selected_scope.key, source, license_hash))
                    if fail:
                        class Failure:
                            def __getattr__(self, name): return getattr(conn, name)
                            def commit(self):
                                assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',
                                                    (source,)).fetchone()['n'] == 1
                                assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt '
                                    'WHERE idempotency_key=%s', (key,)).fetchone()['n'] == 1
                                assert conn.execute(sql.SQL('SELECT epoch FROM public.{} WHERE bundle_id=%s').format(
                                    sql.Identifier(fence_table)), (source,)).fetchone()['epoch'] == 1
                                raise RuntimeError('b75 precommit rollback')
                        yield Failure()
                    else:
                        yield conn
            return AipProductionContractStore(connect_factory=connection).revoke_evidence_bundle(
                scope, 'b75-test-only', source, key, RevokeEvidenceBundleRequest(
                    expected_revision=1, expected_content_hash=license_hash, reason=reason))

        def raw(source, selected_scope=scope, content_hash=license_hash):
            with connect(selected_scope) as conn:
                conn.execute("SET LOCAL statement_timeout='10s'")
                conn.execute("""INSERT INTO aip_evidence_bundle_revoke_event
                    (org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor)
                    VALUES(%s,%s,%s,%s,1,%s,'b75 raw insert','b75-test-only')""",
                    (*selected_scope.key, 'b75-event-' + secrets.token_hex(5), source, content_hash))

        if lock_entry_candidate:
            admin.execute(sql.SQL('''CREATE FUNCTION public.{}(text,text,text,bigint,text) RETURNS void
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $l$
                BEGIN
                  PERFORM 1 FROM public.{} WHERE org_id=$1 AND project_id=$2 AND bundle_id=$3
                    AND revision=$4 AND content_hash=$5 FOR UPDATE;
                  IF NOT FOUND THEN RAISE EXCEPTION 'exact lock source unavailable' USING ERRCODE='42501'; END IF;
                END $l$''').format(sql.Identifier(lock_function), sql.Identifier(fence_table)))
            admin.execute(sql.SQL('ALTER FUNCTION public.{}(text,text,text,bigint,text) OWNER TO {}').format(
                sql.Identifier(lock_function), sql.Identifier(owner)))
            admin.execute(sql.SQL('REVOKE ALL ON FUNCTION public.{}(text,text,text,bigint,text) FROM PUBLIC').format(sql.Identifier(lock_function)))
            admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION public.{}(text,text,text,bigint,text) TO aos_runtime').format(sql.Identifier(lock_function)))
        source = fresh('store')
        if lock_entry_probe:
            with connect(scope) as conn:
                # Preserve the real privilege error: caller cannot reuse the old pre-replay lock.
                if lock_entry_candidate:
                    conn.execute(sql.SQL('SELECT public.{}(%s,%s,%s,1,%s)').format(sql.Identifier(lock_function)),
                                 (*scope.key, source, license_hash))
                else:
                    assert conn.execute(sql.SQL('SELECT epoch FROM public.{} WHERE org_id=%s '
                        'AND project_id=%s AND bundle_id=%s AND revision=1 AND content_hash=%s '
                        'FOR UPDATE').format(sql.Identifier(fence_table)),
                        (*scope.key, source, license_hash)).fetchone() is not None
            assert state(source) == (0, 0, 0), 'lock entry must not mutate epoch'
            if lock_entry_candidate:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connect(scope) as conn:
                        conn.execute(sql.SQL('SELECT public.{}(%s,%s,%s,1,%s)').format(sql.Identifier(lock_function)),
                                     (*scope.key, source, 'e' * 64))
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connect(type(scope)(org_id='dev-org', project_id='dev-project')) as conn:
                        conn.execute(sql.SQL('SELECT public.{}(%s,%s,%s,1,%s)').format(sql.Identifier(lock_function)),
                                     (*scope.key, source, license_hash))
                assert state(source) == (0, 0, 0)
        assert store(source, source).revoked
        assert state(source) == (1, 1, 1)
        assert store(source, source).revoked
        assert state(source) == (1, 1, 1)
        assert store(source, source + '-new-key').revoked
        assert state(source) == (1, 1, 2), 'new key on existing event must not advance epoch'
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connect(scope) as conn:
                conn.execute(sql.SQL('UPDATE public.{} SET epoch=42').format(sql.Identifier(fence_table)))
        raw_source = fresh('raw')
        raw(raw_source)
        assert state(raw_source) == (1, 1, 0)
        missing = fresh('missing', head=False)
        wrong = fresh('wrong-hash')
        foreign = fresh('canary')
        for selected_source, selected_scope, selected_hash, expected in (
            (missing, scope, license_hash, (None, 0, 0)),
            (wrong, scope, 'e' * 64, (0, 0, 0)),
            (foreign, type(scope)(org_id='dev-org', project_id='dev-project'), license_hash, (0, 0, 0)),
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                raw(selected_source, selected_scope, selected_hash)
            assert state(selected_source) == expected
        if composition_probe:
            from aos_api.aip_production_contract_store import ProductionContractIdempotencyConflict
            with pytest.raises(ProductionContractIdempotencyConflict):
                store(source, source, reason='b77 conflicting body')
            assert state(source) == (1, 1, 2)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                raw('unrelated-b77-' + suffix)
            concurrent_source = fresh('concurrent')
            def invoke_concurrent():
                try:
                    return 'ok' if store(concurrent_source, concurrent_source, concurrent=True).revoked else 'not-revoked'
                except psycopg.Error as exc:
                    return exc.sqlstate
            with psycopg.connect(get_dsn(), autocommit=True) as blocker:
                blocker.execute('BEGIN')
                blocker_pid = blocker.execute('SELECT pg_backend_pid()').fetchone()[0]
                blocker.execute(sql.SQL('SELECT epoch FROM public.{} WHERE bundle_id=%s FOR UPDATE').format(
                    sql.Identifier(fence_table)), (concurrent_source,))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(invoke_concurrent) for _ in range(2)]
                    try:
                        pids = [writer_pids.get(timeout=8) for _ in range(2)]
                        assert len(set(pids)) == 2
                        deadline = time.monotonic() + 6
                        while time.monotonic() < deadline:
                            graph = {pid: admin.execute('SELECT pg_blocking_pids(%s) AS blockers',
                                (pid,)).fetchone()['blockers'] for pid in pids}
                            def reaches(pid, seen=None):
                                seen = set() if seen is None else seen
                                if pid == blocker_pid: return True
                                if pid in seen: return False
                                return any(reaches(parent, seen | {pid}) for parent in graph.get(pid, []))
                            if all(reaches(pid) for pid in pids): break
                            assert not any(f.done() for f in futures), ('writer escaped blocker', graph)
                            time.sleep(0.025)
                        else:
                            raise AssertionError(('exact two-writer lock chain missing', graph))
                    finally:
                        blocker.execute('ROLLBACK')
                    outcomes = [f.result(timeout=12) for f in futures]
            assert outcomes == ['ok', 'ok'], ('B77_NO_PRE_REPLAY_LOCK_RACE', outcomes, state(concurrent_source))
            assert state(concurrent_source) == (1, 1, 1)
        failure = fresh('rollback')
        with pytest.raises(RuntimeError, match='b75 precommit rollback'):
            store(failure, failure, fail=True)
        assert state(failure) == (0, 0, 0)
        if composition_probe:
            assert pre_replay_lock and race_args is not None
            _assert_license_race(**race_args, writer_lock_function=lock_function, event_driven=True)
    finally:
        admin.execute(sql.SQL('DROP TRIGGER IF EXISTS {} ON public.{}').format(sql.Identifier(function), sql.Identifier(event_table)))
        admin.execute(sql.SQL('DROP FUNCTION IF EXISTS public.{}(text,text,text,bigint,text)').format(sql.Identifier(lock_function)))
        admin.execute(sql.SQL('DROP FUNCTION IF EXISTS public.{}()').format(sql.Identifier(function)))
        for table in created_policies:
            admin.execute(sql.SQL('DROP POLICY {} ON public.{}').format(sql.Identifier(policy), sql.Identifier(table)))
        admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(owner)))
        admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(owner)))
        admin.execute(sql.SQL('GRANT UPDATE(epoch) ON public.{} TO aos_runtime').format(sql.Identifier(fence_table)))
