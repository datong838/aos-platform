"""Opt-in real PG clone transaction and rollback proof; never targets current DB."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.a0v_e17_reader_maintenance import (  # noqa: E402
    FRESH_DATABASE,
    POLICY,
    ReaderMaintenanceBlocked,
    apply_fresh_clone,
    main,
)
from aos_api.aip_binding_readiness_reader_connection import (  # noqa: E402
    READINESS_READER_LOGIN,
    READINESS_READER_TABLES,
    ReadinessReaderConnectionFactory,
    ReadinessReaderDatabaseConfig,
)
from aos_api.tenant_scope import TenantScope  # noqa: E402


@pytest.mark.skipif(os.environ.get("AOS_E17_READER_APPLY_TEST_ONLY") != "1",
                    reason="requires exact disposable restored PG clone")
def test_fresh_clone_apply_fault_rolls_back_then_reader_admits(tmp_path, capsys):
    assert os.environ.get("AOS_DOTENV_DISABLED") == "1"
    meta = json.loads(subprocess.run(
        ["docker", "--context", "colima-aos-a0v-test-only", "inspect", "aos-a0v-test-pg"],
        check=True, capture_output=True, text=True,
    ).stdout)[0]
    env = dict(value.split("=", 1) for value in meta["Config"]["Env"] if "=" in value)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    admin = private / "admin.pgpass"
    password_file = private / "reader.password"
    reader_passfile = private / "reader.pgpass"
    password = secrets.token_urlsafe(32)
    admin.write_text(f"127.0.0.1:5433:{FRESH_DATABASE}:aos_app:{env['POSTGRES_PASSWORD']}\n")
    password_file.write_text(password)
    reader_passfile.write_text(f"127.0.0.1:5433:{FRESH_DATABASE}:{READINESS_READER_LOGIN}:{password}\n")
    for file in (admin, password_file, reader_passfile):
        file.chmod(0o600)

    def counts() -> tuple[int, int, int, int]:
        with psycopg.connect(host="127.0.0.1", port=5433, dbname=FRESH_DATABASE,
                             user="aos_app", passfile=str(admin)) as conn:
            conn.read_only = True
            return (
                conn.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s",
                             (READINESS_READER_LOGIN,)).fetchone()[0],
                conn.execute("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND policyname=%s",
                             (POLICY,)).fetchone()[0],
                conn.execute("SELECT count(*) FROM bundle_installation").fetchone()[0],
                conn.execute("SELECT count(*) FROM aip_agent_registry_receipt").fetchone()[0],
            )

    assert counts() == (0, 0, 1, 6)
    created = False
    try:
        with pytest.raises(ReaderMaintenanceBlocked, match="READER_CLONE_INJECTED_FAILURE"):
            apply_fresh_clone(admin, password_file, fail_after_policy=5)
        assert counts() == (0, 0, 1, 6)
        exit_code = main(["--target", "fresh-clone", "--apply-fresh-clone",
                          "--admin-passfile", str(admin),
                          "--reader-password-file", str(password_file)])
        created = True
        assert exit_code == 0
        assert json.loads(capsys.readouterr().out)["outcome"] == "READER_FRESH_CLONE_APPLY_GREEN"
        assert counts() == (1, 17, 1, 6)
        with pytest.raises(ReaderMaintenanceBlocked, match="READER_CLONE_CATALOG_REQUIRED"):
            apply_fresh_clone(admin, password_file)
        assert counts() == (1, 17, 1, 6)
        reader = ReadinessReaderConnectionFactory(ReadinessReaderDatabaseConfig(
            "127.0.0.1", 5433, FRESH_DATABASE, reader_passfile,
        ))
        with reader(None) as connection:
            assert connection.execute("SELECT count(*) AS n FROM aip_capability_revision").fetchone()["n"] == 10
        with reader(TenantScope("org-org", "dev-project")) as connection:
            assert connection.execute("SELECT count(*) AS n FROM aip_evidence_bundle_revision").fetchone()["n"] == 0
    finally:
        if created:
            with psycopg.connect(host="127.0.0.1", port=5433, dbname=FRESH_DATABASE,
                                 user="aos_app", passfile=str(admin)) as conn:
                for table in READINESS_READER_TABLES:
                    if table != "aip_capability_revision":
                        conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(
                            sql.Identifier(POLICY), sql.Identifier(table)))
                conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(READINESS_READER_LOGIN)))
            with psycopg.connect(host="127.0.0.1", port=5433, dbname="postgres",
                                 user="aos_app", password=env["POSTGRES_PASSWORD"]) as conn:
                conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(READINESS_READER_LOGIN)))
    assert counts() == (0, 0, 1, 6)
