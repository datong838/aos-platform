#!/usr/bin/env python3
"""Prove Y renews after one real stale row-lock entry without changing data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-y/contention-proof"
Y_ID = "c76d26b9-8a93-4476-a6fe-206e10930bc9"
GENERATION = "87cd4104-999d-4224-b1ee-772b22a05445"
APPLY_OPERATION = "017a11cc-87d5-468d-b15a-dcf5390a72f4"
SCOPE = ("org-org", "dev-project")
MAX_LOCK_SECONDS = 30.0
STALE_HOLD_SECONDS = 4.25


def connect():
    sys.path.insert(0, str(ROOT / "scripts"))
    from a0v_formal_text_model_renewal import database_connect
    return database_connect("aos_meta_head")


def freeze(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def latest(conn) -> dict:
    event = conn.execute("""SELECT sequence,occurred_at,payload FROM extension_runtime_event
      WHERE org_id=%s AND project_id=%s AND operation_id=%s AND type='runtime_lease_renewed'
      ORDER BY sequence DESC LIMIT 1""", (*SCOPE, APPLY_OPERATION)).fetchone()
    operation = conn.execute("""SELECT revision,status,phase,failure_code FROM extension_runtime_operation
      WHERE org_id=%s AND project_id=%s AND installation_id=%s AND operation_id=%s""",
      (*SCOPE, Y_ID, APPLY_OPERATION)).fetchone()
    binding = conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,desired_state,observed_state
      FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s
      AND installation_id=%s AND generation=%s""", (*SCOPE, Y_ID, GENERATION)).fetchone()
    resources = conn.execute("""SELECT resource_id::text,cleanup_state,observed_release,expires_at
      FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s
      AND operation_id=%s AND generation=%s ORDER BY resource_id""",
      (*SCOPE, APPLY_OPERATION, GENERATION)).fetchall()
    canary = conn.execute("""SELECT count(*) n FROM extension_runtime_binding
      WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()["n"]
    now = conn.execute("SELECT clock_timestamp() now").fetchone()["now"]
    if (event is None or operation is None or dict(operation)["status"] != "succeeded"
            or dict(operation)["phase"] != "succeeded" or dict(operation)["failure_code"] is not None
            or binding is None or dict(binding) != {"revision": 4, "execution_epoch": 3,
                "enabled": True, "operation_fence": False, "desired_state": "enabled",
                "observed_state": "ready"}
            or len(resources) != 3 or any(row["cleanup_state"] != "pending"
                or row["observed_release"] is not False or row["expires_at"] <= now for row in resources)
            or canary != 0):
        raise RuntimeError("exact live Y renewal baseline required")
    return {"event": dict(event), "operation": dict(operation), "binding": dict(binding),
            "resources": [dict(row) for row in resources], "canary": canary, "now": now}


def fresh_cycle(conn) -> dict:
    deadline = time.monotonic() + 75
    while True:
        value = latest(conn)
        age = (value["now"] - value["event"]["occurred_at"]).total_seconds()
        if 0 <= age <= 8:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError("fresh Y renewal cycle not observed")
        time.sleep(1)


def run() -> dict:
    output = STATE / "result.json"
    if output.exists():
        raise RuntimeError("immutable Y contention proof exists")
    with connect()() as observer:
        baseline = fresh_cycle(observer)
        # Host checks every two seconds after a sixty-second renewal delay and
        # other workers make the observed cadence vary. Enter early, then stop
        # 4.25s after the real blocked renewal rather than using a guessed edge.
        target = baseline["event"]["occurred_at"] + timedelta(seconds=50)
        wait = (target - baseline["now"]).total_seconds()
        if wait > 0:
            time.sleep(wait)
        with connect()() as locker:
            lock_pid = locker.execute("SELECT pg_backend_pid() pid").fetchone()["pid"]
            locked = locker.execute("""SELECT installation_id FROM bundle_installation
              WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",
              (*SCOPE, Y_ID)).fetchone()
            if locked is None or str(locked["installation_id"]) != Y_ID:
                locker.rollback()
                raise RuntimeError("exact Y installation row lock required")
            acquired = locker.execute("SELECT clock_timestamp() now").fetchone()["now"]
            lock_deadline = time.monotonic() + MAX_LOCK_SECONDS
            blocked = None
            blocked_at = None
            while time.monotonic() < lock_deadline:
                observer.execute("SELECT pg_stat_clear_snapshot()")
                row = observer.execute("""SELECT pid,wait_event_type,wait_event,query_start
                  FROM pg_stat_activity WHERE pid<>%s AND wait_event_type='Lock'
                  AND query LIKE '%%bundle_installation%%' ORDER BY query_start LIMIT 1""",
                  (lock_pid,)).fetchone()
                if row is not None:
                    blocked = dict(row)
                    blocked_at = time.monotonic()
                    break
                time.sleep(0.1)
            if blocked is None or blocked_at is None:
                locker.rollback()
                raise RuntimeError("Y Host row-lock wait not observed")
            if blocked_at + STALE_HOLD_SECONDS > lock_deadline:
                locker.rollback()
                raise RuntimeError("Y Host wait left no bounded stale interval")
            remaining = STALE_HOLD_SECONDS - (time.monotonic() - blocked_at)
            if remaining > 0:
                time.sleep(remaining)
            released = locker.execute("SELECT clock_timestamp() now").fetchone()["now"]
            locker.commit()
        deadline = time.monotonic() + 40
        while True:
            current = latest(observer)
            if current["event"]["sequence"] > baseline["event"]["sequence"]:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Y renewal did not recover after contention")
            time.sleep(0.5)
    health = datetime.fromisoformat(current["event"]["payload"]["healthCheckedAt"])
    if (health <= released or current["operation"]["revision"] <= baseline["operation"]["revision"]
            or any(after["expires_at"] <= before["expires_at"]
                   for before, after in zip(baseline["resources"], current["resources"]))):
        raise RuntimeError("Y post-contention renewal evidence differs")
    result = {"outcome": "Y_STALE_REPROBE_RENEWAL_GREEN",
              "baselineSequence": baseline["event"]["sequence"],
              "renewedSequence": current["event"]["sequence"],
              "baselineOperationRevision": baseline["operation"]["revision"],
              "renewedOperationRevision": current["operation"]["revision"],
              "lock": {"acquiredAt": acquired, "releasedAt": released,
                       "blockedBackend": blocked, "minimumBlockedSeconds": STALE_HOLD_SECONDS,
                       "maximumLockSeconds": MAX_LOCK_SECONDS},
              "renewal": current["event"], "binding": current["binding"],
              "resources": current["resources"], "canary": current["canary"],
              "businessWrites": 0, "sourceReads": 0}
    freeze(output, result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, default=str, indent=2))
