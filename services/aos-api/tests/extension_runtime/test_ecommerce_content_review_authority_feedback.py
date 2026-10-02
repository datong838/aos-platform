from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import aos_api.ecommerce_growth_runtime_adapters as adapters
from aos_api.aip_production_contracts import BriefLifecycle, ContractReadiness, Coverage
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash as production_canonical_hash
from aos_api.ecommerce_business_investigation_review_command import review_issue_exact_ref
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentReviewHostService,
    _analysis_command_hash,
    _strict_content_review_command,
)
from aos_api.ecommerce_growth_runtime_store import RuntimeReceiptRecord
from aos_api.db import connect, connect_serializable
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 9, 9, 8, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def ref(kind: str, identity: str, fill: str = "a", revision: int = 1):
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": "sha256:" + fill * 64,
    }


def command(decision: str = "ACCEPT", key: str = "content-review-1"):
    value = {
        "operation": "content.review",
        "artifactRef": ref("ArtifactRevision", "content-1", "1"),
        "taskRef": ref("Task", "task-1", "2"),
        "briefRef": ref("TaskBriefRevision", "brief-1", "3"),
        "growthPlanRef": ref("GrowthPlanRevision", "plan-1", "4"),
        "sourceArtifactRefs": [
            ref("ArtifactRevision", f"source-{index}", str(index + 4))
            for index in range(1, 5)
        ],
        "reviewIssueRef": ref("ReviewIssueRevision", "issue-1", "9"),
        "reviewerAuthorityRef": ref(
            "ReviewerAuthorityRevision", "responsibility-1/content.review", "b"
        ),
        "artifactContentHash": "sha256:" + "1" * 64,
        "decision": decision,
        "returnStage": None if decision == "ACCEPT" else "content_generation",
        "idempotencyKey": key,
    }
    value["requestHash"] = _analysis_command_hash(value)
    return value


def artifact(item):
    return {
        "artifactRef": item["artifactRef"],
        "taskRef": item["taskRef"],
        "briefRef": item["briefRef"],
        "growthPlanRef": item["growthPlanRef"],
        "sourceArtifactRefs": item["sourceArtifactRefs"],
        "productNames": ["栖月汇玫瑰精粹面霜"],
        "channels": ["微信小店"],
        "factSourceRefs": [ref("EvidenceBundleRevision", "evidence-1", "c")],
        "body": "七夕会员专享内容已核对商品信息与服务承诺。",
        "constraintChecks": ["库存与价格信息已核对"],
    }


def test_content_review_keeps_handoff_task_creation_ref_after_task_progresses():
    item = command()
    task_payload = {
        "type": "ecommerce.workshop.business_task",
        "title": "七夕会员复购内容策划",
        "description": "根据已批准方案制作内容",
        "priority": 50,
        "goal": {"sourceHandoffRef": ref("HandoffReceipt", "handoff-1")},
        "selectionRef": None,
        "policyRevision": None,
    }
    task_hash = _analysis_command_hash(task_payload).removeprefix("sha256:")
    item["taskRef"] = ref("Task", "task-1") | {"contentHash": "sha256:" + task_hash}
    brief_spec = {
        "taskRef": item["taskRef"],
        "growthPlanRef": item["growthPlanRef"],
        "artifactRefs": item["sourceArtifactRefs"],
        "externalPublicationRequested": False,
    }
    brief_payload = {
        "briefType": "content_campaign",
        "schemaRef": ref("ContentCampaignBriefSchema", "schema-1"),
        "spec": brief_spec,
    }
    brief_hash = _analysis_command_hash(brief_payload).removeprefix("sha256:")
    item["briefRef"] = ref("TaskBriefRevision", "brief-1") | {"contentHash": "sha256:" + brief_hash}
    rows = (
        {"task_id": "task-1", "task_type": task_payload["type"],
         "title": task_payload["title"], "description": task_payload["description"],
         "priority": 50, "goal": task_payload["goal"], "selection_ref": None,
         "policy_revision": None, "request_hash": task_hash, "version": 4},
        {"task_id": "task-1", "current_revision": 1, "version": 1},
        {"task_id": "task-1", "brief_type": "content_campaign",
         "schema_ref": brief_payload["schemaRef"], "spec": brief_spec,
         "content_hash": brief_hash, "lifecycle": "draft"},
    )

    class Tx:
        def __init__(self, values):
            self.values = values
            self.index = 0

        def execute(self, _query, _params=()):
            row = self.values[self.index]
            self.index += 1
            return Result(row)

    assert ContentReviewHostService._task_brief_authority(
        HostTransaction(Tx(rows)), SCOPE, item
    ) == task_payload["title"]
    drifted = deepcopy(item)
    drifted["taskRef"]["contentHash"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="Task exact authority drifted"):
        ContentReviewHostService._task_brief_authority(
            HostTransaction(Tx(rows)), SCOPE, drifted
        )


class Result:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class RuntimeTransaction:
    def __init__(self, receipts):
        self.receipts = receipts

    def execute(self, query, params=()):
        if "FROM public.ecommerce_growth_runtime_command_receipt" in query:
            value = self.receipts.get(params[-1])
            return Result(None if value is None else {"request_hash": value[0], "response": value[1]})
        if "FROM public.extension_runtime_binding" in query:
            return Result({"revision": 1})
        raise AssertionError(query)


class RuntimeStore:
    receipts = {}

    def __init__(self, _transaction, _scope):
        pass

    def put(self, *, idempotency_key, request_hash, response, **_):
        prior = self.receipts.get(idempotency_key)
        if prior is not None and prior[0] != request_hash:
            raise ValueError("runtime drift")
        self.receipts.setdefault(idempotency_key, (request_hash, deepcopy(response)))
        return RuntimeReceiptRecord(response=deepcopy(self.receipts[idempotency_key][1]), replayed=prior is not None)

    def read(self, *, idempotency_key, **_):
        value = self.receipts.get(idempotency_key)
        return None if value is None else deepcopy(value[1])


class FeedbackPort:
    plans = {}
    calls = 0

    def __init__(self, *_args, **_kwargs):
        pass

    def enqueue(self, *, review_receipt, feedback_plan):
        assert review_receipt["receiptRef"] == feedback_plan["reviewReceiptRef"]
        self.__class__.calls += 1
        replayed = feedback_plan["commandId"] in self.plans
        self.plans.setdefault(feedback_plan["commandId"], deepcopy(feedback_plan))
        return {"replayed": replayed}

    def read(self, *, command_id):
        plan = self.plans.get(command_id)
        if plan is None:
            return None
        return {
            **{key: plan[key] for key in (
                "commandId", "requestHash", "decision", "reviewReceiptRef",
                "artifactRef", "taskRef", "briefRef"
            )},
            "segments": [
                {
                    "sequence": index,
                    "payload": deepcopy(payload),
                    "state": "pending",
                    "attempt": 0,
                }
                for index, payload in enumerate(plan["segments"], start=1)
            ],
            "checkpoint": {"completedSequence": 0, "version": 1},
        }


def dispatch():
    return SimpleNamespace(
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        operation_id="ecommerce_growth_content_review",
        handler_kind="extension",
        dispatch_revision=5,
        installation_id="11111111-1111-4111-8111-111111111111",
        generation="22222222-2222-4222-8222-222222222222",
        execution_epoch=3,
        cutover_group_id="33333333-3333-4333-8333-333333333333",
        cutover_group_revision=11,
        runtime_revision=1,
        checked_at=NOW,
    )


@pytest.fixture
def isolated(monkeypatch):
    RuntimeStore.receipts = {}
    FeedbackPort.plans = {}
    FeedbackPort.calls = 0
    monkeypatch.setattr(adapters, "BoundEcommerceGrowthRuntimeStore", RuntimeStore)
    monkeypatch.setattr(adapters, "BoundEcommerceGrowthFeedbackPort", FeedbackPort)
    item = command()
    monkeypatch.setattr(ContentReviewHostService, "_artifact_authority", staticmethod(lambda *_: artifact(item)))
    monkeypatch.setattr(ContentReviewHostService, "_task_brief_authority", staticmethod(lambda *_: "七夕会员复购内容策划"))
    monkeypatch.setattr(ContentReviewHostService, "_issue_authority", staticmethod(lambda *_: None))
    monkeypatch.setattr(ContentReviewHostService, "_reviewer_authority", staticmethod(lambda *_: None))
    return item


@pytest.mark.parametrize("decision,count", (("ACCEPT", 3), ("RETURN", 1)))
def test_receipt_first_review_and_feedback_are_exact_and_replayable(isolated, decision, count):
    item = command(decision)
    service = ContentReviewHostService()
    service._artifact_authority = staticmethod(lambda *_: artifact(item))
    transaction = HostTransaction(RuntimeTransaction(RuntimeStore.receipts))
    service.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch(), command=item)
    first = service.execute(
        transaction=transaction, scope=SCOPE, dispatch_ref=dispatch(), command=item,
        checked_at=NOW, occurred_at=None,
    )
    assert first["decision"] == decision
    assert first["replayed"] is False
    assert set(first["sideEffects"].values()) == {0}
    plan = next(iter(FeedbackPort.plans.values()))
    assert len(plan["segments"]) == count
    assert set(plan["sideEffects"].values()) == {0}
    assert service.verify_receipt(
        transaction=transaction, scope=SCOPE, dispatch=dispatch(), command=item, receipt=first
    ) == first
    replay = service.execute(
        transaction=transaction, scope=SCOPE, dispatch_ref=dispatch(), command=item,
        checked_at=NOW, occurred_at=None,
    )
    assert replay == first and FeedbackPort.calls == 2


def test_content_review_command_rejects_hash_source_and_decision_drift():
    item = command()
    assert _strict_content_review_command(item)["key"] == "content-review-1"
    for changed in (
        {**item, "requestHash": "sha256:" + "f" * 64},
        {**item, "sourceArtifactRefs": item["sourceArtifactRefs"][:3]},
        {**item, "decision": "REQUEST_MORE"},
        {**item, "returnStage": "content_generation"},
    ):
        with pytest.raises(ValueError):
            _strict_content_review_command(changed)
    boolean_alias = {
        **item,
        "sourceArtifactRefs": [
            {**item["sourceArtifactRefs"][0], "revision": True},
            *item["sourceArtifactRefs"][1:],
        ],
    }
    boolean_alias["requestHash"] = _analysis_command_hash(
        {name: value for name, value in boolean_alias.items() if name != "requestHash"}
    )
    with pytest.raises(ValueError):
        _strict_content_review_command(boolean_alias)


def test_accepted_stage_review_execution_stays_closed_before_database_effects(monkeypatch):
    item = command()
    item["sourceKind"] = "accepted-stage-v1"
    item["sourceArtifactRefs"] = [ref("Artifact", "original-stage-artifact")]
    item["requestHash"] = _analysis_command_hash(
        {name: value for name, value in item.items() if name != "requestHash"}
    )
    assert _strict_content_review_command(item)["sourceRefs"][0].resource_type == "Artifact"

    class NoDatabaseEffects:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("accepted stage review reached the database")

    class ReadCurrentTimeOnly:
        def execute(self, statement, *_args, **_kwargs):
            assert statement == "SELECT clock_timestamp() AS checked_at"
            return Result({"checked_at": NOW})

    observed = []
    monkeypatch.setattr(
        ContentReviewHostService, "_artifact_authority",
        staticmethod(lambda *_args: artifact(item)),
    )
    monkeypatch.setattr(
        ContentReviewHostService, "_accepted_stage_task_brief_authority",
        staticmethod(lambda *_args, **kwargs: observed.append(kwargs["checked_at"])),
    )
    service = ContentReviewHostService()
    with pytest.raises(ValueError, match="dispatch operation drifted"):
        service.revalidate(transaction=NoDatabaseEffects(), scope=SCOPE,
                           dispatch=SimpleNamespace(operation_id="ecommerce_growth_content_generate"),
                           command=item)
    with pytest.raises(ValueError, match="Host is not wired"):
        service.revalidate(transaction=ReadCurrentTimeOnly(), scope=SCOPE,
                           dispatch=SimpleNamespace(operation_id="ecommerce_growth_content_review"),
                           command=item)
    assert observed == [NOW]
    with pytest.raises(ValueError, match="Host is not wired"):
        service.execute(transaction=NoDatabaseEffects(), scope=SCOPE, dispatch_ref=None,
                        command=item, checked_at=NOW, occurred_at=NOW)
    with pytest.raises(ValueError, match="Host is not wired"):
        service.verify_receipt(transaction=NoDatabaseEffects(), scope=SCOPE,
                               dispatch=None, command=item, receipt={})


def test_reviewer_authority_is_one_current_ready_content_review_slot(monkeypatch):
    item = command()
    class Dump:
        def __init__(self, value):
            self.value = value

        def model_dump(self, **_):
            return deepcopy(self.value)

    assignee = {"kind": "human_principal", "resourceId": "reviewer-1", "version": 1}
    slot_payload = {
        "slotId": "content.review",
        "responsibilityType": "independent_review",
        "requiredCapabilityIds": ["content.review"],
        "inputSchemaRef": {"resourceType": "Schema", "resourceId": "review-in", "revision": "1"},
        "outputSchemaRef": {"resourceType": "Schema", "resourceId": "review-out", "revision": "1"},
        "gateRefs": [],
        "returnStage": "content_generation",
        "assignee": assignee,
        "assigneeResolutionReceiptId": "resolution-1",
    }
    slot = SimpleNamespace(
        slot_id="content.review",
        responsibility_type="independent_review",
        required_capability_ids=["content.review"],
        assignee=Dump(assignee),
        assignee_resolution_receipt_id="resolution-1",
        model_dump=lambda **_: deepcopy(slot_payload),
    )
    template_ref = ref("ResponsibilityTemplateRevision", "template-1", "c")
    raw_plan = {
        "profile": "legacy",
        "templateRef": template_ref,
        "slots": [slot_payload],
        "mergeDecisions": [],
        "profileRecommendationRef": None,
        "profileConfirmationId": None,
        "mergePolicyRef": None,
        "mergeDecisionReceiptIds": [],
    }
    plan_hash = adapters.production_contract_canonical_hash(raw_plan)
    plan = SimpleNamespace(
        plan_id="responsibility-1", revision=1, version=1, content_hash=plan_hash,
        profile="legacy", template_ref=Dump(template_ref), merge_decisions=[],
        profile_recommendation_ref=None, profile_confirmation_id=None,
        merge_policy_ref=None, merge_decision_receipt_ids=[],
        lifecycle=BriefLifecycle.FROZEN, readiness=ContractReadiness.READY,
        coverage=Coverage.COMPLETE, blockers=[], uncovered_slots=[], slots=[slot],
    )
    projection = {
        "responsibilityPlanRef": {
            "resourceType": "ResponsibilityPlanRevision",
            "resourceId": "responsibility-1",
            "revision": 1,
            "contentHash": "sha256:" + plan_hash,
        },
        "slotId": "content.review",
        "responsibilityType": "independent_review",
        "requiredCapabilityIds": ["content.review"],
        "assignee": {"kind": "human_principal", "resourceId": "reviewer-1", "version": 1},
        "assigneeResolutionReceiptId": "resolution-1",
    }
    item["reviewerAuthorityRef"]["contentHash"] = adapters.budget_canonical_hash(projection, prefixed=True)

    class Tx:
        def __init__(self, decision_actor="reviewer-1"):
            self.decision_actor = decision_actor

        def execute(self, query, *_):
            if "aip_review_issue_event" in query:
                return Result(one={"actor": self.decision_actor})
            return Result(many=[{
                "plan_id": "responsibility-1", "current_revision": 1, "version": 1,
                "profile": "legacy", "template_ref": template_ref, "slots": [slot_payload],
                "merge_decisions": [], "profile_recommendation_ref": None,
                "profile_confirmation_id": None, "merge_policy_ref": None,
                "merge_decision_receipt_ids": [], "content_hash": plan_hash,
                "lifecycle": "frozen",
            }])

    monkeypatch.setattr(
        adapters.AipProductionContractStore,
        "get_responsibility_plan",
        lambda *_args, **_kwargs: plan,
    )
    ContentReviewHostService._reviewer_authority(HostTransaction(Tx()), SCOPE, item)
    with pytest.raises(ValueError, match="human decision actor"):
        ContentReviewHostService._reviewer_authority(
            HostTransaction(Tx("another-reviewer")), SCOPE, item
        )
    with pytest.raises(ValueError, match="human decision actor"):
        ContentReviewHostService._reviewer_authority(
            HostTransaction(Tx(None)), SCOPE, item
        )
    item["reviewerAuthorityRef"]["contentHash"] = "sha256:" + "e" * 64
    with pytest.raises(ValueError, match="one current responsibility slot"):
        ContentReviewHostService._reviewer_authority(HostTransaction(Tx()), SCOPE, item)


def test_missing_feedback_or_receipt_tamper_fails_verification(isolated):
    item = isolated
    service = ContentReviewHostService()
    transaction = HostTransaction(RuntimeTransaction(RuntimeStore.receipts))
    receipt = service.execute(
        transaction=transaction, scope=SCOPE, dispatch_ref=dispatch(), command=item,
        checked_at=NOW, occurred_at=None,
    )
    FeedbackPort.plans.clear()
    assert service.verify_receipt(
        transaction=transaction, scope=SCOPE, dispatch=dispatch(), command=item, receipt=receipt
    ) == {}
    broken = deepcopy(receipt)
    broken["sideEffects"]["externalPublicationCount"] = 1
    assert service.verify_receipt(
        transaction=transaction, scope=SCOPE, dispatch=dispatch(), command=item, receipt=broken
    ) == {}
    drifted_command = {**item, "decision": "RETURN", "returnStage": "content_generation"}
    drifted_command["requestHash"] = _analysis_command_hash(
        {name: value for name, value in drifted_command.items() if name != "requestHash"}
    )
    assert service.verify_receipt(
        transaction=transaction, scope=SCOPE, dispatch=dispatch(),
        command=drifted_command, receipt=receipt,
    ) == {}


def test_feedback_readback_rejects_boolean_sequence_alias():
    item = command()
    receipt = {
        "receiptRef": ref("ContentReviewReceipt", "review-1"),
        "decision": "RETURN",
        "artifactRef": item["artifactRef"],
        "taskRef": item["taskRef"],
        "briefRef": item["briefRef"],
    }
    plan = ContentReviewHostService._feedback_plan(
        receipt, artifact(item), "七夕会员复购内容策划"
    )
    readback = {
        **{key: plan[key] for key in (
            "commandId", "requestHash", "decision", "reviewReceiptRef",
            "artifactRef", "taskRef", "briefRef"
        )},
        "segments": [{"sequence": True, "payload": deepcopy(plan["segments"][0])}],
    }
    assert ContentReviewHostService._feedback_matches(readback, plan) is False
    readback["segments"][0]["sequence"] = 1
    readback["segments"][0]["payload"]["sequence"] = True
    assert ContentReviewHostService._feedback_matches(readback, plan) is False


def test_artifact_owner_rejects_boolean_exact_ref_alias():
    item = command()
    payload = artifact(item)
    content_hash = adapters.budget_canonical_hash(
        {name: value for name, value in payload.items() if name != "artifactRef"}
    )
    item["artifactRef"]["contentHash"] = "sha256:" + content_hash
    item["artifactContentHash"] = item["artifactRef"]["contentHash"]
    payload["artifactRef"] = deepcopy(item["artifactRef"])
    source_rows = [
        {
            "artifact_id": value["resourceId"],
            "content_hash": value["contentHash"].removeprefix("sha256:"),
            "family_revision": value["revision"],
        }
        for value in item["sourceArtifactRefs"]
    ]

    class Tx:
        def __init__(self, stored):
            self.stored = stored

        def execute(self, query, _params=()):
            if "artifact_id=%s" in query:
                return Result({
                    "artifact_id": "content-1", "run_id": "run-1",
                    "artifact_type": "content_campaign", "content_hash": content_hash,
                    "metadata": {"ecommerceGrowthContentArtifact": self.stored},
                    "family_revision": 1,
                })
            return Result(many=source_rows)

    assert ContentReviewHostService._artifact_authority(
        HostTransaction(Tx(payload)), SCOPE, item
    )["body"] == payload["body"]
    polluted = deepcopy(payload)
    polluted["artifactRef"]["revision"] = True
    with pytest.raises(ValueError, match="exact projection drifted"):
        ContentReviewHostService._artifact_authority(
            HostTransaction(Tx(polluted)), SCOPE, item
        )


def test_review_issue_owner_requires_exact_human_resolution_event(monkeypatch):
    monkeypatch.setattr(ContentReviewHostService, "_issue_eval_authority", staticmethod(lambda *_: None))
    item = command()
    row = {
        "issue_id": "issue-1",
        "rule_ref": {
            "resourceType": "ReviewRuleRevision",
            "resourceId": "rule-1",
            "revision": 1,
            "contentHash": "a" * 64,
        },
        "severity": "error",
        "artifact_id": "content-1",
        "artifact_hash": item["artifactRef"]["contentHash"].removeprefix("sha256:"),
        "eval_report_id": "eval-1",
        "eval_report_revision": 1,
        "eval_report_hash": "c" * 64,
        "location": {"section": "正文"},
        "evidence_refs": [],
        "suggested_fix": "调整内容表达",
        "return_stage": "content_generation",
        "status": "open",
        "version": 1,
        "created_by": "reviewer",
        "created_at": NOW,
        "updated_by": "reviewer",
        "updated_at": NOW,
    }
    issue = AipProductionContractStore()._review_issue(SCOPE, row)
    item["reviewIssueRef"] = review_issue_exact_ref(issue).model_dump(
        mode="json", by_alias=True, exclude_none=True)

    class Tx:
        def __init__(self, value, event=None, decision=None):
            self.value = value
            self.event = event
            self.decision = decision

        def execute(self, query, *_):
            if "aip_review_issue_event" in query:
                return Result(self.event)
            if "aip_return_decision" in query:
                return Result(self.decision)
            return Result(self.value)

    with pytest.raises(ValueError, match="exact lineage drifted"):
        ContentReviewHostService._issue_authority(HostTransaction(Tx(row)), SCOPE, item)
    resolved = {**row, "status": "resolved", "version": 2}
    resolved_issue = AipProductionContractStore()._review_issue(SCOPE, resolved)
    item["reviewIssueRef"] = review_issue_exact_ref(resolved_issue).model_dump(
        mode="json", by_alias=True, exclude_none=True)
    payload = {"expectedVersion": 1, "reason": "已核对商品事实与禁用表达", "resolutionRefs": [
        {"resourceType": "Artifact", "resourceId": item["artifactRef"]["resourceId"],
         "revision": 1, "contentHash": item["artifactRef"]["contentHash"].removeprefix("sha256:")},
    ]}
    event = {"event_type": "resolved", "issue_version": 2, "actor": "reviewer",
             "payload": payload, "payload_hash": production_canonical_hash(payload)}
    ContentReviewHostService._issue_authority(HostTransaction(Tx(resolved, event)), SCOPE, item)
    missing_event = {**event, "payload_hash": "0" * 64}
    with pytest.raises(ValueError, match="human decision"):
        ContentReviewHostService._issue_authority(HostTransaction(Tx(resolved, missing_event)), SCOPE, item)
    no_artifact = {**payload, "resolutionRefs": []}
    with pytest.raises(ValueError, match="exact Artifact resolution"):
        ContentReviewHostService._issue_authority(
            HostTransaction(Tx(resolved, {**event, "payload": no_artifact,
                                          "payload_hash": production_canonical_hash(no_artifact)})),
            SCOPE, item)
    with pytest.raises(ValueError, match="human decision"):
        ContentReviewHostService._issue_authority(
            HostTransaction(Tx(resolved, {**event, "actor": "unrelated-reviewer"})),
            SCOPE, item)
    polluted = deepcopy(row)
    polluted["rule_ref"]["revision"] = True
    with pytest.raises(ValueError, match="exact lineage drifted"):
        ContentReviewHostService._issue_authority(
            HostTransaction(Tx(polluted, event)), SCOPE, item
        )

    returned = {**row, "status": "returned", "version": 2,
                "return_stage": "content_generate"}
    returned_issue = AipProductionContractStore()._review_issue(SCOPE, returned)
    return_item = {**item, "decision": "RETURN", "returnStage": "content_generation",
                   "reviewIssueRef": review_issue_exact_ref(returned_issue).model_dump(
                       mode="json", by_alias=True, exclude_none=True)}
    return_payload = {"expectedVersion": 1, "runId": "run-1",
                      "targetStage": "content_generate", "reason": "事实表述需修改",
                      "attemptIdempotencyKey": "return-1", "decisionHash": "d" * 64,
                      "stepRunId": "step-2"}
    return_event = {"event_type": "returned", "issue_version": 2,
                    "actor": "reviewer", "payload": return_payload,
                    "payload_hash": production_canonical_hash(return_payload)}
    with pytest.raises(ValueError, match="ReturnDecision"):
        ContentReviewHostService._issue_authority(
            HostTransaction(Tx(returned, return_event)), SCOPE, return_item)
    return_decision = {"issue_version": 1, "run_id": "run-1",
                       "step_key": "content_generate", "step_run_id": "step-2",
                       "decision_hash": "d" * 64, "actor": "reviewer"}
    ContentReviewHostService._issue_authority(
        HostTransaction(Tx(returned, return_event, return_decision)), SCOPE, return_item)
    wrong_decision = {**return_decision, "step_key": "content_generation"}
    with pytest.raises(ValueError, match="ReturnDecision"):
        ContentReviewHostService._issue_authority(
            HostTransaction(Tx(returned, return_event, wrong_decision)), SCOPE, return_item)


def test_content_review_rechecks_exact_issue_eval_subject_and_attempt():
    item = command()
    issue = SimpleNamespace(
        eval_report_ref=SimpleNamespace(
            resource_id="eval-1", revision=1, content_hash="c" * 64),
        artifact_ref=SimpleNamespace(artifact_id="content-1", content_hash="1" * 64),
    )
    subject = {"resourceType": "Artifact", "resourceId": "content-1", "contentHash": "1" * 64}
    attempt = {"resourceType": "StepRunAttempt", "runId": "run-1",
               "stepKey": "content_generate", "stepRunId": "step-1",
               "attempt": 1, "inputHash": "a" * 64}
    report = {"content_hash": "c" * 64, "gate_passed": True,
              "subject_artifact_ref": subject,
              "stage_attempt_ref": attempt,
              "eval_contract_ref": {"resourceType": "EvalContractRevision", "resourceId": "contract-1", "revision": 1, "contentHash": "a" * 64},
              "gate_policy_ref": {"resourceType": "EvalContractRevision", "resourceId": "contract-1", "revision": 1, "contentHash": "a" * 64}}
    artifact = {"run_id": "run-1", "artifact_type": "ecommerce_content",
                "content_hash": "1" * 64}
    step = {"step_run_id": "step-1", "run_id": "run-1", "step_key": "content_generate",
            "attempt": 1, "input_hash": "a" * 64, "status": "succeeded"}
    plan = {"run_plan_revision_id": "plan-1", "plan_revision_id": "plan-1",
            "current_plan_revision_id": "plan-1", "approval_status": "approved",
            "steps": [{"stepKey": "content_generate", "gateRefs": []},
                      {"stepKey": "content_review", "gateRefs": [report["eval_contract_ref"]]}]}

    class Tx:
        def __init__(self, selected=report, latest=step, original_plan=plan):
            self.selected, self.latest, self.original_plan = selected, latest, original_plan

        def execute(self, query, *_):
            if "aip_eval_report_revision" in query:
                return Result(self.selected)
            if "aip_artifact" in query:
                return Result(artifact)
            if "ORDER BY attempt DESC" in query:
                return Result(self.latest)
            if "aip_step_run" in query:
                return Result(step)
            if "aip_plan_revision" in query:
                return Result(self.original_plan)
            raise AssertionError(query)

    authority = ContentReviewHostService._issue_eval_authority
    authority(HostTransaction(Tx()), SCOPE, item, issue)
    with pytest.raises(ValueError, match="attempt"):
        authority(HostTransaction(Tx(latest={**step, "status": "running"})), SCOPE, item, issue)
    with pytest.raises(ValueError, match="pre-review"):
        authority(HostTransaction(Tx({**report, "gate_passed": False})), SCOPE, item, issue)
    returned_failed = {**item, "decision": "RETURN", "returnStage": "content_generation"}
    authority(HostTransaction(Tx({**report, "gate_passed": False})), SCOPE, returned_failed, issue)
    with pytest.raises(ValueError, match="Plan"):
        authority(HostTransaction(Tx(original_plan={**plan,
            "steps": [{"stepKey": "content_generate", "gateRefs": []},
                      {"stepKey": "content_review", "gateRefs": []}]})), SCOPE, item, issue)
    with pytest.raises(ValueError, match="EvalReport"):
        authority(HostTransaction(Tx({**report, "gate_policy_ref": {
            "resourceType": "MediaGatePolicyRevision", "resourceId": "fixture",
            "revision": 1, "contentHash": "a" * 64}})), SCOPE, item, issue)
    with pytest.raises(ValueError, match="EvalReport"):
        authority(HostTransaction(Tx({**report, "subject_artifact_ref":
            {**subject, "resourceId": "other-content"}})), SCOPE, item, issue)
    with pytest.raises(ValueError, match="EvalReport"):
        authority(HostTransaction(Tx({**report, "stage_attempt_ref":
            {**attempt, "stepRunId": None}})), SCOPE, item, issue)
    with pytest.raises(ValueError, match="EvalReport"):
        authority(HostTransaction(Tx({**report, "gate_policy_ref": None})), SCOPE, item, issue)
    with pytest.raises(ValueError, match="EvalReport"):
        authority(HostTransaction(Tx(latest={**step, "step_run_id": "step-2",
            "attempt": 2})), SCOPE, item, issue)
    returned = {**item, "decision": "RETURN", "returnStage": "content_generation"}
    authority(HostTransaction(Tx(latest={**step, "step_run_id": "step-2",
        "attempt": 2})), SCOPE, returned, issue)


def _seed_runtime(scope, operation):
    installation, generation, group = uuid4(), uuid4(), uuid4()
    with connect(inherit_scope=False) as conn:
        conn.execute("SET LOCAL session_replication_role=replica")
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES(%s,'正向隔离组织') ON CONFLICT(id) DO NOTHING",
            (scope.org_id,),
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
               VALUES(%s,%s,'正向隔离工作区') ON CONFLICT(org_id,project_id) DO NOTHING""",
            scope.key,
        )
        conn.execute(
            """INSERT INTO bundle_installation(
                 org_id,project_id,installation_pk,installation_id,display_name,current_revision,
                 active_revision,previous_active_revision,etag_version,created_by)
               VALUES(%s,%s,%s,%s,'内容评审隔离测试',1,NULL,NULL,1,'test')""",
            (*scope.key, installation, installation),
        )
        conn.execute(
            """INSERT INTO extension_runtime_binding(
              org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
              profile_ref,execution_epoch,desired_state,observed_state,enabled,operation_fence,config_ref)
              VALUES(%s,%s,%s,%s,1,'{}','internal-python-v1',3,'enabled','ready',true,false,'{}')""",
            (*scope.key, installation, generation),
        )
        conn.execute(
            """INSERT INTO extension_operation_dispatch_binding(
              org_id,project_id,operation_id,handler_kind,installation_id,generation,execution_epoch,
              operation_fence,revision,cutover_group_id,cutover_group_revision,updated_by)
              VALUES(%s,%s,%s,'extension',%s,%s,3,false,5,%s,11,'test')""",
            (*scope.key, operation, installation, generation, group),
        )
    return SimpleNamespace(
        org_id=scope.org_id,
        project_id=scope.project_id,
        operation_id=operation,
        handler_kind="extension",
        dispatch_revision=5,
        installation_id=str(installation),
        generation=str(generation),
        execution_epoch=3,
        cutover_group_id=str(group),
        cutover_group_revision=11,
        runtime_revision=1,
        checked_at=NOW,
    )


def test_real_postgres_receipt_and_feedback_commit_or_roll_back_together(monkeypatch):
    scope = TenantScope("org-org", "dev-project")
    live_dispatch = _seed_runtime(scope, "ecommerce_growth_content_review")
    key = "content-review-pg-" + uuid4().hex
    item = command(key=key)
    service = ContentReviewHostService()
    monkeypatch.setattr(ContentReviewHostService, "_artifact_authority", staticmethod(lambda *_: artifact(item)))
    monkeypatch.setattr(ContentReviewHostService, "_task_brief_authority", staticmethod(lambda *_: "七夕会员复购内容策划"))
    monkeypatch.setattr(ContentReviewHostService, "_issue_authority", staticmethod(lambda *_: None))
    monkeypatch.setattr(ContentReviewHostService, "_reviewer_authority", staticmethod(lambda *_: None))
    with connect_serializable(scope) as conn:
        receipt = service.execute(
            transaction=HostTransaction(conn), scope=scope, dispatch_ref=live_dispatch,
            command=item, checked_at=NOW, occurred_at=None,
        )
        assert service.verify_receipt(
            transaction=HostTransaction(conn), scope=scope, dispatch=live_dispatch,
            command=item, receipt=receipt,
        ) == receipt
    with connect(scope) as conn:
        runtime_count = conn.execute(
            """SELECT count(*) n FROM ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s AND operation_id=%s AND idempotency_key=%s""",
            (*scope.key, live_dispatch.operation_id, key),
        ).fetchone()["n"]
        feedback_count = conn.execute(
            """SELECT count(*) n FROM ecommerce_growth_feedback_command
                WHERE org_id=%s AND project_id=%s AND review_receipt_ref->>'resourceId'=%s""",
            (*scope.key, receipt["receiptRef"]["resourceId"]),
        ).fetchone()["n"]
        assert (runtime_count, feedback_count) == (1, 1)

    rollback_key = key + "-rollback"
    rollback_item = command(key=rollback_key)
    monkeypatch.setattr(ContentReviewHostService, "_artifact_authority", staticmethod(lambda *_: artifact(rollback_item)))

    class BrokenFeedback:
        def enqueue(self, **_):
            raise ValueError("forced feedback failure")

    monkeypatch.setattr(ContentReviewHostService, "_feedback_port", staticmethod(lambda *_: BrokenFeedback()))
    with pytest.raises(ValueError, match="forced feedback failure"):
        with connect_serializable(scope) as conn:
            service.execute(
                transaction=HostTransaction(conn), scope=scope, dispatch_ref=live_dispatch,
                command=rollback_item, checked_at=NOW, occurred_at=None,
            )
    with connect(scope) as conn:
        assert conn.execute(
            """SELECT count(*) n FROM ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s AND operation_id=%s AND idempotency_key=%s""",
            (*scope.key, live_dispatch.operation_id, rollback_key),
        ).fetchone()["n"] == 0
