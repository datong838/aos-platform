"""Missing rollout gates reject; self-asserted all-green remains no-authority."""

from copy import deepcopy

import pytest

from a0v_w5c7h_rollout_rejection_contract import classify


GATES = {
    "controlPlaneSigned": "CONTROL_PLANE_SIGNATURE_UNPROVEN",
    "rootProvenanceVerified": "FLEET_ROOT_PROVENANCE_UNPROVEN",
    "assetDeploymentCoveringAllMachines": "FLEET_ASSET_DEPLOYMENT_COVERAGE_UNPROVEN",
    "allLaunchSurfacesManaged": "UNMANAGED_LAUNCH_SURFACE_NOT_EXCLUDED",
    "oldCredentialsRevoked": "OLD_HOST_RESTART_AUTHORITY_NOT_REVOKED",
    "perNodeStopAckComplete": "PER_NODE_STOP_ACK_INCOMPLETE",
    "dbMigrationVerified": "REAL_DB_FENCE_MIGRATION_UNVERIFIED",
    "allWorkerTransactionalFencesVerified": "WORKER_TRANSACTION_FENCE_UNVERIFIED",
    "freshOwnerPlanAndKeyVerified": "FRESH_OWNER_CLOSURE_PLAN_KEY_UNVERIFIED",
}


def _evidence():
    return {**{name: True for name in GATES}, "physicalSecondHostCount": 0}


def _denied(result):
    assert result["automaticAction"] is False
    assert result["topologyComplete"] is False
    assert result["closureAuthorized"] is False


def test_all_self_asserted_green_still_never_authorizes_and_does_not_mutate():
    evidence = _evidence()
    before = deepcopy(evidence)
    assert classify(evidence) == {
        "automaticAction": False, "topologyComplete": False,
        "closureAuthorized": False, "outcome": "SELF_ASSERTED_READY_NO_AUTHORITY",
        "reason": "NO_INDEPENDENT_CONTROL_PLANE_OR_LIVE_OWNER_PROOF"}
    assert evidence == before


@pytest.mark.parametrize("name,reason", GATES.items())
def test_each_missing_rollout_gate_rejects_exactly(name, reason):
    evidence = _evidence()
    evidence[name] = False
    result = classify(evidence)
    _denied(result)
    assert result == {"automaticAction": False, "topologyComplete": False,
                      "closureAuthorized": False,
                      "outcome": "ROLLOUT_REJECTED_UNPROVEN_GATES",
                      "missingGates": [reason]}


def test_nonzero_physical_second_host_rejects_even_if_all_other_flags_true():
    evidence = _evidence()
    evidence["physicalSecondHostCount"] = 1
    result = classify(evidence)
    _denied(result)
    assert result["missingGates"] == ["PHYSICAL_SECOND_HOST_NOT_ZERO"]


def test_multiple_missing_gates_are_stable_and_not_silently_collapsed():
    evidence = _evidence()
    evidence["controlPlaneSigned"] = False
    evidence["oldCredentialsRevoked"] = False
    evidence["physicalSecondHostCount"] = 2
    result = classify(evidence)
    _denied(result)
    assert result["missingGates"] == [
        "CONTROL_PLANE_SIGNATURE_UNPROVEN",
        "OLD_HOST_RESTART_AUTHORITY_NOT_REVOKED",
        "PHYSICAL_SECOND_HOST_NOT_ZERO",
    ]


@pytest.mark.parametrize("change", [
    lambda e: e.pop("controlPlaneSigned"),
    lambda e: e.update(topologyComplete=True),
    lambda e: e.update(closureAuthorized=True),
    lambda e: e.update(controlPlaneSigned=1),
    lambda e: e.update(physicalSecondHostCount=True),
    lambda e: e.update(physicalSecondHostCount=-1),
    lambda e: e.update(knownLocalPids=0),
])
def test_malformed_self_authority_or_local_zero_fallback_freezes(change):
    evidence = _evidence()
    change(evidence)
    result = classify(evidence)
    _denied(result)
    assert result["outcome"] == "FROZEN_ROLLOUT_EVIDENCE"


def test_nondictionary_input_freezes():
    result = classify(None)
    _denied(result)
    assert result["outcome"] == "FROZEN_ROLLOUT_EVIDENCE"
