from copy import deepcopy
from datetime import UTC, datetime

import pytest

from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceipt,
)
from aos_api.aip_business_investigation_runtime import BusinessInvestigationRuntimeBinder
from aos_api.aip_contracts import TenantContext
from aos_api.aip_task_models import PlanStep, TaskTimeline
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunStateRevision,
)
from aos_api.ecommerce_growth_runtime_adapters import (
    ReviewAdvanceHostService,
    _analysis_command_hash,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, 9, tzinfo=UTC)
HEX_A = "a" * 64
HEX_B = "b" * 64


def authorities():
    tenant = TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id)
    case_ref = {
        "resourceType": "BusinessInvestigationCaseRevision",
        "resourceId": "case-1",
        "revision": 1,
        "contentHash": "sha256:" + HEX_A,
    }
    domain = BusinessInvestigationRunRecord.model_validate(
        {
            "tenant": tenant.model_dump(mode="json", by_alias=True),
            "runId": "investigation-run-1",
            "version": 1,
            "contentHash": "sha256:" + "0" * 64,
            "caseRef": case_ref,
            "analysisType": "initial_store_analysis",
            "triggerKind": "recovery",
            "triggerKey": "analysis-1",
            "lifecycle": "PREPARING",
            "control": "RUNNING",
            "createdBy": "ecommerce-growth-analysis-host",
            "createdAt": NOW,
        }
    )
    domain = domain.model_copy(update={"content_hash": domain.calculated_content_hash()})
    run_ref = {
        "resourceType": "BusinessInvestigationRun",
        "resourceId": domain.run_id,
        "revision": 1,
        "contentHash": domain.content_hash,
    }
    step = PlanStep(step_key="analysis", title="Analysis").model_dump(
        mode="json", by_alias=True
    )
    task_row = {
        "task_id": "task-1", "task_type": "business_investigation", "title": "Analysis",
        "description": "", "status": "approved", "priority": 50, "goal": {},
        "selection_ref": None, "policy_revision": None, "created_by": "analyst",
        "created_at": NOW, "updated_at": NOW, "current_plan_revision_id": "plan-1",
        "version": 3,
    }
    plan_row = {
        "plan_revision_id": "plan-1", "task_id": "task-1", "revision": 1,
        "content_hash": HEX_A, "steps": [step], "dependencies": [], "risk": {},
        "approval_status": "approved", "approved_by": "analyst", "approved_at": NOW,
        "created_by": "analyst", "created_at": NOW,
    }
    runtime_start_row = {
        "run_id": "task-run-1", "task_id": "task-1", "plan_revision_id": "plan-1",
        "status": "paused", "logic_graph_id": None, "logic_revision": None,
        "dependency_snapshot_hash": None, "pause_requested_at": None, "pause_reason": None,
        "started_at": NOW, "finished_at": None, "last_checkpoint_id": None,
        "version": 1, "created_by": "analyst", "created_at": NOW, "updated_at": NOW,
    }
    runtime_row = {
        **runtime_start_row,
        "status": "succeeded",
        "finished_at": NOW,
        "version": 2,
    }
    compilation = BusinessInvestigationCompilationReceipt.model_validate(
        {
            "tenant": tenant.model_dump(mode="json", by_alias=True),
            "receiptId": "compilation-1", "commandId": "compile-1",
            "requestHash": "sha256:" + HEX_B, "runRef": run_ref, "taskId": "task-1",
            "planRef": {"resourceType": "PlanRevision", "resourceId": "plan-1", "revision": 1, "contentHash": HEX_A},
            "profileRef": {"resourceType": "InvestigationProfileRevision", "resourceId": "profile-1", "revision": 1, "contentHash": HEX_A},
            "logicRef": {"resourceType": "LogicRevision", "resourceId": "logic-1", "revision": 1, "contentHash": HEX_A},
            "skillBindingSetRef": {"resourceType": "SkillBindingSetRevision", "resourceId": "skills-1", "revision": 1, "contentHash": HEX_A},
            "responsibilityPlanRef": {"resourceType": "ResponsibilityPlanRevision", "resourceId": "responsibility-1", "revision": 1, "contentHash": HEX_A},
            "inputHash": HEX_A, "stageCompilationHash": HEX_A,
            "compilationHash": HEX_B, "runtimeAuthorized": False, "createdAt": NOW,
        }
    )
    timeline = TaskTimeline(
        task=AipTaskStore._task(task_row), plan=AipTaskStore._plan(plan_row),
        run=AipTaskStore._run(runtime_start_row), checkpoints=[],
    )
    binding = BusinessInvestigationRuntimeBinder._binding_from_lineage(
        tenant=tenant,
        case_ref=BusinessInvestigationRuntimeBinder._aip_ref(domain.case_ref, expected_type="BusinessInvestigationCaseRevision"),
        run_ref=BusinessInvestigationRuntimeBinder._aip_ref(compilation.run_ref, expected_type="BusinessInvestigationRun"),
        compilation_hash=compilation.compilation_hash, task_id=compilation.task_id,
        expected_plan_ref=compilation.plan_ref, task_run_id="task-run-1", timeline=timeline,
    )
    body = {
        "requestHash": "sha256:" + HEX_B,
        "runRef": run_ref,
        "compilationRef": compilation.exact_ref.model_dump(
            mode="json", by_alias=True, exclude_none=True
        ),
        "planRef": {"resourceType": "PlanRevision", "resourceId": "plan-1", "revision": 1, "contentHash": "sha256:" + HEX_A},
        "taskRunRef": {"resourceType": "TaskRun", "resourceId": "task-run-1", "revision": 1, "contentHash": "sha256:" + binding.binding_hash},
        "phase": "PREPARING", "completed": False,
    }
    receipt_ref = {
        "resourceType": "AnalysisRuntimeReceipt", "resourceId": "analysis-receipt-1",
        "revision": 1, "contentHash": _analysis_command_hash(body),
        "receiptId": "analysis-receipt-1",
    }
    response = {"receiptRef": receipt_ref, **body}
    state = BusinessInvestigationRunStateRevision.model_validate(
        {
            "tenant": tenant.model_dump(mode="json", by_alias=True),
            "runId": domain.run_id,
            "version": 1,
            "lifecycle": "PREPARING",
            "control": "RUNNING",
            "eventSequence": 1,
            "contentHash": "sha256:" + "0" * 64,
            "createdBy": "analyst",
            "createdAt": NOW,
        }
    )
    state = state.model_copy(update={"content_hash": state.calculated_content_hash()})
    return {
        "receipt": {"request_hash": body["requestHash"], "response": response, "target_receipt_ref": receipt_ref},
        "run": {
            "run_authority": domain.model_dump(mode="json", by_alias=True),
            "state_authority": state.model_dump(mode="json", by_alias=True),
        },
        "compilation": {"receipt_data": compilation.model_dump(mode="json", by_alias=True)},
        "runtime": runtime_row, "task": task_row, "plan": plan_row, "checkpoints": [],
        "command": {
            "analysisReceiptRef": receipt_ref,
            "caseRef": case_ref,
            "runRef": run_ref,
            "currentPlanRef": body["planRef"],
        },
    }


class Transaction:
    def __init__(self, values):
        self.values = values

    def execute(self, query, _params):
        key = (
            "receipt" if "runtime_command_receipt" in query else
            "run" if "ecommerce_investigation_run run" in query else
            "compilation" if "compile_receipt" in query else
            "runtime" if "aip_task_run" in query else
            "task" if "aip_task\n" in query else
            "plan" if "aip_plan_revision" in query else "checkpoints"
        )
        value = self.values[key]

        class Result:
            def fetchone(self): return value
            def fetchall(self): return value if isinstance(value, list) else [value]

        return Result()


def test_sales_weapon_review_requires_original_analysis_cutoff():
    values = authorities()
    with pytest.raises(ValueError, match="cutoff"):
        ReviewAdvanceHostService._revalidate_analysis_runtime(
            transaction=Transaction(values), scope=SCOPE, command=values["command"],
            artifact_task_run_id="task-run-1", expected_cutoff=NOW.isoformat(),
        )


@pytest.mark.parametrize(
    "drift",
    [
        "receipt_hash",
        "run",
        "case",
        "state_hash",
        "state_control",
        "plan",
        "task_run_status",
        "artifact_run",
        "compilation_bool",
        "compilation_tenant",
    ],
)
def test_review_analysis_runtime_exact_lineage(drift):
    values = authorities()
    command = deepcopy(values["command"])
    artifact_run = "task-run-1"
    if drift == "receipt_hash":
        command["analysisReceiptRef"]["contentHash"] = "sha256:" + HEX_B
    elif drift == "run":
        command["runRef"]["contentHash"] = "sha256:" + HEX_B
    elif drift == "case":
        command["caseRef"]["resourceId"] = "case-2"
    elif drift == "state_hash":
        values["run"]["state_authority"]["contentHash"] = "sha256:" + HEX_B
    elif drift == "state_control":
        state = values["run"]["state_authority"]
        state.update(
            {
                "version": 2,
                "eventSequence": 2,
                "priorRef": {
                    "resourceType": "BusinessInvestigationRunStateRevision",
                    "resourceId": "investigation-run-1",
                    "revision": 1,
                    "contentHash": "sha256:" + HEX_A,
                },
                "control": "CANCELLED",
            }
        )
        parsed = BusinessInvestigationRunStateRevision.model_validate(
            {**state, "contentHash": "sha256:" + "0" * 64}
        )
        state["contentHash"] = parsed.calculated_content_hash()
    elif drift == "plan":
        command["currentPlanRef"]["revision"] = 2
    elif drift == "task_run_status":
        values["runtime"]["status"] = "queued"
    elif drift == "artifact_run":
        artifact_run = "task-run-2"
    elif drift == "compilation_bool":
        values["compilation"]["receipt_data"]["planRef"]["revision"] = True
    elif drift == "compilation_tenant":
        values["compilation"]["receipt_data"]["tenant"]["orgId"] = "dev-org"
    if drift:
        with pytest.raises(ValueError):
            ReviewAdvanceHostService._revalidate_analysis_runtime(
                transaction=Transaction(values), scope=SCOPE, command=command,
                artifact_task_run_id=artifact_run,
            )


def test_review_analysis_runtime_accepts_exact_authorities():
    values = authorities()
    ReviewAdvanceHostService._revalidate_analysis_runtime(
        transaction=Transaction(values), scope=SCOPE, command=values["command"],
        artifact_task_run_id="task-run-1",
    )


def test_review_analysis_runtime_locks_current_mutable_authorities():
    values = authorities()
    transaction = Transaction(values)
    queries = []
    original = transaction.execute

    def execute(query, params):
        queries.append(query)
        return original(query, params)

    transaction.execute = execute
    ReviewAdvanceHostService._revalidate_analysis_runtime(
        transaction=transaction,
        scope=SCOPE,
        command=values["command"],
        artifact_task_run_id="task-run-1",
    )
    assert any("FOR SHARE OF state" in query for query in queries)
    assert sum("FOR SHARE" in query for query in queries) == 3
