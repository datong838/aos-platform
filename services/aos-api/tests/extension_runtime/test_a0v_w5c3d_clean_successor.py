"""Clean successor may not treat either retired installation as a live baseline."""

from copy import deepcopy

import pytest

import a0v_w5c3d_clean_successor as wave


def _snapshot():
    return {
        "formerId": "former",
        "former": {"head": {"state": "uninstalled", "etag_version": 4,
                            "lock_hash": "lock"}, "bindings": [],
                   "operations": [{"operation_id": wave.retired.OPERATION,
                                   "status": "failed"}],
                   "resources": [{"cleanup_state": "released", "observed_release": True}
                                 for _ in range(3)], "canaryInstallations": 0},
        "old": {"head": {"state": "uninstalled"}},
        "host": {"pid": 1, "liveTargets": []},
        "heads": [{"active_revision": None}, {"active_revision": None}],
        "routes": {"total": 9, "legacy": 9},
        "schedules": {"total": 12, "enabled": 0},
        "commands": 0, "attempts": 0,
        "budget": {"revision": 13, "valid": True},
        "counts": {"claims": 40, "runs": 53},
    }


def test_exact_retired_baseline(monkeypatch):
    monkeypatch.setattr(wave.previous, "_load", lambda name: {"lockHash": "lock"})
    assert wave._require(_snapshot(), command_count=0)["formerId"] == "former"


@pytest.mark.parametrize("change", [
    lambda s: s["heads"][0].update(active_revision=5),
    lambda s: s["former"]["resources"][0].update(cleanup_state="pending"),
    lambda s: s["former"]["head"].update(state="approved"),
    lambda s: s["host"].update(liveTargets=[{"installationId": "other"}]),
    lambda s: s.update(commands=1),
])
def test_drift_blocks_clean_approval(monkeypatch, change):
    monkeypatch.setattr(wave.previous, "_load", lambda name: {"lockHash": "lock"})
    snapshot = deepcopy(_snapshot())
    change(snapshot)
    with pytest.raises(ValueError, match="BASELINE_DRIFT"):
        wave._require(snapshot, command_count=0)
