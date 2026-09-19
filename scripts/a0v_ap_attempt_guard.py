#!/usr/bin/env python3
"""Read the exact AP recovery boundary without taking the installation lock."""
from __future__ import annotations

from datetime import datetime, timedelta
import json

import a0v_am_attempt_guard as shared
import a0v_ap_saved_snapshot_recovery as recovery
import a0v_ap_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


ATTEMPT_ID = "93e2fc05-ebcb-46e1-8288-2bb0be32ae31"
SECOND_ATTEMPT_ID = "434092c8-c519-440f-8822-5ecff74287b5"
HEARTBEAT_FRESHNESS = timedelta(seconds=90)
SAVED_RECOVERY_EXECUTION_LIMIT_SECONDS = 300
OPERATION_KEY = "snapshot-group-completion:c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
BASE_IDEMPOTENCY_KEY = "snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
REQUEST_HASH = "sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7"


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def classify(facts: dict) -> dict:
    expected = {
        "attemptId": SECOND_ATTEMPT_ID,
        "attemptCount": 2,
        "installationId": successor.AP_ID,
        "generation": successor.AP_GENERATION,
        "operationKind": "recoverable_store",
        "operationKey": OPERATION_KEY,
        "idempotencyKey": BASE_IDEMPOTENCY_KEY + ":2",
        "requestHash": REQUEST_HASH,
        "definitionRevision": 62,
        "definitionState": "enabled",
        "recoveryRevision": 20,
        "manifestHash": recovery.MANIFEST,
        "members": 12,
        "datasetReceipts": 12,
        "relationships": 1,
        "linkCommands": 1,
        "linkCount": 1168,
        "routes": 9,
        "liveResources": 3,
        "devOrgCanary": 0,
    }
    if any(facts.get(key) != value for key, value in expected.items()):
        raise RuntimeError("AP guard authority differs")
    if facts.get("state") not in {"running", "succeeded", "failed", "abandoned"}:
        raise RuntimeError("AP guard authority differs")
    for key, maximum in {
        "runningRuns": 12,
        "succeededRuns": 12,
        "failedRuns": 12,
        "retirements": 1,
        "linkStoreReceipts": 1,
        "ecomLinks": 1168,
        "linkOutbox": 1168,
        "projectionPending": 1168,
    }.items():
        value = facts.get(key)
        if type(value) is not int or not 0 <= value <= maximum:
            raise RuntimeError("AP guard authority differs")
    if sum(facts[key] for key in ("runningRuns", "succeededRuns", "failedRuns")) != 12:
        raise RuntimeError("AP guard authority differs")
    if type(facts.get("revision")) is not int or facts["revision"] < 1:
        raise RuntimeError("AP guard authority differs")
    elapsed = facts.get("attemptElapsedSeconds")
    if facts.get("acceptedAt") is None or type(elapsed) is not int or elapsed < 0:
        raise RuntimeError("AP guard authority differs")
    remaining, expired = facts.get("controlSecondsRemaining"), facts.get("controlExpired")
    if type(remaining) is not int or type(expired) is not bool or expired is not (remaining < 0):
        raise RuntimeError("AP guard authority differs")

    state = facts["state"]
    if state == "running":
        observed = _as_datetime(facts["observedAt"])
        heartbeat = _as_datetime(facts["heartbeatAt"])
        lease = _as_datetime(facts["leaseUntil"])
        healthy = heartbeat >= observed - HEARTBEAT_FRESHNESS and lease > observed
        store_progress = any(facts[key] for key in (
            "retirements", "linkStoreReceipts", "ecomLinks", "linkOutbox",
        ))
        if healthy and elapsed > SAVED_RECOVERY_EXECUTION_LIMIT_SECONDS and not store_progress:
            return {
                "outcome": "RUNNING_HEARTBEAT_ONLY_DIAGNOSE",
                "automaticAction": False,
                "heartbeatHealthy": True,
                "executionLimitExceeded": True,
            }
        return {
            "outcome": "RUNNING_HEALTHY_NO_ACTION" if healthy else "RUNNING_STALE_DIAGNOSE_ONLY",
            "automaticAction": False,
            "heartbeatHealthy": healthy,
        }
    if state == "succeeded":
        if facts["succeededRuns"] != 12 or facts["runningRuns"] or facts["failedRuns"]:
            raise RuntimeError("AP guard authority differs")
        if any(facts[key] != value for key, value in {
            "retirements": 1,
            "linkStoreReceipts": 1,
            "ecomLinks": 1168,
            "linkOutbox": 1168,
            "projectionPending": 0,
        }.items()):
            raise RuntimeError("AP guard authority differs")
        return {"outcome": "SUCCEEDED_STRICT_CLOSURE", "automaticAction": False}
    if state == "abandoned":
        if (
            facts.get("terminalReason") != "ATTEMPT_LEASE_EXPIRED"
            or facts.get("terminalErrorType") is not None
            or facts.get("firstAttemptId") != ATTEMPT_ID
            or facts.get("firstAttemptState") != "failed"
            or facts.get("firstTerminalReason") != "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED"
            or facts.get("firstTerminalErrorType") != "IngressJournalConflict"
        ):
            raise RuntimeError("AP guard authority differs")
        return {"outcome": "FAILED_CHAIN_PAUSE_REQUIRED", "automaticAction": False}
    if (
        facts.get("terminalReason") != "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED"
        or facts.get("terminalErrorType") != "IngressJournalConflict"
    ):
        raise RuntimeError("AP guard authority differs")
    return {"outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False}


def read_facts(conn) -> dict:
    scope = ("org-org", "dev-project")
    attempts = conn.execute(
        """SELECT attempt_id::text,state,operation_key,idempotency_key,request_hash,
          terminal_reason_code,terminal_error_type
          FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
            AND execution_epoch=3 AND operation_kind='recoverable_store'
            AND operation_key=%s ORDER BY accepted_at,attempt_id""",
        (*scope, successor.AP_ID, successor.AP_GENERATION, OPERATION_KEY),
    ).fetchall()
    if len(attempts) != 2:
        raise RuntimeError("AP guard authority differs")
    first, attempt = (dict(row) for row in attempts)
    if (
        first["attempt_id"] != ATTEMPT_ID
        or first["idempotency_key"] != BASE_IDEMPOTENCY_KEY + ":1"
        or first["request_hash"] != REQUEST_HASH
        or first["state"] != "failed"
        or first["terminal_reason_code"] != "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED"
        or first["terminal_error_type"] != "IngressJournalConflict"
        or attempt["attempt_id"] != SECOND_ATTEMPT_ID
        or attempt["idempotency_key"] != BASE_IDEMPOTENCY_KEY + ":2"
        or attempt["request_hash"] != REQUEST_HASH
    ):
        raise RuntimeError("AP guard authority differs")
    shared.ATTEMPT = SECOND_ATTEMPT_ID
    shared.INSTALLATION = successor.AP_ID
    shared.GENERATION = successor.AP_GENERATION
    shared.LINK_KEY = recovery.LINK_IDEMPOTENCY_KEY
    facts = shared.read_facts(conn)
    extra = conn.execute(
        """SELECT clock_timestamp() observed_at,
          (SELECT count(*) FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
              AND execution_epoch=3 AND operation_fence IS FALSE
              AND revision=99 AND cutover_group_revision=126) routes,
          (SELECT count(*) FROM meta_schedule_run r
            JOIN pipeline_snapshot_schedule_member m
              ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='succeeded' AND r.executor_stopped IS TRUE
              AND r.finished_at IS NOT NULL) succeeded_runs,
          (SELECT count(*) FROM meta_schedule_run r
            JOIN pipeline_snapshot_schedule_member m
              ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='failed' AND r.executor_stopped IS TRUE
              AND r.finished_at IS NOT NULL) failed_runs""",
        (*scope, successor.AP_ID, successor.AP_GENERATION,
         *scope, recovery.GROUP, *scope, recovery.GROUP),
    ).fetchone()
    return facts | {
        "attemptCount": 2,
        "operationKey": attempt["operation_key"],
        "idempotencyKey": attempt["idempotency_key"],
        "requestHash": attempt["request_hash"],
        "terminalReason": attempt["terminal_reason_code"],
        "terminalErrorType": attempt["terminal_error_type"],
        "firstAttemptId": first["attempt_id"],
        "firstAttemptState": first["state"],
        "firstTerminalReason": first["terminal_reason_code"],
        "firstTerminalErrorType": first["terminal_error_type"],
        "observedAt": extra["observed_at"],
        "routes": extra["routes"],
        "succeededRuns": extra["succeeded_runs"],
        "failedRuns": extra["failed_runs"],
    }


def main() -> int:
    try:
        shared.baseline.setup()
        with consumer_connection(runtime_worker_connection, shared.baseline.SCOPE) as conn:
            facts = read_facts(conn)
        print(json.dumps(facts | classify(facts), ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as error:
        print(json.dumps({
            "outcome": "SAFE_BLOCKED",
            "automaticAction": False,
            "errorType": type(error).__name__,
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
