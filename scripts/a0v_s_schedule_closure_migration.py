#!/usr/bin/env python3
"""Deploy the additive schedule unaccepted-analysis closure with frozen evidence."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/migration-082"
SOURCE, TARGET = "a0v_081", "a0v_082"
MIGRATION = ROOT / "services/aos-api/alembic/versions/a0v_082_schedule_unaccepted_analysis_closure.py"
TABLES = (
    "ecommerce_investigation_case_revision",
    "ecommerce_investigation_schedule_policy_revision",
    "ecommerce_investigation_schedule_policy_command_receipt",
    "automation_occurrence",
    "ecommerce_investigation_run",
    "ecommerce_analyst_growth_plan_revision",
    "aip_action_proposal",
    "aip_action_approval_event",
    "ecommerce_unaccepted_analysis_closure_receipt",
)
OCCURRENCE = "3c927751-b91a-53d0-8a42-7c5223ea109d"


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


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
    counts = {table: conn.execute(f"SELECT count(*) AS n FROM public.{table}").fetchone()["n"]
              for table in TABLES}
    exists = conn.execute(
        "SELECT to_regclass('public.ecommerce_schedule_policy_control_receipt') IS NOT NULL AS ok"
    ).fetchone()["ok"]
    controls = 0
    canary = 0
    if exists:
        controls = conn.execute("SELECT count(*) AS n FROM ecommerce_schedule_policy_control_receipt").fetchone()["n"]
        canary = conn.execute("SELECT count(*) AS n FROM ecommerce_schedule_policy_control_receipt "
                              "WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    return {
        "version": conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"],
        "counts": counts,
        "controlReceiptTable": bool(exists),
        "controlReceipts": controls,
        "canaryControlReceipts": canary,
        "heldSchedule": conn.execute("""SELECT count(*) AS n FROM automation_occurrence o
          JOIN automation_occurrence_dispatch_attempt a USING(org_id,project_id,occurrence_id)
          WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.occurrence_id=%s
            AND o.trigger_source='schedule' AND o.operation_id='ecommerce_growth_schedule_trigger'
            AND o.status='needs_attention' AND o.receipt_ref IS NULL
            AND a.status='unknown' AND a.receipt_ref IS NULL AND a.claim_until<clock_timestamp()""",
            (OCCURRENCE,)).fetchone()["n"],
        "targetReceipts": conn.execute("""SELECT count(*) AS n
          FROM ecommerce_growth_runtime_command_receipt r
          JOIN automation_occurrence_dispatch_attempt a ON a.org_id=r.org_id
            AND a.project_id=r.project_id AND a.target_idempotency_key=r.idempotency_key
          WHERE a.occurrence_id=%s AND r.operation_id='ecommerce_growth_analysis_advance'""",
            (OCCURRENCE,)).fetchone()["n"],
        "targetRuns": conn.execute("""SELECT count(*) AS n FROM ecommerce_investigation_run r
          JOIN automation_occurrence_dispatch_attempt a ON a.org_id=r.org_id AND a.project_id=r.project_id
            AND r.trigger_key=a.target_idempotency_key WHERE a.occurrence_id=%s""",
            (OCCURRENCE,)).fetchone()["n"],
    }


def prepare() -> dict:
    _require_m1()
    if _chain() != [TARGET]:
        raise RuntimeError("single migration step required")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        before = _snapshot(conn)
    if (
        before["version"] != SOURCE
        or not before["controlReceiptTable"]
        or before["controlReceipts"] != 1
        or before["canaryControlReceipts"] != 0
        or before["heldSchedule"] != 1
        or before["targetReceipts"] != 0
        or before["targetRuns"] != 0
    ):
        raise RuntimeError("exact a0v_081 held schedule baseline required")
    result = {"outcome": "A0V_082_SCHEDULE_UNACCEPTED_CLOSURE_PREPARED", "source": SOURCE,
              "target": TARGET, "migrationHash": _sha(MIGRATION.read_bytes()),
              "preparedAt": datetime.now(UTC).isoformat(), "before": before}
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
            "SELECT pg_try_advisory_lock(hashtext('aos.a0v-082.main'),hashtext(current_database())) AS ok"
        ).fetchone()["ok"]
        if not acquired:
            raise RuntimeError("migration lock busy")
        try:
            if _snapshot(lock) != proof["before"]:
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
            lock.execute("SELECT pg_advisory_unlock(hashtext('aos.a0v-082.main'),hashtext(current_database()))")
    if (after["version"] != TARGET or after["counts"] != proof["before"]["counts"]
            or not after["controlReceiptTable"] or after["controlReceipts"] != 1
            or after["canaryControlReceipts"] != 0):
        raise RuntimeError("migration changed business state")
    result = {"outcome": "A0V_082_SCHEDULE_UNACCEPTED_CLOSURE_APPLIED", "before": proof["before"],
              "after": after, "migrationHash": proof["migrationHash"]}
    _write("apply", result)
    return result


def audit() -> dict:
    proof = _load("apply")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        current = _snapshot(conn)
    if current != proof["after"]:
        raise RuntimeError("post-migration authority drifted")
    result = {"outcome": "A0V_082_SCHEDULE_UNACCEPTED_CLOSURE_GREEN",
              "current": current, "externalEffects": 0}
    _write("audit", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply", "audit"))
    args = parser.parse_args()
    print(json.dumps(globals()[args.phase](), ensure_ascii=False, sort_keys=True, default=str))
