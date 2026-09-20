#!/usr/bin/env python3
"""Pause BL's exact terminal definition through the original stop-only Owner."""
from __future__ import annotations

import argparse
import json

import a0v_bl_attempt_guard as guard
import a0v_bl_expired_attempt_recovery as expired
import a0v_bl_saved_snapshot_recovery as saved
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
from aos_api.tenant_scope import TenantScope


def classify(facts: dict, processes: dict[str, int]) -> dict:
    if guard.classify(facts).get("outcome") != "ABANDONED_FREEZE_BOUNDARY":
        raise RuntimeError("BL terminal pause authority differs")
    if (facts.get("revision"), facts.get("terminalReason"), facts.get("terminalErrorType")) != (
            46, "ATTEMPT_LEASE_EXPIRED", None):
        raise RuntimeError("BL terminal pause authority differs")
    expected = {
        "attemptCount": 1, "runningRuns": 12, "succeededRuns": 0, "failedRuns": 0,
        "retirements": 0, "linkStoreReceipts": 0, "ecomLinks": 0,
        "linkOutbox": 0, "projectionPending": 0,
    }
    if {key: facts.get(key) for key in expected} != expected:
        raise RuntimeError("BL terminal pause facts differ")
    if processes != {"runtimeHost": 0, "snapshotWorker": 0, "supervisor": 0}:
        raise RuntimeError("BL terminal pause process boundary differs")
    return {"outcome": "BL_TERMINAL_PAUSE_RECOVERY_PREFLIGHT_GREEN",
            "sourceReads": 0, "attemptsCreated": 0}


def run(*, apply: bool) -> dict:
    facts = expired._facts()
    preflight = classify(facts, expired.process_counts())
    if not apply:
        return preflight
    scope = TenantScope(org_id="org-org", project_id="dev-project")
    owner = PipelineSnapshotScheduleDefinitionOwner(
        controls=None, installation_store=PostgresInstallationStore()
    )
    with consumer_connection(expired._runtime_connect_factory(), dict(
            org_id=scope.org_id, project_id=scope.project_id)) as conn:
        require_runtime_role(conn, org_id=scope.org_id, project_id=scope.project_id,
            protected_tables=("public.pipeline_snapshot_schedule_definition_revision",
                              "public.pipeline_snapshot_schedule_definition_head",
                              "public.pipeline_snapshot_schedule_current_member"))
        current = owner.read(conn, scope=scope, definition_id=saved.recovery.snapshot.DEFINITION_ID)
        if current is None or current["body"]["state"] != "enabled" or current["ref"]["revision"] != 117:
            raise RuntimeError("BL exact enabled definition unavailable")
        result = owner.transition(
            conn, scope=scope, definition_id=saved.recovery.snapshot.DEFINITION_ID,
            actor=saved.recovery.snapshot.ACTOR, intent="disable", expected_ref=current["ref"],
            idempotency_key=saved.recovery.PAUSE_KEY,
        )
    if result["body"]["state"] != "disabled" or result["ref"]["revision"] != 118:
        raise RuntimeError("BL terminal pause readback differs")
    return {"outcome": "BL_SAVED_SNAPSHOT_TERMINAL_RECOVERY_PAUSED",
            "attemptId": guard.ATTEMPT_ID, "definition": result,
            "sourceReads": 0, "attemptsCreated": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(run(apply=args.apply), ensure_ascii=False, default=str, indent=2))
    except Exception as error:
        print(json.dumps({"outcome": "SAFE_BLOCKED", "automaticAction": False,
                          "errorType": type(error).__name__}, ensure_ascii=False))
        raise SystemExit(2)
