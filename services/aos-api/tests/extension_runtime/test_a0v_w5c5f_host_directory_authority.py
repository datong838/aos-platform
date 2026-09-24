"""Exact managed host-directory read-only classifier; no live close."""

from copy import deepcopy
from pathlib import Path

import pytest

import a0v_w5c5f_host_directory_authority as audit
from a0v_w5c4t_closure_feasibility import HASH


def snapshot():
    assignment = {"host_id": audit.HOST_ID, "state": "assigned", "revision": 1}
    identity = {"database_role": audit.DIRECTORY_ROLE, "host_id": audit.HOST_ID,
                "enabled": True, "revision": 1, "role_oid_matches": True,
                "eligible_directory_member": True, "non_privileged_login": True}
    return {"assignment": assignment, "assignmentHistory": [deepcopy(assignment)],
            "identities": [identity], "identityHistory": [{key: identity[key] for key in
                ("database_role", "host_id", "enabled", "revision", "role_oid_matches")}],
            "leaseStates": [{"cleanup_state": "released", "observed_release": True,
                             "n": 3}],
            "definition": {"revision": 4, "state": "disabled", "content_hash": HASH},
            "runs": {"n": 12, "running": 12}, "closureReceipts": 0}


def test_exact_directory_is_not_all_host_proof():
    result = audit.classify(snapshot())
    assert result["outcome"] == "MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY"
    assert result["topologyComplete"] is False
    assert result["closureAuthorized"] is False
    assert result["automaticAction"] is False


@pytest.mark.parametrize("mutate", [
    lambda v: v["assignment"].update(host_id="other"),
    lambda v: v["assignment"].update(revision=2),
    lambda v: v["assignmentHistory"].append(deepcopy(v["assignmentHistory"][0])),
    lambda v: v["identities"].append(deepcopy(v["identities"][0])),
    lambda v: v["identities"][0].update(role_oid_matches=False),
    lambda v: v["identities"][0].update(non_privileged_login=False),
    lambda v: v["identities"][0].update(eligible_directory_member=False),
    lambda v: v["identityHistory"][0].update(revision=2),
    lambda v: v["leaseStates"][0].update(cleanup_state="uncertain"),
    lambda v: v["leaseStates"][0].update(observed_release=False),
    lambda v: v["leaseStates"][0].update(n=4),
    lambda v: v["definition"].update(state="enabled"),
    lambda v: v["runs"].update(running=11),
    lambda v: v.update(closureReceipts=1),
    lambda v: v.update(assignment=None),
])
def test_any_drift_freezes(mutate):
    value = snapshot()
    mutate(value)
    assert audit.classify(value)["outcome"] == "FROZEN_HOST_DIRECTORY_AUTHORITY"


def test_observer_has_no_write_or_lock_acquisition():
    source = Path(audit.__file__).read_text()
    assert "REPEATABLE READ READ ONLY" in source
    for forbidden in ("FOR UPDATE", "pg_try_advisory_lock", "pg_advisory_lock(",
                      "pipeline_snapshot_stalled_group_close_a0v_091(",
                      "INSERT INTO", "UPDATE extension_runtime", "DELETE FROM"):
        assert forbidden not in source
