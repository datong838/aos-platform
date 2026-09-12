import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ecommerce_1_7_registry_successor.py"
SPEC = importlib.util.spec_from_file_location("successor17", PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_missing_real_sessions_are_rejected():
    with pytest.raises(ValueError, match="actual session"):
        M.require_sessions({"runtimeAdmissions": {}})


def test_root_switch_is_cas_and_replay_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "STATE", tmp_path)
    env = tmp_path / "env"
    original = f"AOS_BUNDLE_ROOT={M.OLD_ROOT}\nUNCHANGED=value\n"
    env.write_text(original)
    assert M.switch_root(env) is True
    assert M.switch_root(env) is False
    assert (tmp_path / "env-before-v7").read_text() == original
    assert "UNCHANGED=value" in env.read_text()
    env.write_text("AOS_BUNDLE_ROOT=/unexpected\n")
    with pytest.raises(ValueError, match="CAS"):
        M.switch_root(env)
    assert env.read_text() == "AOS_BUNDLE_ROOT=/unexpected\n"


@pytest.mark.parametrize("field", ["registration", "heartbeat", "cleanup", "contributionCount", "heartbeatChecks"])
def test_session_receipt_must_include_every_stage(field):
    sessions = {key: {"registration": "exact", "heartbeat": "alive", "cleanup": "released", "contributionCount": n, "heartbeatChecks": 2048}
                for key, n in [("domain.ecommerce.core", 1), ("platform.ecommerce.niushop", 2), ("solution.ecommerce.growth", 23)]}
    M.require_sessions({"runtimeSessions": sessions})
    sessions["solution.ecommerce.growth"].pop(field)
    with pytest.raises(ValueError, match="incomplete"):
        M.require_sessions({"runtimeSessions": sessions})
