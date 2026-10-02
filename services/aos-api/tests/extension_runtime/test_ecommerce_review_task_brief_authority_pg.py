from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from psycopg.types.json import Jsonb

from aos_api.db import connect_serializable
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService, ContentReviewHostService,
    ReviewAdvanceHostService,
    TransactionBoundConnectFactory,
    _analysis_command_hash,
    _strict_review_accept_command,
)
from aos_api.aip_task_store import AipTaskIdempotencyConflict, AipTaskStore
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, BudgetReservationBlocked
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_contracts import ExactContractRef, PlanStep, ResourceRef
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, SalesWeaponMethod
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_authority_contracts import sales_weapon_method


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, 4, tzinfo=UTC)
HASH = "sha256:" + "a" * 64


def ref(kind: str, identity: str) -> dict[str, object]:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": HASH,
    }


def command(*, title: str = "制定七夕会员复购活动方案") -> dict[str, object]:
    artifacts = [ref("ArtifactRevision", f"artifact-{index}") for index in range(4)]
    return {
        "idempotencyKey": "review-task-brief-1",
        "occurrenceRef": ref("AutomationOccurrence", "occurrence-1"),
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "runRef": ref("BusinessInvestigationRun", "run-1"),
        "analysisReceiptRef": ref("AnalysisRuntimeReceipt", "analysis-1"),
        "currentPlanRef": ref("PlanRevision", "plan-1"),
        "growthPlanRef": ref("GrowthPlanRevision", "growth-plan-1"),
        "reviewIssueRef": ref("ReviewIssueRevision", "review-issue-1"),
        "evalReportRef": ref("EvalReportRevision", "eval-report-1"),
        "artifactBindings": [
            {"family": family, "artifactRef": artifact}
            for family, artifact in zip(
                ("portrait", "diagnosis", "growth_plan", "evidence_summary"),
                artifacts,
                strict=True,
            )
        ],
        "targetModuleId": "ecommerce.content-campaign",
        "sourceSlotId": "analyst.solution",
        "targetSlotId": "content.plan",
        "markings": ["internal"],
        "expiresAt": "2026-09-10T04:00:00+00:00",
        "taskSpec": {
            "taskType": "ecommerce.workshop.business_task",
            "briefType": "content_campaign",
            "title": title,
            "objective": "围绕栖月汇微商城会员设计七夕复购活动",
            "channels": ["微信小店", "私域社群"],
            "audience": "近九十天已购会员",
            "timeWindow": "七夕活动前七天至活动后三天",
            "constraints": ["毛利率不低于百分之十五", "库存不足商品不得主推"],
            "growthPlanRef": ref("GrowthPlanRevision", "growth-plan-1"),
            "artifactRefs": artifacts,
        },
    }


def accepted_stage_command() -> dict[str, object]:
    value = command()
    value.pop("reviewIssueRef")
    value.pop("artifactBindings")
    stage_artifact = {**ref("Artifact", "stage-artifact-1"), "contentHash": "a" * 64}
    stage_plan = {**value["currentPlanRef"], "contentHash": "a" * 64}
    value.update({
        "operation": "review_handoff.advance",
        "decision": "ACCEPT",
        "sourceKind": "accepted-stage-v1",
        "stageDecisionRef": {**ref("AnalystStageDecisionRevision", "decision-1"),
                             "contentHash": "a" * 64},
        "stageTaskRunId": "task-run-1",
        "stagePlanRef": stage_plan,
        "stageAttemptRef": {
            "resourceType": "StepRunAttempt", "runId": "task-run-1",
            "stepKey": "solution-design", "stepRunId": "step-run-1",
            "attempt": 1, "inputHash": "a" * 64,
        },
        "stageArtifactRef": stage_artifact,
        "responsibilityPlanRef": {**ref("ResponsibilityPlanRevision", "responsibility-1"),
                                  "contentHash": "a" * 64},
        "cutoffAt": NOW.isoformat(),
        "returnStage": None,
    })
    value["taskSpec"]["artifactRefs"] = [ref("Artifact", "stage-artifact-1")]
    value["requestHash"] = _analysis_command_hash(value)
    return value


def test_accepted_stage_task_brief_v3_persists_one_original_artifact_and_exact_source():
    value = accepted_stage_command()
    _strict_review_accept_command(value)
    host = ReviewAdvanceHostService()
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        first = host._review_lineage(
            transaction=transaction, scope=SCOPE, command=value, occurred_at=NOW,
        )
        assert host._review_lineage(
            transaction=transaction, scope=SCOPE, command=value, occurred_at=NOW,
        ) == first
        task = conn.execute(
            "SELECT goal FROM public.aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s",
            (*SCOPE.key, first["taskRef"]["resourceId"]),
        ).fetchone()
        brief = conn.execute(
            "SELECT schema_ref,spec FROM public.aip_task_brief_revision "
            "WHERE org_id=%s AND project_id=%s AND brief_id=%s AND revision=1",
            (*SCOPE.key, first["briefRef"]["resourceId"]),
        ).fetchone()
        expected_source = {
            name: value[name] for name in (
                "sourceKind", "cutoffAt", "expiresAt", "markings", "occurrenceRef", "caseRef",
                "runRef", "analysisReceiptRef", "currentPlanRef", "growthPlanRef",
                "evalReportRef", "stageDecisionRef", "stageTaskRunId", "stagePlanRef",
                "stageAttemptRef", "stageArtifactRef", "responsibilityPlanRef",
            )
        }
        expected_handoff_body = {
            "operation": "review_handoff.accept",
            **{name: value[name] for name in (
                "occurrenceRef", "caseRef", "runRef", "analysisReceiptRef",
                "currentPlanRef", "growthPlanRef", "evalReportRef", "targetModuleId",
                "sourceSlotId", "targetSlotId", "markings", "expiresAt",
            )},
            "sourceLineage": expected_source,
        }
        assert first["handoffRef"]["contentHash"] == _analysis_command_hash(expected_handoff_body)
        assert brief["schema_ref"]["resourceId"] == "schema://aos/ecommerce/content-campaign-brief/v3"
        assert task["goal"]["sourceLineage"] == brief["spec"]["sourceLineage"] == expected_source
        assert task["goal"]["artifactRefs"] == brief["spec"]["artifactRefs"] == [
            ref("Artifact", "stage-artifact-1")
        ]
        assert "reviewIssueRef" not in expected_source
        assert brief["spec"]["externalPublicationRequested"] is False
        drift = accepted_stage_command()
        drift["stageDecisionRef"]["resourceId"] = "another-decision"
        drift["requestHash"] = _analysis_command_hash(
            {name: item for name, item in drift.items() if name != "requestHash"}
        )
        _strict_review_accept_command(drift)
        with pytest.raises(AipTaskIdempotencyConflict):
            host._review_lineage(
                transaction=transaction, scope=SCOPE, command=drift, occurred_at=NOW,
            )
        conn.rollback()
        assert conn.execute(
            "SELECT count(*) AS n FROM public.aip_task WHERE org_id=%s AND project_id=%s",
            SCOPE.key,
        ).fetchone()["n"] == 0
        assert conn.execute(
            "SELECT count(*) AS n FROM public.aip_task_brief_revision "
            "WHERE org_id=%s AND project_id=%s",
            SCOPE.key,
        ).fetchone()["n"] == 0


def test_accepted_stage_receipt_readback_requires_original_task_brief(monkeypatch):
    value = accepted_stage_command()
    host = ReviewAdvanceHostService()
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        refs = host._review_lineage(
            transaction=transaction, scope=SCOPE, command=value, occurred_at=NOW,
        )
        receipt = host._accept_receipt(value, refs, SCOPE, value["idempotencyKey"], NOW)
        journal = {value["idempotencyKey"]: receipt}
        monkeypatch.setattr(host, "_components", lambda *_: (
            None, None, SimpleNamespace(read=lambda key: journal.get(key))))
        check = lambda item: host.verify_receipt(
            transaction=transaction, scope=SCOPE, dispatch=None,
            command=value, receipt=item,
        )
        assert check(receipt) == receipt

        missing = host._accept_receipt(
            value, {**refs, "taskRef": {**refs["taskRef"], "resourceId": "missing-task"}},
            SCOPE, value["idempotencyKey"], NOW,
        )
        journal[value["idempotencyKey"]] = missing
        assert check(missing) == {}

        missing_brief = host._accept_receipt(
            value, {**refs, "briefRef": {**refs["briefRef"], "resourceId": "missing-brief"}},
            SCOPE, value["idempotencyKey"], NOW,
        )
        journal[value["idempotencyKey"]] = missing_brief
        assert check(missing_brief) == {}
        conn.rollback()


def test_content_generate_reader_requires_independent_v3_task_brief_lineage():
    value = accepted_stage_command()
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        refs = ReviewAdvanceHostService()._review_lineage(
            transaction=transaction, scope=SCOPE, command=value, occurred_at=NOW,
        )
        authorities = {
            name: InvestigationExactRef.model_validate(refs[name + "Ref"])
            for name in ("handoff", "task", "brief")
        }
        authorities["growth_plan"] = InvestigationExactRef.model_validate(value["growthPlanRef"])
        expected = {name: value[name] for name in (
            "sourceKind", "cutoffAt", "expiresAt", "markings", "occurrenceRef",
            "caseRef", "runRef", "analysisReceiptRef", "currentPlanRef",
            "growthPlanRef", "evalReportRef", "stageDecisionRef", "stageTaskRunId",
            "stagePlanRef", "stageAttemptRef", "stageArtifactRef",
            "responsibilityPlanRef",
        )}
        reader = ContentGenerateHostService()
        kwargs = dict(transaction=transaction, scope=SCOPE, authorities=authorities,
                      source_values=value["taskSpec"]["artifactRefs"],
                      source_kind="accepted-stage-v1", source_lineage=expected)
        reader._task_brief(**kwargs)
        with pytest.raises(ValueError, match="Task/Brief exact lineage drifted"):
            reader._task_brief(**{**kwargs, "source_lineage": None})
        with pytest.raises(ValueError, match="Task/Brief exact lineage drifted"):
            reader._task_brief(**{**kwargs, "source_lineage": {
                **expected, "markings": ["public"],
            }})
        with pytest.raises(ValueError, match="Task/Brief exact lineage drifted"):
            reader._task_brief(**{**kwargs, "source_lineage": {
                **expected, "stageArtifactRef": {
                    **expected["stageArtifactRef"], "resourceId": "another-artifact",
                },
            }})
        conn.rollback()


def test_content_review_v3_reader_rejects_brief_without_current_stage_owner_and_receipt():
    value = accepted_stage_command()
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        refs = ReviewAdvanceHostService()._review_lineage(
            transaction=transaction, scope=SCOPE, command=value, occurred_at=NOW,
        )
        review = {
            "sourceKind": "accepted-stage-v1",
            "taskRef": refs["taskRef"], "briefRef": refs["briefRef"],
            "growthPlanRef": value["growthPlanRef"],
            "sourceArtifactRefs": value["taskSpec"]["artifactRefs"],
        }
        with pytest.raises(ValueError):
            ContentReviewHostService._accepted_stage_task_brief_authority(
                transaction, SCOPE, review, checked_at=NOW,
            )
        with pytest.raises(ValueError, match="expired"):
            ContentReviewHostService._accepted_stage_task_brief_authority(
                transaction, SCOPE, review,
                checked_at=datetime(2026, 9, 11, 4, tzinfo=UTC),
            )
        with pytest.raises(ValueError, match="Task authority is missing"):
            ContentReviewHostService._accepted_stage_task_brief_authority(
                transaction, TenantScope("dev-org", "dev-project"), review,
                checked_at=NOW,
            )
        conn.rollback()


def test_content_review_v3_reader_reaches_persisted_receipt_only_after_current_stage_owner(monkeypatch):
    # Reuse the original StageDecision/GrowthPlan stores on this disposable PG.
    # The controlled fixture is not a formal human approval or a business pass.
    import test_analyst_stage_handoff_source_pg as stage_test

    _owner, _draft, decision, args = stage_test.source.__wrapped__(
        SimpleNamespace(param=None)
    )
    stage = stage_test.host_command(decision, args)
    value = accepted_stage_command()
    value.update(stage)
    value["currentPlanRef"] = {
        **stage["stagePlanRef"],
        "contentHash": "sha256:" + stage["stagePlanRef"]["contentHash"],
    }
    source_artifact = {
        **stage["stageArtifactRef"],
        "contentHash": "sha256:" + stage["stageArtifactRef"]["contentHash"],
    }
    value["taskSpec"]["growthPlanRef"] = stage["growthPlanRef"]
    value["taskSpec"]["artifactRefs"] = [source_artifact]
    value["requestHash"] = _analysis_command_hash(
        {name: item for name, item in value.items() if name != "requestHash"}
    )
    _strict_review_accept_command(value)
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        refs = ReviewAdvanceHostService()._review_lineage(
            transaction=transaction, scope=SCOPE, command=value,
            occurred_at=decision.created_at,
        )
        review = {
            "sourceKind": "accepted-stage-v1",
            "taskRef": refs["taskRef"], "briefRef": refs["briefRef"],
            "growthPlanRef": value["growthPlanRef"],
            "sourceArtifactRefs": value["taskSpec"]["artifactRefs"],
        }
        conn.execute("SET LOCAL ROLE aos_runtime")
        checked_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        with pytest.raises(ValueError, match="Review authority is not unique"):
            ContentReviewHostService._accepted_stage_task_brief_authority(
                transaction, SCOPE, review, checked_at=checked_at,
            )
        # The isolated seam tests the remaining original v3 Brief reader only;
        # it is never used as a formal persisted Review Receipt acceptance.
        monkeypatch.setattr(
            ContentGenerateHostService, "_review_receipt",
            staticmethod(lambda *_args, **_kwargs: None),
        )
        assert ContentReviewHostService._accepted_stage_task_brief_authority(
            transaction, SCOPE, review, checked_at=checked_at,
        ) == value["taskSpec"]["title"]
        conn.rollback()


def test_review_lineage_uses_real_task_and_brief_owners_and_outer_rollback():
    host = ReviewAdvanceHostService()
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        first = host._review_lineage(
            transaction=transaction,
            scope=SCOPE,
            command=command(),
            occurred_at=NOW,
        )
        replay = host._review_lineage(
            transaction=transaction,
            scope=SCOPE,
            command=command(),
            occurred_at=NOW,
        )
        assert replay == first
        assert first["handoffRef"]["resourceType"] == "HandoffReceipt"
        assert first["handoffRef"]["receiptId"] == first["handoffRef"]["resourceId"]
        assert first["taskRef"]["resourceType"] == "Task"
        assert first["briefRef"]["resourceType"] == "TaskBriefRevision"
        assert all(value["contentHash"].startswith("sha256:") for value in first.values())

        task = conn.execute(
            "SELECT task_type,title,goal,request_hash FROM public.aip_task "
            "WHERE org_id=%s AND project_id=%s AND task_id=%s",
            (*SCOPE.key, first["taskRef"]["resourceId"]),
        ).fetchone()
        brief = conn.execute(
            "SELECT task_id,brief_type,spec,content_hash FROM public.aip_task_brief_revision "
            "WHERE org_id=%s AND project_id=%s AND brief_id=%s AND revision=1",
            (*SCOPE.key, first["briefRef"]["resourceId"]),
        ).fetchone()
        assert task["task_type"] == "ecommerce.workshop.business_task"
        assert task["goal"]["workshopAssignment"]["roleKey"] == "campaign_planner"
        assert first["taskRef"]["contentHash"] == "sha256:" + task["request_hash"]
        assert brief["task_id"] == first["taskRef"]["resourceId"]
        assert brief["brief_type"] == "content_campaign"
        assert brief["spec"].get("salesWeaponMethod") is None
        assert brief["spec"]["sourceHandoffRef"] == first["handoffRef"]
        assert brief["spec"]["externalPublicationRequested"] is False
        assert first["briefRef"]["contentHash"] == "sha256:" + brief["content_hash"]

        original_goal = task["goal"]
        drifted_goal = {
            **original_goal,
            "sourceHandoffRef": {
                **original_goal["sourceHandoffRef"],
                "revision": True,
            },
        }
        conn.execute(
            "UPDATE public.aip_task SET goal=%s::jsonb WHERE org_id=%s AND project_id=%s AND task_id=%s",
            (Jsonb(drifted_goal), *SCOPE.key, first["taskRef"]["resourceId"]),
        )
        with pytest.raises(ValueError, match="Task authority drifted"):
            host._review_lineage(
                transaction=transaction,
                scope=SCOPE,
                command=command(),
                occurred_at=NOW,
            )
        conn.execute(
            "UPDATE public.aip_task SET goal=%s::jsonb WHERE org_id=%s AND project_id=%s AND task_id=%s",
            (Jsonb(original_goal), *SCOPE.key, first["taskRef"]["resourceId"]),
        )

        with pytest.raises(AipTaskIdempotencyConflict):
            host._review_lineage(
                transaction=transaction,
                scope=SCOPE,
                command=command(title="制定中秋会员复购活动方案"),
                occurred_at=NOW,
            )
        conn.rollback()
        assert conn.execute(
            "SELECT count(*) AS n FROM public.aip_task WHERE org_id=%s AND project_id=%s",
            SCOPE.key,
        ).fetchone()["n"] == 0
        assert conn.execute(
            "SELECT count(*) AS n FROM public.aip_task_brief_revision "
            "WHERE org_id=%s AND project_id=%s",
            SCOPE.key,
        ).fetchone()["n"] == 0


def test_review_task_brief_preserves_approved_sales_weapon_provenance():
    host = ReviewAdvanceHostService()
    method = SalesWeaponMethod.model_validate(sales_weapon_method())
    decision = AnalystExactRef(resource_type="DecisionSummaryRevision", resource_id="decision-1",
                               revision=1, content_hash="a" * 64)
    approved = SimpleNamespace(sales_weapon_method=method, decision_ref=decision)
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        result = host._review_lineage(
            transaction=transaction, scope=SCOPE,
            command=command(), occurred_at=NOW, approved_plan=approved,
        )
        row = conn.execute(
            "SELECT schema_ref,spec FROM public.aip_task_brief_revision WHERE org_id=%s AND project_id=%s "
            "AND brief_id=%s AND revision=1",
            (*SCOPE.key, result["briefRef"]["resourceId"]),
        ).fetchone()
        assert row["spec"]["salesWeaponMethod"] == method.model_dump(mode="json", by_alias=True)
        assert row["spec"]["decisionRef"] == decision.model_dump(mode="json", by_alias=True)
        assert row["spec"]["sourceCutoffAt"] == method.source_cutoff_at.isoformat()
        assert row["schema_ref"]["resourceId"] == "schema://aos/ecommerce/content-campaign-brief/v2"
        conn.rollback()
        assert conn.execute(
            "SELECT count(*) AS n FROM public.aip_task_brief_revision "
            "WHERE org_id=%s AND project_id=%s",
            SCOPE.key,
        ).fetchone()["n"] == 0


def test_content_plan_and_run_owner_can_share_outer_review_transaction_without_partial_commit():
    host = ReviewAdvanceHostService()
    method = SalesWeaponMethod.model_validate(sales_weapon_method())
    decision = AnalystExactRef(resource_type="DecisionSummaryRevision", resource_id="decision-1",
                               revision=1, content_hash="a" * 64)
    approved = SimpleNamespace(sales_weapon_method=method, decision_ref=decision)
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        lineage = host._review_lineage(
            transaction=transaction, scope=SCOPE, command=command(),
            occurred_at=NOW, approved_plan=approved,
        )
        task_id = lineage["taskRef"]["resourceId"]
        store = AipTaskStore(TransactionBoundConnectFactory(transaction, SCOPE))
        plan = store.create_plan(
            SCOPE, "ecommerce-growth-content-owner", task_id, "review-task-brief-1:plan",
            CreatePlanRevisionRequest(
                expected_task_version=1,
                steps=[PlanStep(step_key="content_generate", title="生成可读内容",
                                responsibility_slot_ids=["content.generate"],
                                assignee_refs=[ResourceRef(resource_type="AgentInstance",
                                                           resource_id="content-agent-1", revision="1",
                                                           authority="aip-assignee-directory")],
                                capability_refs=[ExactContractRef(resource_type="CapabilityRevision",
                                                                   resource_id="copy.generate", revision=1,
                                                                   content_hash="a" * 64)]),
                       PlanStep(step_key="content_review", title="人工审核内容")],
                dependencies=[lineage["briefRef"]],
                risk={"externalPublicationAllowed": False},
            ),
        )
        task = store.get_task(SCOPE, task_id)
        store.approve_plan(
            SCOPE, "ecommerce-growth-content-owner", task_id, plan.revision,
            task.version, plan.content_hash,
        )
        task = store.get_task(SCOPE, task_id)
        run = store.create_run(
            SCOPE, "ecommerce-growth-content-owner", task_id, "review-task-brief-1:run",
            CreateTaskRunRequest(plan_revision_id=plan.id, expected_task_version=task.version),
        )
        started = store.start_run(
            SCOPE, run.id, expected_run_version=run.version,
            expected_task_version=task.version, actor="ecommerce-growth-content-owner",
            idempotency_key="review-task-brief-1:start",
        )
        assert started.run.status.value == "running"
        creation_ref = BudgetExactRef.model_validate(lineage["taskRef"])
        AipBudgetReservationStore()._task_authority(
            conn, SCOPE, creation_ref, operation_id="ecommerce_growth_content_generate"
        )
        with pytest.raises(BudgetReservationBlocked):
            AipBudgetReservationStore()._task_authority(
                conn, SCOPE, creation_ref, operation_id="other.operation"
            )
        assert store.create_run(
            SCOPE, "ecommerce-growth-content-owner", task_id, "review-task-brief-1:run",
            CreateTaskRunRequest(plan_revision_id=plan.id, expected_task_version=task.version),
        ).id == run.id
        assert conn.execute(
            "SELECT count(*) AS n FROM public.aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s",
            (*SCOPE.key, task_id),
        ).fetchone()["n"] == 1
        conn.rollback()
        assert conn.execute(
            "SELECT count(*) AS n FROM public.aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s",
            (*SCOPE.key, task_id),
        ).fetchone()["n"] == 0
