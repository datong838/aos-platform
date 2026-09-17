#!/usr/bin/env python3
"""Deploy a0v_083 after freezing the exact no-effect twelve-source group."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/migration-083"
SOURCE, TARGET = "a0v_082", "a0v_083"
GROUP = "f8d6b5af-f7a3-5f15-88ee-6432012f9537"
MIGRATION = ROOT / "services/aos-api/alembic/versions/a0v_083_snapshot_unaccepted_group_closure.py"
TABLES = (
    "pipeline_snapshot_schedule_claim", "pipeline_snapshot_schedule_member",
    "pipeline_snapshot_group_claim", "pipeline_snapshot_group_input", "pipeline_snapshot_group_member",
    "pipeline_controlled_source_claim", "ecommerce_ingress_command",
    "ecommerce_ingress_derived_command", "ecommerce_ingress_dataset_receipt", "meta_schedule_run",
)


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / f"{name}.json"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load(name):
    path = STATE / f"{name}.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {name} proof required")
    return json.loads(path.read_text(encoding="utf-8"))


def _storage():
    import a0v_controlled_source_claim_deploy as storage
    return storage


def _require_m1():
    if subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() != "m1":
        raise RuntimeError("m1 checkout required")


def _chain():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config(str(ROOT / "services/aos-api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "services/aos-api/alembic"))
    directory = ScriptDirectory.from_config(config)
    if directory.get_heads() != [TARGET]:
        raise RuntimeError("exact migration head required")
    return [step.revision for step in directory.iterate_revisions(TARGET, SOURCE)]


def _snapshot(conn):
    counts = {table: conn.execute(f"SELECT count(*) AS n FROM public.{table}").fetchone()["n"]
              for table in TABLES}
    receipt_table = conn.execute(
        "SELECT to_regclass('public.pipeline_snapshot_unaccepted_group_closure_receipt') IS NOT NULL AS ok"
    ).fetchone()["ok"]
    receipt_count = conn.execute(
        "SELECT count(*) AS n FROM pipeline_snapshot_unaccepted_group_closure_receipt"
    ).fetchone()["n"] if receipt_table else 0
    group = conn.execute("""SELECT c.request#>'{definitionRef}' AS original_ref,
          h.state,h.revision,h.content_hash,
          (SELECT count(*) FROM pipeline_snapshot_schedule_member m
            WHERE (m.org_id,m.project_id,m.group_id)=(c.org_id,c.project_id,c.group_id)) AS members,
          (SELECT count(*) FROM pipeline_snapshot_schedule_member m JOIN meta_schedule_run r
            ON (r.org_id,r.project_id,r.id)=(m.org_id,m.project_id,m.run_id)
            WHERE (m.org_id,m.project_id,m.group_id)=(c.org_id,c.project_id,c.group_id)
              AND r.status='running' AND r.finished_at IS NULL AND NOT r.executor_stopped) AS running,
          (SELECT count(*) FROM pipeline_snapshot_group_claim g
            WHERE (g.org_id,g.project_id,g.group_id)=(c.org_id,c.project_id,c.group_id)) AS group_claims,
          (SELECT count(*) FROM pipeline_snapshot_group_input g
            WHERE (g.org_id,g.project_id,g.group_id)=(c.org_id,c.project_id,c.group_id)) AS group_inputs,
          (SELECT count(*) FROM pipeline_controlled_source_claim x JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(x.org_id,x.project_id,x.run_id)
            WHERE (m.org_id,m.project_id,m.group_id)=(c.org_id,c.project_id,c.group_id)) AS source_claims
        FROM pipeline_snapshot_schedule_claim c
        JOIN pipeline_snapshot_schedule_definition_head h ON h.org_id=c.org_id AND h.project_id=c.project_id
          AND 'snapshot-schedule-'||h.definition_id::text=c.request#>>'{definitionRef,resourceId}'
        WHERE c.org_id='org-org' AND c.project_id='dev-project' AND c.group_id=%s""", (GROUP,)).fetchone()
    return {
        "version": conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"],
        "counts": counts, "receiptTable": bool(receipt_table), "receiptCount": receipt_count,
        "group": dict(group) if group else None,
    }


def prepare():
    _require_m1()
    if _chain() != [TARGET]:
        raise RuntimeError("single migration step required")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        before = _snapshot(conn)
    group = before["group"] or {}
    if (before["version"] != SOURCE or before["receiptTable"] or group.get("state") != "disabled"
            or group.get("revision") != 6 or group.get("members") != 12 or group.get("running") != 12
            or group.get("group_claims") != 0 or group.get("group_inputs") != 0
            or group.get("source_claims") != 0):
        raise RuntimeError("exact a0v_082 no-effect group baseline required")
    result = {"outcome": "A0V_083_SNAPSHOT_GROUP_CLOSURE_PREPARED", "source": SOURCE,
              "target": TARGET, "migrationHash": _sha(MIGRATION.read_bytes()),
              "preparedAt": datetime.now(UTC).isoformat(), "before": before}
    _write("prepare", result)
    return result


def apply():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import URL
    _require_m1()
    proof = _load("prepare")
    if proof["migrationHash"] != _sha(MIGRATION.read_bytes()) or _chain() != [TARGET]:
        raise RuntimeError("frozen migration proof differs")
    storage = _storage()
    args = storage.parameters(storage.MAIN)
    with storage.connect(storage.MAIN, autocommit=True) as lock:
        acquired = lock.execute(
            "SELECT pg_try_advisory_lock(hashtext('aos.a0v-083.main'),hashtext(current_database())) AS ok"
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
            lock.execute("SELECT pg_advisory_unlock(hashtext('aos.a0v-083.main'),hashtext(current_database()))")
    if (after["version"] != TARGET or after["counts"] != proof["before"]["counts"]
            or not after["receiptTable"] or after["receiptCount"] != 0
            or after["group"] != proof["before"]["group"]):
        raise RuntimeError("migration changed business state")
    result = {"outcome": "A0V_083_SNAPSHOT_GROUP_CLOSURE_APPLIED", "before": proof["before"],
              "after": after, "migrationHash": proof["migrationHash"]}
    _write("apply", result)
    return result


def audit():
    proof = _load("apply")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        current = _snapshot(conn)
    if current != proof["after"]:
        raise RuntimeError("post-migration authority drifted")
    result = {"outcome": "A0V_083_SNAPSHOT_GROUP_CLOSURE_MIGRATION_GREEN",
              "current": current, "externalEffects": 0}
    _write("audit", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
