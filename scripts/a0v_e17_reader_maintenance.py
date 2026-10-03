"""Read-only preflight for the existing E17 restored Reader clone.

No current-database or apply mode exists in this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

from aos_api.aip_binding_readiness_reader_connection import (
    READINESS_READER_LOGIN,
    READINESS_READER_TABLES,
)


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = "colima-aos-a0v-test-only"
CONTAINER = "aos-a0v-test-pg"
CLONE_VOLUME = "3fa61191c25330f46d4bb8acc67604d272d3b2d213378cf7c2bd38da3bb735e0"
DATABASE = "aos_e17_s3owan_restore_20261004"
PORT = 5433
POLICY = "e17_aip_binding_reader_scope"
BACKUP = ROOT.parent / "aos-recovery/.aos-current-backup-20261003-1952-135/current-full.dump"
BACKUP_SHA256 = "be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc"
RESTORE_PROOF = (ROOT / ".evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/"
                 "w5cb4-e17-s3owan-current135-independent-restore-verification-20261004.md")
_FORBIDDEN_PG_ENV = ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")


class ReaderMaintenanceBlocked(RuntimeError):
    pass


def _require_private_passfile(path: Path) -> None:
    try:
        parent, secret = path.parent.lstat(), path.lstat()
        if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode)
                or not stat.S_ISREG(secret.st_mode)
                or parent.st_uid != os.geteuid() or secret.st_uid != os.geteuid()
                or stat.S_IMODE(parent.st_mode) != 0o700
                or stat.S_IMODE(secret.st_mode) != 0o600):
            raise ValueError("private passfile required")
    except (OSError, ValueError):
        raise ReaderMaintenanceBlocked("READER_ADMIN_PRIVATE_CREDENTIAL_REQUIRED") from None


def _require_target(container: dict) -> None:
    try:
        port = container["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
        mounts = container["Mounts"]
        pg_user = dict(item.split("=", 1) for item in container["Config"]["Env"] if "=" in item)["POSTGRES_USER"]
        valid = (container["Name"] == f"/{CONTAINER}"
                 and container["State"]["Running"] is True
                 and port == str(PORT) and pg_user == "aos_app"
                 and len(mounts) == 1
                 and mounts[0]["Name"] == CLONE_VOLUME
                 and mounts[0]["Destination"] == "/var/lib/postgresql/data")
    except (KeyError, IndexError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ReaderMaintenanceBlocked("READER_CLONE_TARGET_REQUIRED")


def _require_catalog(version: str, tables: list[dict], role_count: int,
                     policy_count: int) -> None:
    names = {row["relname"] for row in tables}
    valid = (version == "a0v_135" and role_count == 0 and policy_count == 0
             and len(tables) == len(READINESS_READER_TABLES)
             and names == set(READINESS_READER_TABLES))
    if valid:
        for row in tables:
            global_catalog = row["relname"] == "aip_capability_revision"
            if (row["relkind"] != "r" or
                    (row["relrowsecurity"], row["relforcerowsecurity"]) !=
                    ((False, False) if global_catalog else (True, True))):
                valid = False
                break
    if not valid:
        raise ReaderMaintenanceBlocked("READER_CLONE_CATALOG_REQUIRED")


def _require_restore_proof() -> None:
    try:
        digest = hashlib.sha256()
        with BACKUP.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        proof = RESTORE_PROOF.read_text(encoding="utf-8")
        valid = (digest.hexdigest() == BACKUP_SHA256
                 and BACKUP_SHA256 in proof and DATABASE in proof
                 and "完整 pg_restore 均 exit0" in proof)
    except OSError:
        valid = False
    if not valid:
        raise ReaderMaintenanceBlocked("READER_CLONE_RESTORE_PROOF_REQUIRED")


def _inspect_clone() -> dict:
    try:
        result = subprocess.run(
            ["docker", "--context", CONTEXT, "inspect", CONTAINER],
            check=True, capture_output=True, text=True, timeout=10,
        )
        container, = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ReaderMaintenanceBlocked("READER_CLONE_TARGET_REQUIRED") from None
    _require_target(container)
    return container


def _read_catalog(passfile: Path) -> tuple[str, int]:
    try:
        conn = psycopg.connect(
            host="127.0.0.1", port=PORT, dbname=DATABASE, user="aos_app",
            passfile=str(passfile), connect_timeout=5, row_factory=dict_row,
            options="-c statement_timeout=10000 -c lock_timeout=5000 -c search_path=public,pg_catalog",
        )
        with conn:
            conn.isolation_level = IsolationLevel.REPEATABLE_READ
            conn.read_only = True
            identity = conn.execute("""SELECT current_database() AS database,
                session_user AS login,current_user AS role,
                current_setting('transaction_read_only') AS readonly""").fetchone()
            if identity != {"database": DATABASE, "login": "aos_app",
                            "role": "aos_app", "readonly": "on"}:
                raise ReaderMaintenanceBlocked("READER_CLONE_ADMIN_IDENTITY_REQUIRED")
            versions = conn.execute("SELECT version_num FROM alembic_version").fetchall()
            version = versions[0]["version_num"] if len(versions) == 1 else ""
            tables = conn.execute("""SELECT c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relname=ANY(%s)""",
                (list(READINESS_READER_TABLES),)).fetchall()
            role_count = conn.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname=%s",
                                      (READINESS_READER_LOGIN,)).fetchone()["n"]
            policy_count = conn.execute("""SELECT count(*) AS n FROM pg_policies
                WHERE schemaname='public' AND policyname=%s""", (POLICY,)).fetchone()["n"]
            _require_catalog(version, tables, role_count, policy_count)
            shape = conn.execute("""SELECT (SELECT count(*) FROM pg_tables WHERE schemaname='public') AS tables,
                (SELECT count(*) FROM pg_sequences WHERE schemaname='public') AS sequences,
                (SELECT count(*) FROM bundle_installation) AS installations,
                (SELECT count(*) FROM aip_agent_registry_receipt) AS receipts""").fetchone()
            if shape != {"tables": 592, "sequences": 12, "installations": 1, "receipts": 6}:
                raise ReaderMaintenanceBlocked("READER_CLONE_CATALOG_REQUIRED")
            return version, len(tables)
    except ReaderMaintenanceBlocked:
        raise
    except Exception:
        raise ReaderMaintenanceBlocked("READER_CLONE_DATABASE_READ_FAILED") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=("clone",))
    parser.add_argument("--admin-passfile", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if os.environ.get("AOS_DOTENV_DISABLED") != "1" or any(
                os.environ.get(key) for key in _FORBIDDEN_PG_ENV):
            raise ReaderMaintenanceBlocked("READER_CLONE_EXACT_ENV_REQUIRED")
        _require_private_passfile(args.admin_passfile)
        _inspect_clone()
        _require_restore_proof()
        version, table_count = _read_catalog(args.admin_passfile)
        print(json.dumps({"outcome": "READER_CLONE_DRY_RUN_GREEN", "database": DATABASE,
                          "version": version, "reader_tables": table_count,
                          "current_database_write": False}, sort_keys=True))
        return 0
    except ReaderMaintenanceBlocked as exc:
        print(json.dumps({"outcome": "READER_CLONE_DRY_RUN_BLOCKED", "reason": str(exc)},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
