"""The natural observer accepts an active independent worker, but not drift."""

from datetime import datetime, timezone
import json

import pytest

import a0v_w5c4r_observe_natural_attempt as wave


@pytest.mark.parametrize("state", ["IDLE", "RUNNING"])
def test_worker_accepts_healthy_state(monkeypatch, tmp_path, state):
    status = tmp_path / "status.json"
    value = {"observedAt": datetime.now(timezone.utc).isoformat(),
             "workerState": state, "workerTaskAlive": True,
             "workerError": None, "hostInThisProcess": False,
             "topology": "independent", "pid": 42}
    status.write_text(json.dumps(value))
    monkeypatch.setattr(wave.prior, "WORKER_STATUS", status)
    monkeypatch.setattr(wave.prior, "_listener", lambda port: 42)

    assert wave._worker()["workerState"] == state


@pytest.mark.parametrize("state", ["STOPPING", "STOPPED"])
def test_worker_rejects_inactive_state(monkeypatch, tmp_path, state):
    status = tmp_path / "status.json"
    status.write_text(json.dumps({"observedAt": datetime.now(timezone.utc).isoformat(),
                                  "workerState": state, "workerTaskAlive": True,
                                  "workerError": None, "hostInThisProcess": False,
                                  "topology": "independent", "pid": 42}))
    monkeypatch.setattr(wave.prior, "WORKER_STATUS", status)
    monkeypatch.setattr(wave.prior, "_listener", lambda port: 42)

    with pytest.raises(ValueError, match="INDEPENDENT_WORKER_DRIFT"):
        wave._worker()
