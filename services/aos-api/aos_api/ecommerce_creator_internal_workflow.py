"""Canonical internal-only creator drafting, review and history workflow."""
from __future__ import annotations

from typing import Callable, Protocol

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractError
from aos_api.aip_production_contracts import CreateBriefRequest, ReviseBriefRequest
from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore, AipTaskStoreError
from aos_api.db import connect_read_only
from aos_api.ecommerce_creator_internal_workflow_contracts import (
    CreatorInternalWorkflowCommandRequest, CreatorInternalWorkflowCommandResponse,
    CreatorInternalWorkflowDraft, CreatorInternalWorkflowHistoryResponse,
    CreatorInternalWorkflowListResponse, CreatorInternalWorkflowReceipt,
    CreatorInternalWorkflowSideEffects,
)
from aos_api.tenant_scope import TenantScope


class CreatorInternalWorkflowError(RuntimeError):
    code = "CREATOR_INTERNAL_WORKFLOW_ERROR"


class CreatorInternalWorkflowConflict(CreatorInternalWorkflowError):
    code = "CREATOR_INTERNAL_WORKFLOW_CONFLICT"


class TaskAuthority(Protocol):
    def create_task(self, scope, actor, idempotency_key, body): ...


class BriefAuthority(Protocol):
    def create_brief(self, scope, actor, key, body): ...
    def revise_brief(self, scope, actor, brief_id, key, body): ...
    def get_brief(self, scope, brief_id, revision=None): ...
    def list_briefs(self, scope): ...


class EcommerceCreatorInternalWorkflow:
    def __init__(self, task_store: TaskAuthority | None = None, brief_store: BriefAuthority | None = None, receipt_reader: Callable[[TenantScope, str, str], str | None] | None = None) -> None:
        self._tasks = task_store or AipTaskStore()
        self._briefs = brief_store or AipProductionContractStore()
        self._receipt_reader = receipt_reader or self._receipt

    def execute(self, scope: TenantScope, actor: str, idempotency_key: str, body: CreatorInternalWorkflowCommandRequest) -> CreatorInternalWorkflowCommandResponse:
        key = idempotency_key.strip()
        if not key or len(key) > 120:
            raise CreatorInternalWorkflowConflict("Idempotency-Key must be 1..120 characters")
        operation = "task_brief.create" if body.command == "create" else "task_brief.revise"
        receipt_key = f"{key}:creator-brief"
        replay = self._receipt_reader(scope, operation, receipt_key) is not None
        try:
            if body.command == "create":
                task = self._tasks.create_task(scope, actor, f"{key}:creator-task", CreateTaskRequest(
                    type="ecommerce.workshop.creator_internal_task", title=body.title,
                    description="达人邀约驾驶舱内部业务准备与审核任务。",
                    goal={"purpose": body.purpose, "externalEffectsAllowed": False},
                ))
                draft = self._briefs.create_brief(scope, actor, receipt_key, CreateBriefRequest(
                    task_id=task.id, brief_type="creator_internal_workflow", schema_ref=self._schema_ref(), spec=self._spec(body, "draft"),
                ))
                task_id = task.id
            else:
                assert body.draft_ref is not None and body.expected_version is not None
                current = self._briefs.get_brief(scope, body.draft_ref.resource_id)
                self._require_creator_brief(current)
                self._require_exact(current, body.draft_ref, body.expected_version)
                self._require_transition(current.spec.get("status", "draft"), body.command)
                if current.spec["purpose"] != body.purpose:
                    raise CreatorInternalWorkflowConflict("creator workflow purpose is immutable")
                if body.command == "restore":
                    assert body.restore_revision is not None
                    if body.restore_revision >= current.revision:
                        raise CreatorInternalWorkflowConflict(
                            "restoreRevision must reference an earlier revision"
                        )
                    previous = self._briefs.get_brief(scope, current.brief_id, body.restore_revision)
                    self._require_creator_brief(previous)
                    if previous.spec["purpose"] != current.spec["purpose"]:
                        raise CreatorInternalWorkflowConflict("creator workflow history purpose drift")
                    spec = dict(previous.spec)
                    spec["status"] = "draft"
                    spec["restoredFromRevision"] = body.restore_revision
                else:
                    status = {"save": "draft", "submit_review": "in_review", "approve": "approved", "reject": "rejected"}[body.command]
                    spec = self._spec(body, status)
                draft = self._briefs.revise_brief(scope, actor, current.brief_id, receipt_key, ReviseBriefRequest(
                    expected_version=body.expected_version, brief_type="creator_internal_workflow", schema_ref=self._schema_ref(), spec=spec,
                ))
                task_id = draft.task_id
        except (ProductionContractError, AipTaskStoreError, ValueError) as exc:
            raise CreatorInternalWorkflowConflict(str(exc)) from exc
        receipt_id = self._receipt_reader(scope, operation, receipt_key)
        if receipt_id is None:
            raise CreatorInternalWorkflowError("canonical Brief Receipt is unavailable")
        return CreatorInternalWorkflowCommandResponse(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id), command=body.command,
            task_id=task_id, draft=self._draft(draft),
            receipt=CreatorInternalWorkflowReceipt(receipt_id=receipt_id, operation=operation, idempotency_key=receipt_key, replay=replay),
            side_effects=CreatorInternalWorkflowSideEffects(),
            message={"create":"内部业务草稿已创建。","save":"修改已保存为新版本。","submit_review":"已提交内部审核。","approve":"内部审核已批准。","reject":"内部审核已驳回。","restore":"历史版本已恢复为新草稿。"}[body.command],
        )

    def history(self, scope: TenantScope, brief_id: str) -> CreatorInternalWorkflowHistoryResponse:
        try:
            current = self._briefs.get_brief(scope, brief_id)
            self._require_creator_brief(current)
            items = []
            for revision in range(1, current.revision + 1):
                value = self._briefs.get_brief(scope, brief_id, revision)
                self._require_creator_brief(value)
                items.append(self._draft(value, version=revision))
        except (ProductionContractError, ValueError) as exc:
            raise CreatorInternalWorkflowConflict(str(exc)) from exc
        return CreatorInternalWorkflowHistoryResponse(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id), items=items, count=len(items))

    def list(self, scope: TenantScope) -> CreatorInternalWorkflowListResponse:
        try:
            values = self._briefs.list_briefs(scope).items
            items = []
            seen_purposes: set[str] = set()
            for value in values:
                if value.brief_type != "creator_internal_workflow":
                    continue
                self._require_creator_brief(value)
                purpose = value.spec["purpose"]
                if purpose in seen_purposes:
                    continue
                seen_purposes.add(purpose)
                items.append(self._draft(value))
        except (ProductionContractError, ValueError) as exc:
            raise CreatorInternalWorkflowConflict(str(exc)) from exc
        return CreatorInternalWorkflowListResponse(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            items=items,
            count=len(items),
        )

    @staticmethod
    def _schema_ref() -> ResourceRef:
        return ResourceRef(resource_type="CreatorInternalWorkflowSchema", resource_id="schema://aos/ecommerce/creator-internal-workflow/v1", revision="1", authority="aos://ecommerce-workshop/creator-growth")

    @staticmethod
    def _spec(body: CreatorInternalWorkflowCommandRequest, status: str) -> dict:
        return {"purpose": body.purpose, "title": body.title, "summary": body.summary, "details": body.details, "status": status, "externalEffectsAllowed": False}

    @staticmethod
    def _draft(value, *, version: int | None = None) -> CreatorInternalWorkflowDraft:
        return CreatorInternalWorkflowDraft(resource_id=value.brief_id, revision=value.revision, version=version or value.version, content_hash=value.content_hash, purpose=value.spec["purpose"], title=value.spec["title"], summary=value.spec["summary"], details=value.spec.get("details", {}), status=value.spec.get("status", "draft"))

    @classmethod
    def _require_creator_brief(cls, value) -> None:
        if value.brief_type != "creator_internal_workflow" or value.schema_ref != cls._schema_ref():
            raise CreatorInternalWorkflowConflict("task brief is not a creator internal workflow")
        spec = value.spec
        if not isinstance(spec, dict) or spec.get("externalEffectsAllowed") is not False:
            raise CreatorInternalWorkflowConflict("creator workflow safety marker is invalid")
        if spec.get("purpose") not in {"candidate_import", "outreach_batch", "outreach_message", "collaboration", "delivery_check", "relationship_plan"}:
            raise CreatorInternalWorkflowConflict("creator workflow purpose is invalid")
        if spec.get("status") not in {"draft", "in_review", "approved", "rejected"}:
            raise CreatorInternalWorkflowConflict("creator workflow status is invalid")
        if not isinstance(spec.get("title"), str) or not isinstance(spec.get("summary"), str) or not isinstance(spec.get("details", {}), dict):
            raise CreatorInternalWorkflowConflict("creator workflow content is invalid")

    @staticmethod
    def _require_exact(current, exact, expected_version: int) -> None:
        if current.brief_id != exact.resource_id or current.revision != exact.revision or current.content_hash != exact.content_hash or current.version != expected_version:
            raise CreatorInternalWorkflowConflict("draft exact ref or expectedVersion is stale")

    @staticmethod
    def _require_transition(current_status: str, command: str) -> None:
        allowed = {
            "save": {"draft", "rejected"},
            "submit_review": {"draft", "rejected"},
            "approve": {"in_review"},
            "reject": {"in_review"},
            "restore": {"draft", "in_review", "approved", "rejected"},
        }
        if current_status not in allowed[command]:
            raise CreatorInternalWorkflowConflict(
                f"command {command} is not allowed from status {current_status}"
            )

    @staticmethod
    def _receipt(scope: TenantScope, operation: str, key: str) -> str | None:
        with connect_read_only(scope) as conn:
            row = conn.execute("SELECT receipt_id FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s", (*scope.key, operation, key)).fetchone()
        return str(row["receipt_id"]) if row else None
