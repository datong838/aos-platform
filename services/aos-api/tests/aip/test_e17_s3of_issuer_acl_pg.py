"""E17-s3o-f: ordinary tenant runtime must not issue AIP authority receipts."""

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

from aos_api.aip_assignee_issuer_connection import (
    AssigneeIssuerConnectionFactory,
    AssigneeIssuerConnectionBlocked,
    AssigneeIssuerDatabaseConfig,
)
from aos_api.aip_assignee_resolution import AssigneeResolutionStatus, ResolveAssigneeRequest
from aos_api.aip_assignee_resolution_store import AipAssigneeResolutionStore
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


@pytest.mark.xfail(
    strict=True,
    reason="E17-s3o-f RED: current aos_runtime can directly issue Assignee Receipt",
)
def test_runtime_cannot_insert_assignee_resolution_receipt_directly() -> None:
    # conftest owns a fresh disposable DB and drops it after this test session.
    scope = TenantScope("org-org", "dev-project")
    with connect(scope) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """INSERT INTO aip_assignee_resolution_receipt
                   (org_id, project_id, receipt_id, subject_id, kind, resource_id,
                    version, status, blocker_codes, actor, content_hash)
                   VALUES (%s, %s, %s, 's3of-subject', 'human_principal',
                           's3of-principal', 1, 'blocked', '[]'::jsonb,
                           'untrusted-runtime', %s)""",
                (*scope.key, f"s3of-{uuid4().hex}", "a" * 64),
            )


@pytest.fixture()
def isolated_assignee_issuer():
    """Provision an issuer in this disposable test DB; never touch current DB."""
    parts = conninfo_to_dict(get_dsn())
    database = parts.get("dbname", "")
    assert (database.startswith("aos_test_") and database.endswith("_ti4_test")
            and parts.get("host") == "127.0.0.1" and str(parts.get("port")) == "5433")
    issuer = "aos_aip_assignee_issuer"
    password = secrets.token_urlsafe(32)
    scope = TenantScope("org-org", "dev-project")
    scoped_reads = (
        "meta_membership", "aip_agent_instance", "aip_skill_binding",
        "aip_tool_binding", "aip_capability_binding",
        "aip_assignee_resolution_receipt",
    )
    with psycopg.connect(get_dsn()) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (issuer,)).fetchone() is None
        admin.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}")
            .format(sql.Identifier(issuer), sql.Literal(password))
        )
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(issuer)))
        admin.execute("INSERT INTO twa_org(id,name) VALUES('org-org','栖月汇') ON CONFLICT DO NOTHING")
        admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES"
                      "('org-org','dev-project','开发工作区') ON CONFLICT DO NOTHING")
        admin.execute("INSERT INTO meta_org(id,name) VALUES('org-org','隔离测试组织') ON CONFLICT DO NOTHING")
        admin.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES"
                      "('org-org','dev-project','隔离测试工作区') ON CONFLICT DO NOTHING")
        admin.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) "
                      "VALUES('org-org','dev-project','s3og-human','owner') ON CONFLICT DO NOTHING")
        admin.execute("REVOKE INSERT,UPDATE,DELETE ON aip_assignee_resolution_receipt FROM aos_runtime")
        for table in scoped_reads:
            admin.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
                sql.Identifier("public", table), sql.Identifier(issuer)))
            admin.execute(sql.SQL("""CREATE POLICY s3oh_assignee_issuer_scope ON {} TO {}
                USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))
                WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
                   AND project_id=NULLIF(current_setting('aos.project_id',true),''))""").format(
                sql.Identifier("public", table), sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT ON public.aip_agent_template_revision TO {}")
                      .format(sql.Identifier(issuer)))
        admin.execute(sql.SQL("GRANT SELECT,INSERT ON aip_assignee_resolution_receipt TO {}")
                      .format(sql.Identifier(issuer)))
    with tempfile.TemporaryDirectory(prefix="aos-s3og-issuer-") as directory:
        path = Path(directory) / "pgpass"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"127.0.0.1:5433:{database}:{issuer}:{password}\n")
        factory = AssigneeIssuerConnectionFactory(
            AssigneeIssuerDatabaseConfig("127.0.0.1", 5433, database, path)
        )
        try:
            yield factory, scope
        finally:
            # Test-only role is cluster-wide; restore this DB's ACL and remove it.
            with psycopg.connect(get_dsn()) as admin:
                for table in scoped_reads:
                    admin.execute(sql.SQL("DROP POLICY IF EXISTS s3oh_assignee_issuer_scope ON {}")
                                  .format(sql.Identifier("public", table)))
                admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(issuer)))
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(issuer)))
                admin.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON "
                              "aip_assignee_resolution_receipt TO aos_runtime")


def test_isolated_runtime_denied_and_separate_issuer_resolves(isolated_assignee_issuer) -> None:
    factory, scope = isolated_assignee_issuer
    with connect(scope) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("""INSERT INTO aip_assignee_resolution_receipt
                (org_id,project_id,receipt_id,subject_id,kind,resource_id,version,
                 status,blocker_codes,actor,content_hash)
                VALUES(%s,%s,%s,'s3og-subject','human_principal','s3og-human',1,
                       'blocked','[]'::jsonb,'runtime',%s)""",
                         (*scope.key, f"s3og-{uuid4().hex}", "a" * 64))
    store = AipAssigneeResolutionStore(connect_factory=factory)
    receipt = store.resolve(
        scope,
        ResolveAssigneeRequest(
            subject_id=f"s3og-subject-{uuid4().hex}",
            assignee=AssigneeRef(kind=AssigneeKind.HUMAN_PRINCIPAL,
                                 resource_id="s3og-human", version=1),
        ),
        "s3og-issuer", now=datetime.now(UTC),
    )
    assert receipt.status is AssigneeResolutionStatus.RESOLVED
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT status FROM aip_assignee_resolution_receipt "
            "WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
            (*scope.key, receipt.receipt_id),
        ).fetchone()
        assert row["status"] == "resolved"
    for statement in (
        "UPDATE aip_assignee_resolution_receipt SET actor='forged' "
        "WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
        "DELETE FROM aip_assignee_resolution_receipt "
        "WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
    ):
        with factory(scope) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement, (*scope.key, receipt.receipt_id))
    # dev-org is a zero-effect visibility canary, never a positive issuer tenant.
    with factory(TenantScope("dev-org", "dev-project")) as conn:
        assert conn.execute(
            "SELECT 1 FROM aip_assignee_resolution_receipt WHERE receipt_id=%s",
            (receipt.receipt_id,),
        ).fetchone() is None


def test_assignee_issuer_rejects_nonprivate_passfile(tmp_path: Path) -> None:
    secret = tmp_path / "pgpass"
    secret.write_text("test-only", encoding="utf-8")
    secret.chmod(0o644)
    with pytest.raises(AssigneeIssuerConnectionBlocked, match="PRIVATE_CREDENTIAL"):
        AssigneeIssuerDatabaseConfig("127.0.0.1", 5433, "aos_test_only", secret)


def test_assignee_issuer_rejects_runtime_acl_widening(isolated_assignee_issuer) -> None:
    factory, scope = isolated_assignee_issuer
    with psycopg.connect(get_dsn()) as admin:
        admin.execute("GRANT INSERT ON aip_assignee_resolution_receipt TO aos_runtime")
    with pytest.raises(AssigneeIssuerConnectionBlocked, match="DATABASE_IDENTITY_REQUIRED"):
        with factory(scope):
            pass


_REGISTRY_INSERT = """INSERT INTO aip_agent_registry_receipt
    (org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
     resource_ref,result_ref,status,created_by,created_at)
    VALUES(%s,%s,%s,'agent_instance.create',%s,%s,'{}'::jsonb,'{}'::jsonb,
           'applied','untrusted-direct-writer',now())"""


@pytest.mark.xfail(
    strict=True,
    reason="E17-s3o-h RED: current aos_runtime can directly issue Registry Receipt",
)
def test_runtime_cannot_issue_registry_receipt_directly() -> None:
    scope = TenantScope("org-org", "dev-project")
    with psycopg.connect(get_dsn()) as admin:
        admin.execute("INSERT INTO twa_org(id,name) VALUES('org-org','隔离测试组织') ON CONFLICT DO NOTHING")
        admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES"
                      "('org-org','dev-project','隔离测试工作区') ON CONFLICT DO NOTHING")
    identifier = uuid4().hex
    with connect(scope) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(_REGISTRY_INSERT,
                         (*scope.key, f"s3oh-{identifier}", identifier, "a" * 64))


def test_assignee_issuer_cannot_issue_registry_receipt_directly(isolated_assignee_issuer) -> None:
    factory, scope = isolated_assignee_issuer
    identifier = uuid4().hex
    with factory(scope) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(_REGISTRY_INSERT,
                         (*scope.key, f"s3oh-issuer-{identifier}", identifier, "a" * 64))


def test_assignee_issuer_has_no_cross_domain_write_grants(isolated_assignee_issuer) -> None:
    factory, scope = isolated_assignee_issuer
    names = (
        "aip_agent_registry_receipt", "aip_skill_binding",
        "aip_capability_binding", "aip_tool_binding",
    )
    with factory(scope) as conn:
        grants = {
            name: tuple(conn.execute(
                "SELECT has_table_privilege(current_user,%s,%s) AS granted", (name, command)
            ).fetchone()["granted"] for command in ("INSERT", "UPDATE", "DELETE"))
            for name in names
        }
    assert not any(any(flags) for flags in grants.values()), grants
