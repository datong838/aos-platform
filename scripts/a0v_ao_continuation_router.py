#!/usr/bin/env python3
"""Read-only deterministic continuation router for AO and its first natural chain."""
from __future__ import annotations

from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys


TERMINAL_FACTS = {
    "succeeded_attempt": 1,
    "abandoned_attempts": 1,
    "attempts": 2,
    "members": 12,
    "succeeded_runs": 12,
    "dataset_receipts": 12,
    "relationships": 1,
    "link_commands": 1,
    "link_count": 1168,
    "retirements": 1,
    "store_receipts": 1,
    "live_links": 1168,
    "store_outbox": 1168,
    "projection_pending": 0,
    "routes": 9,
    "live_resources": 3,
    "canary": 0,
}

CLOSED_SNAPSHOT = {
    "installationId": "d4186607-c93f-4fd0-8daa-46e349184ab9",
    "generation": "00bb99df-d436-483d-86df-496718c6f129",
    "operationKind": "recoverable_store",
    "state": "succeeded",
    "definitionRevision": 60,
    "definitionState": "disabled",
    "recoveryRevision": 19,
    "manifestHash": "sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01",
    "members": 12,
    "runningRuns": 0,
    "succeededRuns": 12,
    "failedRuns": 0,
    "datasetReceipts": 12,
    "relationships": 1,
    "linkCommands": 1,
    "linkCount": 1168,
    "retirements": 1,
    "linkStoreReceipts": 1,
    "ecomLinks": 1168,
    "linkOutbox": 1168,
    "projectionPending": 0,
    "liveResources": 3,
    "devOrgCanary": 0,
    "routes": 9,
    "attemptCount": 2,
    "operationKey": "snapshot-group-completion:c5ff1926-45b0-56de-b6b3-07d5b7d053a1",
    "idempotencyKey": "snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:2",
    "requestHash": "sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7",
    "originalAttemptState": "abandoned",
    "originalTerminalReason": "ATTEMPT_LEASE_EXPIRED",
}


def _artifact(path: Path, outcome: str, *, terminal: bool = False) -> bool:
    if not path.exists():
        return False
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError("private immutable continuation artifact required")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("outcome") != outcome:
        raise RuntimeError("continuation artifact outcome differs")
    if terminal and value.get("terminalFacts") != TERMINAL_FACTS:
        raise RuntimeError("AO terminal artifact facts differ")
    return True


def _require_artifact_prefix(artifacts: dict) -> None:
    dependencies = (
        ("v3Approval", "v3Preflight"),
        ("v3Put", "v3Approval"),
        ("v3Disable", "v3Put"),
        ("v3DisableApproval", "v3Disable"),
        ("v3DisablePut", "v3DisableApproval"),
    )
    if any(artifacts.get(item) and not artifacts.get(required) for item, required in dependencies):
        raise RuntimeError("continuation artifact prefix differs")


def _require_closed_snapshot(snapshot: dict) -> None:
    if any(snapshot.get(key) != value for key, value in CLOSED_SNAPSHOT.items()):
        raise RuntimeError("current AO closed-runtime authority differs")
    if snapshot.get("completedAt") is None:
        raise RuntimeError("current AO closed-runtime authority differs")


def classify(snapshot: dict, artifacts: dict, policy: dict | None = None,
             phase: str | None = None, attempt_guard: dict | None = None) -> dict:
    state = snapshot.get("state")
    if state in {"running", "failed", "abandoned"} or (
        state == "succeeded" and snapshot.get("definitionState") == "enabled"
    ):
        if attempt_guard is None:
            raise RuntimeError("exact AO attempt guard result required")
        next_actions = {
            "RUNNING_HEALTHY_NO_ACTION": "OBSERVE_AO_RECOVERY",
            "RUNNING_HEARTBEAT_ONLY_DIAGNOSE": "DIAGNOSE_AO_BOUNDED_EXECUTION",
            "RUNNING_STALE_DIAGNOSE_ONLY": "DIAGNOSE_AO_HEARTBEAT",
            "ABANDONED_WAIT_NATURAL_SUCCESSOR": "WAIT_AO_NATURAL_SUCCESSOR",
            "FAILED_FREEZE_BOUNDARY": "FREEZE_AO_FAILURE_BOUNDARY",
            "SUCCEEDED_STRICT_CLOSURE": "RUN_AO_INSPECT_THEN_DISABLE",
        }
        if attempt_guard.get("outcome") not in next_actions:
            raise RuntimeError("unknown AO attempt guard result")
        if attempt_guard.get("automaticAction") is not False:
            raise RuntimeError("read-only AO attempt guard required")
        return attempt_guard | {"nextAction": next_actions[attempt_guard["outcome"]]}

    _require_closed_snapshot(snapshot)
    if not artifacts.get("recoveryClosed"):
        raise RuntimeError("exact AO disabled recovery closure required")
    _require_artifact_prefix(artifacts)
    if policy is None:
        raise RuntimeError("current advisor Policy required after AO closure")

    revision, enabled = policy.get("revision"), policy.get("enabled")
    if revision == 2 and enabled is True:
        if artifacts.get("v3Put"):
            raise RuntimeError("Policy v3 put outcome requires current revision 3")
        if not artifacts.get("v3Preflight"):
            action = "RUN_POLICY_V3_PREFLIGHT"
        elif not artifacts.get("v3Approval"):
            action = "RUN_POLICY_V3_APPROVAL"
        else:
            action = "RUN_POLICY_V3_PUT"
    elif revision == 3 and enabled is True:
        if not artifacts.get("v3Put") or phase is None:
            raise RuntimeError("Policy v3 current state lacks exact put or observation")
        if phase != "growth_plan_ready":
            action = "OBSERVE_POLICY_V3_NATURAL_CHAIN"
        elif not artifacts.get("v3Disable"):
            action = "RUN_POLICY_V3_DISABLE_READINESS"
        elif not artifacts.get("v3DisableApproval"):
            action = "RUN_POLICY_V4_DISABLE_APPROVAL"
        elif not artifacts.get("v3DisablePut"):
            action = "RUN_POLICY_V4_DISABLE_PUT"
        else:
            raise RuntimeError("Policy v4 put outcome requires current revision 4")
    elif revision == 4 and enabled is False:
        if not artifacts.get("v3DisablePut"):
            raise RuntimeError("disabled Policy v4 lacks exact canonical put outcome")
        action = "START_FIRST_CHAIN_PLAN_REVIEW"
    else:
        raise RuntimeError("unknown advisor Policy continuation state")
    return {
        "outcome": "AO_CONTINUATION_ROUTED",
        "automaticAction": False,
        "nextAction": action,
        "policyRevision": revision,
        "policyEnabled": enabled,
        "naturalChainPhase": phase,
    }


def _artifacts(recovery, v3) -> dict:
    return {
        "recoveryClosed": _artifact(
            recovery.STATE / "disable-result.json",
            "AO_SAVED_SNAPSHOT_COMPLETE_DISABLED",
            terminal=True,
        ),
        "v3Preflight": _artifact(
            v3.STATE / "preflight-result.json", "AO_ADVISOR_BASELINE_V3_PREFLIGHT_GREEN"
        ),
        "v3Approval": _artifact(
            v3.STATE / "approval-result.json", "AO_ADVISOR_BASELINE_V3_APPROVED"
        ),
        "v3Put": _artifact(
            v3.STATE / "put-result.json", "AO_ADVISOR_BASELINE_V3_SAVED"
        ),
        "v3Disable": _artifact(
            v3.STATE / "disable-result.json", "AO_ADVISOR_BASELINE_V3_DISABLE_READY"
        ),
        "v3DisableApproval": _artifact(
            v3.STATE / "disable-approval-result.json",
            "AO_ADVISOR_BASELINE_V4_DISABLE_APPROVED",
        ),
        "v3DisablePut": _artifact(
            v3.STATE / "disable-put-result.json", "AO_ADVISOR_BASELINE_V4_DISABLED"
        ),
    }


def observe() -> dict:
    import a0v_ao_advisor_baseline_v3 as v3
    import a0v_ao_advisor_baseline_v3_observe as chain
    import a0v_ao_attempt_guard as guard
    import a0v_ao_saved_snapshot_recovery as recovery
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection

    guard.shared.baseline.setup()
    with consumer_connection(runtime_worker_connection, guard.shared.baseline.SCOPE) as conn:
        snapshot = guard.read_facts(conn)
    if snapshot["state"] != "succeeded" or snapshot["definitionState"] == "enabled":
        return {
            "snapshot": snapshot,
            **classify(snapshot, {}, attempt_guard=guard.classify(snapshot)),
        }

    artifacts = _artifacts(recovery, v3)
    previous, _profile, _plane = v3.setup()
    baseline = v3._current_facts(previous)
    policy = baseline["policy"]
    observed = chain.observe(previous) if policy.get("revision") == 3 else None
    routed = classify(
        snapshot,
        artifacts,
        policy=policy,
        phase=None if observed is None else observed["phase"],
    )
    return {
        "snapshot": snapshot,
        "artifacts": artifacts,
        "policy": policy,
        "chain": None if observed is None else {
            "phase": observed["phase"],
            "occurrences": len(observed["occurrences"]),
            "runs": len(observed["runs"]),
            "growthPlans": len(observed["growthPlans"]),
            "canary": observed["canary"],
        },
        "sourceReads": 0,
        "businessWrites": 0,
        **routed,
    }


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
            "nextAction": "DIAGNOSE_CONTINUATION_AUTHORITY",
            "errorType": type(error).__name__,
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    raise SystemExit(main())
