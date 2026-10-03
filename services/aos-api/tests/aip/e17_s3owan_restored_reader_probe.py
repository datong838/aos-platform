"""One-shot, test-only Reader ACL probe against the restored a0v_135 clone."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_binding_readiness_reader_connection import (
    READINESS_READER_LOGIN,
    READINESS_READER_TABLES,
    ReadinessReaderConnectionBlocked,
    ReadinessReaderConnectionFactory,
    ReadinessReaderDatabaseConfig,
)
from aos_api.aip_binding_readiness_service import PostgresBindingDependencyAuthority
from aos_api.tenant_scope import TenantScope


CONTEXT = "colima-aos-a0v-test-only"
CONTAINER = "aos-a0v-test-pg"
DATABASE = "aos_e17_s3owan_restore_20261004"
PORT = 5433
POLICY = "e17_s3owan_restored_reader_scope"


def _admin_password() -> str:
    result = subprocess.run(
        ["docker", "--context", CONTEXT, "inspect", CONTAINER],
        check=True, capture_output=True, text=True,
    )
    container = json.loads(result.stdout)[0]
    assert container["Name"] == f"/{CONTAINER}"
    assert container["State"]["Running"] is True
    assert container["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"] == str(PORT)
    mounts = container["Mounts"]
    assert len(mounts) == 1 and mounts[0]["Destination"] == "/var/lib/postgresql/data"
    assert mounts[0]["Name"] != "aos-a0v-recovery-pg-data"
    env = dict(item.split("=", 1) for item in container["Config"]["Env"] if "=" in item)
    assert env["POSTGRES_USER"] == "aos_app"
    return env["POSTGRES_PASSWORD"]


def _connect_admin(password: str, database: str = DATABASE):
    return psycopg.connect(
        host="127.0.0.1", port=PORT, dbname=database,
        user="aos_app", password=password,
    )


def _blocked(factory, scope, expected: str) -> None:
    try:
        with factory(scope):
            raise AssertionError(f"Reader unexpectedly admitted: {expected}")
    except ReadinessReaderConnectionBlocked as exc:
        assert str(exc) == expected, str(exc)


def main() -> None:
    assert os.environ.get("AOS_DOTENV_DISABLED") == "1"
    password = _admin_password()
    with _connect_admin(password) as admin:
        assert admin.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "a0v_135"
        assert admin.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
        ).fetchone()[0] == 592
        assert admin.execute(
            "SELECT 1 FROM pg_roles WHERE rolname=%s", (READINESS_READER_LOGIN,)
        ).fetchone() is None

    reader_password = secrets.token_urlsafe(32)
    scope = TenantScope("org-org", "dev-project")
    other_scope = TenantScope("org-org", "other-project")
    bundle_id = f"e17-s3owan-test-only-{uuid4().hex}"
    bundle_hash = "c" * 64
    evidence = VersionedAssetRef(
        asset_type="EvidenceBundleRevision", asset_id=bundle_id,
        revision=1, content_hash=bundle_hash,
    )
    with tempfile.TemporaryDirectory(prefix="aos-e17-s3owan-reader-") as directory:
        passfile = Path(directory) / "pgpass"
        fd = os.open(passfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(
                f"127.0.0.1:{PORT}:{DATABASE}:{READINESS_READER_LOGIN}:{reader_password}\n"
            )
        factory = ReadinessReaderConnectionFactory(ReadinessReaderDatabaseConfig(
            host="127.0.0.1", port=PORT, database=DATABASE, passfile=passfile,
        ))
        _blocked(factory, scope, "READINESS_READER_CONNECTION_FAILED")
        print("RED absent_role_rejected")

        created = False
        try:
            with _connect_admin(password) as admin:
                admin.execute(sql.SQL(
                    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}"
                ).format(sql.Identifier(READINESS_READER_LOGIN), sql.Literal(reader_password)))
                admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(DATABASE), sql.Identifier(READINESS_READER_LOGIN)))
                admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(READINESS_READER_LOGIN)))
                for table in READINESS_READER_TABLES:
                    admin.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
                        sql.Identifier(table), sql.Identifier(READINESS_READER_LOGIN)))
                    if table != "aip_capability_revision":
                        admin.execute(sql.SQL(
                            "CREATE POLICY {} ON {} TO {} USING "
                            "(org_id=NULLIF(current_setting('aos.org_id',true),'') "
                            "AND project_id=NULLIF(current_setting('aos.project_id',true),''))"
                        ).format(sql.Identifier(POLICY), sql.Identifier(table),
                                 sql.Identifier(READINESS_READER_LOGIN)))
                admin.execute("""INSERT INTO aip_evidence_bundle_revision
                    (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
                     item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
                     license_summary,content_hash,lifecycle,created_by)
                    VALUES(%s,%s,%s,1,'{}'::jsonb,'[]'::jsonb,NOW(),'[]'::jsonb,
                           'complete','[]'::jsonb,'[]'::jsonb,'[]'::jsonb,'fresh',
                           '{}'::jsonb,'{}'::jsonb,%s,'frozen','test-only')""",
                    (*scope.key, bundle_id, bundle_hash))
            created = True

            authority = PostgresBindingDependencyAuthority(factory)
            with factory(None) as reader:
                assert reader.execute(
                    "SELECT count(*) AS n FROM aip_capability_revision"
                ).fetchone()["n"] == 10
            with factory(scope) as reader:
                identity = reader.execute("""SELECT session_user AS login,
                    current_user AS role,current_setting('transaction_read_only') AS readonly""").fetchone()
                assert identity == {"login": READINESS_READER_LOGIN,
                                    "role": READINESS_READER_LOGIN, "readonly": "on"}
            assert authority.exact_assets_available(scope, [evidence])
            assert not authority.exact_assets_available(other_scope, [evidence])
            print("GREEN independent_login_global_and_tenant_scope")

            with _connect_admin(password) as admin:
                admin.execute("""INSERT INTO aip_evidence_bundle_revoke_event
                    (org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor)
                    VALUES(%s,%s,%s,%s,1,%s,'test-only-revocation','test-only')""",
                    (*scope.key, f"revoke-{uuid4().hex}", bundle_id, bundle_hash))
            assert not authority.exact_assets_available(scope, [evidence])
            print("GREEN exact_revocation_rejected")

            for statement, expected in (
                ("REVOKE SELECT ON aip_evidence_bundle_revoke_event FROM {}",
                 "READINESS_READER_DATABASE_IDENTITY_REQUIRED"),
                ("GRANT SELECT ON aip_capability_binding TO {}",
                 "READINESS_READER_DATABASE_IDENTITY_REQUIRED"),
                ("GRANT INSERT ON aip_eval_dataset_revision TO {}",
                 "READINESS_READER_DATABASE_IDENTITY_REQUIRED"),
            ):
                with _connect_admin(password) as admin:
                    admin.execute(sql.SQL(statement).format(sql.Identifier(READINESS_READER_LOGIN)))
                _blocked(factory, scope, expected)
                with _connect_admin(password) as admin:
                    if statement.startswith("REVOKE"):
                        inverse = "GRANT SELECT ON aip_evidence_bundle_revoke_event TO {}"
                    elif "aip_capability_binding" in statement:
                        inverse = "REVOKE SELECT ON aip_capability_binding FROM {}"
                    else:
                        inverse = "REVOKE INSERT ON aip_eval_dataset_revision FROM {}"
                    admin.execute(sql.SQL(inverse).format(sql.Identifier(READINESS_READER_LOGIN)))
            print("GREEN missing_acl_extra_read_and_write_rejected")
            with _connect_admin(password) as admin:
                admin.execute(sql.SQL("ALTER ROLE {} INHERIT").format(
                    sql.Identifier(READINESS_READER_LOGIN)))
            _blocked(factory, scope, "READINESS_READER_DATABASE_IDENTITY_REQUIRED")
            with _connect_admin(password) as admin:
                admin.execute(sql.SQL("ALTER ROLE {} NOINHERIT").format(
                    sql.Identifier(READINESS_READER_LOGIN)))
            print("GREEN inheritable_role_rejected")
        finally:
            if created:
                with _connect_admin(password) as admin:
                    for table in READINESS_READER_TABLES:
                        if table != "aip_capability_revision":
                            admin.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(
                                sql.Identifier(POLICY), sql.Identifier(table)))
                    admin.execute(sql.SQL("DROP OWNED BY {}").format(
                        sql.Identifier(READINESS_READER_LOGIN)))
                with _connect_admin(password, "postgres") as admin:
                    admin.execute(sql.SQL("DROP ROLE {}").format(
                        sql.Identifier(READINESS_READER_LOGIN)))
    with _connect_admin(password) as admin:
        assert admin.execute(
            "SELECT 1 FROM pg_roles WHERE rolname=%s", (READINESS_READER_LOGIN,)
        ).fetchone() is None
    print("GREEN clone_reader_role_cleanup")


if __name__ == "__main__":
    main()
