"""AM guard is an exact read-only router, never an execution authority."""
import importlib.util
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_am_attempt_guard.py"
SPEC = importlib.util.spec_from_file_location("a0v_am_attempt_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def facts(**changes):
    value = {
        "attemptId": guard.ATTEMPT,
        "installationId": guard.INSTALLATION,
        "generation": guard.GENERATION,
        "operationKind": "recoverable_store",
        "state": "running",
        "revision": 565,
        "definitionRevision": 53,
        "definitionState": "enabled",
        "recoveryRevision": 17,
        "manifestHash": guard.MANIFEST,
        "members": 12,
        "runningRuns": 12,
        "datasetReceipts": 12,
        "relationships": 1,
        "linkCommands": 1,
        "linkCount": 1168,
        "retirements": 0,
        "linkStoreReceipts": 0,
        "ecomLinks": 0,
        "linkOutbox": 0,
        "projectionPending": 0,
        "liveResources": 3,
        "devOrgCanary": 0,
    }
    value.update(changes)
    return value


@pytest.mark.parametrize(("state", "outcome"), (
    ("running", "RUNNING_NO_ACTION"),
    ("succeeded", "SUCCEEDED_RUN_CLOSURE"),
    ("failed", "FAILED_DIAGNOSE_BOUNDARY"),
))
def test_exact_state_only_routes_to_a_non_executing_decision(state, outcome):
    assert guard.classify(facts(state=state))["outcome"] == outcome


@pytest.mark.parametrize(("field", "value"), (
    ("attemptId", "another"),
    ("members", 11),
    ("datasetReceipts", 11),
    ("linkCommands", 2),
    ("linkCount", 1167),
    ("devOrgCanary", 1),
    ("state", "cancelled"),
))
def test_identity_or_boundary_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError, match="AM guard authority differs"):
        guard.classify(facts(**{field: value}))


def test_script_is_select_only_and_contains_no_business_action():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"\b(?:insert|update|delete|call|run_definition|transition|register_successor)\b",
        re.IGNORECASE,
    )
    assert forbidden.search(source) is None
    assert "consumer_connection" in source
    assert "SELECT" in source
