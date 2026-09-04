"""Tenant-safe internal drafting and approval-preview workflow."""

from __future__ import annotations

import re
from typing import Callable, Protocol

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractConflict,
    ProductionContractDependencyBlocked,
    ProductionContractError,
    ProductionContractNotFound,
)
from aos_api.aip_production_contracts import (
    CreateBriefRequest,
    ReviseBriefRequest,
    TaskBriefRevision,
)
from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import (
    AipTaskIdempotencyConflict,
    AipTaskStore,
    AipTaskStoreError,
)
from aos_api.db import connect_read_only
from aos_api.ecommerce_content_campaign_workflow_contracts import (
    ContentCampaignApprovalCheck,
    ContentCampaignApprovalPreviewRequest,
    ContentCampaignApprovalPreviewResponse,
    ContentCampaignWorkflowCommandRequest,
    ContentCampaignWorkflowCommandResponse,
    ContentCampaignWorkflowDraft,
    ContentCampaignWorkflowReceipt,
    ContentCampaignWorkflowSideEffects,
    ContentCampaignWorkflowTask,
)
from aos_api.ecommerce_workshop_content_campaign import EcommerceWorkshopContentCampaign
from aos_api.tenant_scope import TenantScope


class ContentCampaignWorkflowError(RuntimeError):
    code = "CONTENT_CAMPAIGN_WORKFLOW_ERROR"


class ContentCampaignWorkflowConflict(ContentCampaignWorkflowError):
    code = "CONTENT_CAMPAIGN_WORKFLOW_CONFLICT"


class ContentCampaignWorkflowUnavailable(ContentCampaignWorkflowError):
    code = "CONTENT_CAMPAIGN_WORKFLOW_UNAVAILABLE"


class TaskAuthority(Protocol):
    def create_task(self, scope, actor, idempotency_key, body): ...


class BriefAuthority(Protocol):
    def create_brief(self, scope, actor, key, body): ...
    def revise_brief(self, scope, actor, brief_id, key, body): ...
    def get_brief(self, scope, brief_id, revision=None): ...


ReceiptReader = Callable[[TenantScope, str, str], str | None]


class EcommerceContentCampaignWorkflow:
    def __init__(
        self,
        *,
        task_store: TaskAuthority | None = None,
        brief_store: BriefAuthority | None = None,
        campaign_reader: EcommerceWorkshopContentCampaign | None = None,
        receipt_reader: ReceiptReader | None = None,
    ) -> None:
        self._tasks = task_store or AipTaskStore()
        self._briefs = brief_store or AipProductionContractStore()
        self._campaigns = campaign_reader or EcommerceWorkshopContentCampaign()
        self._receipt_reader = receipt_reader or self._read_receipt

    def execute(
        self,
        scope: TenantScope,
        *,
        actor: str,
        idempotency_key: str,
        body: ContentCampaignWorkflowCommandRequest,
    ) -> ContentCampaignWorkflowCommandResponse:
        key = idempotency_key.strip()
        if not key or len(key) > 120:
            raise ContentCampaignWorkflowConflict("Idempotency-Key must be 1..120 characters")
        operation = "task_brief.create" if body.command == "generate" else "task_brief.revise"
        receipt_key = f"{key}:brief"
        replay = self._receipt_reader(scope, operation, receipt_key) is not None
        try:
            if body.command == "generate":
                task = self._tasks.create_task(
                    scope,
                    actor,
                    f"{key}:task",
                    CreateTaskRequest(
                        type="ecommerce.workshop.business_task",
                        title=self._task_title(body.objective),
                        description="根据运营人员提交的目标形成内容与活动草稿。",
                        goal={
                            "objective": body.objective,
                            "workshopAssignment": {
                                "roleKey": "campaign_planner",
                                "colleagueName": "活动策划师",
                                "status": "requested",
                            },
                        },
                    ),
                )
                task_id = task.id
                draft = self._briefs.create_brief(
                    scope,
                    actor,
                    receipt_key,
                    CreateBriefRequest(
                        task_id=task_id,
                        brief_type="content_campaign",
                        schema_ref=self._schema_ref(),
                        spec=self._spec(body),
                    ),
                )
            else:
                exact = body.draft_ref
                assert exact is not None and body.expected_version is not None
                current = self._briefs.get_brief(scope, exact.resource_id)
                self._require_exact(current, exact, body.expected_version)
                spec = self._revision_spec(scope, current, body)
                draft = self._briefs.revise_brief(
                    scope,
                    actor,
                    exact.resource_id,
                    receipt_key,
                    ReviseBriefRequest(
                        expected_version=body.expected_version,
                        brief_type="content_campaign",
                        schema_ref=self._schema_ref(),
                        spec=spec,
                    ),
                )
                task_id = draft.task_id
                task = type("Task", (), {"title": self._task_title(body.objective)})()
        except (
            AipTaskIdempotencyConflict,
            ProductionContractConflict,
            ProductionContractNotFound,
        ) as exc:
            raise ContentCampaignWorkflowConflict(str(exc)) from exc
        except (AipTaskStoreError, ProductionContractDependencyBlocked, ProductionContractError) as exc:
            raise ContentCampaignWorkflowUnavailable(str(exc)) from exc

        receipt_id = self._receipt_reader(scope, operation, receipt_key)
        if receipt_id is None:
            raise ContentCampaignWorkflowUnavailable("canonical Brief Receipt is unavailable")
        return ContentCampaignWorkflowCommandResponse(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            command=body.command,
            task=ContentCampaignWorkflowTask(task_id=task_id, title=task.title),
            draft=self._draft(draft),
            receipt=ContentCampaignWorkflowReceipt(
                receipt_id=receipt_id,
                operation=operation,
                idempotency_key=receipt_key,
                replay=replay,
            ),
            side_effects=ContentCampaignWorkflowSideEffects(),
            message={
                "generate": "活动方案草稿已生成，可继续编辑或执行审批前检查。",
                "save": "活动方案草稿已保存为新版本。",
                "regenerate": "已根据当前输入生成新版本，原版本保留可回读。",
                "apply_risk_decision": "风险决策与经营约束已写入新版本，可继续审阅或撤销。",
                "undo_risk_decision": "已撤销最近一次风险决策并生成新版本，历史版本保持可回读。",
            }[body.command],
        )

    def _revision_spec(
        self,
        scope: TenantScope,
        current: TaskBriefRevision,
        body: ContentCampaignWorkflowCommandRequest,
    ) -> dict:
        if body.command in {"save", "regenerate"}:
            next_spec = self._spec(body)
            next_spec["riskDecisions"] = list(current.spec.get("riskDecisions", []))
            return next_spec
        if body.command == "apply_risk_decision":
            assert body.risk_decision is not None
            next_spec = dict(current.spec)
            decisions = list(current.spec.get("riskDecisions", []))
            decisions = [item for item in decisions if item.get("category") != body.risk_decision.category]
            decisions.append(
                {
                    **body.risk_decision.model_dump(mode="json", by_alias=True),
                    "appliedFromRevision": current.revision,
                }
            )
            next_spec.update(
                {
                    "constraints": list(dict.fromkeys([*body.constraints, body.risk_decision.constraint])),
                    "riskDecisions": decisions,
                    "generationMode": body.command,
                    "lastAction": "risk_decision_applied",
                    "externalPublicationRequested": False,
                }
            )
            return next_spec
        if current.revision <= 1:
            raise ContentCampaignWorkflowConflict("no previous draft revision is available for undo")
        previous = self._briefs.get_brief(scope, current.brief_id, revision=current.revision - 1)
        next_spec = dict(previous.spec)
        next_spec.update(
            {
                "generationMode": body.command,
                "lastAction": "risk_decision_undone",
                "undoOfRevision": current.revision,
                "externalPublicationRequested": False,
            }
        )
        return next_spec

    def preview_approval(
        self,
        scope: TenantScope,
        body: ContentCampaignApprovalPreviewRequest,
    ) -> ContentCampaignApprovalPreviewResponse:
        try:
            draft = self._briefs.get_brief(scope, body.draft_ref.resource_id)
            self._require_exact(draft, body.draft_ref, draft.version)
            authority = self._campaigns.read(org_id=scope.org_id, project_id=scope.project_id)
        except (ProductionContractError, ValueError) as exc:
            raise ContentCampaignWorkflowConflict(str(exc)) from exc
        plan = next((item for item in authority.slices if str(item.slice_id) == "plan"), None)
        plan_ready = bool(
            plan is not None
            and str(plan.status) == "ready"
            and plan.count_ledger.eligible > 0
            and not plan.blockers
        )
        checks = [
            ContentCampaignApprovalCheck(name="草稿版本", passed=True, detail="已精确回读当前草稿版本。"),
            ContentCampaignApprovalCheck(
                name="经营目标与预算",
                passed=plan_ready,
                detail="已关联正式活动计划。" if plan_ready else "需关联同一租户的正式经营目标与预算版本。",
            ),
            ContentCampaignApprovalCheck(name="外部发布", passed=True, detail="本次仅预览，未创建发布动作。"),
        ]
        next_actions = [] if plan_ready else ["补充正式经营目标与预算版本"]
        if plan_ready:
            next_actions.append("提交独立审批，审批通过后再决定是否创建发布动作")
        return ContentCampaignApprovalPreviewResponse(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            status="reviewable" if plan_ready else "needs_input",
            approval_allowed=plan_ready,
            draft=self._draft(draft),
            checks=checks,
            next_actions=next_actions,
            evaluated_at=authority.evaluated_at,
            data_cutoff=authority.data_cutoff,
            side_effects=ContentCampaignWorkflowSideEffects(),
        )

    @staticmethod
    def _schema_ref() -> ResourceRef:
        return ResourceRef(
            resource_type="ContentCampaignBriefSchema",
            resource_id="schema://aos/ecommerce/content-campaign-brief/v1",
            revision="1",
            authority="aos://ecommerce-workshop/content-campaign",
        )

    @staticmethod
    def _spec(body: ContentCampaignWorkflowCommandRequest) -> dict:
        return {
            "objective": body.objective,
            "channels": body.channels,
            "audience": body.audience,
            "timeWindow": body.time_window,
            "constraints": body.constraints,
            "generationMode": body.command,
            "source": "operator_input",
            "externalPublicationRequested": False,
        }

    @staticmethod
    def _task_title(objective: str) -> str:
        subject = re.sub(r"^(策划|制定|创建|生成|设计)", "", objective).strip("，。 ")
        subject = subject[:80] or "内容与活动"
        return f"制定{subject}方案"

    @staticmethod
    def _draft(value: TaskBriefRevision) -> ContentCampaignWorkflowDraft:
        return ContentCampaignWorkflowDraft(
            resource_id=value.brief_id,
            revision=value.revision,
            version=value.version,
            content_hash=value.content_hash,
            objective=str(value.spec.get("objective", "")),
            channels=list(value.spec.get("channels", [])),
            constraints=list(value.spec.get("constraints", [])),
            risk_decisions=list(value.spec.get("riskDecisions", [])),
            last_action=value.spec.get("lastAction"),
        )

    @staticmethod
    def _require_exact(current: TaskBriefRevision, exact, expected_version: int) -> None:
        if (
            current.brief_id != exact.resource_id
            or current.revision != exact.revision
            or current.content_hash != exact.content_hash
            or current.version != expected_version
        ):
            raise ContentCampaignWorkflowConflict("draft exact ref or expectedVersion is stale")

    @staticmethod
    def _read_receipt(scope: TenantScope, operation: str, key: str) -> str | None:
        with connect_read_only(scope) as conn:
            row = conn.execute(
                "SELECT receipt_id FROM aip_production_contract_receipt "
                "WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
                (*scope.key, operation, key),
            ).fetchone()
        return str(row["receipt_id"]) if row else None
