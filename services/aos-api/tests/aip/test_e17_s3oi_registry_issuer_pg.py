"""E17-s3o-i: original AgentInstance + RegistryReceipt transaction under issuer ACL."""

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
    AgentInstanceOverlay,
    CreateAgentInstanceRequest,
    PublishAgentTemplateRequest,
    UpdateAgentInstanceRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryStore,
)
from aos_api.aip_registry_issuer_connection import (
    RegistryIssuerConnectionFactory,
    RegistryIssuerConnectionBlocked,
    RegistryIssuerDatabaseConfig,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


@pytest.fixture()
def isolated_registry_case():
    scope = TenantScope("org-org", "dev-project")
    suffix = uuid4().hex[:12]
    template_id = f"s3oi-template-{suffix}"
    instance_id = f"s3oi-instance-{suffix}"
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','隔离测试组织') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES"
                     "('org-org','dev-project','隔离测试工作区') ON CONFLICT DO NOTHING")
        conn.commit()
    AipAgentRegistryStore().publish_template(
        PublishAgentTemplateRequest(
            template_id=template_id, revision=1, display_name="隔离测试内容官",
            role_key="s3oi_content", lifecycle="published",
            source_ref=ResourceRef(resource_type="TestFixture", resource_id=template_id,
                                   revision="1", authority="test-only"),
            source_license="test-only", manifest={}, content_hash="a" * 64,
        ),
        actor="test-only",
    )
    request = CreateAgentInstanceRequest(
        instance_id=instance_id,
        template=VersionedAssetRef(asset_type="AgentTemplate", asset_id=template_id,
                                   revision=1, content_hash="a" * 64),
        overlay=AgentInstanceOverlay(display_name="隔离测试内容官"),
    )
    with connect() as conn:
        conn.execute("REVOKE INSERT,UPDATE,DELETE ON aip_agent_registry_receipt FROM aos_runtime")
        conn.commit()
    try:
        yield scope, request
    finally:
        with connect() as conn:
            conn.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON aip_agent_registry_receipt TO aos_runtime")
            conn.commit()


@pytest.fixture()
def isolated_registry_issuer(isolated_registry_case):
    parts = conninfo_to_dict(get_dsn())
    database = parts.get("dbname", "")
    assert (database.startswith("aos_test_") and database.endswith("_ti4_test")
            and parts.get("host") == "127.0.0.1" and str(parts.get("port")) == "5433")
    issuer = "aos_aip_registry_issuer"
    password = secrets.token_urlsafe(32)
    scoped_tables = ("aip_agent_instance", "aip_agent_registry_receipt")
    with psycopg.connect(get_dsn()) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (issuer,)).fetchone() is None
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                      .format(sql.Identifier(issuer), sql.Literal(password)))
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT ON aip_agent_template_revision TO {}")
                      .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE ON aip_agent_instance TO {}")
                      .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT,INSERT ON aip_agent_registry_receipt TO {}")
                      .format(sql.Identifier(issuer)))
        for table in scoped_tables:
            admin.execute(sql.SQL("""CREATE POLICY s3oi_registry_issuer_scope ON {} TO {}
                USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))
                WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))""").format(
                sql.Identifier("public", table), sql.Identifier(issuer)))
    with tempfile.TemporaryDirectory(prefix="aos-s3oi-issuer-") as directory:
        path = Path(directory) / "pgpass"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"127.0.0.1:5433:{database}:{issuer}:{password}\n")
        factory = RegistryIssuerConnectionFactory(
            RegistryIssuerDatabaseConfig("127.0.0.1", 5433, database, path))
        try:
            yield factory
        finally:
            with psycopg.connect(get_dsn()) as admin:
                for table in scoped_tables:
                    admin.execute(sql.SQL("DROP POLICY IF EXISTS s3oi_registry_issuer_scope ON {}")
                                  .format(sql.Identifier("public", table)))
                admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(issuer)))
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(issuer)))


def test_original_create_instance_uses_independent_registry_issuer(
    isolated_registry_case, isolated_registry_issuer,
) -> None:
    scope, request = isolated_registry_case
    store = AipAgentRegistryStore(connect_factory=isolated_registry_issuer)
    try:
        instance, receipt = store.create_instance(
            scope, request, idempotency_key=f"s3oi:{request.instance_id}",
            actor="test-only", occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryPersistenceError:
        with connect(scope) as conn:
            assert conn.execute(
                "SELECT 1 FROM aip_agent_instance WHERE org_id=%s AND project_id=%s "
                "AND instance_id=%s", (*scope.key, request.instance_id),
            ).fetchone() is None
        raise
    assert instance.instance_id == request.instance_id
    assert receipt.status == "applied"
    replay, replay_receipt = store.create_instance(
        scope, request, idempotency_key=f"s3oi:{request.instance_id}",
        actor="test-only", occurred_at=datetime.now(UTC),
    )
    assert replay.instance_id == instance.instance_id
    assert replay_receipt.receipt_id == receipt.receipt_id
    updated, update_receipt = store.update_instance(
        scope, request.instance_id,
        UpdateAgentInstanceRequest(
            expected_version=1, from_status="provisioning", to_status="active",
            overlay=AgentInstanceOverlay(display_name="隔离测试内容官"),
        ),
        idempotency_key=f"s3oi:update:{request.instance_id}",
        actor="test-only", occurred_at=datetime.now(UTC),
    )
    assert updated.status == "active"
    assert update_receipt.status == "applied"
    with connect(scope) as conn:
        rows = conn.execute(
            "SELECT operation FROM aip_agent_registry_receipt WHERE org_id=%s "
            "AND project_id=%s AND result_ref->>'resourceId'=%s ORDER BY operation",
            (*scope.key, request.instance_id),
        ).fetchall()
        assert [row["operation"] for row in rows] == [
            "agent_instance.create", "agent_instance.update",
        ]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """INSERT INTO aip_agent_registry_receipt
                   (org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
                    resource_ref,result_ref,status,created_by,created_at)
                   VALUES(%s,%s,%s,'agent_instance.create',%s,%s,
                          '{}'::jsonb,'{}'::jsonb,'applied','runtime',now())""",
                (*scope.key, f"s3oi-direct-{uuid4().hex}", uuid4().hex, "a" * 64),
            )
    with pytest.raises(AipAgentRegistryNotFound):
        store.get_instance(TenantScope("dev-org", "dev-project"), request.instance_id)
    with isolated_registry_issuer(scope) as conn:
        for table in ("aip_skill_binding", "aip_capability_binding", "aip_tool_binding",
                      "aip_assignee_resolution_receipt"):
            assert not conn.execute(
                "SELECT has_table_privilege(current_user,%s,'INSERT') AS granted", (table,)
            ).fetchone()["granted"]


def test_registry_issuer_rejects_nonprivate_passfile(tmp_path: Path) -> None:
    secret = tmp_path / "pgpass"
    secret.write_text("test-only", encoding="utf-8")
    secret.chmod(0o644)
    with pytest.raises(RegistryIssuerConnectionBlocked, match="PRIVATE_CREDENTIAL"):
        RegistryIssuerDatabaseConfig("127.0.0.1", 5433, "aos_test_only", secret)


def test_registry_issuer_rejects_runtime_receipt_acl_widening(
    isolated_registry_case, isolated_registry_issuer,
) -> None:
    scope, _ = isolated_registry_case
    with connect() as conn:
        conn.execute("GRANT INSERT ON aip_agent_registry_receipt TO aos_runtime")
        conn.commit()
    with pytest.raises(RegistryIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with isolated_registry_issuer(scope):
            pass
