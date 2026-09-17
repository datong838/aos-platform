"""T interruption recovery follows the accepted reset and predecessor-free successor protocol."""

import importlib.util
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_t_interruption_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_t_interruption_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def operation(kind, *, status="succeeded", phase="succeeded", expired=False):
    return {
        "operation_id": recovery.T_VERIFY_OPERATION if kind == "runtime-verify" else "apply",
        "kind": kind,
        "status": status,
        "phase": phase,
        "deadline_expired": expired,
    }


def snapshot(*, resettable=True):
    return {
        "head": {
            "state": "applied" if resettable else "approved",
            "etag_version": 4 if resettable else 5,
            "lock_hash": recovery.T_LOCK,
        },
        "bindings": [],
        "operations": [
            operation("runtime-apply"),
            operation(
                "runtime-verify",
                status="accepted" if resettable else "cancelled",
                phase="accepted" if resettable else "cancelled",
                expired=resettable,
            ),
        ],
        "resources": [
            {"cleanup_state": "released", "observed_release": True} for _ in range(3)
        ],
        "canaryInstallations": 0,
    }


class Profile:
    def __init__(self, value):
        self.value = value

    def observe_installation(self, identity):
        assert identity == recovery.T_ID
        return self.value


def test_fixed_recovery_sequence_and_no_predecessor_for_u():
    assert recovery.ACTIONS == (
        "recovery-preflight", "reset-t", "create-u", "uninstall-t", "prepare-u", "verify-u",
        "stage-u", "configure-u", "enable-u", "observe",
    )
    source = PATH.read_text(encoding="utf-8")
    assert '"predecessor": None' in source
    assert "current_installation_ref=" not in source
    assert "profile.lifecycle(\"u\", action)" in source


def test_interrupted_t_accepts_only_expired_exact_verify_and_released_resources():
    assert recovery.interrupted_t(Profile(snapshot()), resettable=True)["head"]["state"] == "applied"
    bad = snapshot()
    bad["operations"][1]["deadline_expired"] = False
    with pytest.raises(ValueError, match="exact resettable"):
        recovery.interrupted_t(Profile(bad), resettable=True)
    bad = snapshot()
    bad["resources"][0]["observed_release"] = False
    with pytest.raises(ValueError, match="exact resettable"):
        recovery.interrupted_t(Profile(bad), resettable=True)


def test_terminal_t_requires_all_operations_terminal():
    assert recovery.interrupted_t(Profile(snapshot(resettable=False)), resettable=False)["head"]["state"] == "approved"
    bad = snapshot(resettable=False)
    bad["operations"][1]["status"] = "accepted"
    with pytest.raises(ValueError, match="terminal T"):
        recovery.interrupted_t(Profile(bad), resettable=False)


def test_unknown_action_fails_before_profile(monkeypatch):
    monkeypatch.setattr(recovery, "load_profile", lambda: pytest.fail("must not load profile"))
    with pytest.raises(ValueError, match="unsupported T interruption"):
        recovery.run("retry")
