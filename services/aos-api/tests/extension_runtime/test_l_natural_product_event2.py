from pathlib import Path
import copy
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))

import a0v_l_natural_product_event as base
import a0v_l_natural_product_event2 as second


def test_second_natural_window_uses_separate_state_and_policy9():
    original = (base.STATE, base.POLICY_REVISION, base.EXPECTED_BINDING_REVISION)
    try:
        second.configure()
        assert base.STATE.name == "natural-product-event-v2"
        assert base.POLICY_REVISION == 9
        assert base.EXPECTED_BINDING_REVISION == 1
    finally:
        base.STATE, base.POLICY_REVISION, base.EXPECTED_BINDING_REVISION = original


def test_second_natural_executor_has_no_manual_run_call():
    source = Path(second.__file__).read_text()
    assert "/run" not in source


def _snapshot(status=None):
    value = {
        "schedule": {"enabled": True}, "runs": [], "ingress": [],
        "occurrences": [], "attempts": [], "investigationRuns": [],
        "inflight": {"running": 0, "unresolved": 0},
        "negativeCanaryDispatch": 0,
    }
    if status is not None:
        value["runs"] = [{"id": "run-1", "status": status}]
    return value


def test_watch_disarms_succeeded_run_after_investigation(monkeypatch):
    terminal = _snapshot("succeeded")
    terminal["investigationRuns"] = [{"run_id": "analysis-1"}]
    final = copy.deepcopy(terminal); final["schedule"]["enabled"] = False
    monkeypatch.setattr(base, "_private", lambda name: {})
    monkeypatch.setattr(base, "snapshot", lambda: terminal)
    monkeypatch.setattr(base, "validate_ready", lambda value, require_drained=False: value)
    monkeypatch.setattr(base, "disarm", lambda: {"snapshot": final})
    result = second.watch(initial_timeout_seconds=1, poll_seconds=0)
    assert result["outcome"] == "L_POLICY9_NATURAL_TERMINAL_OBSERVED"
    assert result["downstreamReady"] is True
    assert result["snapshot"]["schedule"]["enabled"] is False


def test_watch_disarms_failed_run_without_downstream(monkeypatch):
    terminal = _snapshot("failed")
    final = copy.deepcopy(terminal); final["schedule"]["enabled"] = False
    monkeypatch.setattr(base, "_private", lambda name: {})
    monkeypatch.setattr(base, "snapshot", lambda: terminal)
    monkeypatch.setattr(base, "validate_ready", lambda value, require_drained=False: value)
    monkeypatch.setattr(base, "disarm", lambda: {"snapshot": final})
    result = second.watch(initial_timeout_seconds=1, poll_seconds=0)
    assert result["terminalRun"]["status"] == "failed"
    assert result["downstreamReady"] is False


def test_watch_times_out_empty_window_and_disarms(monkeypatch):
    current = _snapshot()
    final = copy.deepcopy(current); final["schedule"]["enabled"] = False
    calls = iter([0, 2])
    monkeypatch.setattr(base, "_private", lambda name: {})
    monkeypatch.setattr(base, "snapshot", lambda: final if final["schedule"]["enabled"] is False else current)
    monkeypatch.setattr(base, "validate_ready", lambda value, require_drained=False: value)
    monkeypatch.setattr(base, "disarm", lambda: {"snapshot": final})
    result = second.watch(initial_timeout_seconds=1, poll_seconds=0,
                          clock=lambda: next(calls), pause=lambda _: None)
    assert result["outcome"] == "L_POLICY9_NATURAL_WINDOW_TIMED_OUT"


def test_watch_rejects_more_than_one_run(monkeypatch):
    value = _snapshot("succeeded")
    value["runs"].append({"id": "run-2", "status": "failed"})
    monkeypatch.setattr(base, "_private", lambda name: {})
    monkeypatch.setattr(base, "snapshot", lambda: value)
    monkeypatch.setattr(base, "validate_ready", lambda value, require_drained=False: value)
    with pytest.raises(ValueError, match="more than one"):
        second.watch(initial_timeout_seconds=1, poll_seconds=0)


def test_watch_waits_for_running_terminal_after_disarm(monkeypatch):
    running = _snapshot("running")
    terminal = _snapshot("failed")
    final = copy.deepcopy(terminal); final["schedule"]["enabled"] = False
    snapshots = iter([running, terminal, final])
    clock_values = iter([0, 2, 2, 3])
    monkeypatch.setattr(base, "_private", lambda name: {})
    monkeypatch.setattr(base, "snapshot", lambda: next(snapshots))
    monkeypatch.setattr(base, "validate_ready", lambda value, require_drained=False: value)
    monkeypatch.setattr(base, "disarm", lambda: {"snapshot": final})
    result = second.watch(initial_timeout_seconds=1, running_timeout_seconds=10,
                          poll_seconds=0, clock=lambda: next(clock_values), pause=lambda _: None)
    assert result["terminalRun"]["status"] == "failed"


def test_watch_disarms_succeeded_run_when_downstream_times_out(monkeypatch):
    terminal = _snapshot("succeeded")
    final = copy.deepcopy(terminal); final["schedule"]["enabled"] = False
    calls = iter([0, 2])
    monkeypatch.setattr(base, "_private", lambda name: {})
    monkeypatch.setattr(base, "snapshot", lambda: terminal)
    monkeypatch.setattr(base, "validate_ready", lambda value, require_drained=False: value)
    monkeypatch.setattr(base, "disarm", lambda: {"snapshot": final})
    result = second.watch(initial_timeout_seconds=1, poll_seconds=0,
                          clock=lambda: next(calls), pause=lambda _: None)
    assert result["outcome"] == "L_POLICY9_NATURAL_DOWNSTREAM_TIMED_OUT"
