#!/usr/bin/env python3
"""Watch BA's natural recovery attempt and stop at its first terminal state."""
from __future__ import annotations

import argparse
import json
import time

import a0v_am_attempt_guard as shared
import a0v_ba_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


OPERATION_KEY = "snapshot-group-completion:c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
TERMINAL_STATES = {"succeeded", "failed", "abandoned"}


def classify(rows: list[dict]) -> dict:
    if not rows:
        return {"outcome": "WAITING_FOR_NATURAL_ATTEMPT", "terminal": False}
    if len(rows) != 1:
        return {"outcome": "SAFE_BLOCKED_MULTIPLE_ATTEMPTS", "terminal": False,
                "attemptCount": len(rows)}
    row = rows[0]
    if row.get("state") == "running":
        return {"outcome": "NATURAL_ATTEMPT_RUNNING", "terminal": False} | row
    if row.get("state") in TERMINAL_STATES:
        return {"outcome": "FIRST_NATURAL_ATTEMPT_TERMINAL", "terminal": True} | row
    return {"outcome": "SAFE_BLOCKED_UNKNOWN_STATE", "terminal": False} | row


def read_rows() -> list[dict]:
    shared.baseline.setup()
    with consumer_connection(runtime_worker_connection, shared.baseline.SCOPE) as conn:
        rows = conn.execute(
            """SELECT attempt_id::text,state,revision,accepted_at,heartbeat_at,lease_until,
              terminal_reason_code,terminal_error_type,idempotency_key,request_hash
              FROM extension_runtime_execution_attempt
              WHERE org_id='org-org' AND project_id='dev-project'
                AND installation_id=%s AND generation=%s
                AND operation_kind='recoverable_store' AND operation_key=%s
              ORDER BY accepted_at,attempt_id""",
            (successor.BA_ID, successor.BA_GENERATION, OPERATION_KEY),
        ).fetchall()
    return [dict(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=2)
    parser.add_argument("--budget-seconds", type=int, default=1800)
    args = parser.parse_args()
    started = time.monotonic()
    while True:
        result = classify(read_rows())
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
        if result["terminal"]:
            return 0
        if result["outcome"].startswith("SAFE_BLOCKED"):
            return 2
        if not args.watch:
            return 0
        if time.monotonic() - started >= args.budget_seconds:
            print(json.dumps({"outcome": "WATCH_BUDGET_EXHAUSTED", "terminal": False}), flush=True)
            return 3
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
