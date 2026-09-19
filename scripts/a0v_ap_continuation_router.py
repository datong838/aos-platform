#!/usr/bin/env python3
"""Read-only deterministic continuation router for the AP recovery attempt."""
from __future__ import annotations

from contextlib import redirect_stdout
import json
import os
import sys


def classify(snapshot: dict, attempt_guard: dict) -> dict:
    if attempt_guard.get("automaticAction") is not False:
        raise RuntimeError("read-only AP attempt guard required")
    actions = {
        "RUNNING_HEALTHY_NO_ACTION": "OBSERVE_AP_RECOVERY",
        "RUNNING_HEARTBEAT_ONLY_DIAGNOSE": "DIAGNOSE_AP_BOUNDED_EXECUTION",
        "RUNNING_STALE_DIAGNOSE_ONLY": "DIAGNOSE_AP_HEARTBEAT",
        "SUCCEEDED_STRICT_CLOSURE": "RUN_AP_INSPECT_THEN_DISABLE",
        "FAILED_FREEZE_BOUNDARY": "FREEZE_AP_FAILURE_BOUNDARY",
        "ABANDONED_FREEZE_BOUNDARY": "FREEZE_AP_ABANDONED_BOUNDARY",
        "FAILED_CHAIN_PAUSE_REQUIRED": "RUN_AP_FAILED_PAUSE",
    }
    outcome = attempt_guard.get("outcome")
    if outcome not in actions:
        raise RuntimeError("unknown AP attempt guard result")
    return attempt_guard | {
        "nextAction": actions[outcome],
        "attemptId": snapshot.get("attemptId"),
        "state": snapshot.get("state"),
        "sourceReads": 0,
        "businessWrites": 0,
    }


def observe() -> dict:
    import a0v_ap_attempt_guard as guard
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection

    guard.shared.baseline.setup()
    with consumer_connection(runtime_worker_connection, guard.shared.baseline.SCOPE) as conn:
        snapshot = guard.read_facts(conn)
    return {"snapshot": snapshot, **classify(snapshot, guard.classify(snapshot))}


def main() -> int:
    try:
        with redirect_stdout(sys.stderr):
            result = observe()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as error:
        print(json.dumps({
            "outcome": "SAFE_BLOCKED",
            "automaticAction": False,
            "nextAction": "DIAGNOSE_AP_CONTINUATION_AUTHORITY",
            "errorType": type(error).__name__,
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    raise SystemExit(main())
