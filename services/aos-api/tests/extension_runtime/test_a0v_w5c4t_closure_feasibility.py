"""Read-only W5c4t closure time/effects routing."""

from datetime import datetime, timedelta, timezone

import a0v_w5c4t_closure_feasibility as wave


START = datetime(2026, 9, 24, 20, 0, 4, 800482, tzinfo=timezone.utc)


def snapshot(now):
    return {
        "observedAt": now,
        "head": {"revision": 4, "state": "disabled", "content_hash": wave.HASH},
        "claims": [{"group_id": wave.GROUP, "trigger": "cron",
                    "scheduled_for": "2026-09-24 20:00:00+00:00"}],
        "attempts": [{"attempt_id": wave.ATTEMPT, "state": "failed",
                      "terminal_reason_code": "RECOVERABLE_EXECUTION_EXCEPTION",
                      "terminal_error_type": "PermissionError"}],
        "runs": {"n": 12, "stalled": 12, "latest_started": START},
        "effects": {"groupClaims": 1, "groupInputs": 1, "groupMembers": 12,
                    "sourceClaims": 12, "ingressCommands": 12,
                    "derivedCommands": 0, "datasetReceipts": 0},
        "facts": {"storeReceipts": 26, "liveLinks": 0, "pending": 0,
                  "canary": 0, "stalledReceipts": 0, "unacceptedReceipts": 0},
    }


def test_effects_reject_unaccepted_path_and_wait_24h():
    result = wave.classify(snapshot(START + timedelta(hours=23)))
    assert result["outcome"] == "STALLED_WAIT_24H"
    assert result["unacceptedPath"] == "UNACCEPTED_PATH_REJECTED_EFFECTS"
    assert result["automaticAction"] is False


def test_exact_boundary_still_waits():
    assert wave.classify(snapshot(START + timedelta(hours=24)))["outcome"] == "STALLED_WAIT_24H"


def test_after_boundary_only_recommends_fresh_authority():
    result = wave.classify(snapshot(START + timedelta(hours=24, microseconds=1)))
    assert result["outcome"] == "STALLED_ELIGIBLE_REQUIRES_FRESH_AUTHORITY"
    assert result["automaticAction"] is False


def test_second_attempt_or_effect_drift_freezes():
    value = snapshot(START + timedelta(hours=25))
    value["attempts"].append(dict(value["attempts"][0]))
    assert wave.classify(value)["outcome"] == "FROZEN_FEASIBILITY_BOUNDARY"
    value = snapshot(START + timedelta(hours=25))
    value["effects"]["datasetReceipts"] = 1
    assert wave.classify(value)["outcome"] == "FROZEN_FEASIBILITY_BOUNDARY"


def test_definition_or_run_drift_freezes():
    value = snapshot(START + timedelta(hours=25))
    value["head"]["state"] = "enabled"
    assert wave.classify(value)["outcome"] == "FROZEN_FEASIBILITY_BOUNDARY"
    value = snapshot(START + timedelta(hours=25))
    value["runs"]["stalled"] = 11
    assert wave.classify(value)["outcome"] == "FROZEN_FEASIBILITY_BOUNDARY"
