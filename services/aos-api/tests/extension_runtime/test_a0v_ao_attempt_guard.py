"""AO guard is a lock-free read-only router, never execution authority."""
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ao_attempt_guard.py"
SPEC = importlib.util.spec_from_file_location("a0v_ao_attempt_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def facts(**changes):
    observed = datetime(2026, 9, 19, 3, 30, tzinfo=UTC)
    value = {
        "attemptId": guard.recovery.ATTEMPT_ID,
        "attemptCount": 1,
        "operationKey": guard.OPERATION_KEY,
        "idempotencyKey": guard.BASE_IDEMPOTENCY_KEY + ":1",
        "requestHash": guard.REQUEST_HASH,
        "originalAttemptState": "running",
        "originalTerminalReason": None,
        "secondAttemptId": None,
        "secondAttemptState": None,
        "secondTerminalReason": None,
        "secondTerminalErrorType": None,
        "latestTerminalReason": None,
        "installationId": guard.successor.AO_ID,
        "generation": guard.successor.AO_GENERATION,
        "operationKind": "recoverable_store",
        "state": "running",
        "revision": 92,
        "acceptedAt": observed - timedelta(seconds=120),
        "attemptElapsedSeconds": 120,
        "heartbeatAt": observed - timedelta(seconds=10),
        "leaseUntil": observed + timedelta(seconds=110),
        "observedAt": observed,
        "controlSecondsRemaining": 18805,
        "controlExpired": False,
        "definitionRevision": 59,
        "definitionState": "enabled",
        "recoveryRevision": 19,
        "manifestHash": guard.recovery.MANIFEST,
        "members": 12,
        "runningRuns": 12,
        "succeededRuns": 0,
        "failedRuns": 0,
        "datasetReceipts": 12,
        "relationships": 1,
        "linkCommands": 1,
        "linkCount": 1168,
        "retirements": 0,
        "linkStoreReceipts": 0,
        "ecomLinks": 0,
        "linkOutbox": 0,
        "projectionPending": 0,
        "routes": 9,
        "liveResources": 3,
        "devOrgCanary": 0,
    }
    value.update(changes)
    return value


def test_healthy_running_attempt_is_observation_only():
    assert guard.classify(facts()) == {
        "outcome": "RUNNING_HEALTHY_NO_ACTION",
        "automaticAction": False,
        "heartbeatHealthy": True,
    }


def test_healthy_heartbeat_without_store_progress_past_execution_limit_is_diagnosis_only():
    assert guard.classify(facts(attemptElapsedSeconds=301)) == {
        "outcome": "RUNNING_HEARTBEAT_ONLY_DIAGNOSE",
        "automaticAction": False,
        "heartbeatHealthy": True,
        "executionLimitExceeded": True,
    }


def test_store_progress_does_not_claim_heartbeat_only_boundary():
    result = guard.classify(facts(attemptElapsedSeconds=301, linkStoreReceipts=1))
    assert result["outcome"] == "RUNNING_HEALTHY_NO_ACTION"


@pytest.mark.parametrize("changes", (
    {"heartbeatAt": datetime(2026, 9, 19, 3, 28, tzinfo=UTC)},
    {"leaseUntil": datetime(2026, 9, 19, 3, 30, tzinfo=UTC)},
))
def test_stale_running_attempt_never_executes(changes):
    result = guard.classify(facts(**changes))
    assert result["outcome"] == "RUNNING_STALE_DIAGNOSE_ONLY"
    assert result["automaticAction"] is False


def test_terminal_success_only_routes_to_strict_closure():
    result = guard.classify(facts(
        state="succeeded", runningRuns=0, succeededRuns=12,
        originalAttemptState="succeeded",
        heartbeatAt=None, leaseUntil=None,
    ))
    assert result == {"outcome": "SUCCEEDED_STRICT_CLOSURE", "automaticAction": False}


def test_failed_attempt_only_routes_to_frozen_diagnosis():
    result = guard.classify(facts(
        state="failed", runningRuns=0, failedRuns=12,
        originalAttemptState="failed",
        heartbeatAt=None, leaseUntil=None,
    ))
    assert result == {"outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False}


def test_expired_original_waits_for_natural_successor_only():
    result = guard.classify(facts(
        state="abandoned", originalAttemptState="abandoned",
        originalTerminalReason="ATTEMPT_LEASE_EXPIRED",
        heartbeatAt=None, leaseUntil=None,
    ))
    assert result == {
        "outcome": "ABANDONED_WAIT_NATURAL_SUCCESSOR", "automaticAction": False,
    }


def test_exact_second_attempt_is_observed_without_manual_execution():
    result = guard.classify(facts(
        attemptId=guard.SECOND_ATTEMPT_ID, attemptCount=2,
        idempotencyKey=guard.BASE_IDEMPOTENCY_KEY + ":2",
        originalAttemptState="abandoned",
        originalTerminalReason="ATTEMPT_LEASE_EXPIRED",
    ))
    assert result["outcome"] == "RUNNING_HEALTHY_NO_ACTION"


def test_exact_three_attempt_failure_chain_routes_to_pause():
    result = guard.classify(facts(
        attemptId=guard.THIRD_ATTEMPT_ID, attemptCount=3, state="abandoned",
        idempotencyKey=guard.BASE_IDEMPOTENCY_KEY + ":3",
        originalAttemptState="abandoned",
        originalTerminalReason="ATTEMPT_LEASE_EXPIRED",
        secondAttemptId=guard.SECOND_ATTEMPT_ID,
        secondAttemptState="failed",
        secondTerminalReason="RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
        secondTerminalErrorType="IngressJournalConflict",
        latestTerminalReason="ATTEMPT_LEASE_EXPIRED",
        heartbeatAt=None, leaseUntil=None,
    ))
    assert result == {"outcome": "FAILED_CHAIN_PAUSE_REQUIRED", "automaticAction": False}


@pytest.mark.parametrize("changes", (
    {"attemptCount": 4},
    {"attemptCount": 2, "attemptId": "second", "idempotencyKey": guard.BASE_IDEMPOTENCY_KEY + ":3",
     "originalAttemptState": "abandoned", "originalTerminalReason": "ATTEMPT_LEASE_EXPIRED"},
    {"attemptId": guard.THIRD_ATTEMPT_ID, "attemptCount": 3,
     "idempotencyKey": guard.BASE_IDEMPOTENCY_KEY + ":3",
     "originalAttemptState": "abandoned", "originalTerminalReason": "ATTEMPT_LEASE_EXPIRED",
     "secondAttemptId": guard.SECOND_ATTEMPT_ID, "secondAttemptState": "failed",
     "secondTerminalReason": "wrong", "secondTerminalErrorType": "IngressJournalConflict",
     "latestTerminalReason": "ATTEMPT_LEASE_EXPIRED"},
    {"requestHash": "sha256:" + "0" * 64},
))
def test_attempt_chain_drift_fails_closed(changes):
    with pytest.raises(RuntimeError, match="AO guard authority differs"):
        guard.classify(facts(**changes))


@pytest.mark.parametrize(("field", "value"), (
    ("definitionRevision", 58),
    ("recoveryRevision", 18),
    ("datasetReceipts", 11),
    ("linkCount", 1167),
    ("routes", 8),
    ("devOrgCanary", 1),
    ("ecomLinks", 1169),
    ("attemptElapsedSeconds", -1),
    ("acceptedAt", None),
))
def test_identity_or_boundary_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError, match="AO guard authority differs"):
        guard.classify(facts(**{field: value}))


def test_script_is_select_only_and_has_no_business_action():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"\b(?:insert|update|delete|call|run_definition|transition|register_successor)\b",
        re.IGNORECASE,
    )
    assert forbidden.search(source) is None
    assert "consumer_connection" in source
    assert "SELECT" in source
