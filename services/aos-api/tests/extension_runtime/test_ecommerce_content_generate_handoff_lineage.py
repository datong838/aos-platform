from copy import deepcopy
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService,
    ReviewAdvanceHostService,
    _analysis_command_hash,
    _strict_content_generate_command,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
HEX_A = "a" * 64
HEX_B = "b" * 64


def ref(kind, identity, *, digest=HEX_A, receipt=False):
    value = {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": "sha256:" + digest,
    }
    if receipt:
        value["receiptId"] = identity
    return value


def authorities():
    handoff = ref("HandoffReceipt", "handoff-1", receipt=True)
    sources = [ref("ArtifactRevision", f"artifact-{index}") for index in range(4)]
    goal = {
        "objective": "围绕会员复购设计内容方案",
        "sourceHandoffRef": handoff,
        "growthPlanRef": ref("GrowthPlanRevision", "growth-plan-1"),
        "artifactRefs": sources,
        "workshopAssignment": {
            "roleKey": "campaign_planner",
            "colleagueName": "活动策划师",
            "status": "requested",
        },
    }
    task_payload = {
        "type": "ecommerce.workshop.business_task",
        "title": "制定会员复购内容方案",
        "description": "围绕会员复购设计内容方案",
        "priority": 50,
        "goal": goal,
        "selectionRef": None,
        "policyRevision": None,
    }
    task_hash = _analysis_command_hash(task_payload).removeprefix("sha256:")
    task_ref = ref("Task", "task-1", digest=task_hash)
    schema_ref = {
        "resourceType": "ContentCampaignBriefSchema",
        "resourceId": "schema://aos/ecommerce/content-campaign-brief/v1",
        "revision": "1",
        "authority": "aos://ecommerce-workshop/content-campaign",
    }
    spec = {
        "sourceHandoffRef": handoff,
        "taskRef": task_ref,
        "growthPlanRef": goal["growthPlanRef"],
        "artifactRefs": sources,
        "objective": goal["objective"],
        "channels": ["微信小店"],
        "audience": "近九十天已购会员",
        "timeWindow": "九月第二周",
        "constraints": ["库存不足商品不得主推"],
        "externalPublicationRequested": False,
    }
    brief_hash = _analysis_command_hash(
        {"briefType": "content_campaign", "schemaRef": schema_ref, "spec": spec}
    ).removeprefix("sha256:")
    brief_ref = ref("TaskBriefRevision", "brief-1", digest=brief_hash)
    brief_request = {
        "taskId": "task-1",
        "briefType": "content_campaign",
        "schemaRef": schema_ref,
        "spec": spec,
    }
    authority_refs = {
        "handoff": handoff,
        "task": task_ref,
        "brief": brief_ref,
        "growth_plan": goal["growthPlanRef"],
        "agent_instance": ref("AgentInstanceRevision", "agent-1"),
        "responsibility_plan": ref("ResponsibilityPlanRevision", "responsibility-1"),
        "capability": ref("CapabilityRevision", "capability-1"),
        "model_route": ref("ModelRouteRevision", "route-1"),
        "budget": ref("BudgetRevision", "budget-1"),
        "pricing": ref("ModelPriceSnapshotRevision", "pricing-1"),
        "approval": ref("ActionApprovalEvent", "approval-1"),
        "capacity_reservation": ref("CapacityReservation", "capacity-1"),
    }
    review_body = {
        "requestHash": "sha256:" + HEX_B,
        "decision": "ACCEPT",
        "occurrenceRef": ref("AutomationOccurrence", "occurrence-1"),
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "runRef": ref("BusinessInvestigationRun", "run-1"),
        "analysisReceiptRef": ref("AnalysisRuntimeReceipt", "analysis-1"),
        "currentPlanRef": ref("PlanRevision", "plan-1"),
        "reviewIssueRef": ref("ReviewIssueRevision", "issue-1"),
        "evalReportRef": ref("EvalReportRevision", "eval-1"),
        "returnStage": None,
        "handoffRef": handoff,
        "taskRef": task_ref,
        "briefRef": brief_ref,
        "growthPlanRef": goal["growthPlanRef"],
        "artifactBindings": [
            {"family": family, "artifactRef": artifact}
            for family, artifact in zip(
                ("portrait", "diagnosis", "growth_plan", "evidence_summary"),
                sources,
                strict=True,
            )
        ],
        "cutoffAt": "2026-09-09T09:00:00+00:00",
        "decidedAt": "2026-09-09T09:01:00+00:00",
        "replayed": False,
        "sideEffects": {
            "externalEffectsAllowed": False,
            "providerInvocationCount": 0,
            "approvalCreatedCount": 0,
            "taskRunCreatedCount": 0,
            "externalPublicationCount": 0,
            "externalBusinessMutationCount": 0,
        },
    }
    review_ref = ref(
        "ReviewDecisionReceipt",
        "review-1",
        digest=_analysis_command_hash(review_body).removeprefix("sha256:"),
        receipt=True,
    )
    command_body = {
        "operation": "content.generate",
        "authorityRefs": authority_refs,
        "sourceArtifactRefs": sources,
        "factSourceRefs": [ref("DataFulfillmentReceipt", "fulfillment-1", receipt=True)],
        "currency": "CNY",
        "upperBoundFen": 1000,
        "maxInputTokens": 2000,
        "maxOutputTokens": 1000,
        "idempotencyKey": "content-generate-1",
    }
    command = deepcopy(command_body)
    command["requestHash"] = _analysis_command_hash(command_body)
    return {
        "review": {
            "request_hash": review_body["requestHash"],
            "response": {"receiptRef": review_ref, **review_body},
            "target_receipt_ref": review_ref,
        },
        "task": {
            **task_payload,
            "task_type": task_payload["type"],
            "selection_ref": None,
            "policy_revision": None,
            "request_hash": task_hash,
        },
        "head": {"task_id": "task-1", "current_revision": 1, "version": 1},
        "brief": {
            "task_id": "task-1",
            "brief_type": "content_campaign",
            "schema_ref": schema_ref,
            "spec": spec,
            "content_hash": brief_hash,
            "lifecycle": "draft",
            "created_by": "ecommerce-growth-review-host",
        },
        "receipt": {
            "request_hash": _analysis_command_hash(brief_request).removeprefix("sha256:"),
            "result_ref": {**brief_ref, "contentHash": brief_hash},
            "created_by": "ecommerce-growth-review-host",
        },
        "command": command,
    }


class Transaction:
    def __init__(self, values):
        self.values = values
        self.queries = []

    def execute(self, query, _params):
        self.queries.append(query)
        key = (
            "review"
            if "runtime_command_receipt" in query
            else "task"
            if "public.aip_task\n" in query
            else "head"
            if "task_brief_head" in query
            else "brief"
            if "task_brief_revision" in query
            else "receipt"
        )
        value = self.values[key]

        class Result:
            def fetchone(self):
                return value

            def fetchall(self):
                return [value]

        return Result()


def test_content_generate_accepts_review_handoff_and_current_task_brief(monkeypatch):
    values = authorities()
    monkeypatch.setattr(
        ReviewAdvanceHostService, "_revalidate_growth_plan", staticmethod(lambda **_: None)
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_agent_capability_authority",
        staticmethod(lambda *_: None),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_route_budget_approval_authority",
        staticmethod(lambda *_args, **_kwargs: (object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_resolution_capacity_authority",
        staticmethod(lambda *_args, **_kwargs: None),
    )
    transaction = Transaction(values)
    result = ContentGenerateHostService().revalidate(
        transaction=transaction,
        scope=SCOPE,
        dispatch=SimpleNamespace(operation_id="ecommerce_growth_content_generate"),
        command=values["command"],
    )
    assert result["key"] == "content-generate-1"
    assert result["reviewReceiptRef"]["resourceType"] == "ReviewDecisionReceipt"
    assert sum("FOR SHARE" in query for query in transaction.queries) == 2


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("upperBoundFen",), True),
        (("authorityRefs", "brief", "revision"), True),
        (("authorityRefs", "brief", "unexpected"), "x"),
    ],
)
def test_content_generate_strict_command_rejects_drift(path, value):
    command = deepcopy(authorities()["command"])
    target = command
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    body = {key: item for key, item in command.items() if key != "requestHash"}
    command["requestHash"] = _analysis_command_hash(body)
    with pytest.raises(ValueError):
        _strict_content_generate_command(command)


@pytest.mark.parametrize(
    "drift",
    [
        "review_decision",
        "review_hash",
        "review_ref_bool",
        "handoff",
        "artifact",
        "task",
        "brief_head",
        "brief_ref_hash",
        "brief_receipt_bool",
        "brief_spec",
    ],
)
def test_content_generate_rejects_review_task_brief_drift(monkeypatch, drift):
    values = authorities()
    monkeypatch.setattr(
        ReviewAdvanceHostService, "_revalidate_growth_plan", staticmethod(lambda **_: None)
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_agent_capability_authority",
        staticmethod(lambda *_: None),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_route_budget_approval_authority",
        staticmethod(lambda *_args, **_kwargs: (object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_resolution_capacity_authority",
        staticmethod(lambda *_args, **_kwargs: None),
    )
    if drift == "review_decision":
        values["review"]["response"]["decision"] = "RETURN"
    elif drift == "review_hash":
        values["review"]["response"]["receiptRef"]["contentHash"] = "sha256:" + HEX_B
    elif drift == "review_ref_bool":
        values["review"]["target_receipt_ref"]["revision"] = True
    elif drift == "handoff":
        values["command"]["authorityRefs"]["handoff"]["receiptId"] = "handoff-2"
        body = {
            key: value for key, value in values["command"].items() if key != "requestHash"
        }
        values["command"]["requestHash"] = _analysis_command_hash(body)
    elif drift == "artifact":
        values["command"]["sourceArtifactRefs"][0]["resourceId"] = "artifact-x"
        body = {
            key: value for key, value in values["command"].items() if key != "requestHash"
        }
        values["command"]["requestHash"] = _analysis_command_hash(body)
    elif drift == "task":
        values["task"]["goal"]["objective"] = "另一目标"
    elif drift == "brief_head":
        values["head"]["current_revision"] = 2
    elif drift == "brief_ref_hash":
        values["command"]["authorityRefs"]["brief"]["contentHash"] = "sha256:" + HEX_B
        body = {
            key: value for key, value in values["command"].items() if key != "requestHash"
        }
        values["command"]["requestHash"] = _analysis_command_hash(body)
    elif drift == "brief_receipt_bool":
        values["receipt"]["result_ref"]["revision"] = True
    elif drift == "brief_spec":
        values["brief"]["spec"]["externalPublicationRequested"] = True
    with pytest.raises(ValueError):
        ContentGenerateHostService().revalidate(
            transaction=Transaction(values),
            scope=SCOPE,
            dispatch=SimpleNamespace(operation_id="ecommerce_growth_content_generate"),
            command=values["command"],
        )
