from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, 3, 0, tzinfo=UTC)
HASH = "sha256:" + "a" * 64
OCCURRENCE_ID = UUID("11111111-1111-4111-8111-111111111111")
CUTOFF = datetime(2026, 9, 8, 1, tzinfo=UTC)
FAMILIES = ("portrait", "diagnosis", "growth_plan", "evidence_summary")


def ref(kind, identity, *, receipt=None, revision=1):
    value = {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": HASH,
    }
    if receipt is not None:
        value["receiptId"] = receipt
    return value


def command_hash(payload):
    import hashlib
    import json

    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def artifacts():
    return [
        {"family": family, "artifactRef": ref("ArtifactRevision", f"artifact-{family}")}
        for family in FAMILIES
    ]


def accept_command(**changes):
    plan = ref("GrowthPlanRevision", "growth-plan-1")
    bindings = artifacts()
    body = {
        "operation": "review_handoff.advance",
        "occurrenceRef": ref("AutomationOccurrence", str(OCCURRENCE_ID)),
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "runRef": ref("BusinessInvestigationRun", "run-1"),
        "analysisReceiptRef": ref("AnalysisRuntimeReceipt", "analysis-receipt-1"),
        "currentPlanRef": ref("PlanRevision", "plan-1"),
        "growthPlanRef": plan,
        "reviewIssueRef": ref("ReviewIssueRevision", "issue-1"),
        "evalReportRef": ref("EvalReportRevision", "eval-1"),
        "artifactBindings": bindings,
        "decision": "ACCEPT",
        "returnStage": None,
        "targetModuleId": "ecommerce.content-campaign",
        "sourceSlotId": "analyst.solution",
        "targetSlotId": "content.plan",
        "markings": ["internal"],
        "expiresAt": (CUTOFF + timedelta(days=1)).isoformat(),
        "taskSpec": {
            "taskType": "ecommerce.workshop.business_task",
            "briefType": "content_campaign",
            "title": "制定七夕会员复购活动方案",
            "objective": "围绕栖月汇微商城会员设计七夕复购活动",
            "channels": ["微信小店", "私域社群"],
            "audience": "近九十天已购会员",
            "timeWindow": "七夕活动前七天至活动后三天",
            "constraints": ["毛利率不低于百分之十五", "库存不足商品不得主推"],
            "growthPlanRef": plan,
            "artifactRefs": [item["artifactRef"] for item in bindings],
        },
        "cutoffAt": CUTOFF.isoformat(),
        "idempotencyKey": "review-1",
    }
    body.update(changes)
    if "requestHash" not in body:
        body["requestHash"] = command_hash({key: value for key, value in body.items() if key != "requestHash"})
    return body


def wired_host(monkeypatch, *, occurrence_hash=HASH):
    from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService

    journal = {}
    occurrence = {
        "occurrenceId": str(OCCURRENCE_ID),
        "policyId": "policy-1",
        "policyRevision": 1,
        "policyHash": HASH,
        "operationId": "ecommerce_growth_review_advance",
        "installationId": "11111111-1111-4111-8111-111111111111",
        "generation": "22222222-2222-4222-8222-222222222222",
        "executionEpoch": 9,
        "scheduledAt": CUTOFF.isoformat(),
        "localSlot": "2026-09-08T09:00:00+08:00",
        "triggerSource": "schedule",
        "sourceEventId": None,
        "status": "claimed",
        "deadline": CUTOFF.isoformat(),
    }
    case = SimpleNamespace(case_id="case-1", revision=1, content_hash=HASH)

    class Cases:
        def get(self, _scope, case_id):
            if case_id != "case-1":
                raise ValueError("case missing")
            return case

    class Receipts:
        def put(self, key, payload, **_kwargs):
            existing = journal.get(key)
            if existing is not None:
                if existing != payload:
                    raise ValueError("review Receipt idempotency content drift")
                return existing
            journal[key] = payload
            return payload

        def read(self, key):
            return journal.get(key)

    host = ReviewAdvanceHostService()
    monkeypatch.setattr(
        host,
        "_components",
        lambda *_: (
            lambda occurrence_id: {**occurrence, "occurrenceId": str(occurrence_id)},
            Cases(),
            Receipts(),
        ),
    )
    monkeypatch.setattr(host, "_occurrence_content_hash", lambda _payload: occurrence_hash)
    monkeypatch.setattr(
        host,
        "_review_lineage",
        lambda **_: {
            "handoffRef": ref("HandoffReceipt", "handoff-1"),
            "taskRef": ref("Task", "task-1"),
            "briefRef": ref("TaskBriefRevision", "brief-1"),
        },
    )
    return host, journal


def test_review_advance_host_is_the_runtime_registry_service():
    from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService

    assert ReviewAdvanceHostService.executor_identity == "ecommerce-growth-review-host"


@pytest.mark.parametrize("mutation", ["extra", "return", "hash_drift", "wrong_family", "tenant"])
def test_accept_command_rejects_unknown_mode_and_drift(mutation):
    from aos_api.ecommerce_growth_runtime_adapters import _strict_review_accept_command

    value = accept_command()
    if mutation == "extra":
        value["tenantOverride"] = True
    if mutation == "return":
        value["decision"] = "RETURN"
        value["returnStage"] = "diagnosis"
        value["targetModuleId"] = None
        value["sourceSlotId"] = None
        value["targetSlotId"] = None
        value["markings"] = []
        value["expiresAt"] = None
        value["taskSpec"] = None
        value["requestHash"] = command_hash({k: v for k, v in value.items() if k != "requestHash"})
    if mutation == "hash_drift":
        value["requestHash"] = "sha256:" + "b" * 64
    if mutation == "wrong_family":
        value["artifactBindings"] = artifacts()
        value["artifactBindings"][0]["family"] = "other"
        value["requestHash"] = command_hash({k: v for k, v in value.items() if k != "requestHash"})
    if mutation == "tenant":
        value["tenant"] = {"orgId": "org-org", "projectId": "dev-project"}
        value["requestHash"] = command_hash({k: v for k, v in value.items() if k != "requestHash"})
    with pytest.raises(ValueError):
        _strict_review_accept_command(value)


def test_accept_returns_internal_handoff_receipt_and_rereads(monkeypatch):
    host, journal = wired_host(monkeypatch)
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_review_advance")
    command = accept_command()
    host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command)
    response = host.execute(
        transaction=transaction,
        scope=SCOPE,
        dispatch_ref=dispatch,
        command=command,
        checked_at=NOW,
        occurred_at=NOW,
    )
    assert response["decision"] == "ACCEPT"
    assert response["receiptRef"]["resourceType"] == "ReviewDecisionReceipt"
    assert response["handoffRef"]["resourceId"] == "handoff-1"
    assert response["taskRef"]["resourceType"] == "Task"
    assert response["briefRef"]["resourceType"] == "TaskBriefRevision"
    assert response["sideEffects"]["externalEffectsAllowed"] is False
    assert response["sideEffects"]["providerInvocationCount"] == 0
    assert journal[command["idempotencyKey"]] == response
    assert (
        host.verify_receipt(
            transaction=transaction,
            scope=SCOPE,
            dispatch=dispatch,
            command=command,
            receipt=response,
        )
        == response
    )


def test_return_fail_closed_until_wired(monkeypatch):
    host, _journal = wired_host(monkeypatch)
    command = accept_command(
        decision="RETURN",
        returnStage="diagnosis",
        targetModuleId=None,
        sourceSlotId=None,
        targetSlotId=None,
        markings=[],
        expiresAt=None,
        taskSpec=None,
    )
    with pytest.raises(ValueError, match="not wired"):
        host.revalidate(
            transaction=HostTransaction(SimpleNamespace()),
            scope=SCOPE,
            dispatch=SimpleNamespace(operation_id="ecommerce_growth_review_advance"),
            command=command,
        )
