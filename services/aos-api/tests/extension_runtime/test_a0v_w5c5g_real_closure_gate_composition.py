"""A read-only composition must never become real closure authority."""

from copy import deepcopy
from pathlib import Path

import pytest

import a0v_w5c5g_real_closure_gate_composition as gate


def snapshot(outcome="STALLED_WAIT_24H"):
    return {
        "baseline": {"outcome": outcome, "automaticAction": False,
                     "topologyComplete": False,
                     "eligibleStrictlyAfterUtc": "2026-09-25T20:00:04.800482+00:00"},
        "knownHost": {"outcome":
            "KNOWN_LAUNCHER_QUIET_REGISTRATION_ROLE_READY_INCOMPLETE_TOPOLOGY",
            "automaticAction": False, "knownHostCount": 0},
        "registration": {"outcome": "REGISTRATION_CONNECTOR_READ_ONLY_HANDSHAKE_GREEN",
                         "automaticAction": False, "closureAuthorized": False},
        "closureAudit": {"outcome": "NOT_YET_CLOSED", "automaticAction": False,
                         "runningRuns": 12, "closureReceipts": 0},
        "managedDirectory": {"outcome":
            "MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY",
            "automaticAction": False, "releasedResourceLeases": 3,
            "runningOriginalRuns": 12},
    }


def test_waiting_with_incomplete_topology():
    result = gate.classify(snapshot())
    assert result["outcome"] == "REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY"
    assert result["closureAuthorized"] is False
    assert result["topologyComplete"] is False
    assert "FULL_MACHINE_HOST_TOPOLOGY" in result["unresolved"]


def test_time_eligible_still_cannot_close():
    result = gate.classify(snapshot("REQUIRES_SEPARATE_REAL_CLOSURE_PLAN"))
    assert result["outcome"] == "REAL_CLOSURE_TIME_ELIGIBLE_BUT_NOT_AUTHORIZED"
    assert result["closureAuthorized"] is False
    assert result["automaticAction"] is False


@pytest.mark.parametrize("mutate", [
    lambda v: v["baseline"].update(outcome="FROZEN_REAL_CLOSURE_PREFLIGHT"),
    lambda v: v["baseline"].update(topologyComplete=True),
    lambda v: v["knownHost"].update(knownHostCount=1),
    lambda v: v["knownHost"].update(outcome="FROZEN_HOST_ROLE_TOPOLOGY"),
    lambda v: v["registration"].update(outcome="FROZEN_REGISTRATION_HANDSHAKE"),
    lambda v: v["registration"].update(closureAuthorized=True),
    lambda v: v["closureAudit"].update(outcome="INDEPENDENT_STALLED_CLOSURE_AUDIT_GREEN"),
    lambda v: v["closureAudit"].update(runningRuns=11),
    lambda v: v["closureAudit"].update(closureReceipts=1),
    lambda v: v["managedDirectory"].update(releasedResourceLeases=2),
    lambda v: v["managedDirectory"].update(outcome="FROZEN_HOST_DIRECTORY_AUTHORITY"),
    lambda v: v["managedDirectory"].update(automaticAction=True),
    lambda v: v.pop("baseline"),
])
def test_any_drift_freezes(mutate):
    value = deepcopy(snapshot())
    mutate(value)
    assert gate.classify(value)["outcome"] == "FROZEN_REAL_CLOSURE_GATE_COMPOSITION"


def test_no_close_or_key_generation_in_composer():
    source = Path(gate.__file__).read_text()
    for forbidden in (".close(", "idempotency_key=", "idempotencyKey", "INSERT INTO",
                      "UPDATE ", "DELETE FROM", "pipeline_snapshot_stalled_group_close_a0v_091("):
        assert forbidden not in source
