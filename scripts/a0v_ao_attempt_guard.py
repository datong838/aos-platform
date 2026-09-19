#!/usr/bin/env python3
"""Read the exact AO recovery boundary without taking the installation lock."""
from __future__ import annotations

from datetime import datetime, timedelta
import json

import a0v_am_attempt_guard as shared
import a0v_ao_saved_snapshot_recovery as recovery
import a0v_ao_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


HEARTBEAT_FRESHNESS = timedelta(seconds=90)


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def classify(facts: dict) -> dict:
    expected = {
        "attemptId": recovery.ATTEMPT_ID,
        "installationId": successor.AO_ID,
        "generation": successor.AO_GENERATION,
        "operationKind": "recoverable_store",
        "definitionRevision": 59,
        "definitionState": "enabled",
        "recoveryRevision": 19,
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
        raise RuntimeError("AO guard authority differs")
    if facts.get("state") not in {"running", "succeeded", "failed"}:
        raise RuntimeError("AO guard authority differs")
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
            raise RuntimeError("AO guard authority differs")
    if sum(facts[key] for key in ("runningRuns", "succeededRuns", "failedRuns")) != 12:
        raise RuntimeError("AO guard authority differs")
    if type(facts.get("revision")) is not int or facts["revision"] < 1:
        raise RuntimeError("AO guard authority differs")
    remaining, expired = facts.get("controlSecondsRemaining"), facts.get("controlExpired")
    if type(remaining) is not int or type(expired) is not bool or expired is not (remaining < 0):
        raise RuntimeError("AO guard authority differs")

    state = facts["state"]
    if state == "running":
        observed = _as_datetime(facts.get("observedAt"))
        heartbeat = _as_datetime(facts.get("heartbeatAt"))
        lease = _as_datetime(facts.get("leaseUntil"))
        healthy = heartbeat >= observed - HEARTBEAT_FRESHNESS and lease > observed
        return {
            "outcome": "RUNNING_HEALTHY_NO_ACTION" if healthy else "RUNNING_STALE_DIAGNOSE_ONLY",
            "automaticAction": False,
            "heartbeatHealthy": healthy,
        }
    if state == "succeeded":
        if facts["succeededRuns"] != 12 or facts["runningRuns"] or facts["failedRuns"]:
            raise RuntimeError("AO guard authority differs")
        return {"outcome": "SUCCEEDED_STRICT_CLOSURE", "automaticAction": False}
    return {"outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False}


def read_facts(conn) -> dict:
    shared.ATTEMPT = recovery.ATTEMPT_ID
    shared.INSTALLATION = successor.AO_ID
    shared.GENERATION = successor.AO_GENERATION
    shared.LINK_KEY = recovery.LINK_IDEMPOTENCY_KEY
    facts = shared.read_facts(conn)
    scope = ("org-org", "dev-project")
    extra = conn.execute(
        """SELECT clock_timestamp() observed_at,
          (SELECT count(*) FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
              AND execution_epoch=3 AND operation_fence IS FALSE
              AND revision=96 AND cutover_group_revision=123) routes,
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
        (
            *scope, successor.AO_ID, successor.AO_GENERATION,
            *scope, recovery.GROUP,
            *scope, recovery.GROUP,
        ),
    ).fetchone()
    return facts | {
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
