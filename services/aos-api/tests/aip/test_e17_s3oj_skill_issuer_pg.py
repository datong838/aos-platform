"""E17-s3o-j: original SkillBinding create and Receipt under a narrow issuer."""

from __future__ import annotations

import os
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from aos_api.aip_agent_registry_contracts import (
    CreateAgentInstanceRequest, CreateSkillBindingRequest,
    EvaluateOperationalBindingRequest, OperationalBindingDependencies,
    PublishAgentTemplateRequest, UpdateSkillBindingRequest, VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict, AipAgentRegistryPersistenceError, AipAgentRegistryStore,
)
from aos_api.aip_registry_issuer_connection import (
    RegistryIssuerConnectionFactory,
    RegistryIssuerConnectionBlocked,
    RegistryIssuerDatabaseConfig,
)
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_contracts import ResourceRef
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


@pytest.fixture()
def skill_case():
    parts = conninfo_to_dict(get_dsn())
    database = parts.get("dbname", "")
    assert (database.startswith("aos_test_") and database.endswith("_ti4_test")
            and parts.get("host") == "127.0.0.1" and str(parts.get("port")) == "5433")
    scope = TenantScope("org-org", "dev-project")
    suffix = uuid4().hex[:12]
    skill_id, instance_id, binding_id = (f"s3oj-{part}-{suffix}" for part in
                                        ("skill", "instance", "binding"))
    hash_value = "a" * 64
    def asset(kind: str) -> str:
        return (f'{{"assetType":"{kind}","assetId":"s3oj-test-only",'
                f'"revision":1,"contentHash":"{hash_value}"}}')
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','隔离测试组织') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES"
                     "('org-org','dev-project','隔离测试工作区') ON CONFLICT DO NOTHING")
        conn.execute("""INSERT INTO aip_skill_template_revision
            (skill_id,revision,canonical_logic_id,lifecycle,input_schema,output_schema,
             tool_allowlist,required_capabilities,risk_level,memory_policy_ref,
             handoff_policy_ref,source_ref,source_license,parent_ref,publication_tenant,
             release_gate_ref,publication_ref,model_route_ref,runtime_policy_ref,
             logic_revision_ref,content_hash,created_by)
            VALUES (%s,1,%s,'published','{}'::jsonb,'{}'::jsonb,
             '[]'::jsonb,'[]'::jsonb,'low',%s::jsonb,%s::jsonb,
             '{"resourceType":"TestFixture","resourceId":"s3oj-test-only","revision":"1","authority":"test-only"}'::jsonb,
             'test-only',%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
             %s::jsonb,%s::jsonb,%s::jsonb,%s,'test-only')""",
                     (skill_id, f"s3oj.test-only.{suffix}", asset("MemoryPolicy"), asset("HandoffPolicy"),
                      asset("SkillTemplate"), '{"orgId":"org-org","projectId":"dev-project"}',
                      asset("EvalGateDecision"),
                      '{"resourceType":"PublicationEvent","resourceId":"s3oj-test-only","revision":"1","authority":"test-only"}',
                      asset("ModelRouteRevision"), asset("RuntimePolicyRevision"),
                      asset("LogicRevision"), hash_value))
        conn.commit()
    template_id = f"s3oj-template-{suffix}"
    store = AipAgentRegistryStore()
    store.publish_template(PublishAgentTemplateRequest(
        template_id=template_id, revision=1, display_name="隔离 Skill 夹具",
        role_key="s3oj_test", lifecycle="published",
        source_ref=ResourceRef(resource_type="TestFixture", resource_id=template_id,
                               revision="1", authority="test-only"),
        source_license="test-only", manifest={}, content_hash=hash_value,
    ), actor="test-only")
    store.create_instance(scope, CreateAgentInstanceRequest(
        instance_id=instance_id,
        template=VersionedAssetRef(asset_type="AgentTemplate", asset_id=template_id,
                                   revision=1, content_hash=hash_value),
    ), idempotency_key=f"s3oj:instance:{instance_id}", actor="test-only",
       occurred_at=datetime.now(UTC))
    with connect() as conn:
        conn.execute("REVOKE INSERT,UPDATE,DELETE ON aip_agent_registry_receipt FROM aos_runtime")
        conn.commit()
    request = CreateSkillBindingRequest(
        binding_id=binding_id, instance_id=instance_id,
        skill=VersionedAssetRef(asset_type="SkillTemplate", asset_id=skill_id,
                                revision=1, content_hash=hash_value),
        budget_policy_ref=VersionedAssetRef(asset_type="BudgetPolicyRevision",
                                            asset_id="s3oj-test-only", revision=1,
                                            content_hash=hash_value),
    )
    try:
        yield scope, request
    finally:
        with connect() as conn:
            conn.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON aip_agent_registry_receipt TO aos_runtime")
            conn.commit()


@pytest.fixture()
def skill_issuer(skill_case):
    parts = conninfo_to_dict(get_dsn())
    database = parts["dbname"]
    issuer = "aos_aip_skill_issuer"
    password = secrets.token_urlsafe(32)
    with psycopg.connect(get_dsn()) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (issuer,)).fetchone() is None
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                      .format(sql.Identifier(issuer), sql.Literal(password)))
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}")
                      .format(sql.Identifier(issuer)))
        for table, privileges in (
            ("aip_agent_template_revision", "SELECT"),
            ("aip_agent_instance", "SELECT"),
            ("aip_skill_template_revision", "SELECT"),
            ("aip_publication_event", "SELECT"),
            ("aip_capability_binding", "SELECT"),
            ("aip_agent_registry_receipt", "SELECT,INSERT"),
            ("aip_skill_binding", "SELECT,INSERT,UPDATE"),
        ):
            admin.execute(sql.SQL("GRANT {} ON {} TO {}")
                          .format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(issuer)))
        for table in ("aip_agent_instance", "aip_agent_registry_receipt", "aip_skill_binding"):
            admin.execute(sql.SQL("""CREATE POLICY s3oj_issuer_scope ON {} TO {}
                USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))
                WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
                          .format(sql.Identifier(table), sql.Identifier(issuer)))
    with tempfile.TemporaryDirectory(prefix="aos-s3oj-issuer-") as directory:
        path = Path(directory) / "pgpass"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"127.0.0.1:5433:{database}:{issuer}:{password}\n")
        factory = RegistryIssuerConnectionFactory(
            RegistryIssuerDatabaseConfig("127.0.0.1", 5433, database, path),
            command_family="skill")
        try:
            yield factory
        finally:
            with psycopg.connect(get_dsn()) as admin:
                for table in ("aip_agent_instance", "aip_agent_registry_receipt", "aip_skill_binding"):
                    admin.execute(sql.SQL("DROP POLICY IF EXISTS s3oj_issuer_scope ON {}")
                                  .format(sql.Identifier(table)))
                admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(issuer)))
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(issuer)))


def test_skill_original_create_replay_and_tenant_isolation(skill_case, skill_issuer):
    scope, request = skill_case
    store = AipSkillRegistry(connect_factory=skill_issuer)
    key = f"s3oj:{request.binding_id}"
    binding, receipt = store.create_binding(
        scope, request, idempotency_key=key,
        actor="test-only", occurred_at=datetime.now(UTC))
    assert binding.binding_id == request.binding_id and receipt.status == "applied"
    replay, replay_receipt = store.create_binding(
        scope, request, idempotency_key=key,
        actor="test-only", occurred_at=datetime.now(UTC))
    assert replay.binding_id == binding.binding_id
    assert replay_receipt.receipt_id == receipt.receipt_id
    with pytest.raises(AipAgentRegistryConflict):
        store.create_binding(scope, request.model_copy(update={"instance_id": "drift"}),
                             idempotency_key=key, actor="test-only",
                             occurred_at=datetime.now(UTC))
    with connect(scope) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_skill_binding WHERE binding_id=%s",
                            (request.binding_id,)).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                            "WHERE operation='skill_binding.create' AND result_ref->>'resourceId'=%s",
                            (request.binding_id,)).fetchone()["n"] == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("""INSERT INTO aip_agent_registry_receipt
                (org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
                 resource_ref,result_ref,status,created_by,created_at)
                VALUES(%s,%s,%s,'skill_binding.create',%s,%s,
                       '{}'::jsonb,'{}'::jsonb,'applied','runtime',now())""",
                         (*scope.key, f"s3oj-direct-{uuid4().hex}", uuid4().hex, "a" * 64))
    with skill_issuer(TenantScope("dev-org", "dev-project")) as conn:
        assert conn.execute("SELECT 1 FROM aip_skill_binding WHERE binding_id=%s",
                            (request.binding_id,)).fetchone() is None


def test_skill_issuer_identity_accepts_narrow_skill_acl(skill_case, skill_issuer):
    scope, _ = skill_case
    with skill_issuer(scope) as conn:
        assert conn.execute("SELECT session_user AS login").fetchone()["login"] == "aos_aip_skill_issuer"
        assert not conn.execute("SELECT has_table_privilege(current_user,'aip_agent_instance','INSERT') AS granted").fetchone()["granted"]
        assert conn.execute("SELECT has_table_privilege(current_user,'aip_skill_binding','UPDATE') AS granted").fetchone()["granted"]
        assert not conn.execute("SELECT has_table_privilege(current_user,'aip_skill_binding','DELETE') AS granted").fetchone()["granted"]
        for table in ("aip_capability_binding", "aip_tool_binding",
                      "aip_assignee_resolution_receipt"):
            assert not conn.execute(
                "SELECT has_table_privilege(current_user,%s,'INSERT') AS granted", (table,)
            ).fetchone()["granted"]


def test_skill_issuer_rejects_missing_insert_without_partial_binding(skill_case, skill_issuer):
    scope, request = skill_case
    with connect() as conn:
        conn.execute("REVOKE INSERT ON aip_skill_binding FROM aos_aip_skill_issuer")
        conn.commit()
    with pytest.raises(AipAgentRegistryPersistenceError) as failure:
        AipSkillRegistry(connect_factory=skill_issuer).create_binding(
            scope, request, idempotency_key=f"s3oj:missing:{request.binding_id}",
            actor="test-only", occurred_at=datetime.now(UTC))
    assert isinstance(failure.value.__cause__, RegistryIssuerConnectionBlocked)
    assert "DATABASE_IDENTITY_REQUIRED" in str(failure.value.__cause__)
    with connect(scope) as conn:
        assert conn.execute("SELECT 1 FROM aip_skill_binding WHERE binding_id=%s",
                            (request.binding_id,)).fetchone() is None


def test_skill_issuer_rejects_write_widening(skill_case, skill_issuer):
    scope, _ = skill_case
    with connect() as conn:
        conn.execute("GRANT DELETE ON aip_skill_binding TO aos_aip_skill_issuer")
        conn.commit()
    with pytest.raises(RegistryIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with skill_issuer(scope):
            pass


def test_original_skill_evaluate_blocked_and_revoke_cas(skill_case, skill_issuer):
    scope, request = skill_case
    store = AipSkillRegistry(connect_factory=skill_issuer)
    binding, _ = store.create_binding(scope, request,
        idempotency_key=f"s3ok:create:{request.binding_id}", actor="test-only",
        occurred_at=datetime.now(UTC))
    evaluation = EvaluateOperationalBindingRequest(
        expected_version=binding.version,
        dependencies=OperationalBindingDependencies(
            budget_policy_ref=request.budget_policy_ref,
        ),
    )
    assessed, readiness, receipt = store.evaluate_binding(
        scope, binding.binding_id, evaluation,
        idempotency_key=f"s3ok:evaluate:{binding.binding_id}",
        actor="test-only", evaluated_at=datetime.now(UTC))
    assert assessed.version == 2
    assert readiness.readiness.value == "blocked"
    assert "SKILL_PUBLICATION_REVOKED" in readiness.reasons
    assert receipt.status == "applied"
    replay, _, replay_receipt = store.evaluate_binding(
        scope, binding.binding_id, evaluation,
        idempotency_key=f"s3ok:evaluate:{binding.binding_id}",
        actor="test-only", evaluated_at=datetime.now(UTC))
    assert replay.version == assessed.version
    assert replay_receipt.receipt_id == receipt.receipt_id
    revoked, revoke_receipt = store.update_binding(
        scope, binding.binding_id,
        UpdateSkillBindingRequest(expected_version=2, from_status="provisioning",
                                  to_status="revoked"),
        idempotency_key=f"s3ok:revoke:{binding.binding_id}",
        actor="test-only", occurred_at=datetime.now(UTC))
    assert revoked.status == "revoked" and revoked.version == 3
    assert revoke_receipt.status == "applied"
    with pytest.raises(AipAgentRegistryConflict):
        store.update_binding(
            scope, binding.binding_id,
            UpdateSkillBindingRequest(expected_version=2, from_status="provisioning",
                                      to_status="revoked"),
            idempotency_key=f"s3ok:stale:{binding.binding_id}",
            actor="test-only", occurred_at=datetime.now(UTC))


def test_skill_evaluate_rejects_missing_publication_read_without_partial_receipt(
    skill_case, skill_issuer,
):
    scope, request = skill_case
    store = AipSkillRegistry(connect_factory=skill_issuer)
    binding, _ = store.create_binding(scope, request,
        idempotency_key=f"s3ok:create:{request.binding_id}", actor="test-only",
        occurred_at=datetime.now(UTC))
    with connect() as conn:
        conn.execute("REVOKE SELECT ON aip_publication_event FROM aos_aip_skill_issuer")
        conn.commit()
    with pytest.raises(AipAgentRegistryPersistenceError) as failure:
        store.evaluate_binding(scope, binding.binding_id,
            EvaluateOperationalBindingRequest(
                expected_version=1,
                dependencies=OperationalBindingDependencies(
                    budget_policy_ref=request.budget_policy_ref)),
            idempotency_key=f"s3ok:evaluate:{binding.binding_id}",
            actor="test-only", evaluated_at=datetime.now(UTC))
    assert isinstance(failure.value.__cause__, RegistryIssuerConnectionBlocked)
    with connect(scope) as conn:
        assert conn.execute("SELECT version FROM aip_skill_binding WHERE binding_id=%s",
                            (binding.binding_id,)).fetchone()["version"] == 1
        assert conn.execute("SELECT 1 FROM aip_agent_registry_receipt "
                            "WHERE operation='skill_binding.evaluate' AND result_ref->>'resourceId'=%s",
                            (binding.binding_id,)).fetchone() is None


def test_skill_issuer_rejects_publication_event_without_force_rls(skill_case, skill_issuer):
    scope, _ = skill_case
    with connect() as conn:
        conn.execute("ALTER TABLE aip_publication_event NO FORCE ROW LEVEL SECURITY")
        conn.commit()
    try:
        with pytest.raises(RegistryIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
            with skill_issuer(scope):
                pass
    finally:
        with connect() as conn:
            conn.execute("ALTER TABLE aip_publication_event FORCE ROW LEVEL SECURITY")
            conn.commit()
