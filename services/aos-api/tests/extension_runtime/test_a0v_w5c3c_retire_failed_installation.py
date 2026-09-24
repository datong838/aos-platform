"""The W5c3c retirement must require a terminal, released failed preparation."""

from copy import deepcopy

import pytest

import a0v_w5c3c_retire_failed_installation as wave


def _snapshot():
    return {
        "installationId": "installation", "old": {"head": {"state": "uninstalled"}},
        "new": {
            "head": {"lock_hash": "lock", "state": "approved", "etag_version": 3},
            "bindings": [], "operations": [{"operation_id": wave.OPERATION,
                "kind": "runtime-apply", "status": "failed", "phase": "preparing",
                "revision": 7, "failure_code": "PREPARATION_EXECUTION_FAILED"}],
            "resources": [{"cleanup_state": "released", "observed_release": True}
                          for _ in range(3)], "canaryInstallations": 0,
        },
        "host": {"pid": 1, "liveTargets": []},
        "routes": {"total": 9, "legacy": 9},
        "schedules": {"total": 12, "enabled": 0},
        "attempts": 0, "commands": 0, "counts": {"claims": 40, "runs": 53},
    }


def test_exact_failed_released_gate(monkeypatch):
    monkeypatch.setattr(wave.successor, "_load", lambda name: {"lockHash": "lock"})
    assert wave._require(_snapshot(), retired=False)["installationId"] == "installation"


@pytest.mark.parametrize("field,value", [
    ("status", "accepted"), ("status", "succeeded"),
    ("failure_code", "OTHER"), ("revision", 6),
])
def test_other_operation_cannot_retire(monkeypatch, field, value):
    monkeypatch.setattr(wave.successor, "_load", lambda name: {"lockHash": "lock"})
    snapshot = _snapshot()
    snapshot["new"]["operations"][0][field] = value
    with pytest.raises(ValueError, match="BOUNDARY_DRIFT"):
        wave._require(snapshot, retired=False)


def test_unreleased_resource_cannot_retire(monkeypatch):
    monkeypatch.setattr(wave.successor, "_load", lambda name: {"lockHash": "lock"})
    snapshot = deepcopy(_snapshot())
    snapshot["new"]["resources"][0]["observed_release"] = False
    with pytest.raises(ValueError, match="BOUNDARY_DRIFT"):
        wave._require(snapshot, retired=False)
