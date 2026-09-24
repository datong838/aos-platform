"""Independent closure-audit classifier; no live closure or shared DB writes."""

from copy import deepcopy

import pytest

import a0v_w5c4t_closure_feasibility as boundary
import a0v_w5c5e_independent_closure_audit as audit
from aos_api.asset_registry.canonical_json import canonical_sha256


def snapshot():
    original = {"resourceType": "SnapshotScheduleDefinitionRevision",
                "resourceId": "snapshot-schedule-" + boundary.DEFINITION,
                "revision": 3, "contentHash": "sha256:" + "a" * 64}
    return {
        "head": {"revision": 4, "state": "disabled", "content_hash": boundary.HASH},
        "claims": [{"group_id": boundary.GROUP, "trigger": "cron",
                    "scheduled_for": "2026-09-24 20:00:00+00:00",
                    "request": {"definitionRef": original},
                    "record": {"schemaVersion": "aos.snapshot-schedule-claim/v2"}}],
        "attempts": [{"attempt_id": boundary.ATTEMPT, "state": "failed",
                      "terminal_reason_code": "RECOVERABLE_EXECUTION_EXCEPTION",
                      "terminal_error_type": "PermissionError"}],
        "runs": {"n": 12, "running": 12, "closed": 0, "schedulesEnabled": 0},
        "effects": deepcopy(boundary.EFFECTS), "receiptCount": 0, "receipt": None,
        "facts": deepcopy(boundary.FACTS),
    }


def closed_snapshot():
    value = snapshot()
    value["runs"] = {"n": 12, "running": 0, "closed": 12, "schedulesEnabled": 0}
    value["receiptCount"] = 1
    value["facts"]["stalledReceipts"] = 1
    request = {"schemaVersion": "aos.pipeline-snapshot.stalled-group-closure/v1",
               "groupId": boundary.GROUP,
               "originalDefinitionRef": value["claims"][0]["request"]["definitionRef"],
               "currentDisabledDefinitionRef": {
                   "resourceType": "SnapshotScheduleDefinitionRevision",
                   "resourceId": "snapshot-schedule-" + boundary.DEFINITION,
                   "revision": 4, "contentHash": boundary.HASH},
               "reasonCode": audit.REASON, "idempotencyKey": "synthetic-w5c5e"}
    request_hash = canonical_sha256(request)
    body = {"schemaVersion": "aos.pipeline-snapshot.stalled-group-closure-receipt/v1",
            "receiptId": "00000000-0000-0000-0000-000000000001",
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "request": request, "requestHash": request_hash, "actor": "synthetic-test-actor",
            "businessAccepted": False,
            "priorScheduleClaim": value["claims"][0]["record"],
            "runEvidence": {"memberCount": 12, "stalledRunCount": 12,
                            "staleOver24hCount": 12},
            "effectEvidence": {wire: value["effects"][key]
                               for key, wire in audit.EFFECT_KEYS.items()}}
    value["receipt"] = {"receipt_id": body["receiptId"],
                        "content_hash": canonical_sha256(body),
                        "request_hash": request_hash,
                        "idempotency_key": request["idempotencyKey"],
                        "actor": body["actor"], "authority_data": body}
    return value


def test_not_closed_is_not_success():
    assert audit.classify(snapshot())["outcome"] == "NOT_YET_CLOSED"


def test_complete_exact_receipt_and_twelve_terminal_runs():
    result = audit.classify(closed_snapshot())
    assert result["outcome"] == "INDEPENDENT_STALLED_CLOSURE_AUDIT_GREEN"
    assert result["businessAccepted"] is False
    assert result["automaticAction"] is False


@pytest.mark.parametrize("mutate", [
    lambda x: x["runs"].update(closed=11),
    lambda x: x["runs"].update(running=1),
    lambda x: x["receipt"].update(content_hash="sha256:" + "b" * 64),
    lambda x: x["receipt"]["authority_data"]["effectEvidence"].update(groupMemberCount=11),
    lambda x: x["receipt"]["authority_data"].update(businessAccepted=True),
    lambda x: x["facts"].update(storeReceipts=27),
    lambda x: x["facts"].update(liveLinks=1),
    lambda x: x["facts"].update(pending=1),
    lambda x: x["facts"].update(canary=1),
    lambda x: x["receipt"]["authority_data"]["request"].update(groupId="wrong"),
    lambda x: x["receipt"].update(idempotency_key="wrong"),
    lambda x: x["claims"][0]["record"].update(schemaVersion="wrong"),
])
def test_drift_freezes(mutate):
    value = closed_snapshot()
    mutate(value)
    assert audit.classify(value)["outcome"] == "FROZEN_INDEPENDENT_CLOSURE_AUDIT"


def test_no_receipt_but_partial_run_terminal_freezes():
    value = snapshot()
    value["runs"].update(running=11, closed=1)
    assert audit.classify(value)["outcome"] == "FROZEN_INDEPENDENT_CLOSURE_AUDIT"
