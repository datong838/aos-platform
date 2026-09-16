#!/usr/bin/env python3
"""Deploy and execute the exact A0-V schedule cursor repair once."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260916/state/z-q-source-cursor-repair-v1"
SOURCE, TARGET = "a0v_076", "a0v_077"
MIGRATION = ROOT / "services/aos-api/alembic/versions/a0v_077_schedule_cursor_repair.py"
SCHEDULE = "sch-p02-qyh-controlled-20260913-v1"
EXPECTED = "scr-bddff0a74c2a4365"
TARGET_RUN = "scr-4eda5462575a4740"
KEY = "a0v-qyh-product-source-cursor-repair-20260917-v1"


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _write(name: str, value: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / f"{name}.json"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load(name: str) -> dict:
    path = STATE / f"{name}.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {name} proof required")
    return json.loads(path.read_text(encoding="utf-8"))


def _storage():
    import a0v_controlled_source_claim_deploy as storage
    return storage


def _require_m1() -> None:
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if branch != "m1":
        raise RuntimeError("m1 checkout required")
    leases = json.loads(
        (ROOT.parent / "docs/palantier/AOS项目开发上下文/memory/leases.json").read_text()
    )["leases"]
    now = datetime.now(timezone.utc)
    if not any(
        item.get("owner") == "m1" and item.get("status") == "ACTIVE"
        and datetime.fromisoformat(item["lease_expires_at"]) > now
        for item in leases
    ):
        raise RuntimeError("active m1 lease required")


def _chain() -> list[str]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config(str(ROOT / "services/aos-api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "services/aos-api/alembic"))
    directory = ScriptDirectory.from_config(config)
    if directory.get_heads() != [TARGET]:
        raise RuntimeError("exact migration head required")
    return [step.revision for step in directory.iterate_revisions(TARGET, SOURCE)]


def _snapshot(conn) -> dict:
    schedule = conn.execute(
        "SELECT id,enabled,last_run,updated_at FROM meta_schedule "
        "WHERE org_id='org-org' AND project_id='dev-project' AND id=%s",
        (SCHEDULE,),
    ).fetchone()
    runs = [dict(row) for row in conn.execute(
        "SELECT id,status,trigger,scheduled_for,started_at,finished_at,duration_ms,rows_written,"
        "error_code,executor_stopped FROM meta_schedule_run "
        "WHERE org_id='org-org' AND project_id='dev-project' AND schedule_id=%s "
        "ORDER BY finished_at NULLS LAST,id",
        (SCHEDULE,),
    ).fetchall()]
    has_receipts = conn.execute(
        "SELECT to_regclass('public.schedule_cursor_repair_receipt') IS NOT NULL AS ok"
    ).fetchone()["ok"]
    receipt_count = 0
    canary_receipts = 0
    if has_receipts:
        receipt_count = conn.execute(
            "SELECT count(*) AS n FROM schedule_cursor_repair_receipt"
        ).fetchone()["n"]
        canary_receipts = conn.execute(
            "SELECT count(*) AS n FROM schedule_cursor_repair_receipt "
            "WHERE org_id='dev-org' AND project_id='dev-project'"
        ).fetchone()["n"]
    result = {
        "version": conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"],
        "schedule": None if schedule is None else dict(schedule),
        "runsHash": _sha(json.dumps(runs, sort_keys=True, default=str).encode()),
        "latestStoppedSuccess": next((row for row in reversed(runs)
            if row["status"] == "succeeded" and row["executor_stopped"]), None),
        "running": sum(1 for row in runs if row["status"] == "running"),
        "receiptCount": receipt_count,
        "canaryReceipts": canary_receipts,
    }
    return json.loads(json.dumps(result, default=str))


def prepare() -> dict:
    _require_m1()
    if _chain() != [TARGET]:
        raise RuntimeError("single migration step required")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        before = _snapshot(conn)
    schedule = before["schedule"]
    latest = before["latestStoppedSuccess"]
    if (before["version"] != SOURCE or schedule is None or schedule["enabled"]
            or schedule["last_run"].get("id") != EXPECTED or latest is None
            or latest["id"] != TARGET_RUN or before["running"] != 0
            or before["receiptCount"] != 0 or before["canaryReceipts"] != 0):
        raise RuntimeError("exact stale cursor baseline required")
    result = {"outcome": "A0V_077_CURSOR_REPAIR_PREPARED", "source": SOURCE,
              "target": TARGET, "migrationHash": _sha(MIGRATION.read_bytes()), "before": before}
    _write("prepare", result)
    return result


def apply() -> dict:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import URL
    _require_m1()
    proof = _load("prepare")
    if (proof["migrationHash"] != _sha(MIGRATION.read_bytes()) or _chain() != [TARGET]
            or proof["source"] != SOURCE or proof["target"] != TARGET):
        raise RuntimeError("frozen migration proof differs")
    storage = _storage()
    args = storage.parameters(storage.MAIN)
    with storage.connect(storage.MAIN, autocommit=True) as lock:
        acquired = lock.execute(
            "SELECT pg_try_advisory_lock(hashtext('aos.a0v-077.main'),hashtext(current_database())) AS ok"
        ).fetchone()["ok"]
        if not acquired:
            raise RuntimeError("migration lock busy")
        try:
            current = _snapshot(lock)
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
            after = _snapshot(lock)
        finally:
            lock.execute("SELECT pg_advisory_unlock(hashtext('aos.a0v-077.main'),hashtext(current_database()))")
    if (after["version"] != TARGET or after["schedule"] != proof["before"]["schedule"]
            or after["runsHash"] != proof["before"]["runsHash"] or after["receiptCount"] != 0):
        raise RuntimeError("migration changed business state")
    result = {"outcome": "A0V_077_CURSOR_REPAIR_MIGRATION_APPLIED", "before": proof["before"],
              "after": after, "migrationHash": proof["migrationHash"]}
    _write("apply", result)
    return result


def repair() -> dict:
    _require_m1()
    proof = _load("apply")
    if proof["after"]["version"] != TARGET:
        raise RuntimeError("applied migration proof required")
    request = {"schemaVersion": "aos.schedule-cursor-repair/v1", "orgId": "org-org",
               "projectId": "dev-project", "scheduleId": SCHEDULE,
               "expectedCurrentRunId": EXPECTED, "targetRunId": TARGET_RUN,
               "idempotencyKey": KEY}
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        before = _snapshot(conn)
    with storage.connect(storage.MAIN) as conn:
        conn.execute("SET LOCAL ROLE aos_extension_maintainer")
        receipt = conn.execute(
            "SELECT schedule_cursor_repair_a0v_077(%s::jsonb,%s) AS body",
            (json.dumps(request), "a0v-cursor-repair-operator"),
        ).fetchone()["body"]
    with storage.connect(storage.MAIN) as conn:
        after = _snapshot(conn)
    if (receipt.get("replayed") or receipt.get("targetRunId") != TARGET_RUN
            or before["schedule"]["last_run"]["id"] != EXPECTED
            or after["schedule"]["last_run"]["id"] != TARGET_RUN
            or after["runsHash"] != before["runsHash"] or after["receiptCount"] != 1
            or after["canaryReceipts"] != 0):
        raise RuntimeError("cursor repair verification failed")
    result = {"outcome": "A0V_077_SOURCE_CURSOR_REPAIRED", "request": request,
              "receipt": receipt, "before": before, "after": after}
    _write("repair", result)
    return result


def audit() -> dict:
    proof = _load("repair")
    storage = _storage()
    request = proof["request"]
    with storage.connect(storage.MAIN) as conn:
        conn.execute("SET LOCAL ROLE aos_extension_maintainer")
        replay = conn.execute(
            "SELECT schedule_cursor_repair_a0v_077(%s::jsonb,%s) AS body",
            (json.dumps(request), "a0v-cursor-repair-operator"),
        ).fetchone()["body"]
    with storage.connect(storage.MAIN) as conn:
        current = _snapshot(conn)
    if (not replay.get("replayed") or replay.get("receiptId") != proof["receipt"]["receiptId"]
            or current["schedule"]["last_run"]["id"] != TARGET_RUN
            or current["receiptCount"] != 1 or current["canaryReceipts"] != 0):
        raise RuntimeError("cursor repair replay audit failed")
    result = {"outcome": "A0V_077_SOURCE_CURSOR_REPAIR_GREEN", "replay": replay,
              "current": current, "externalEffects": 0}
    _write("audit", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply", "repair", "audit"))
    args = parser.parse_args()
    print(json.dumps(globals()[args.phase](), ensure_ascii=False, indent=2, default=str))
