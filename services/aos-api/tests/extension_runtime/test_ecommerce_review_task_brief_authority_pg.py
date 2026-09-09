from datetime import UTC, datetime

import pytest
from psycopg.types.json import Jsonb

from aos_api.db import connect_serializable
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService
from aos_api.aip_task_store import AipTaskIdempotencyConflict
from aos_api.tenant_scope import TenantScope


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
