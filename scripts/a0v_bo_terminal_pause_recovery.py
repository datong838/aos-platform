#!/usr/bin/env python3
"""Pause BO after its exact two terminal no-effect attempts; never execute work."""
from __future__ import annotations

import argparse
import json
import subprocess

import a0v_am_attempt_guard as shared
import a0v_bl_attempt_guard as predecessor_guard
import a0v_bo_saved_snapshot_recovery as saved
import a0v_bo_successor_business as successor
import a0v_bo_terminal_supervisor as supervisor
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
from aos_api.tenant_scope import TenantScope


ATTEMPT_IDS = (
    "57881020-86fe-44cc-be3e-2cd90787205e",
    "9d1fc481-7eb2-426f-8b0b-65627f06ec97",
)
REQUEST_HASH = "sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7"


def process_counts() -> dict[str, int]:
    output = subprocess.check_output(["ps", "-ax", "-o", "command="], text=True, timeout=10)
    rows = output.splitlines()
    return {
        "runtimeHost": sum("scripts/a0v_ecommerce_runtime_host.py" in row for row in rows),
        "snapshotWorker": sum("scripts/a0v_bo_snapshot_product_api.py" in row for row in rows),
        "supervisor": sum("scripts/a0v_bo_terminal_supervisor.py" in row for row in rows),
    }


def facts() -> dict:
    rows = supervisor.read_rows()
    shared.ATTEMPT = ATTEMPT_IDS[0]
    shared.INSTALLATION = successor.BO_ID
    shared.GENERATION = successor.BO_GENERATION
    shared.LINK_KEY = predecessor_guard.LINK_KEY
    with consumer_connection(runtime_worker_connection, shared.baseline.SCOPE) as conn:
        boundary = shared.read_facts(conn)
    return {"attempts": rows, "boundary": boundary, "processes": process_counts()}


def classify(value: dict) -> dict:
    rows = value["attempts"]
    if len(rows) != 2 or tuple(row["attempt_id"] for row in rows) != ATTEMPT_IDS:
        raise RuntimeError("BO terminal attempt boundary differs")
    for index, row in enumerate(rows, start=1):
        if (
            row["state"] != "failed"
            or row["revision"] != 2
            or row["terminal_reason_code"] != "RECOVERABLE_EXECUTION_EXCEPTION"
            or row["terminal_error_type"] != "RuntimeConflict"
            or row["idempotency_key"]
                != f"snapshot-group:{saved.GROUP}:{index}"
            or row["request_hash"] != REQUEST_HASH
        ):
            raise RuntimeError("BO terminal attempt facts differ")
    boundary = value["boundary"]
    expected = {
        "definitionRevision": 120, "definitionState": "enabled", "recoveryRevision": 39,
        "members": 12, "runningRuns": 12, "datasetReceipts": 12,
        "relationships": 1, "linkCommands": 1, "linkCount": 1168,
        "retirements": 0, "linkStoreReceipts": 0, "ecomLinks": 0,
        "linkOutbox": 0, "projectionPending": 0, "liveResources": 3,
        "devOrgCanary": 0,
    }
    if any(boundary.get(key) != expected_value for key, expected_value in expected.items()):
        raise RuntimeError("BO terminal no-effect boundary differs")
    if value["processes"] != {"runtimeHost": 1, "snapshotWorker": 0, "supervisor": 0}:
        raise RuntimeError("BO terminal process boundary differs")
    return {"outcome": "BO_TERMINAL_PAUSE_PREFLIGHT_GREEN", "attemptCount": 2,
            "sourceReads": 0, "attemptsCreated": 0}


def run(*, apply: bool) -> dict:
    preflight = classify(facts())
    if not apply:
        return preflight
    scope = TenantScope(org_id="org-org", project_id="dev-project")
    owner = PipelineSnapshotScheduleDefinitionOwner(
        controls=None, installation_store=PostgresInstallationStore()
    )
    with consumer_connection(runtime_worker_connection, shared.baseline.SCOPE) as conn:
        require_runtime_role(
            conn, org_id=scope.org_id, project_id=scope.project_id,
            protected_tables=("public.pipeline_snapshot_schedule_definition_revision",
                              "public.pipeline_snapshot_schedule_definition_head",
                              "public.pipeline_snapshot_schedule_current_member"),
        )
        current = owner.read(conn, scope=scope, definition_id=saved.recovery.snapshot.DEFINITION_ID)
        if current is None or current["body"]["state"] != "enabled" or current["ref"]["revision"] != 120:
            raise RuntimeError("BO exact enabled definition unavailable")
        result = owner.transition(
            conn, scope=scope, definition_id=saved.recovery.snapshot.DEFINITION_ID,
            actor=saved.recovery.snapshot.ACTOR, intent="disable", expected_ref=current["ref"],
            idempotency_key=saved.recovery.PAUSE_KEY,
        )
    if result["body"]["state"] != "disabled" or result["ref"]["revision"] != 121:
        raise RuntimeError("BO terminal pause readback differs")
    return preflight | {"outcome": "BO_TERMINAL_PAUSE_RECOVERY_GREEN",
                        "attemptIds": ATTEMPT_IDS, "definition": result}


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
