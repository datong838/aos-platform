#!/usr/bin/env python3
"""Formally abandon BL's one expired attempt after the runtime credential loss."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import subprocess
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

import a0v_bl_attempt_guard as guard
from a0v_formal_text_model_renewal import database_connect
from aos_api.extension_runtime.generation_attempts import ExpiredSignedReadAttemptRecovery


EXPECTED_REVISION = 45
TERMINAL_REVISION = 46


def process_counts() -> dict[str, int]:
    output = subprocess.check_output(
        ["ps", "-ax", "-o", "command="], text=True, timeout=10
    )
    return {
        "runtimeHost": sum("scripts/a0v_ecommerce_runtime_host.py" in row for row in output.splitlines()),
        "snapshotWorker": sum("scripts/a0v_snapshot_product_api.py" in row for row in output.splitlines()),
        "supervisor": sum("scripts/a0v_bl_terminal_supervisor.py" in row for row in output.splitlines()),
    }


def classify(facts: dict, processes: dict[str, int]) -> dict:
    exact = {
        "attemptId": guard.ATTEMPT_ID, "attemptCount": 1,
        "installationId": guard.successor.BL_ID,
        "generation": guard.successor.BL_GENERATION,
        "state": "running", "revision": EXPECTED_REVISION,
        "definitionRevision": 117, "definitionState": "enabled",
        "recoveryRevision": 38, "routes": 9, "runningRuns": 12,
        "datasetReceipts": 12, "linkStoreReceipts": 0, "ecomLinks": 0,
        "projectionPending": 0, "succeededRuns": 0, "failedRuns": 0,
        "devOrgCanary": 0,
    }
    if any(facts.get(key) != value for key, value in exact.items()):
        raise RuntimeError("BL expired recovery authority differs")
    if facts.get("attemptElapsedSeconds", 0) < 1800:
        raise RuntimeError("BL 1800 second budget not reached")
    if facts.get("leaseUntil") is None or facts["leaseUntil"] > facts["observedAt"]:
        raise RuntimeError("BL attempt lease is not expired")
    if processes != {"runtimeHost": 0, "snapshotWorker": 0, "supervisor": 0}:
        raise RuntimeError("BL runtime process boundary differs")
    return {"outcome": "BL_EXPIRED_ATTEMPT_RECOVERY_PREFLIGHT_GREEN",
            "automaticAction": False, "sourceReads": 0, "attemptsCreated": 0}


def _facts() -> dict:
    with database_connect("aos_meta_head")() as conn:
        return guard.read_facts(conn)


def _runtime_connect_factory():
    with database_connect("aos_meta_head")() as source:
        parameters = source.info.get_parameters()
        parameters["password"] = source.info.password

    @contextmanager
    def connect():
        with psycopg.connect(
            **parameters, autocommit=True, row_factory=dict_row
        ) as conn:
            conn.execute("SET SESSION AUTHORIZATION aos_runtime")
            conn.autocommit = False
            yield conn

    return connect


def run(*, apply: bool) -> dict:
    before = _facts()
    preflight = classify(before, process_counts())
    if not apply:
        return preflight | {"attemptRevision": before["revision"]}
    recovered = ExpiredSignedReadAttemptRecovery(
        connect=_runtime_connect_factory()
    ).run_once(org_id="org-org", project_id="dev-project", limit=1)
    if recovered != (UUID(guard.ATTEMPT_ID),):
        raise RuntimeError("BL expired recovery delivery differs")
    after = _facts()
    if (after.get("state"), after.get("revision"), after.get("terminalReason"),
            after.get("terminalErrorType"), after.get("attemptCount")) != (
            "abandoned", TERMINAL_REVISION, "ATTEMPT_LEASE_EXPIRED", None, 1):
        raise RuntimeError("BL expired recovery readback differs")
    return {
        "outcome": "BL_EXPIRED_ATTEMPT_RECOVERY_GREEN",
        "attemptId": guard.ATTEMPT_ID, "attemptRevision": TERMINAL_REVISION,
        "terminalReason": "ATTEMPT_LEASE_EXPIRED", "terminalErrorType": None,
        "sourceReads": 0, "attemptsCreated": 0, "replayed": False,
    }


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
