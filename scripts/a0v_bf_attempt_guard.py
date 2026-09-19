#!/usr/bin/env python3
"""Read BF's exact single natural recovery attempt without executing work."""
from __future__ import annotations

import json

import a0v_am_attempt_guard as shared
import a0v_bd_attempt_guard as base
import a0v_bf_saved_snapshot_recovery as recovery
import a0v_bf_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


ORIGINAL_ATTEMPT_ID = "0a79f73d-7243-4778-90af-2e2109115e73"
ATTEMPT_ID = "b61340d4-391f-415d-ac77-65ed8f72321d"
OPERATION_KEY = base.OPERATION_KEY
BASE_IDEMPOTENCY_KEY = base.IDEMPOTENCY_KEY.rsplit(":", 1)[0]
IDEMPOTENCY_KEY = BASE_IDEMPOTENCY_KEY + ":2"
REQUEST_HASH = base.REQUEST_HASH
LINK_KEY = base.LINK_KEY


def classify(facts: dict) -> dict:
    exact = {
        "attemptId": ATTEMPT_ID, "attemptCount": 2,
        "installationId": successor.BF_ID, "generation": successor.BF_GENERATION,
        "definitionRevision": 99, "definitionState": "enabled", "recoveryRevision": 32,
        "routes": 9,
    }
    if any(facts.get(key) != value for key, value in exact.items()):
        raise RuntimeError("BF guard authority differs")
    history = facts.get("attemptHistory")
    expected_history = (
        (ORIGINAL_ATTEMPT_ID, BASE_IDEMPOTENCY_KEY + ":1", "failed",
         "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"),
        (ATTEMPT_ID, IDEMPOTENCY_KEY, "failed",
         "RECOVERABLE_INGRESS_CANCELLED", "IngressJournalConflict"),
    )
    if type(history) is not list or len(history) != 2:
        raise RuntimeError("BF guard authority differs")
    for row, expected_row in zip(history, expected_history):
        attempt_id, key, state, reason, error_type = expected_row
        if (row.get("attempt_id") != attempt_id or row.get("idempotency_key") != key
                or row.get("request_hash") != REQUEST_HASH or row.get("state") != state
                or row.get("terminal_reason_code") != reason
                or row.get("terminal_error_type") != error_type):
            raise RuntimeError("BF guard authority differs")
    mapped = dict(facts) | {
        "attemptId": base.ATTEMPT_ID,
        "installationId": base.successor.BD_ID,
        "generation": base.successor.BD_GENERATION,
        "definitionRevision": 93,
        "recoveryRevision": 30,
        "attemptCount": 1,
        "idempotencyKey": base.IDEMPOTENCY_KEY,
        "terminalReason": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
        "terminalErrorType": "IngressJournalConflict",
    }
    try:
        return base.classify(mapped)
    except RuntimeError as error:
        raise RuntimeError("BF guard authority differs") from error


def read_facts(conn) -> dict:
    scope = ("org-org", "dev-project")
    attempts = conn.execute(
        """SELECT attempt_id::text,idempotency_key,request_hash,state,
          terminal_reason_code,terminal_error_type
          FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
            AND execution_epoch=3 AND operation_kind='recoverable_store' AND operation_key=%s
          ORDER BY accepted_at,attempt_id""",
        (*scope, successor.BF_ID, successor.BF_GENERATION, OPERATION_KEY),
    ).fetchall()
    if len(attempts) != 2:
        raise RuntimeError("BF guard authority differs")
    rows = [dict(row) for row in attempts]
    attempt = rows[-1]
    shared.ATTEMPT, shared.INSTALLATION, shared.GENERATION = (
        ATTEMPT_ID, successor.BF_ID, successor.BF_GENERATION)
    shared.LINK_KEY = LINK_KEY
    facts = shared.read_facts(conn)
    extra = conn.execute(
        """SELECT clock_timestamp() observed_at,
          (SELECT count(*) FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
              AND execution_epoch=3 AND operation_fence IS FALSE
              AND revision=144 AND cutover_group_revision=171) routes,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='succeeded' AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) succeeded_runs,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='failed' AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) failed_runs""",
        (*scope, successor.BF_ID, successor.BF_GENERATION,
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
