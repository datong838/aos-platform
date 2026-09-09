from datetime import UTC, datetime

import pytest
from psycopg.types.json import Jsonb

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect_serializable
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService,
    ReviewAdvanceHostService,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, 11, tzinfo=UTC)
HASH = "sha256:" + "a" * 64


def ref(kind, identity):
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": HASH,
    }


def review_command():
    artifacts = [ref("ArtifactRevision", f"artifact-{index}") for index in range(4)]
    growth_plan = ref("GrowthPlanRevision", "growth-plan-1")
    return {
        "idempotencyKey": "content-lineage-pg-1",
        "occurrenceRef": ref("AutomationOccurrence", "occurrence-1"),
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "runRef": ref("BusinessInvestigationRun", "run-1"),
        "analysisReceiptRef": ref("AnalysisRuntimeReceipt", "analysis-1"),
        "currentPlanRef": ref("PlanRevision", "plan-1"),
        "growthPlanRef": growth_plan,
        "reviewIssueRef": ref("ReviewIssueRevision", "issue-1"),
        "evalReportRef": ref("EvalReportRevision", "eval-1"),
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
        "expiresAt": "2026-09-10T11:00:00+00:00",
        "taskSpec": {
            "taskType": "ecommerce.workshop.business_task",
            "briefType": "content_campaign",
            "title": "制定会员复购内容方案",
            "objective": "围绕会员复购设计内容方案",
            "channels": ["微信小店"],
            "audience": "近九十天已购会员",
            "timeWindow": "九月第二周",
            "constraints": ["库存不足商品不得主推"],
            "growthPlanRef": growth_plan,
            "artifactRefs": artifacts,
        },
    }


def parsed_refs(lineage):
    return {
        name: InvestigationExactRef.model_validate(lineage[f"{name}Ref"])
        for name in ("handoff", "task", "brief")
    }


def test_content_generate_reads_public_review_task_brief_and_outer_rollback():
    command = review_command()
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        lineage = ReviewAdvanceHostService()._review_lineage(
            transaction=transaction,
            scope=SCOPE,
            command=command,
            occurred_at=NOW,
        )
        refs = parsed_refs(lineage)
        refs["growth_plan"] = InvestigationExactRef.model_validate(
            command["growthPlanRef"]
        )
        sources = command["taskSpec"]["artifactRefs"]

        conn.execute(
            "CREATE TEMP TABLE aip_task(task_id text, goal jsonb) ON COMMIT DROP"
        )
        conn.execute(
            "INSERT INTO aip_task(task_id,goal) VALUES('shadow-task',%s::jsonb)",
            (Jsonb({"externalPublicationRequested": True}),),
        )
        ContentGenerateHostService._task_brief(
            transaction, SCOPE, refs, sources
        )

        with pytest.raises(ValueError, match="missing"):
            ContentGenerateHostService._task_brief(
                transaction,
                TenantScope("dev-org", "dev-project"),
                refs,
                sources,
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
