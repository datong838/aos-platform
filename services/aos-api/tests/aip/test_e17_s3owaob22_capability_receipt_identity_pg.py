"""Disposable full-schema RED for independently logged-in Capability receipt forgery."""

import json
import secrets

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from aos_api.aip_agent_registry_contracts import PublishCapabilityRevisionRequest, VersionedAssetRef
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_contracts import ResourceRef
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


@pytest.mark.parametrize("evaluate_mode", [
    "legacy_blocked",
    pytest.param("require_trusted_blocked", marks=pytest.mark.xfail(
        strict=True, reason="valid-looking evaluate has no trusted current dependency origin")),
    pytest.param("require_trusted_available", marks=pytest.mark.xfail(
        strict=True, reason="available snapshot and Receipt can be forged without current signed dependencies")),
])
def test_clone_only_capability_operation_guard_preserves_normal_receipts(
    evaluate_mode,
):
    dsn = get_dsn()
    dbname = conninfo_to_dict(dsn)["dbname"]
    assert dbname.startswith("aos_test_") and dbname.endswith("_ti4_test")
    issuer = "s3owaob22_issuer_" + secrets.token_hex(4)
    runtime = "s3owaob22_runtime_" + secrets.token_hex(4)
    passwords = {name: secrets.token_urlsafe(24) for name in (issuer, runtime)}
    published_id = "b30.published." + secrets.token_hex(4)
    evaluated_id = "b30.evaluated." + secrets.token_hex(4)
    catalog_hash = "a" * 64
    published_ref = {"assetType": "CapabilityRevision", "assetId": published_id,
                     "revision": 1, "contentHash": catalog_hash}
    evaluated_ref = {**published_ref, "assetId": evaluated_id}

    def login(name):
        return psycopg.connect(make_conninfo(dsn, user=name, password=passwords[name]))

    def set_scope(conn, org="org-org"):
        conn.execute("SELECT set_config('aos.org_id',%s,true),"
                     "set_config('aos.project_id','dev-project',true)", (org,))

    def receipt(conn, operation, key, *, binding="b22-binding", revision="1",
                source_id=None, source_revision="1"):
        result_type = ("CapabilityBindingReadiness" if operation == "capability_binding.evaluate"
                       else "CapabilityBinding")
        is_create = operation == "capability_binding.create"
        source_type = "Capability" if is_create else "CapabilityBinding"
        source = {
            "resourceType": source_type,
            "resourceId": (published_id if source_id is None else source_id) if is_create else binding,
        }
        if is_create:
            source["revision"] = source_revision
        return conn.execute("""INSERT INTO aip_agent_registry_receipt(
            org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
            resource_ref,result_ref,status,created_by,created_at)
            VALUES('org-org','dev-project',%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                   'applied','b22-test',now())""",
            (key, operation, key, "f" * 64,
             json.dumps(source),
             json.dumps({"resourceType": result_type, "resourceId": binding,
                         "revision": revision})))

    def flush_guards(conn):
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def insert_binding(conn, binding, *, status="provisioning", version=1,
                       capability_ref=None):
        conn.execute("""INSERT INTO aip_capability_binding(
            org_id,project_id,binding_id,capability_ref,secret_ref,health,
            network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
            status,version)
            VALUES('org-org','dev-project',%s,%s::jsonb,'secret://test-only',
                   'unknown','test-only','test-only',1000,1,%s,%s)""",
            (binding, json.dumps(published_ref if capability_ref is None else capability_ref),
             status, version))

    with psycopg.connect(dsn, autocommit=True) as owner:
        owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','formal') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO twa_workspace(org_id,project_id,name) "
                      "VALUES('org-org','dev-project','formal') ON CONFLICT DO NOTHING")
        def asset(kind, name):
            return VersionedAssetRef(asset_type=kind, asset_id=name,
                                     revision=1, content_hash=catalog_hash)

        for capability_id, lifecycle in ((published_id, "published"),
                                         (evaluated_id, "evaluated")):
            AipCapabilityRegistry().publish(
                PublishCapabilityRevisionRequest(
                    capability_id=capability_id, revision=1, display_name="test-only",
                    lifecycle=lifecycle, input_schema_ref=asset("SchemaRevision", "input"),
                    output_schema_ref=asset("SchemaRevision", "output"),
                    risk_level="low", memory_policy_ref=asset("MemoryPolicy", "memory"),
                    handoff_policy_ref=asset("HandoffPolicy", "handoff"),
                    effect_review_schema_ref=asset("SchemaRevision", "effect"),
                    license_policy_ref=asset("LicensePolicy", "license"),
                    readiness_policy_ref=asset("ReadinessPolicy", "readiness"),
                    readiness="unknown", source_ref=ResourceRef(
                        resource_type="SolutionPack", resource_id="b30-test-only",
                        revision="1", authority="isolated-test"),
                    source_license="test-only", content_hash=catalog_hash),
                actor="b30-test-only")
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
            owner.execute(sql.SQL("GRANT SELECT ON aip_capability_revision TO {}")
                          .format(sql.Identifier(issuer)))
            owner.execute(sql.SQL("CREATE POLICY {} ON aip_capability_binding TO {} "
                "USING(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK(org_id=current_setting('aos.org_id',true) AND "
                "project_id=current_setting('aos.project_id',true))")
                .format(sql.Identifier(issuer + "_binding"), sql.Identifier(issuer)))
            owner.execute("ALTER TABLE aip_capability_binding "
                          "ADD COLUMN s3owaob24_last_operation text")
            owner.execute("""CREATE FUNCTION public.s3owaob24_mark_binding_operation()
                RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
                SET search_path=pg_catalog AS $$
                BEGIN
                  IF TG_OP='INSERT' THEN
                    IF NEW.status<>'provisioning' OR NEW.health<>'unknown'
                       OR NEW.version<>1 OR NEW.observed_at IS NOT NULL
                       OR NEW.last_evaluated_at IS NOT NULL
                       OR NEW.dependency_snapshot_hash IS NOT NULL
                       OR NEW.operational_readiness<>'unknown'
                       OR NEW.readiness_expires_at IS NOT NULL
                    THEN RAISE EXCEPTION 'CAPABILITY_CREATE_INITIAL_STATE_REQUIRED'
                        USING ERRCODE='42501';
                    END IF;
                    IF NOT (NEW.capability_ref ?& ARRAY[
                           'assetType','assetId','revision','contentHash'])
                       OR NEW.capability_ref - ARRAY[
                           'assetType','assetId','revision','contentHash'] <> '{}'::jsonb
                       OR NEW.capability_ref->>'assetType' <> 'CapabilityRevision'
                       OR jsonb_typeof(NEW.capability_ref->'revision') <> 'number'
                       OR (NEW.capability_ref->>'revision') !~ '^[1-9][0-9]*$'
                       OR (NEW.capability_ref->>'contentHash') !~ '^[0-9a-f]{64}$'
                    THEN RAISE EXCEPTION 'CAPABILITY_CREATE_EXACT_REF_REQUIRED'
                        USING ERRCODE='42501';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM public.aip_capability_revision c
                        WHERE c.capability_id=NEW.capability_ref->>'assetId'
                          AND c.revision=(NEW.capability_ref->>'revision')::bigint
                          AND c.content_hash=NEW.capability_ref->>'contentHash'
                          AND c.lifecycle='published'
                    ) THEN RAISE EXCEPTION 'CAPABILITY_CREATE_PUBLISHED_SOURCE_REQUIRED'
                        USING ERRCODE='42501';
                    END IF;
                    NEW.s3owaob24_last_operation := 'capability_binding.create';
                  ELSIF NEW.status IS DISTINCT FROM OLD.status
                     OR NEW.health IS DISTINCT FROM OLD.health THEN
                    IF NEW.last_evaluated_at IS DISTINCT FROM OLD.last_evaluated_at
                       OR NEW.dependency_snapshot_hash IS DISTINCT FROM OLD.dependency_snapshot_hash
                    THEN RAISE EXCEPTION 'CAPABILITY_OPERATION_MIXED' USING ERRCODE='42501';
                    END IF;
                    IF (to_jsonb(NEW) - ARRAY['status','health','observed_at',
                        'version','updated_at','s3owaob24_last_operation'])
                       IS DISTINCT FROM
                       (to_jsonb(OLD) - ARRAY['status','health','observed_at',
                        'version','updated_at','s3owaob24_last_operation'])
                    THEN RAISE EXCEPTION 'CAPABILITY_UPDATE_COLUMN_FORBIDDEN' USING ERRCODE='42501';
                    END IF;
                    NEW.s3owaob24_last_operation := 'capability_binding.update';
                  ELSIF NEW.last_evaluated_at IS DISTINCT FROM OLD.last_evaluated_at
                     AND NEW.last_evaluated_at IS NOT NULL
                     AND NEW.dependency_snapshot_hash IS NOT NULL
                     AND NEW.readiness_expires_at > NEW.last_evaluated_at THEN
                    IF (to_jsonb(NEW) - ARRAY['provider_ref','model_route_ref',
                        'runtime_policy_ref','eval_gate_ref','eval_contract_ref',
                        'license_evidence_refs','data_dependency_refs',
                        'tool_dependency_refs','budget_policy_ref','allow_degraded',
                        'dependency_snapshot_hash','operational_readiness',
                        'readiness_reasons','last_evaluated_at','readiness_expires_at',
                        'version','updated_at','s3owaob24_last_operation'])
                       IS DISTINCT FROM
                       (to_jsonb(OLD) - ARRAY['provider_ref','model_route_ref',
                        'runtime_policy_ref','eval_gate_ref','eval_contract_ref',
                        'license_evidence_refs','data_dependency_refs',
                        'tool_dependency_refs','budget_policy_ref','allow_degraded',
                        'dependency_snapshot_hash','operational_readiness',
                        'readiness_reasons','last_evaluated_at','readiness_expires_at',
                        'version','updated_at','s3owaob24_last_operation'])
                    THEN RAISE EXCEPTION 'CAPABILITY_EVALUATE_COLUMN_FORBIDDEN' USING ERRCODE='42501';
                    END IF;
                    NEW.s3owaob24_last_operation := 'capability_binding.evaluate';
                  ELSE
                    RAISE EXCEPTION 'CAPABILITY_OPERATION_SHAPE_REQUIRED' USING ERRCODE='42501';
                  END IF;
                  RETURN NEW;
                END $$""")
            owner.execute("REVOKE ALL ON FUNCTION public.s3owaob24_mark_binding_operation() FROM PUBLIC")
            owner.execute("""CREATE TRIGGER s3owaob24_mark_binding_operation
                BEFORE INSERT OR UPDATE ON aip_capability_binding FOR EACH ROW
                EXECUTE FUNCTION public.s3owaob24_mark_binding_operation()""")
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
                       OR (SELECT count(*) FROM public.aip_agent_registry_receipt r
                           WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
                             AND r.operation LIKE 'capability_binding.%'
                             AND r.result_ref->>'resourceId'=NEW.result_ref->>'resourceId'
                             AND r.result_ref->>'revision'=NEW.result_ref->>'revision'
                             AND r.xmin::text=pg_current_xact_id()::text) <> 1
                       OR NOT EXISTS (
                         SELECT 1 FROM public.aip_capability_binding b
                         WHERE b.org_id=NEW.org_id AND b.project_id=NEW.project_id
                           AND b.binding_id=NEW.result_ref->>'resourceId'
                           AND b.version::text=NEW.result_ref->>'revision'
                           AND b.s3owaob24_last_operation=NEW.operation
                           AND b.xmin::text=pg_current_xact_id()::text
                           AND ((NEW.operation='capability_binding.create'
                                 AND NEW.result_ref->>'resourceType'='CapabilityBinding'
                                 AND NEW.resource_ref->>'resourceType'='Capability'
                                 AND NEW.resource_ref->>'resourceId'=b.capability_ref->>'assetId'
                                 AND NEW.resource_ref->>'revision'=b.capability_ref->>'revision')
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
            owner.execute("""CREATE CONSTRAINT TRIGGER s3owaob22_receipt_guard
                AFTER INSERT ON aip_agent_registry_receipt
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
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
                    IF NEW.last_evaluated_at IS DISTINCT FROM OLD.last_evaluated_at
                       OR NEW.dependency_snapshot_hash IS DISTINCT FROM OLD.dependency_snapshot_hash
                    THEN RAISE EXCEPTION 'CAPABILITY_OPERATION_MIXED' USING ERRCODE='42501';
                    END IF;
                    expected_operation := 'capability_binding.update';
                  ELSIF NEW.last_evaluated_at IS DISTINCT FROM OLD.last_evaluated_at
                     AND NEW.last_evaluated_at IS NOT NULL
                     AND NEW.dependency_snapshot_hash IS NOT NULL
                     AND NEW.readiness_expires_at > NEW.last_evaluated_at THEN
                    expected_operation := 'capability_binding.evaluate';
                  ELSE
                    RAISE EXCEPTION 'CAPABILITY_OPERATION_SHAPE_REQUIRED' USING ERRCODE='42501';
                  END IF;
                  IF session_user<>{}
                     OR (SELECT count(*) FROM public.aip_agent_registry_receipt r
                         WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
                           AND r.operation LIKE 'capability_binding.%'
                           AND r.result_ref->>'resourceId'=NEW.binding_id
                           AND r.result_ref->>'revision'=NEW.version::text
                           AND r.xmin::text=pg_current_xact_id()::text) <> 1
                     OR NOT EXISTS (
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
                for operation, key in (
                    ("skill_binding.create", "b22-normal-skill"),
                    ("agent_run.create", "b22-normal-run"),
                    ("handoff.issue", "b22-normal-handoff"),
                ):
                    receipt(conn, operation, key)
            with login(runtime) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-runtime-forgery")
                    flush_guards(conn)
                conn.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(sql.SQL("SET ROLE {}") .format(sql.Identifier(issuer)))
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-unpaired")
                    flush_guards(conn)
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "agent_instance.create", "b22-issuer-other")
                    flush_guards(conn)
                conn.rollback()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    insert_binding(conn, "b22-no-receipt")
            with login(issuer) as conn:
                set_scope(conn)
                insert_binding(conn, "b22-binding")
                receipt(conn, "capability_binding.create", "b22-created")
            for binding, source_id, source_revision in (
                ("b32-wrong-source-id", "b30.other-capability", "1"),
                ("b32-wrong-source-revision", published_id, "2"),
                ("b32-missing-source-revision", published_id, None),
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with login(issuer) as conn:
                        set_scope(conn)
                        insert_binding(conn, binding)
                        receipt(conn, "capability_binding.create", binding,
                                binding=binding, source_id=source_id,
                                source_revision=source_revision)
            with login(issuer) as conn:
                set_scope(conn)
                assert conn.execute("SELECT session_user,current_user").fetchone() == (issuer, issuer)
                assert conn.execute("SELECT lifecycle FROM aip_capability_revision "
                    "WHERE capability_id=%s", (published_id,)).fetchone()[0] == "published"
                assert conn.execute("SELECT has_table_privilege(session_user, "
                    "'aip_capability_revision','INSERT')").fetchone()[0] is False
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute("ALTER TABLE aip_capability_binding DISABLE TRIGGER ALL")
                conn.rollback()
            for binding, bad_ref in (
                ("b30-empty-ref", {}),
                ("b30-evaluated-ref", evaluated_ref),
                ("b30-wrong-hash", {**published_ref, "contentHash": "b" * 64}),
                ("b30-wrong-revision", {**published_ref, "revision": 2}),
                ("b30-wrong-id", {**published_ref, "assetId": "b30.missing"}),
                ("b30-wrong-type", {**published_ref, "assetType": "Other"}),
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with login(issuer) as conn:
                        set_scope(conn)
                        insert_binding(conn, binding, capability_ref=bad_ref)
                        receipt(conn, "capability_binding.create", binding, binding=binding)
            for binding, status, version in (
                ("b29-active-create", "active", 1),
                ("b29-version-two-create", "provisioning", 2),
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with login(issuer) as conn:
                        set_scope(conn)
                        insert_binding(conn, binding, status=status, version=version)
                        receipt(conn, "capability_binding.create", binding,
                                binding=binding, revision=str(version))
            with login(issuer) as conn:
                set_scope(conn)
                conn.execute("""UPDATE aip_capability_binding SET status='suspended',
                    version=version+1 WHERE binding_id='b22-binding'""")
                receipt(conn, "capability_binding.update", "b22-updated", revision="2")
            def write_untrusted_evaluate(*, readiness="blocked"):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET version=version+1,
                        operational_readiness=%s,dependency_snapshot_hash=%s,
                        last_evaluated_at=now(),readiness_expires_at=now()+interval '15 minutes'
                        WHERE binding_id='b22-binding'""", (readiness, "b" * 64))
                    receipt(conn, "capability_binding.evaluate", "b22-evaluated", revision="3")

            if evaluate_mode != "legacy_blocked":
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    write_untrusted_evaluate(readiness=(
                        "available" if evaluate_mode == "require_trusted_available" else "blocked"
                    ))
                return
            write_untrusted_evaluate()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET version=version+1,
                        updated_at=now() WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.evaluate", "b26-version-only-eval",
                            revision="4")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET status='revoked',
                        last_evaluated_at=now()+interval '1 second',
                        version=version+1 WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.update", "b26-mixed-update",
                            revision="4")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET version=version+1,
                        last_evaluated_at=now()+interval '1 second',
                        readiness_expires_at=now()+interval '16 minutes'
                        WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.evaluate", "b27-eval-first",
                            revision="4")
                    receipt(conn, "capability_binding.evaluate", "b27-eval-duplicate",
                            revision="4")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET status='revoked',
                        secret_ref='secret://test-only-tamper',version=version+1
                        WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.update", "b28-update-extra-column",
                            revision="4")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET version=version+1,
                        last_evaluated_at=now()+interval '1 second',
                        readiness_expires_at=now()+interval '16 minutes',
                        secret_ref='secret://test-only-tamper'
                        WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.evaluate", "b28-eval-extra-column",
                            revision="4")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET status='revoked',
                        version=version+1 WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.update", "b22-update-with-spoof", revision="4")
                    receipt(conn, "capability_binding.create", "b22-spoofed-create", revision="4")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    receipt(conn, "capability_binding.create", "b22-create-before-update", revision="4")
                    conn.execute("""UPDATE aip_capability_binding SET status='revoked',
                        version=version+1 WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.update", "b22-update-after-spoof", revision="4")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET status='revoked',
                        version=version+1 WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.update", "b22-update-with-false-eval", revision="4")
                    receipt(conn, "capability_binding.evaluate", "b22-spoofed-eval", revision="4")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with login(issuer) as conn:
                    set_scope(conn)
                    conn.execute("""UPDATE aip_capability_binding SET
                        s3owaob24_last_operation='capability_binding.create',version=version+1
                        WHERE binding_id='b22-binding'""")
                    receipt(conn, "capability_binding.create", "b22-client-marker-spoof", revision="4")
            with login(issuer) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.UniqueViolation):
                    receipt(conn, "capability_binding.create", "b22-created")
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-late")
                    flush_guards(conn)
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                insert_binding(conn, "b22-wrong-version")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-wrong-version", revision="2",
                            binding="b22-wrong-version")
                    flush_guards(conn)
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn, "dev-org")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt(conn, "capability_binding.create", "b22-cross-tenant")
                    flush_guards(conn)
                conn.rollback()
            with login(issuer) as conn:
                set_scope(conn)
                insert_binding(conn, "b22-rollback")
                receipt(conn, "capability_binding.create", "b22-rollback",
                        binding="b22-rollback")
                conn.rollback()
            assert owner.execute("SELECT count(*) FROM aip_agent_registry_receipt "
                                 "WHERE idempotency_key LIKE 'b22-%'").fetchone()[0] == 7
            assert owner.execute("SELECT count(*) FROM aip_capability_binding "
                                 "WHERE binding_id LIKE 'b22-%'").fetchone()[0] == 1
        finally:
            owner.execute("DROP TRIGGER IF EXISTS s3owaob22_binding_guard ON aip_capability_binding")
            owner.execute("DROP FUNCTION IF EXISTS public.s3owaob22_binding_guard()")
            owner.execute("DROP TRIGGER IF EXISTS s3owaob22_receipt_guard "
                          "ON aip_agent_registry_receipt")
            owner.execute("DROP FUNCTION IF EXISTS public.s3owaob22_receipt_guard()")
            owner.execute("DROP TRIGGER IF EXISTS s3owaob24_mark_binding_operation "
                          "ON aip_capability_binding")
            owner.execute("DROP FUNCTION IF EXISTS public.s3owaob24_mark_binding_operation()")
            owner.execute("ALTER TABLE aip_capability_binding "
                          "DROP COLUMN IF EXISTS s3owaob24_last_operation")
            owner.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_capability_binding")
                          .format(sql.Identifier(issuer + "_binding")))
            owner.execute(sql.SQL("REVOKE SELECT,INSERT,UPDATE ON aip_capability_binding FROM {}")
                          .format(sql.Identifier(issuer)))
            owner.execute(sql.SQL("REVOKE SELECT ON aip_capability_revision FROM {}")
                          .format(sql.Identifier(issuer)))
            for name in (issuer, runtime):
                owner.execute(sql.SQL("DROP POLICY IF EXISTS {} ON aip_agent_registry_receipt")
                              .format(sql.Identifier(name + "_receipt")))
                owner.execute(sql.SQL("REVOKE SELECT,INSERT ON aip_agent_registry_receipt FROM {}")
                              .format(sql.Identifier(name)))
                owner.execute(sql.SQL("DROP ROLE IF EXISTS {}") .format(sql.Identifier(name)))
