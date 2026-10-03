"""E17-s3o-l: original CapabilityBinding create under an isolated issuer."""

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
    CapabilityBindingRequest, CreateCapabilityBindingRequest,
    PublishCapabilityRevisionRequest, VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict, AipAgentRegistryPersistenceError,
)
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_registry_issuer_connection import (
    RegistryIssuerConnectionFactory, RegistryIssuerConnectionBlocked,
    RegistryIssuerDatabaseConfig,
)
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


@pytest.fixture()
def capability_case():
    parts = conninfo_to_dict(get_dsn())
    database = parts.get("dbname", "")
    assert (database.startswith("aos_test_") and database.endswith("_ti4_test")
            and parts.get("host") == "127.0.0.1" and str(parts.get("port")) == "5433")
    scope = TenantScope("org-org", "dev-project")
    suffix = uuid4().hex[:12]
    cap_id, binding_id = f"s3ol-cap-{suffix}", f"s3ol-binding-{suffix}"
    hash_value = "a" * 64
    def ref(kind: str) -> VersionedAssetRef:
        return VersionedAssetRef(asset_type=kind, asset_id=f"s3ol-{kind}-{suffix}",
                                 revision=1, content_hash=hash_value)
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','隔离测试组织') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES"
                     "('org-org','dev-project','隔离测试工作区') ON CONFLICT DO NOTHING")
        conn.commit()
    AipCapabilityRegistry().publish(PublishCapabilityRevisionRequest(
        capability_id=cap_id, revision=1, display_name="隔离能力夹具",
        lifecycle="published", aliases=[],
        input_schema_ref=ref("SchemaRevision"),
        output_schema_ref=ref("SchemaRevision"),
        risk_level="low", memory_policy_ref=ref("MemoryPolicy"),
        handoff_policy_ref=ref("HandoffPolicy"),
        effect_review_schema_ref=ref("SchemaRevision"),
        license_policy_ref=ref("LicensePolicy"),
        readiness_policy_ref=ref("ReadinessPolicy"),
        readiness="available", readiness_reasons=[],
        source_ref=ResourceRef(resource_type="TestFixture", resource_id=cap_id,
                               revision="1", authority="test-only"),
        source_license="test-only", content_hash=hash_value,
    ), actor="test-only")
    request = CreateCapabilityBindingRequest(
        binding_id=binding_id,
        binding=CapabilityBindingRequest(
            capability=VersionedAssetRef(asset_type="CapabilityRevision",
                                         asset_id=cap_id, revision=1,
                                         content_hash=hash_value),
            secret_ref="vault://test-only/s3ol",
            network_policy_revision="s3ol-test-only",
            quota_policy_revision="s3ol-test-only", timeout_ms=1000,
            max_concurrency=1,
        ),
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
def capability_issuer(capability_case):
    parts = conninfo_to_dict(get_dsn())
    database = parts["dbname"]
    issuer = "aos_aip_capability_issuer"
    password = secrets.token_urlsafe(32)
    with psycopg.connect(get_dsn()) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (issuer,)).fetchone() is None
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                      .format(sql.Identifier(issuer), sql.Literal(password)))
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}")
                      .format(sql.Identifier(issuer)))
        for table, privileges in (
            ("aip_capability_revision", "SELECT"),
            ("aip_capability_binding", "SELECT,INSERT"),
            ("aip_agent_registry_receipt", "SELECT,INSERT"),
        ):
            admin.execute(sql.SQL("GRANT {} ON {} TO {}")
                          .format(sql.SQL(privileges), sql.Identifier(table), sql.Identifier(issuer)))
        for table in ("aip_capability_binding", "aip_agent_registry_receipt"):
            admin.execute(sql.SQL("""CREATE POLICY s3ol_issuer_scope ON {} TO {}
                USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))
                WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
                          .format(sql.Identifier(table), sql.Identifier(issuer)))
    with tempfile.TemporaryDirectory(prefix="aos-s3ol-issuer-") as directory:
        path = Path(directory) / "pgpass"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"127.0.0.1:5433:{database}:{issuer}:{password}\n")
        factory = RegistryIssuerConnectionFactory(
            RegistryIssuerDatabaseConfig("127.0.0.1", 5433, database, path),
            command_family="capability")
        try:
            yield factory
        finally:
            with psycopg.connect(get_dsn()) as admin:
                for table in ("aip_capability_binding", "aip_agent_registry_receipt"):
                    admin.execute(sql.SQL("DROP POLICY IF EXISTS s3ol_issuer_scope ON {}")
                                  .format(sql.Identifier(table)))
                admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(issuer)))
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(issuer)))


def test_original_capability_create_replay_and_tenant_isolation(capability_case, capability_issuer):
    scope, request = capability_case
    service = AipCapabilityBindingService(connect_factory=capability_issuer)
    key = f"s3ol:{request.binding_id}"
    created, receipt = service.create(scope, request, idempotency_key=key,
                                      actor="test-only", occurred_at=datetime.now(UTC))
    assert created.binding_id == request.binding_id and created.status == "provisioning"
    assert receipt.status == "applied"
    replay, replay_receipt = service.create(scope, request, idempotency_key=key,
                                           actor="test-only", occurred_at=datetime.now(UTC))
    assert replay.binding_id == created.binding_id
    assert replay_receipt.receipt_id == receipt.receipt_id
    with pytest.raises(AipAgentRegistryConflict):
        service.create(scope, request.model_copy(update={"binding_id": "drift"}),
                       idempotency_key=key, actor="test-only", occurred_at=datetime.now(UTC))
    with capability_issuer(TenantScope("dev-org", "dev-project")) as conn:
        assert conn.execute("SELECT 1 FROM aip_capability_binding WHERE binding_id=%s",
                            (request.binding_id,)).fetchone() is None
    with connect(scope) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_capability_binding WHERE binding_id=%s",
                            (request.binding_id,)).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM aip_agent_registry_receipt "
                            "WHERE operation='capability_binding.create' AND result_ref->>'resourceId'=%s",
                            (request.binding_id,)).fetchone()["n"] == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("""INSERT INTO aip_agent_registry_receipt
                (org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
                 resource_ref,result_ref,status,created_by,created_at)
                VALUES (%s,%s,%s,'capability_binding.create',%s,%s,
                        '{}'::jsonb,'{}'::jsonb,'applied','runtime',now())""",
                (*scope.key, f"s3ol-direct-{uuid4().hex}", uuid4().hex, "a" * 64))


def test_capability_issuer_is_narrow(capability_case, capability_issuer):
    scope, _ = capability_case
    with capability_issuer(scope) as conn:
        assert conn.execute("SELECT session_user AS login").fetchone()["login"] == "aos_aip_capability_issuer"
        for table in ("aip_agent_instance", "aip_skill_binding", "aip_tool_binding",
                      "aip_assignee_resolution_receipt"):
            assert not conn.execute("SELECT has_table_privilege(current_user,%s,'INSERT') AS granted",
                                    (table,)).fetchone()["granted"]
        assert not conn.execute("SELECT has_table_privilege(current_user,'aip_capability_binding','UPDATE') AS granted").fetchone()["granted"]


def test_capability_issuer_rejects_missing_insert_without_partial_binding(
    capability_case, capability_issuer,
):
    scope, request = capability_case
    with connect() as conn:
        conn.execute("REVOKE INSERT ON aip_capability_binding FROM aos_aip_capability_issuer")
        conn.commit()
    with pytest.raises(AipAgentRegistryPersistenceError) as failure:
        AipCapabilityBindingService(connect_factory=capability_issuer).create(
            scope, request, idempotency_key=f"s3ol:missing:{request.binding_id}",
            actor="test-only", occurred_at=datetime.now(UTC))
    assert isinstance(failure.value.__cause__, RegistryIssuerConnectionBlocked)
    with connect(scope) as conn:
        assert conn.execute("SELECT 1 FROM aip_capability_binding WHERE binding_id=%s",
                            (request.binding_id,)).fetchone() is None


def test_capability_issuer_rejects_write_widening(capability_case, capability_issuer):
    scope, _ = capability_case
    with connect() as conn:
        conn.execute("GRANT UPDATE ON aip_capability_binding TO aos_aip_capability_issuer")
        conn.commit()
    with pytest.raises(RegistryIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with capability_issuer(scope):
            pass
