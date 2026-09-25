"""No-effect fleet structure checks never become a closure authority."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from a0v_w5c7c_fleet_universe_structure import classify


NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)


def _manifest():
    return {
        "schemaVersion": "aos.fleet-universe-structure/v1",
        "controlPlaneId": "isolated-example",
        "fleetRevision": 1,
        "issuedAt": (NOW - timedelta(minutes=1)).isoformat(),
        "expiresAt": (NOW + timedelta(minutes=1)).isoformat(),
        "members": [{"machineId": "machine-1", "launchSurface": "launchd",
                     "hostId": "host-1", "databaseRole": "role_1", "roleOid": 41,
                     "deploymentRevision": "isolated-1"}],
    }


def test_valid_shape_is_still_untrusted_and_does_not_mutate_input():
    value = _manifest()
    before = deepcopy(value)
    result = classify(value, now=NOW)
    assert value == before
    assert result == {"automaticAction": False, "topologyComplete": False,
                      "closureAuthorized": False, "outcome": "STRUCTURE_ONLY_UNTRUSTED",
                      "reason": "NO_SIGNED_CONTROL_PLANE_COVERAGE_OR_LIVE_CUTOVER_PROOF",
                      "memberCount": 1}


@pytest.mark.parametrize("change", [
    lambda m: m.pop("members"),
    lambda m: m.update(signatureVerified=True),
    lambda m: m.update(topologyComplete=True),
    lambda m: m.update(members=[]),
    lambda m: m.update(fleetRevision=True),
    lambda m: m.update(issuedAt=(NOW + timedelta(seconds=1)).isoformat()),
    lambda m: m.update(expiresAt=(NOW - timedelta(seconds=1)).isoformat()),
    lambda m: m.update(expiresAt=(NOW + timedelta(minutes=11)).isoformat()),
    lambda m: m["members"][0].update(extra="self-asserted"),
    lambda m: m["members"].append(deepcopy(m["members"][0])),
    lambda m: m["members"].append({**m["members"][0], "hostId": "host-2",
                                     "databaseRole": "role_2", "roleOid": 42}),
    lambda m: m["members"].append({**m["members"][0], "machineId": "machine-2",
                                     "databaseRole": "role_2", "roleOid": 42}),
    lambda m: m["members"].append({**m["members"][0], "machineId": "machine-2",
                                     "hostId": "host-2", "roleOid": 42}),
    lambda m: m["members"].append({**m["members"][0], "machineId": "machine-2",
                                     "hostId": "host-2", "databaseRole": "role_2"}),
])
def test_missing_self_asserted_stale_or_duplicate_input_freezes(change):
    value = _manifest()
    change(value)
    result = classify(value, now=NOW)
    assert result["outcome"] == "FROZEN_FLEET_STRUCTURE"
    assert result["automaticAction"] is False
    assert result["topologyComplete"] is False
    assert result["closureAuthorized"] is False


def test_invalid_reference_clock_freezes():
    result = classify(_manifest(), now=NOW.replace(tzinfo=None))
    assert result["outcome"] == "FROZEN_FLEET_STRUCTURE"
    assert result["closureAuthorized"] is False
