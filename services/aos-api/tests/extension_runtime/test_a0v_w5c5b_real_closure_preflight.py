"""Advisory closure preflight cannot apply an Owner action."""

from datetime import timedelta

import a0v_w5c5b_real_closure_preflight as wave
from test_a0v_w5c4t_closure_feasibility import START, snapshot


def detail(value):
    return {
        "head": dict(value["head"]),
        "claims": list(value["claims"]),
        "attempts": [{**value["attempts"][0], "operation_kind": "recoverable_store"}],
        "runs": [{"status": "running", "executor_stopped": False,
                  "finished_at": None, "n": 12}],
        "member_revisions": [{"revision": 4, "n": 12}],
        "key_revisions": [{"revision": 4, "content_hash": wave.base.HASH,
                           "previous_hash": wave.prior.HASH}],
        "facts": {"members": 12, "enabled": 0, "receipts": 26,
                  "links": 0, "pending": 0, "canary": 0, "key_count": 1},
        "host_alive": False,
        "worker_pid": wave.prior.WORKER_PID,
        "actor_admin": True,
    }


def test_before_and_exact_boundary_wait_without_action():
    for delta in (timedelta(hours=23), timedelta(hours=24)):
        value = snapshot(START + delta)
        result = wave.classify(value, detail(value))
        assert result["outcome"] == "STALLED_WAIT_24H"
        assert result["automaticAction"] is False
        assert result["topologyComplete"] is False


def test_after_boundary_only_routes_to_separate_plan():
    value = snapshot(START + timedelta(hours=24, microseconds=1))
    result = wave.classify(value, detail(value))
    assert result["outcome"] == "REQUIRES_SEPARATE_REAL_CLOSURE_PLAN"
    assert result["automaticAction"] is False
    assert result["topologyComplete"] is False
    assert "all-host topology" in result["remaining"]


def test_actor_or_named_topology_or_definition_drift_freezes():
    value = snapshot(START + timedelta(hours=25))
    for change in ({"actor_admin": False}, {"worker_pid": 0},
                   {"host_alive": True}, {"member_revisions": []},
                   {"key_revisions": []}):
        current = {**detail(value), **change}
        assert wave.classify(value, current)["outcome"] == "FROZEN_REAL_CLOSURE_PREFLIGHT"
    value["head"]["revision"] = 5
    assert wave.classify(value, detail(value))["outcome"] == "FROZEN_REAL_CLOSURE_PREFLIGHT"


def test_second_attempt_and_missing_detail_freeze():
    value = snapshot(START + timedelta(hours=25))
    value["attempts"].append(dict(value["attempts"][0]))
    assert wave.classify(value, detail(value))["outcome"] == "FROZEN_REAL_CLOSURE_PREFLIGHT"
    value = snapshot(START + timedelta(hours=25))
    current = detail(value)
    del current["actor_admin"]
    assert wave.classify(value, current)["outcome"] == "FROZEN_REAL_CLOSURE_PREFLIGHT"
