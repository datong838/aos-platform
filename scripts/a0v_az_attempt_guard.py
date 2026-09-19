#!/usr/bin/env python3
"""Read the exact AZ recovery boundary without taking a lock or executing work."""
from __future__ import annotations

from datetime import datetime, timedelta
import json

import a0v_am_attempt_guard as shared
import a0v_az_saved_snapshot_recovery as recovery
import a0v_az_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


ORIGINAL_ATTEMPT_ID = "5505b051-79f8-47a7-b2e2-4ddfc0893eb1"
ATTEMPT_ID = "af15b2e5-7c72-47f0-9e1d-79855a970fd6"
HEARTBEAT_FRESHNESS = timedelta(seconds=90)
SAVED_RECOVERY_EXECUTION_LIMIT_SECONDS = 1800
OPERATION_KEY = "snapshot-group-completion:c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
BASE_IDEMPOTENCY_KEY = "snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
IDEMPOTENCY_KEY = BASE_IDEMPOTENCY_KEY + ":2"
REQUEST_HASH = "sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7"
LINK_KEY = (
    "snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:"
    "bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b"
)


def _as_datetime(value) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def classify(facts: dict) -> dict:
    expected = {
        "attemptId": ATTEMPT_ID, "attemptCount": 2,
        "installationId": successor.AZ_ID, "generation": successor.AZ_GENERATION,
        "operationKind": "recoverable_store", "operationKey": OPERATION_KEY,
        "idempotencyKey": IDEMPOTENCY_KEY, "requestHash": REQUEST_HASH,
        "definitionRevision": 81, "definitionState": "enabled", "recoveryRevision": 26,
        "manifestHash": recovery.MANIFEST, "members": 12, "datasetReceipts": 12,
        "relationships": 1, "linkCommands": 1, "linkCount": 1168,
        "routes": 9, "liveResources": 3, "devOrgCanary": 0,
    }
    if any(facts.get(key) != value for key, value in expected.items()):
        raise RuntimeError("AZ guard authority differs")
    if facts.get("state") not in {"running", "succeeded", "failed", "abandoned"}:
        raise RuntimeError("AZ guard authority differs")
    history = facts.get("attemptHistory")
    if type(history) is not list or len(history) != 2:
        raise RuntimeError("AZ guard authority differs")
    expected_history = (
        (ORIGINAL_ATTEMPT_ID, BASE_IDEMPOTENCY_KEY + ":1", "failed",
         "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"),
        (ATTEMPT_ID, IDEMPOTENCY_KEY, facts["state"],
         facts.get("terminalReason"), facts.get("terminalErrorType")),
    )
    for row, expected_row in zip(history, expected_history):
        expected_id, expected_key, state, reason, error_type = expected_row
        if (row.get("attempt_id") != expected_id or row.get("idempotency_key") != expected_key
                or row.get("request_hash") != REQUEST_HASH or row.get("state") != state
                or row.get("terminal_reason_code") != reason
                or row.get("terminal_error_type") != error_type):
            raise RuntimeError("AZ guard authority differs")
    for key, maximum in {
        "runningRuns": 12, "succeededRuns": 12, "failedRuns": 12,
        "retirements": 1, "linkStoreReceipts": 1, "ecomLinks": 1168,
        "linkOutbox": 1168, "projectionPending": 1168,
    }.items():
        value = facts.get(key)
        if type(value) is not int or not 0 <= value <= maximum:
            raise RuntimeError("AZ guard authority differs")
    if sum(facts[key] for key in ("runningRuns", "succeededRuns", "failedRuns")) != 12:
        raise RuntimeError("AZ guard authority differs")
    elapsed = facts.get("attemptElapsedSeconds")
    remaining, expired = facts.get("controlSecondsRemaining"), facts.get("controlExpired")
    if (type(facts.get("revision")) is not int or facts["revision"] < 1
            or facts.get("acceptedAt") is None or type(elapsed) is not int or elapsed < 0
            or type(remaining) is not int or type(expired) is not bool
            or expired is not (remaining < 0)):
        raise RuntimeError("AZ guard authority differs")
    if facts["state"] == "running":
        observed = _as_datetime(facts["observedAt"])
        heartbeat, lease = facts.get("heartbeatAt"), facts.get("leaseUntil")
        healthy = bool(heartbeat and lease and _as_datetime(heartbeat) >= observed - HEARTBEAT_FRESHNESS
                       and _as_datetime(lease) > observed)
        no_store_progress = not any(facts[key] for key in (
            "retirements", "linkStoreReceipts", "ecomLinks", "linkOutbox"))
        if healthy and elapsed > SAVED_RECOVERY_EXECUTION_LIMIT_SECONDS and no_store_progress:
            return {"outcome": "RUNNING_HEARTBEAT_ONLY_DIAGNOSE", "automaticAction": False,
                    "heartbeatHealthy": True, "executionLimitExceeded": True}
        return {"outcome": "RUNNING_HEALTHY_NO_ACTION" if healthy else "RUNNING_STALE_DIAGNOSE_ONLY",
                "automaticAction": False, "heartbeatHealthy": healthy}
    if facts["state"] == "succeeded":
        if (facts["succeededRuns"] != 12 or facts["runningRuns"] or facts["failedRuns"]
                or any(facts[key] != value for key, value in {
                    "retirements": 1, "linkStoreReceipts": 1, "ecomLinks": 1168,
                    "linkOutbox": 1168, "projectionPending": 0,
                }.items())):
            raise RuntimeError("AZ guard authority differs")
        return {"outcome": "SUCCEEDED_STRICT_CLOSURE", "automaticAction": False}
    if facts["state"] == "abandoned":
        if (facts.get("terminalReason") != "ATTEMPT_LEASE_EXPIRED"
                or facts.get("terminalErrorType") is not None
                or facts["runningRuns"] != 12 or facts["succeededRuns"] or facts["failedRuns"]
                or any(facts[key] for key in (
                    "retirements", "linkStoreReceipts", "ecomLinks", "linkOutbox", "projectionPending"))):
            raise RuntimeError("AZ guard authority differs")
        return {"outcome": "ABANDONED_FREEZE_BOUNDARY", "automaticAction": False}
    if (facts.get("terminalReason") != "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED"
            or facts.get("terminalErrorType") != "IngressJournalConflict"
            or facts["runningRuns"] != 12 or facts["succeededRuns"] or facts["failedRuns"]
            or any(facts[key] for key in (
                "retirements", "linkStoreReceipts", "ecomLinks", "linkOutbox", "projectionPending"))):
        raise RuntimeError("AZ guard authority differs")
    return {"outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False}


def read_facts(conn) -> dict:
    scope = ("org-org", "dev-project")
    attempts = conn.execute(
        """SELECT attempt_id::text,idempotency_key,request_hash,state,
          terminal_reason_code,terminal_error_type
          FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
            AND execution_epoch=3 AND operation_kind='recoverable_store' AND operation_key=%s
          ORDER BY accepted_at,attempt_id""",
        (*scope, successor.AZ_ID, successor.AZ_GENERATION, OPERATION_KEY),
    ).fetchall()
    if len(attempts) != 2:
        raise RuntimeError("AZ guard authority differs")
    rows = [dict(row) for row in attempts]
    attempt = rows[-1]
    shared.ATTEMPT, shared.INSTALLATION, shared.GENERATION = (
        ATTEMPT_ID, successor.AZ_ID, successor.AZ_GENERATION)
    shared.LINK_KEY = LINK_KEY
    facts = shared.read_facts(conn)
    extra = conn.execute(
        """SELECT clock_timestamp() observed_at,
          (SELECT count(*) FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
              AND execution_epoch=3 AND operation_fence IS FALSE
              AND revision=126 AND cutover_group_revision=153) routes,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='succeeded' AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) succeeded_runs,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='failed' AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) failed_runs""",
        (*scope, successor.AZ_ID, successor.AZ_GENERATION,
         *scope, recovery.GROUP, *scope, recovery.GROUP),
    ).fetchone()
    return facts | {
        "attemptCount": len(rows), "attemptHistory": rows, "operationKey": OPERATION_KEY,
        "idempotencyKey": attempt["idempotency_key"], "requestHash": attempt["request_hash"],
        "terminalReason": attempt["terminal_reason_code"],
        "terminalErrorType": attempt["terminal_error_type"],
        "observedAt": extra["observed_at"], "routes": extra["routes"],
        "succeededRuns": extra["succeeded_runs"], "failedRuns": extra["failed_runs"],
    }


def main() -> int:
    try:
        shared.baseline.setup()
        with consumer_connection(runtime_worker_connection, shared.baseline.SCOPE) as conn:
            facts = read_facts(conn)
        print(json.dumps(facts | classify(facts), ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as error:
        print(json.dumps({"outcome": "SAFE_BLOCKED", "automaticAction": False,
                          "errorType": type(error).__name__}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
