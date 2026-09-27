"""Prepare a restorable, isolated A0-V clone; never migrate the source DB.

The source is the exact local recovery database. No mall source is accessed.
This command intentionally fails if any prior output or target clone exists.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from psycopg import connect, sql
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/aos-api"))
from a0v_formal_text_model_renewal import database_connect  # noqa: E402


SOURCE = "aos_meta_head"
CLONE = "aos_fullstack_preview_20260927"
STATE = ROOT.parent / ".aos-recovery-20260927" / "state" / "safe-fullstack"
CONTEXT = "colima-aos-extension"
CONTAINER = "aos-a0v-recovery-pg"


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _counts_digest(conn, names: list[str] | None = None) -> tuple[int, str]:
    rows = conn.execute("""SELECT tablename FROM pg_tables
        WHERE schemaname='public' ORDER BY tablename""").fetchall()
    available = [row["tablename"] for row in rows]
    if names is not None and any(name not in available for name in names):
        raise RuntimeError("source table disappeared from clone")
    counts = []
    for table in (available if names is None else names):
        count = conn.execute(sql.SQL("SELECT count(*) AS n FROM {}").format(
            sql.Identifier("public", table))).fetchone()["n"]
        counts.append((table, count))
    encoded = json.dumps(counts, separators=(",", ":")).encode()
    return len(counts), hashlib.sha256(encoded).hexdigest()


def _private_json(path: Path, value: dict) -> None:
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def prepare() -> dict:
    if subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT,
                               text=True).strip() != "m1":
        raise RuntimeError("exact m1 single-writer checkout required")
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    backup = STATE / "aos_meta_head-a0v_092-before-fullstack-preview.dump"
    proof = STATE / "prepare.json"
    if backup.exists() or proof.exists():
        raise RuntimeError("retained preparation requires read-only reconciliation")

    with database_connect(SOURCE)() as source:
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        identity = source.execute("""SELECT current_database() AS database,
            current_user AS role, (SELECT version_num FROM alembic_version) AS version""").fetchone()
        if identity["database"] != SOURCE or identity["version"] != "a0v_092":
            raise RuntimeError("exact recovery source/version required")
        exists = source.execute("SELECT 1 FROM pg_database WHERE datname=%s", (CLONE,)).fetchone()
        if exists:
            raise RuntimeError("dedicated preview clone already exists")
        before_tables, before_counts = _counts_digest(source)
        snapshot = source.execute("SELECT pg_export_snapshot() AS id").fetchone()["id"]
        parameters = source.info.get_parameters()
        parameters["password"] = source.info.password
        with backup.open("xb") as output:
            os.chmod(backup, 0o600)
            result = subprocess.run(["docker", "--context", CONTEXT, "exec", CONTAINER,
                "pg_dump", "-U", identity["role"], "-d", SOURCE, "-Fc",
                "--snapshot", snapshot], stdout=output, stderr=subprocess.PIPE,
                timeout=300, check=False)
            output.flush()
            os.fsync(output.fileno())
        if result.returncode or backup.stat().st_size == 0:
            raise RuntimeError("snapshot backup failed; retained file requires inspection")

    with backup.open("rb") as input_file:
        listing = subprocess.run(["docker", "--context", CONTEXT, "exec", "-i",
            CONTAINER, "pg_restore", "--list"], stdin=input_file,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False)
    if listing.returncode or b"TABLE DATA" not in listing.stdout:
        raise RuntimeError("backup archive catalog invalid; do not restore")

    parameters["dbname"] = SOURCE
    with connect(**parameters, row_factory=dict_row, autocommit=True) as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (CLONE,)).fetchone():
            raise RuntimeError("preview clone appeared before creation")
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(CLONE)))
        admin.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(CLONE)))

    with backup.open("rb") as input_file:
        restored = subprocess.run(["docker", "--context", CONTEXT, "exec", "-i",
            CONTAINER, "pg_restore", "-U", identity["role"], "-d", CLONE,
            "--exit-on-error"], stdin=input_file, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=300, check=False)
    if restored.returncode:
        raise RuntimeError("clone restore failed; preserve clone/backup for read-only diagnosis")

    parameters["dbname"] = CLONE
    with connect(**parameters, row_factory=dict_row) as clone:
        clone.execute("SET TRANSACTION READ ONLY")
        version = clone.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
        tables, counts = _counts_digest(clone)
        clone.rollback()
    if version != "a0v_092" or tables != before_tables or counts != before_counts:
        raise RuntimeError("clone identity/counts differ; do not migrate")

    result = {
        "outcome": "RESTORABLE_ISOLATED_A0V_092_CLONE_VERIFIED",
        "source": SOURCE, "clone": CLONE,
        "sourceVersion": identity["version"], "cloneVersion": version,
        "backup": {"path": str(backup), "bytes": backup.stat().st_size,
                   "sha256": _digest(backup), "mode": "0600"},
        "tableCount": tables, "rowCountsDigest": counts,
        "businessWritesToSource": 0,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    _private_json(proof, result)
    return {key: value for key, value in result.items() if key != "backup"} | {
        "backupBytes": result["backup"]["bytes"]}


def migrate_clone() -> dict:
    """Upgrade only the verified clone, one committed Alembic revision at a time."""
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import URL, create_engine

    proof_path = STATE / "prepare.json"
    intent_path = STATE / "clone-migration-intent.json"
    result_path = STATE / "clone-migration.json"
    if not proof_path.is_file() or intent_path.exists() or result_path.exists():
        raise RuntimeError("unique verified preparation and no prior migration intent required")
    proof = json.loads(proof_path.read_text())
    backup = Path(proof["backup"]["path"])
    if (proof.get("outcome") != "RESTORABLE_ISOLATED_A0V_092_CLONE_VERIFIED"
            or proof.get("source") != SOURCE or proof.get("clone") != CLONE
            or backup.is_symlink() or not backup.is_file()
            or backup.stat().st_mode & 0o777 != 0o600
            or backup.stat().st_size != proof["backup"]["bytes"]
            or _digest(backup) != proof["backup"]["sha256"]):
        raise RuntimeError("retained backup/clone proof drifted")

    with database_connect(SOURCE)() as source:
        source.execute("SET TRANSACTION READ ONLY")
        if source.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] != "a0v_092":
            raise RuntimeError("source recovery version changed")
        names = [row["tablename"] for row in source.execute("""SELECT tablename
            FROM pg_tables WHERE schemaname='public' ORDER BY tablename""").fetchall()]
        if _counts_digest(source, names) != (proof["tableCount"], proof["rowCountsDigest"]):
            raise RuntimeError("source recovery counts changed")
        parameters = source.info.get_parameters()
        parameters["password"] = source.info.password
        source.rollback()
    parameters["dbname"] = CLONE
    with connect(**parameters, row_factory=dict_row) as clone:
        clone.execute("SET TRANSACTION READ ONLY")
        if clone.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] != "a0v_092":
            raise RuntimeError("clone version changed before migration")
        if _counts_digest(clone, names) != (proof["tableCount"], proof["rowCountsDigest"]):
            raise RuntimeError("clone counts changed before migration")
        clone.rollback()

    root = ROOT / "services/aos-api"
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    revisions = [f"a0v_{index:03d}" for index in range(93, 107)]
    directory = ScriptDirectory.from_config(cfg)
    actual = [item.revision for item in directory.iterate_revisions("a0v_106", "a0v_092")]
    if directory.get_heads() != ["a0v_106"] or actual[::-1] != revisions:
        raise RuntimeError("exact linear 092 to 106 migration chain required")
    _private_json(intent_path, {"source": SOURCE, "clone": CLONE,
        "sourceVersion": "a0v_092", "targetVersion": "a0v_106",
        "revisions": revisions, "backupSha256": proof["backup"]["sha256"],
        "createdAt": datetime.now(timezone.utc).isoformat()})

    url = URL.create("postgresql+psycopg", username=parameters["user"],
        password=parameters["password"], host=parameters["host"],
        port=int(parameters["port"]), database=CLONE)
    engine = create_engine(url, connect_args={
        "options": "-c lock_timeout=5s -c statement_timeout=60s"})
    try:
        for revision in revisions:
            with engine.begin() as connection:
                cfg.attributes["connection"] = connection
                current = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                expected = "a0v_092" if revision == revisions[0] else revisions[revisions.index(revision) - 1]
                if current != expected:
                    raise RuntimeError("clone migration boundary changed")
                command.upgrade(cfg, revision)
                after = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                if after != revision:
                    raise RuntimeError("clone migration revision not committed as expected")
    finally:
        engine.dispose()
    with connect(**parameters, row_factory=dict_row) as clone:
        clone.execute("SET TRANSACTION READ ONLY")
        version = clone.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
        old_table_count, old_counts = _counts_digest(clone, names)
        all_table_count, _ = _counts_digest(clone)
        clone.rollback()
    if version != "a0v_106" or (old_table_count, old_counts) != (
            proof["tableCount"], proof["rowCountsDigest"]):
        raise RuntimeError("clone migrated schema or historical row counts drifted")
    result = {"outcome": "ISOLATED_CLONE_A0V_106_MIGRATION_VERIFIED",
        "source": SOURCE, "clone": CLONE, "sourceVersion": "a0v_092",
        "cloneVersion": version, "revisions": revisions,
        "originalTableCount": old_table_count, "migratedTableCount": all_table_count,
        "originalRowCountsDigest": old_counts, "businessWritesToSource": 0,
        "createdAt": datetime.now(timezone.utc).isoformat()}
    _private_json(result_path, result)
    return result


def serve_clone() -> None:
    """Serve HTTP against the migrated clone with every natural executor off."""
    from psycopg.conninfo import make_conninfo

    proof_path = STATE / "prepare.json"
    migration_path = STATE / "clone-migration.json"
    if not proof_path.is_file() or not migration_path.is_file():
        raise RuntimeError("verified backup and clone migration required before HTTP")
    proof = json.loads(proof_path.read_text())
    migration = json.loads(migration_path.read_text())
    backup = Path(proof["backup"]["path"])
    if (migration.get("outcome") != "ISOLATED_CLONE_A0V_106_MIGRATION_VERIFIED"
            or migration.get("clone") != CLONE
            or migration.get("businessWritesToSource") != 0
            or backup.is_symlink() or not backup.is_file()
            or _digest(backup) != proof["backup"]["sha256"]):
        raise RuntimeError("isolated HTTP authority proof drifted")
    for port in (8080, 18181):
        listener = subprocess.run(["lsof", "-nP", f"-iTCP:{port}",
            "-sTCP:LISTEN"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=5, check=False)
        if listener.returncode != 1 or listener.stderr:
            raise RuntimeError("HTTP or second runtime port is not free")
    with database_connect(SOURCE)() as source:
        source.execute("SET TRANSACTION READ ONLY")
        if source.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] != "a0v_092":
            raise RuntimeError("recovery source version changed before preview")
        parameters = source.info.get_parameters()
        parameters["password"] = source.info.password
        source.rollback()
    parameters["dbname"] = CLONE
    with connect(**parameters, row_factory=dict_row) as clone:
        clone.execute("SET TRANSACTION READ ONLY")
        if clone.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] != "a0v_106":
            raise RuntimeError("preview clone version changed before HTTP")
        clone.rollback()

    flags = {
        "AOS_DOTENV_DISABLED": "1",
        "AOS_DB_MIGRATION_MODE": "disabled",
        "AOS_QYH_CRON_ENABLED": "false",
        "AOS_AIP_LOGIC_AUTOMATION_ENABLED": "false",
        "AOS_SNAPSHOT_GROUP_WORKER_ENABLED": "false",
        "AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED": "false",
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
        "AOS_JDBC_SSH_PREBUILD_ENABLED": "false",
        "AOS_ECOM_CONTENT_TASKRUN_WORKER_ENABLED": "false",
        "AOS_ECOM_CONTENT_AGENTRUN_WORKER_ENABLED": "false",
        "AOS_ECOM_CONTENT_CAPACITY_WORKER_ENABLED": "false",
        "AOS_ECOM_CONTENT_BUDGET_COMMAND_WORKER_ENABLED": "false",
        "AOS_ECOM_FEEDBACK_WORKER_ENABLED": "false",
        "AOS_ECOM_IMPROVEMENT_WORKER_ENABLED": "false",
        "AOS_ECOM_EFFECT_REVIEW_WORKER_ENABLED": "false",
        "AOS_ECOM_MEMORY_CANDIDATE_WORKER_ENABLED": "false",
        "AOS_ECOM_CONTENT_RETURN_WORKER_ENABLED": "false",
        "AOS_ECOM_CONTENT_WORKER_ENABLED": "false",
        "AOS_ECOM_CONTENT_STEP_WORKER_ENABLED": "false",
        "AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED": "false",
    }
    os.environ.update(flags)
    os.environ["AOS_DATABASE_URL"] = make_conninfo(**parameters)
    print(json.dumps({"outcome": "ISOLATED_CLONE_HTTP_STARTING",
        "database": CLONE, "databaseVersion": "a0v_106",
        "host": "127.0.0.1", "port": 8080,
        "migrationMode": "disabled", "runtimeHost": 0,
        "workersEnabled": 0, "sourceCalls": 0}, sort_keys=True), flush=True)
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    from aos_api.main import app
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080, workers=1,
                reload=False, access_log=False, log_level="warning")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--migrate-clone", action="store_true")
    mode.add_argument("--serve-clone", action="store_true")
    args = parser.parse_args()
    if args.serve_clone:
        serve_clone()
    else:
        print(json.dumps(prepare() if args.prepare else migrate_clone(),
            ensure_ascii=False, sort_keys=True))
