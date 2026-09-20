#!/usr/bin/env python3
"""Read BZ's exact single natural recovery attempt without executing work."""
from __future__ import annotations

import json

import a0v_am_attempt_guard as shared
import a0v_bx_attempt_guard as predecessor_guard
import a0v_bz_saved_snapshot_recovery as recovery
import a0v_bz_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


ATTEMPT_ID = "b7044a35-43f8-4089-ba79-4da3d92cbf64"
OPERATION_KEY = f"snapshot-group-completion:{recovery.GROUP}"
IDEMPOTENCY_KEY = f"snapshot-group:{recovery.GROUP}:1"
REQUEST_HASH = "sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7"
LINK_KEY = predecessor_guard.LINK_KEY


def classify(facts: dict) -> dict:
    expected = {
        "attemptId": ATTEMPT_ID, "attemptCount": 1,
        "installationId": successor.BZ_ID, "generation": successor.BZ_GENERATION,
        "operationKind": "recoverable_store", "operationKey": OPERATION_KEY,
        "idempotencyKey": IDEMPOTENCY_KEY, "requestHash": REQUEST_HASH,
        "state": "failed", "revision": 4,
        "terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION",
        "terminalErrorType": "IngressJournalConflict",
        "definitionRevision": 144, "definitionState": "enabled", "recoveryRevision": 47,
        "manifestHash": recovery.MANIFEST, "members": 12,
        "runningRuns": 12, "succeededRuns": 0, "failedRuns": 0,
        "datasetReceipts": 12, "relationships": 1, "linkCommands": 1,
        "linkCount": 1168, "retirements": 0, "linkStoreReceipts": 0,
        "ecomLinks": 0, "linkOutbox": 0, "projectionPending": 0,
        "liveResources": 3, "devOrgCanary": 0, "routes": 9,
    }
    if any(facts.get(key) != value for key, value in expected.items()):
        raise RuntimeError("BZ guard authority differs")
    return {"outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False}


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
        raise RuntimeError("BZ guard authority differs")
    attempt = dict(row)
    shared.ATTEMPT = ATTEMPT_ID
    shared.INSTALLATION = successor.BZ_ID
    shared.GENERATION = successor.BZ_GENERATION
    shared.LINK_KEY = LINK_KEY
    facts = shared.read_facts(conn)
    extra = conn.execute(
        """SELECT clock_timestamp() observed_at,
          (SELECT count(*) FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
              AND execution_epoch=3 AND operation_fence IS FALSE
              AND revision=201 AND cutover_group_revision=228) routes,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='succeeded' AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) succeeded_runs,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='failed' AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) failed_runs""",
        (*scope, successor.BZ_ID, successor.BZ_GENERATION,
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
        successor.setup()
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
