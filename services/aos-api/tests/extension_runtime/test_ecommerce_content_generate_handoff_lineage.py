from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService,
    ReviewAdvanceHostService,
    _analysis_command_hash,
    _strict_content_generate_command,
)
from aos_api.aip_production_contract_store import canonical_hash as production_hash
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, SalesWeaponMethod
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_authority_contracts import sales_weapon_method
from test_ecommerce_review_task_brief_authority_pg import accepted_stage_command


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


def v2_authorities():
    values = authorities()
    method = SalesWeaponMethod.model_validate(sales_weapon_method())
    decision = AnalystExactRef(resource_type="DecisionSummaryRevision", resource_id="decision-1",
                               revision=1, content_hash=HEX_A)
    task_values = ReviewAdvanceHostService._sales_weapon_task_values(method)
    task = values["task"]
    task["title"] = task_values["title"]
    task["description"] = task_values["objective"]
    task["goal"]["objective"] = task_values["objective"]
    task_payload = {key: task[key] for key in (
        "type", "title", "description", "priority", "goal", "selectionRef", "policyRevision"
    )}
    task["request_hash"] = _analysis_command_hash(task_payload).removeprefix("sha256:")
    task_ref = ref("Task", "task-1", digest=task["request_hash"])
    values["command"]["authorityRefs"]["task"] = task_ref
    spec = values["brief"]["spec"]
    spec.update({
        **{key: task_values[key] for key in (
            "objective", "channels", "audience", "timeWindow", "constraints"
        )},
        "taskRef": task_ref,
        "salesWeaponMethod": method.model_dump(mode="json", by_alias=True),
        "decisionRef": decision.model_dump(mode="json", by_alias=True),
        "sourceCutoffAt": method.source_cutoff_at.isoformat(),
    })
    values["brief"]["schema_ref"] = {
        **values["brief"]["schema_ref"],
        "resourceId": "schema://aos/ecommerce/content-campaign-brief/v2",
        "revision": "2",
    }
    return values, SimpleNamespace(sales_weapon_method=method, decision_ref=decision)


def rehash_v2_brief(values):
    brief = values["brief"]
    spec = brief["spec"]
    digest = _analysis_command_hash({
        "briefType": brief["brief_type"], "schemaRef": brief["schema_ref"], "spec": spec,
    }).removeprefix("sha256:")
    brief["content_hash"] = digest
    values["command"]["authorityRefs"]["brief"] = ref("TaskBriefRevision", "brief-1", digest=digest)
    values["receipt"]["result_ref"] = ref("TaskBriefRevision", "brief-1", digest=digest)
    values["receipt"]["result_ref"]["contentHash"] = digest
    values["receipt"]["request_hash"] = _analysis_command_hash({
        "taskId": "task-1", "briefType": brief["brief_type"],
        "schemaRef": brief["schema_ref"], "spec": spec,
    }).removeprefix("sha256:")


def test_content_generate_accepts_only_plan_identical_v2_sales_weapon_brief():
    values, plan = v2_authorities()
    rehash_v2_brief(values)
    refs = {key: InvestigationExactRef.model_validate(ref_value)
            for key, ref_value in values["command"]["authorityRefs"].items()}
    ContentGenerateHostService._task_brief(
        Transaction(values), SCOPE, refs, values["command"]["sourceArtifactRefs"],
        approved_plan=plan,
    )
    with pytest.raises(ValueError, match="Task/Brief exact lineage drifted"):
        ContentGenerateHostService._task_brief(
            Transaction(values), SCOPE, refs, values["command"]["sourceArtifactRefs"],
            approved_plan=None,
        )
    values["brief"]["spec"]["salesWeaponMethod"]["productLabel"] = "篡改后的商品"
    rehash_v2_brief(values)
    with pytest.raises(ValueError, match="Task/Brief exact lineage drifted"):
        ContentGenerateHostService._task_brief(
            Transaction(values), SCOPE, {key: InvestigationExactRef.model_validate(ref_value)
                                         for key, ref_value in values["command"]["authorityRefs"].items()},
            values["command"]["sourceArtifactRefs"], approved_plan=plan,
        )


def test_v2_fact_sources_require_exact_approved_method_and_current_evidence(monkeypatch):
    values, plan = v2_authorities()
    method = plan.sales_weapon_method
    expected = [
        ref("EvidenceBundleRevision", item.resource_id, digest=item.content_hash)
        for item in method.evidence_refs
    ]
    checked_at = method.source_cutoff_at + timedelta(hours=1)
    calls = []

    def current_sources(transaction, scope, decision_ref, *, markings, now, max_source_age):
        calls.append((transaction, scope, decision_ref, markings, now, max_source_age))
        return SimpleNamespace(evidence_refs=method.evidence_refs, insight_ref=AnalystExactRef(
            resource_type="InsightRevision", resource_id="insight-1",
            revision=1, content_hash=HEX_A,
        ))

    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.require_growth_plan_sources",
        current_sources,
    )
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.require_current_analyst_revision",
        lambda *_: SimpleNamespace(cutoff_at=method.source_cutoff_at),
    )
    transaction = object()
    ContentGenerateHostService._fact_source_authority(
        transaction, SCOPE, expected, plan, checked_at=checked_at,
    )
    assert calls == [(transaction, SCOPE, plan.decision_ref, ["internal"], checked_at, timedelta(days=7))]
    for drift in (
        expected[:-1],
        [ref("EvidenceBundleRevision", expected[0]["resourceId"], digest=HEX_B), *expected[1:]],
        [*expected, ref("DataFulfillmentReceipt", "fulfillment-1", receipt=True)],
    ):
        with pytest.raises(ValueError, match="fact source"):
            ContentGenerateHostService._fact_source_authority(
                transaction, SCOPE, drift, plan, checked_at=checked_at,
            )
    with pytest.raises(ValueError, match="fact source"):
        ContentGenerateHostService._fact_source_authority(
            transaction, SCOPE, expected, plan,
            checked_at=method.source_cutoff_at + timedelta(days=8),
        )
    assert len(calls) == 1


def test_v2_fact_sources_reject_revoked_or_wrong_cutoff(monkeypatch):
    _, plan = v2_authorities()
    method = plan.sales_weapon_method
    expected = [ref("EvidenceBundleRevision", item.resource_id, digest=item.content_hash)
                for item in method.evidence_refs]
    checked_at = method.source_cutoff_at + timedelta(hours=1)
    def revoked(*_args, **_kwargs):
        raise ValueError("evidence revoked")
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.require_growth_plan_sources", revoked,
    )
    with pytest.raises(ValueError, match="evidence revoked"):
        ContentGenerateHostService._fact_source_authority(object(), SCOPE, expected, plan,
                                                           checked_at=checked_at)
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.require_growth_plan_sources",
        lambda *_args, **_kwargs: SimpleNamespace(evidence_refs=method.evidence_refs, insight_ref=AnalystExactRef(
            resource_type="InsightRevision", resource_id="insight-1", revision=1, content_hash=HEX_A,
        )),
    )
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.require_current_analyst_revision",
        lambda *_: SimpleNamespace(cutoff_at=method.source_cutoff_at - timedelta(hours=1)),
    )
    with pytest.raises(ValueError, match="fact source"):
        ContentGenerateHostService._fact_source_authority(object(), SCOPE, expected, plan,
                                                           checked_at=checked_at)
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.require_growth_plan_sources",
        lambda *_args, **_kwargs: SimpleNamespace(evidence_refs=[], insight_ref=None),
    )
    with pytest.raises(ValueError, match="fact source"):
        ContentGenerateHostService._fact_source_authority(object(), SCOPE, expected, plan,
                                                           checked_at=checked_at)


def test_v2_generate_revalidation_stops_before_capacity_on_unbound_facts(monkeypatch):
    values, plan = v2_authorities()
    rehash_v2_brief(values)
    command = values["command"]
    command["requestHash"] = _analysis_command_hash({
        key: value for key, value in command.items() if key != "requestHash"
    })
    monkeypatch.setattr(ReviewAdvanceHostService, "_revalidate_growth_plan",
                        staticmethod(lambda **_: plan))
    monkeypatch.setattr(ContentGenerateHostService, "_review_receipt",
                        staticmethod(lambda *_: {"receiptRef": ref("ReviewDecisionReceipt", "review-1")}))
    monkeypatch.setattr(ContentGenerateHostService, "_task_brief",
                        staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(ContentGenerateHostService, "_agent_capability_authority",
                        staticmethod(lambda *_: (object(), object())))
    monkeypatch.setattr(ContentGenerateHostService, "_route_budget_approval_authority",
                        staticmethod(lambda *_args, **_kwargs: (
                            object(), plan.sales_weapon_method.source_cutoff_at + timedelta(hours=1)
                        )))
    monkeypatch.setattr(ContentGenerateHostService, "_resolution_capacity_authority",
                        staticmethod(lambda *_args, **_kwargs: pytest.fail("capacity must not be read")))
    with pytest.raises(ValueError, match="fact source"):
        ContentGenerateHostService().revalidate(
            transaction=ReturnAuthorityTransaction(None), scope=SCOPE,
            dispatch=SimpleNamespace(operation_id="ecommerce_growth_content_generate"),
            command=command,
        )


class Transaction:
    def __init__(self, values):
        self.values = values
        self.queries = []

    def execute(self, query, _params):
        self.queries.append(query)
        if "aip_return_decision" in query:
            return SimpleNamespace(fetchone=lambda: None)
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
        staticmethod(lambda *_: (object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_route_budget_approval_authority",
        staticmethod(lambda *_args, **_kwargs: (object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_resolution_capacity_authority",
        staticmethod(lambda *_args, **_kwargs: (object(), object(), object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_binding_authority",
        staticmethod(lambda *_args, **_kwargs: (object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_binding_dependency_authority",
        staticmethod(lambda *_args, **_kwargs: None),
    )
    transaction = Transaction(values)
    result = ContentGenerateHostService().revalidate(
        transaction=transaction,
        scope=SCOPE,
        dispatch=SimpleNamespace(operation_id="ecommerce_growth_content_generate"),
        command=values["command"],
    )
    assert result is None
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


def return_command():
    command = deepcopy(authorities()["command"])
    identity = "return-decision-1"
    decision = {
        "issueId": "issue-1", "issueVersion": 1, "runId": "run-1",
        "stepKey": "content_generate", "stepRunId": "step-run-2",
        "attempt": 2, "attemptIdempotencyKey": "repair-attempt-2",
        "reason": "内容需修改", "actor": "human-1",
    }
    command["returnDecisionRef"] = ref(
        "ReturnDecision", identity, digest=production_hash(decision)
    )
    command["idempotencyKey"] = decision["attemptIdempotencyKey"]
    command["requestHash"] = _analysis_command_hash(
        {key: value for key, value in command.items() if key != "requestHash"}
    )
    return command, decision


def test_content_generate_return_envelope_is_exact_and_original_unchanged():
    original = authorities()["command"]
    assert _strict_content_generate_command(original)["returnRef"] is None
    command, _ = return_command()
    assert _strict_content_generate_command(command)["returnRef"].resource_id == "return-decision-1"
    for change in (
        lambda value: value.update(extra="x"),
        lambda value: value["returnDecisionRef"].update(resourceType="Task"),
        lambda value: value["returnDecisionRef"].update(receiptId="return-decision-1"),
    ):
        drift = deepcopy(command)
        change(drift)
        drift["requestHash"] = _analysis_command_hash(
            {key: value for key, value in drift.items() if key != "requestHash"}
        )
        with pytest.raises(ValueError):
            _strict_content_generate_command(drift)


def accepted_stage_content_command():
    command = deepcopy(authorities()["command"])
    command["sourceKind"] = "accepted-stage-v1"
    command["sourceArtifactRefs"] = [ref("Artifact", "stage-artifact-1")]
    command["requestHash"] = _analysis_command_hash(
        {key: value for key, value in command.items() if key != "requestHash"}
    )
    return command


def test_accepted_stage_review_receipt_hash_preserves_original_source_without_fake_issue():
    command = accepted_stage_command()
    lineage = {
        "handoffRef": ref("HandoffReceipt", "handoff-stage-1", receipt=True),
        "taskRef": ref("Task", "task-stage-1"),
        "briefRef": ref("TaskBriefRevision", "brief-stage-1"),
    }
    host = ReviewAdvanceHostService()
    receipt = host._accept_receipt(
        command, lineage, SCOPE, command["idempotencyKey"],
        datetime(2026, 9, 9, 4, 1, tzinfo=timezone.utc),
    )
    source = {name: command[name] for name in (
        "sourceKind", "cutoffAt", "expiresAt", "markings", "occurrenceRef",
        "caseRef", "runRef", "analysisReceiptRef", "currentPlanRef",
        "growthPlanRef", "evalReportRef", "stageDecisionRef", "stageTaskRunId",
        "stagePlanRef", "stageAttemptRef", "stageArtifactRef",
        "responsibilityPlanRef",
    )}
    assert receipt["sourceKind"] == "accepted-stage-v1"
    assert receipt["sourceLineage"] == source
    assert "reviewIssueRef" not in receipt and "artifactBindings" not in receipt
    assert receipt["receiptRef"]["contentHash"] == _analysis_command_hash({
        key: value for key, value in receipt.items() if key != "receiptRef"
    })
    drift = deepcopy(command)
    drift["stageDecisionRef"]["resourceId"] = "another-decision"
    drift["requestHash"] = _analysis_command_hash({
        key: value for key, value in drift.items() if key != "requestHash"
    })
    changed = host._accept_receipt(
        drift, lineage, SCOPE, drift["idempotencyKey"],
        datetime(2026, 9, 9, 4, 1, tzinfo=timezone.utc),
    )
    assert changed["receiptRef"]["contentHash"] != receipt["receiptRef"]["contentHash"]


def test_accepted_stage_content_command_is_strict_and_host_stays_closed():
    command = accepted_stage_content_command()
    parsed = _strict_content_generate_command(command)
    assert parsed["sourceKind"] == "accepted-stage-v1"
    assert [item.resource_type for item in parsed["sourceRefs"]] == ["Artifact"]
    for change in (
        lambda value: value.update(sourceKind="issue-review-v1"),
        lambda value: value["sourceArtifactRefs"].append(ref("Artifact", "another")),
        lambda value: value["sourceArtifactRefs"][0].update(resourceType="ArtifactRevision"),
        lambda value: value.update(returnDecisionRef=ref("ReturnDecision", "returned")),
    ):
        drift = deepcopy(command)
        change(drift)
        drift["requestHash"] = _analysis_command_hash(
            {key: value for key, value in drift.items() if key != "requestHash"}
        )
        with pytest.raises(ValueError):
            _strict_content_generate_command(drift)

    class NoDatabase:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("Host touched database before accepted-stage gate")

    host = ContentGenerateHostService()
    with pytest.raises(ValueError, match="accepted stage content Host is not wired"):
        host.revalidate(transaction=NoDatabase(), scope=SCOPE,
                        dispatch=SimpleNamespace(operation_id="ecommerce_growth_content_generate"),
                        command=command)
    with pytest.raises(ValueError, match="accepted stage content Host is not wired"):
        host.execute(transaction=NoDatabase(), scope=SCOPE, dispatch_ref=None,
                     command=command, checked_at=datetime.now(timezone.utc),
                     occurred_at=datetime.now(timezone.utc))
    with pytest.raises(ValueError, match="accepted stage content Host is not wired"):
        host.verify_receipt(transaction=NoDatabase(), scope=SCOPE, dispatch=None,
                            command=command, receipt={})


class ReturnAuthorityTransaction:
    def __init__(self, row):
        self.row = row

    def execute(self, query, _params):
        assert "aip_return_decision" in query
        row = self.row
        return SimpleNamespace(fetchone=lambda: row)


def test_content_generate_return_requires_current_queued_attempt_and_new_approval(monkeypatch):
    command, decision = return_command()
    base = datetime(2026, 9, 27, 8, tzinfo=timezone.utc)
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_content_generate",
        installation_id="installation-1", generation="generation-1",
        execution_epoch=3, cutover_group_id="group-1",
        cutover_group_revision=2, dispatch_revision=5,
        checked_at=base + timedelta(minutes=2))
    row = {
        "decision_id": "return-decision-1", "decision_hash": production_hash(decision),
        "issue_id": decision["issueId"], "issue_version": 1,
        "run_id": "run-1", "step_key": "content_generate",
        "step_run_id": "step-run-2", "attempt": 2,
        "attempt_idempotency_key": "repair-attempt-2", "reason": decision["reason"],
        "actor": decision["actor"], "decision_created_at": base,
        "run_status": "running", "task_id": "task-1", "task_status": "executing",
        "step_run_id_owner": "run-1", "step_key_owner": "content_generate",
        "step_status": "queued", "step_attempt": 2, "latest_attempt": 2,
        "input_refs": [command["returnDecisionRef"]],
        "issue_status": "returned", "current_issue_version": 2,
        "artifact_id": "content-artifact-1",
        "artifact_hash": HEX_A,
        "persisted_artifact_hash": HEX_A,
        "artifact_metadata": {"ecommerceGrowthContentArtifact": {
            "briefRef": ref("TaskBriefRevision", "brief-1")}},
        "approval_created_at": base + timedelta(seconds=1),
    }
    row["input_refs"].append({
        "resourceType": "Artifact", "resourceId": "content-artifact-1",
        "contentHash": HEX_A,
    })
    calls = []
    approval_calls = []
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.require_frozen_repair_brief",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.require_repair_approval_binding",
        lambda *args, **kwargs: approval_calls.append((args, kwargs)),
    )
    ContentGenerateHostService._return_authority(
        ReturnAuthorityTransaction(row), SCOPE, command,
        _strict_content_generate_command(command), dispatch=dispatch,
    )
    assert len(calls) == 1
    assert len(approval_calls) == 1
    assert calls[0][1]["task_id"] == "task-1"
    assert calls[0][1]["reason"] == decision["reason"]
    with pytest.raises(ValueError, match="versioned repair preparation"):
        ContentGenerateHostService().revalidate(
            transaction=ReturnAuthorityTransaction(row), scope=SCOPE,
            dispatch=dispatch,
            command=command,
        )
    with pytest.raises(ValueError, match="not enabled"):
        ContentGenerateHostService().execute(
            transaction=object(), scope=SCOPE, dispatch_ref=object(),
            command=command, checked_at=base, occurred_at=base,
        )
    for change in (
        {"step_status": "succeeded"}, {"latest_attempt": 3},
        {"approval_created_at": base}, {"task_id": "other-task"},
        {"decision_hash": "b" * 64},
    ):
        with pytest.raises(ValueError):
            ContentGenerateHostService._return_authority(
                ReturnAuthorityTransaction({**row, **change}), SCOPE, command,
                _strict_content_generate_command(command), dispatch=dispatch,
            )
    with pytest.raises(ValueError):
        ContentGenerateHostService._return_authority(
            ReturnAuthorityTransaction(row), SCOPE, authorities()["command"],
            _strict_content_generate_command(authorities()["command"]), dispatch=dispatch,
        )


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
        staticmethod(lambda *_: (object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_route_budget_approval_authority",
        staticmethod(lambda *_args, **_kwargs: (object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_resolution_capacity_authority",
        staticmethod(lambda *_args, **_kwargs: (object(), object(), object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_binding_authority",
        staticmethod(lambda *_args, **_kwargs: (object(), object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_binding_dependency_authority",
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
