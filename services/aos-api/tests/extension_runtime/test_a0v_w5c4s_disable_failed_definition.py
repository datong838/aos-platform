"""W5c4s fail-closed gate without business or source access."""

import pytest

import a0v_w5c4s_disable_failed_definition as wave


def valid():
    return {
        "head": {"revision": 3, "state": "enabled", "content_hash": wave.HASH},
        "claims": [{"group_id": wave.GROUP, "trigger": "cron",
                    "scheduled_for": "2026-09-24 20:00:00+00:00"}],
        "attempts": [{"attempt_id": wave.ATTEMPT, "state": "failed",
                      "operation_kind": "recoverable_store",
                      "terminal_reason_code": "RECOVERABLE_EXECUTION_EXCEPTION",
                      "terminal_error_type": "PermissionError"}],
        "runs": [{"status": "running", "executor_stopped": False,
                  "finished_at": None, "n": 12}],
        "facts": {"members": 12, "enabled": 12, "receipts": 26,
                  "links": 0, "pending": 0, "canary": 0, "key_count": 0},
        "host_alive": False,
        "worker_pid": wave.WORKER_PID,
    }


def test_exact_failed_boundary_accepted():
    assert wave._gate(valid()) is True


def test_second_attempt_rejected():
    value = valid()
    value["attempts"].append(dict(value["attempts"][0]))
    assert wave._gate(value) is False


def test_side_effect_or_canary_rejected():
    for field, changed in (("receipts", 27), ("links", 1), ("pending", 1),
                           ("canary", 1)):
        value = valid()
        value["facts"][field] = changed
        assert wave._gate(value) is False


def test_host_or_definition_drift_rejected():
    value = valid()
    value["host_alive"] = True
    assert wave._gate(value) is False
    value = valid()
    value["head"]["revision"] = 4
    assert wave._gate(value) is False


def test_reused_key_or_run_change_rejected():
    value = valid()
    value["facts"]["key_count"] = 1
    assert wave._gate(value) is False
    value = valid()
    value["runs"][0]["status"] = "succeeded"
    assert wave._gate(value) is False


def test_one_transition_and_no_replay(monkeypatch, tmp_path):
    monkeypatch.setattr(wave, "STATE", tmp_path / "intent")
    monkeypatch.setattr(wave, "preflight", lambda: {"expectedRef": {"revision": 3}})
    calls = []

    class Service:
        def transition(self, **kwargs):
            calls.append(kwargs)
            return {"ref": {"revision": 4}, "body": {"state": "disabled"}}

    monkeypatch.setattr(wave, "_service", lambda: Service())
    assert wave.disable()["outcome"] == "W5C4S_DISABLE_ACCEPTED"
    with pytest.raises(ValueError, match="INTENT_EXISTS"):
        wave.disable()
    assert len(calls) == 1
    assert calls[0]["intent"] == "disable"


def test_unknown_transition_keeps_intent_and_never_retries(monkeypatch, tmp_path):
    monkeypatch.setattr(wave, "STATE", tmp_path / "intent")
    monkeypatch.setattr(wave, "preflight", lambda: {"expectedRef": {"revision": 3}})
    calls = []

    class Service:
        def transition(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("unknown commit boundary")

    monkeypatch.setattr(wave, "_service", lambda: Service())
    with pytest.raises(RuntimeError, match="unknown commit"):
        wave.disable()
    assert (wave.STATE / "intent.json").is_file()
    with pytest.raises(ValueError, match="INTENT_EXISTS"):
        wave.disable()
    assert len(calls) == 1
