"""A returned enable receipt is not success without the live binding audit."""

import pytest

import a0v_w5c3m_natural_enable as wave


def test_audit_rejects_fenced_binding(monkeypatch):
    monkeypatch.setattr(wave, "_load", lambda name: {
        "installationId": wave.staged.prior.INSTALLATION,
        "generation": wave.staged.prior.GENERATION,
        "configRef": {"configurationId": "id", "revision": 1, "hash": "hash"},
        "hostPid": 7, "businessCounts": {"claims": 40, "runs": 53}})
    monkeypatch.setattr(wave, "observe", lambda: {
        "operation": {"operation_id": "op", "kind": "enable", "status": "succeeded",
                      "phase": "succeeded"},
        "installation": {"state": "active", "etag_version": 5},
        "binding": [{"generation": wave.staged.prior.GENERATION,
                     "config_ref": {"configurationId": "id", "revision": 1, "hash": "hash"},
                     "enabled": False, "operation_fence": True,
                     "desired_state": "disabled", "observed_state": "unknown"}],
        "resources": [{"cleanup_state": "pending", "observed_release": False}
                      for _ in range(3)],
        "host": {"pid": 7, "liveTargets": [1]},
        "counts": {"commands": 1, "operations": 1, "attempts": 0,
                   "routes": {"total": 9, "legacy": 9},
                   "schedules": {"total": 12, "enabled": 0},
                   "canary": 0, "business": {"claims": 40, "runs": 53}},
    })
    with pytest.raises(ValueError, match="AUDIT_NOT_GREEN"):
        wave.audit()
