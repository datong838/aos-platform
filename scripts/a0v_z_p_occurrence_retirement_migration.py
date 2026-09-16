#!/usr/bin/env python3
"""Apply the isolated released-occurrence retirement contract to main exactly once."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260916/state/z-p-a0v-076"
SOURCE, TARGET = "a0v_075", "a0v_076"
MIGRATION = ROOT / "services/aos-api/alembic/versions/a0v_076_released_occurrence_retirement.py"
EVENT_FUNCTION = "public.extension_event_control_dispatch_transition_a0v_054(jsonb,text)"
CLOSURE_FUNCTION = "public.ecommerce_unaccepted_analysis_close_a0v_060(jsonb,text)"
TABLES = (
    "extension_runtime_binding", "extension_runtime_operation",
    "extension_runtime_resource_lease", "extension_operation_dispatch_binding",
    "extension_event_control_dispatch_receipt", "automation_schedule_binding",
    "automation_occurrence", "automation_occurrence_dispatch_attempt",
    "ecommerce_growth_runtime_command_receipt", "ecommerce_investigation_run",
    "ecommerce_investigation_schedule_policy_head", "ecommerce_product_event_origin",
    "ecommerce_unaccepted_analysis_closure_receipt",
)


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load(path: Path) -> dict:
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {path.name} required")
    return json.loads(path.read_text(encoding="utf-8"))


def _require_m1() -> None:
    if subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() != "m1":
        raise RuntimeError("m1 checkout required")
    leases = json.loads((ROOT.parent / "docs/palantier/AOS项目开发上下文/memory/leases.json").read_text())["leases"]
    now = datetime.now(timezone.utc)
    if not any(item.get("owner") == "m1" and item.get("status") == "ACTIVE"
               and datetime.fromisoformat(item["lease_expires_at"]) > now for item in leases):
        raise RuntimeError("active m1 lease required")


def _storage():
    import a0v_controlled_source_claim_deploy as storage
    return storage


def _fingerprint(conn) -> dict:
    from psycopg import sql
    result = {}
    for table in TABLES:
        row = conn.execute(sql.SQL(
            "SELECT count(*) AS count,md5(string_agg(md5(to_jsonb(t)::text),'' "
            "ORDER BY md5(to_jsonb(t)::text))) AS digest FROM {} t"
        ).format(sql.Identifier("public", table))).fetchone()
        result[table] = dict(row)
    return result


def _definition(conn, function: str) -> str:
    return conn.execute("SELECT pg_get_functiondef(%s::regprocedure) AS body", (function,)).fetchone()["body"]


def _audit(conn) -> dict:
    versions = [row["version_num"] for row in conn.execute("SELECT version_num FROM alembic_version").fetchall()]
    event = _definition(conn, EVENT_FUNCTION)
    closure = _definition(conn, CLOSURE_FUNCTION)
    return {
        "versions": versions,
        "eventFunctionHash": _sha(event.encode()),
        "closureFunctionHash": _sha(closure.encode()),
        "acceptsSafeUnknown": "a.status='unknown' AND (" in event,
        "supportsReleasedClosure": "v_released_mode:=coalesce" in closure,
        "supportsPendingUnclaimed": "v_o.status NOT IN ('needs_attention','pending')" in closure,
        "fingerprint": _fingerprint(conn),
    }


def _chain() -> list[str]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config(str(ROOT / "services/aos-api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "services/aos-api/alembic"))
    directory = ScriptDirectory.from_config(config)
    if directory.get_heads() != [TARGET]:
        raise RuntimeError("exact migration head required")
    return [step.revision for step in directory.iterate_revisions(TARGET, SOURCE)]


def prepare() -> dict:
    _require_m1()
    if _chain() != [TARGET]:
        raise RuntimeError("single migration step required")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        audit = _audit(conn)
    if (audit["versions"] != [SOURCE] or audit["acceptsSafeUnknown"]
            or audit["supportsReleasedClosure"] or audit["supportsPendingUnclaimed"]):
        raise RuntimeError("main baseline differs")
    result = {
        "outcome": "A0V_076_MAIN_PREPARED", "source": SOURCE, "target": TARGET,
        "migrationHash": _sha(MIGRATION.read_bytes()), "before": audit,
    }
    _write(STATE / "prepare.json", result)
    return result


def apply() -> dict:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import URL
    _require_m1()
    proof = _load(STATE / "prepare.json")
    if (proof.get("outcome") != "A0V_076_MAIN_PREPARED" or proof.get("source") != SOURCE
            or proof.get("target") != TARGET or proof.get("migrationHash") != _sha(MIGRATION.read_bytes())
            or _chain() != [TARGET]):
        raise RuntimeError("frozen migration proof differs")
    storage = _storage()
    args = storage.parameters(storage.MAIN)
    with storage.connect(storage.MAIN, autocommit=True) as lock:
        acquired = lock.execute(
            "SELECT pg_try_advisory_lock(hashtext('aos.a0v-076.main'),hashtext(current_database())) AS ok"
        ).fetchone()["ok"]
        if not acquired:
            raise RuntimeError("migration lock busy")
        try:
            current = _audit(lock)
            if current != proof["before"]:
                raise RuntimeError("main changed after preparation")
            config = Config(str(ROOT / "services/aos-api/alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "services/aos-api/alembic"))
            url = URL.create("postgresql+psycopg", username=args["user"], password=args["password"],
                host=args["host"], port=int(args["port"]), database=storage.MAIN,
                query={"options": "-c lock_timeout=5s -c statement_timeout=30s"})
            config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
            previous = os.environ.pop("AOS_DATABASE_URL", None)
            try:
                command.upgrade(config, TARGET)
            finally:
                if previous is not None:
                    os.environ["AOS_DATABASE_URL"] = previous
            after = _audit(lock)
        finally:
            lock.execute("SELECT pg_advisory_unlock(hashtext('aos.a0v-076.main'),hashtext(current_database()))")
    if (after["versions"] != [TARGET] or not after["acceptsSafeUnknown"]
            or not after["supportsReleasedClosure"] or not after["supportsPendingUnclaimed"]
            or after["fingerprint"] != proof["before"]["fingerprint"]):
        raise RuntimeError("main migration verification failed closed")
    result = {"outcome": "A0V_076_MAIN_APPLIED", "source": SOURCE, "target": TARGET,
              "migrationHash": proof["migrationHash"], "before": proof["before"], "after": after}
    _write(STATE / "apply.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply"))
    args = parser.parse_args()
    print(json.dumps(prepare() if args.phase == "prepare" else apply(), ensure_ascii=False, indent=2))
