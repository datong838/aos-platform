"""Offline terminal assessment is advisory and must fail closed on ambiguity."""

from copy import deepcopy

import a0v_w5c4r_terminal_assessment as wave


SLOT = "2026-09-24T20:00:00+00:00"


def _cases():
    intent = {"nextSlotUtc": SLOT, "workerPid": 37241, "hostPid": 17302}
    result = {"ref": {"revision": 3, "contentHash": "sha256:current"}}
    before = {"observedAt": "2026-09-24T19:59:00+00:00",
              "observation": "WAITING_FOR_NATURAL_TERMINAL",
              "workerPid": 37241, "hostPid": 17302,
              "definition": {"revision": 3, "state": "enabled",
                             "content_hash": "sha256:current"},
              "claims": [], "attempts": [], "runGroups": [],
              "facts": {"routes": 9, "unpaused_gate": 1, "schedules_enabled": 12,
                        "store_receipts": 26, "live_links": 0,
                        "projection_pending": 0, "canary": 0}}
    after = deepcopy(before)
    after.update({"observedAt": "2026-09-24T20:10:00+00:00",
                  "observation": "ATTEMPT_FORMAL_TERMINAL",
                  "claims": [{"group_id": "g1", "trigger": "cron",
                              "scheduled_for": SLOT}],
                  "attempts": [{"attempt_id": "a1", "state": "succeeded",
                                "operation_kind": "recoverable_store",
                                "terminal_reason_code": None,
                                "terminal_error_type": None}],
                  "runGroups": [{"group_id": "g1", "status": "succeeded",
                                 "executor_stopped": True,
                                 "finished_at": "2026-09-24T20:09:00+00:00", "n": 12}]})
    after["facts"]["store_receipts"] = 38
    after["facts"]["live_links"] = 1168
    return before, after, intent, result


def test_succeeded_is_only_independent_audit_candidate():
    before, after, intent, result = _cases()

    value = wave.assess(before, after, intent, result)

    assert value["outcome"] == "SUCCEEDED_REQUIRES_INDEPENDENT_AUDIT"
    assert value["automaticAction"] is False
    assert value["storeReceiptDelta"] == 12
    assert value["liveLinkDelta"] == 1168


def test_before_slot_is_not_terminal_without_action():
    before, after, intent, result = _cases()
    after = deepcopy(before)
    after["observedAt"] = "2026-09-24T19:59:30+00:00"

    value = wave.assess(before, after, intent, result)

    assert value == {"outcome": "NOT_TERMINAL_NO_ACTION", "automaticAction": False}


def test_failed_prestore_is_only_recovery_candidate():
    before, after, intent, result = _cases()
    after["attempts"][0].update({"state": "failed",
                                 "terminal_reason_code": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
                                 "terminal_error_type": "IngressJournalConflict"})
    after["runGroups"] = [{"group_id": "g1", "status": "running",
                           "executor_stopped": False, "finished_at": None, "n": 12}]
    after["facts"]["store_receipts"] = 26
    after["facts"]["live_links"] = 0

    value = wave.assess(before, after, intent, result)

    assert value["outcome"] == "FAILED_PRESTORE_CANDIDATE_REQUIRES_INDEPENDENT_AUDIT"
    assert value["automaticAction"] is False


def test_noncron_claim_and_second_attempt_freeze():
    before, after, intent, result = _cases()
    after["claims"][0]["trigger"] = "manual"
    assert wave.assess(before, after, intent, result)["outcome"] == "FROZEN_ASSESSMENT_BOUNDARY"
    after["claims"][0]["trigger"] = "cron"
    after["attempts"].append(deepcopy(after["attempts"][0]))
    assert wave.assess(before, after, intent, result)["outcome"] == "FROZEN_ASSESSMENT_BOUNDARY"


def test_failed_with_store_delta_freezes():
    before, after, intent, result = _cases()
    after["attempts"][0].update({"state": "failed",
                                 "terminal_reason_code": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
                                 "terminal_error_type": "IngressJournalConflict"})
    after["runGroups"] = [{"group_id": "g1", "status": "running",
                           "executor_stopped": False, "finished_at": None, "n": 12}]
    after["facts"]["live_links"] = 0

    assert wave.assess(before, after, intent, result)["outcome"] == "FROZEN_ASSESSMENT_BOUNDARY"
