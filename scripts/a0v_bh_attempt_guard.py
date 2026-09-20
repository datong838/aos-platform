#!/usr/bin/env python3
"""Read BH's exact single natural recovery attempt without executing work."""
from __future__ import annotations

import json

import a0v_am_attempt_guard as shared
import a0v_bd_attempt_guard as base
import a0v_bh_saved_snapshot_recovery as recovery
import a0v_bh_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


ATTEMPT_ID = "6d8395b6-b04b-4aa3-b002-9b3618e1eaf3"
OPERATION_KEY = base.OPERATION_KEY
IDEMPOTENCY_KEY = base.IDEMPOTENCY_KEY
REQUEST_HASH = base.REQUEST_HASH
LINK_KEY = base.LINK_KEY


def classify(facts: dict) -> dict:
    exact = {
        "attemptId": ATTEMPT_ID, "attemptCount": 1,
        "installationId": successor.BH_ID, "generation": successor.BH_GENERATION,
        "definitionRevision": 105, "definitionState": "enabled", "recoveryRevision": 34,
        "routes": 9,
    }
    if any(facts.get(key) != value for key, value in exact.items()):
        raise RuntimeError("BH guard authority differs")
    mapped = dict(facts) | {
        "attemptId": base.ATTEMPT_ID,
        "installationId": base.successor.BD_ID,
        "generation": base.successor.BD_GENERATION,
        "definitionRevision": 93,
        "recoveryRevision": 30,
    }
    try:
        return base.classify(mapped)
    except RuntimeError as error:
        raise RuntimeError("BH guard authority differs") from error


def read_facts(conn) -> dict:
    scope = ("org-org", "dev-project")
    row = conn.execute(
        """SELECT operation_key,idempotency_key,request_hash,terminal_reason_code,terminal_error_type,
          (SELECT count(*) FROM extension_runtime_execution_attempt x
            WHERE x.org_id=a.org_id AND x.project_id=a.project_id
              AND x.installation_id=a.installation_id AND x.generation=a.generation
              AND x.operation_kind='recoverable_store' AND x.operation_key=%s) attempt_count
          FROM extension_runtime_execution_attempt a
          WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
        (OPERATION_KEY, *scope, ATTEMPT_ID),
    ).fetchone()
    if row is None:
        raise RuntimeError("BH guard authority differs")
    attempt = dict(row)
    shared.ATTEMPT, shared.INSTALLATION, shared.GENERATION = (
        ATTEMPT_ID, successor.BH_ID, successor.BH_GENERATION)
    shared.LINK_KEY = LINK_KEY
    facts = shared.read_facts(conn)
    extra = conn.execute(
        """SELECT clock_timestamp() observed_at,
          (SELECT count(*) FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
              AND execution_epoch=3 AND operation_fence IS FALSE
              AND revision=150 AND cutover_group_revision=177) routes,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='succeeded' AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) succeeded_runs,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='failed' AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) failed_runs""",
        (*scope, successor.BH_ID, successor.BH_GENERATION,
         *scope, recovery.GROUP, *scope, recovery.GROUP),
    ).fetchone()
    return facts | {
        "attemptCount": attempt["attempt_count"], "operationKey": attempt["operation_key"],
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
