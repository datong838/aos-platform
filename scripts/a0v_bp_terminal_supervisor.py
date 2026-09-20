#!/usr/bin/env python3
"""Start BP's sole natural worker and stop it inline at terminal or elapsed budget."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import a0v_am_attempt_guard as shared
import a0v_bp_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts/a0v_bp_snapshot_product_api.py"
OPERATION_KEY = "snapshot-group-completion:c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
TERMINAL_STATES = {"succeeded", "failed", "abandoned"}
_SETUP_COMPLETE = False


def setup() -> None:
    global _SETUP_COMPLETE
    if not _SETUP_COMPLETE:
        successor.setup()
        _SETUP_COMPLETE = True


def classify(rows: list[dict], budget_seconds: int = 1800) -> dict:
    if not rows:
        return {"outcome": "WAITING_FOR_NATURAL_ATTEMPT", "stopWorker": False}
    if len(rows) != 1:
        return {"outcome": "SAFE_BLOCKED_MULTIPLE_ATTEMPTS", "stopWorker": True,
                "attemptCount": len(rows)}
    row = rows[0]
    if row.get("state") in TERMINAL_STATES:
        return {"outcome": "FIRST_NATURAL_ATTEMPT_TERMINAL", "stopWorker": True} | row
    if row.get("state") != "running":
        return {"outcome": "SAFE_BLOCKED_UNKNOWN_STATE", "stopWorker": True} | row
    if row.get("attempt_elapsed_seconds", -1) >= budget_seconds:
        return {"outcome": "ATTEMPT_ELAPSED_BUDGET_EXHAUSTED", "stopWorker": True} | row
    return {"outcome": "NATURAL_ATTEMPT_RUNNING", "stopWorker": False} | row


def read_rows() -> list[dict]:
    setup()
    with consumer_connection(runtime_worker_connection, shared.baseline.SCOPE) as conn:
        rows = conn.execute(
            """SELECT attempt_id::text,state,revision,accepted_at,heartbeat_at,lease_until,
              terminal_reason_code,terminal_error_type,idempotency_key,request_hash,
              greatest(0,floor(extract(epoch from (clock_timestamp()-accepted_at))))::int
                AS attempt_elapsed_seconds
              FROM extension_runtime_execution_attempt
              WHERE org_id='org-org' AND project_id='dev-project'
                AND installation_id=%s AND generation=%s
                AND operation_kind='recoverable_store' AND operation_key=%s
              ORDER BY accepted_at,attempt_id""",
            (successor.BP_ID, successor.BP_GENERATION, OPERATION_KEY),
        ).fetchall()
    return [dict(row) for row in rows]


def stop_worker(worker: subprocess.Popen, timeout_seconds: int = 180,
                kill_timeout_seconds: int = 30) -> dict:
    if worker.poll() is None:
        os.killpg(worker.pid, signal.SIGTERM)
    try:
        return_code = worker.wait(timeout=timeout_seconds)
        escalated = False
    except subprocess.TimeoutExpired:
        os.killpg(worker.pid, signal.SIGKILL)
        try:
            return_code = worker.wait(timeout=kill_timeout_seconds)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("exact BP worker did not stop after bounded escalation") from error
        escalated = True
    return {"workerPid": worker.pid, "workerReturnCode": return_code,
            "workerStopped": worker.poll() is not None, "workerKillEscalated": escalated}


def supervise(*, interval_seconds: int, budget_seconds: int) -> dict:
    if read_rows():
        raise RuntimeError("BP attempt must be zero before supervisor starts worker")
    worker_output = successor.STATE.parent / "snapshot-worker" / "preflight.json"
    worker = subprocess.Popen(
        [sys.executable, str(WORKER), "serve", "--output", str(worker_output)],
        cwd=ROOT, start_new_session=True,
    )
    result: dict = {"outcome": "WORKER_STARTING", "stopWorker": False}
    stop_requested = False
    try:
        while True:
            result = classify(read_rows(), budget_seconds)
            print(json.dumps(result | {"workerPid": worker.pid}, ensure_ascii=False,
                             default=str), flush=True)
            if result["stopWorker"]:
                stop_requested = True
                if worker.poll() is not None:
                    return result | {"workerPid": worker.pid,
                                     "workerReturnCode": worker.returncode,
                                     "workerStopped": True,
                                     "workerKillEscalated": False}
                return result | stop_worker(worker)
            if worker.poll() is not None:
                raise RuntimeError(f"BP worker exited before attempt boundary: {worker.returncode}")
            time.sleep(interval_seconds)
    finally:
        if worker.poll() is None and not stop_requested:
            stop_worker(worker)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-seconds", type=int, default=50)
    parser.add_argument("--budget-seconds", type=int, default=1800)
    args = parser.parse_args()
    result = supervise(interval_seconds=args.interval_seconds,
                       budget_seconds=args.budget_seconds)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0 if result["outcome"] == "FIRST_NATURAL_ATTEMPT_TERMINAL" else 3


if __name__ == "__main__":
    raise SystemExit(main())
