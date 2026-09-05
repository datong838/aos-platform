"""Canonical internal-only media task preparation and recovery workflow."""
from __future__ import annotations

from copy import deepcopy
from typing import Callable, Protocol

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractError
from aos_api.aip_production_contracts import CreateBriefRequest, ReviseBriefRequest
from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore, AipTaskStoreError
from aos_api.db import connect_read_only
from aos_api.ecommerce_media_internal_workflow_contracts import (
    ALLOWED_DETAIL_KEYS,
    MediaInternalWorkflowCommandRequest,
    MediaInternalWorkflowCommandResponse,
    MediaInternalWorkflowDraft,
    MediaInternalWorkflowHistoryResponse,
    MediaInternalWorkflowListResponse,
    MediaInternalWorkflowReceipt,
    MediaInternalWorkflowSideEffects,
)
from aos_api.tenant_scope import TenantScope


class MediaInternalWorkflowError(RuntimeError):
    code = "MEDIA_INTERNAL_WORKFLOW_ERROR"


class MediaInternalWorkflowConflict(MediaInternalWorkflowError):
    code = "MEDIA_INTERNAL_WORKFLOW_CONFLICT"


class TaskAuthority(Protocol):
    def create_task(self, scope, actor, idempotency_key, body): ...


class BriefAuthority(Protocol):
    def create_brief(self, scope, actor, key, body): ...
    def revise_brief(self, scope, actor, brief_id, key, body): ...
    def get_brief(self, scope, brief_id, revision=None): ...
    def list_briefs(self, scope): ...


class EcommerceMediaInternalWorkflow:
    _STATUSES = {"draft", "prepared", "paused", "returned", "scheduled"}
    _MEDIA_TYPES = {"planting_copy", "short_video", "digital_human_live"}
    _PATCH_COMMANDS = {"save_input", "attach_evidence", "reassign"}
    _PREPARE_COMMANDS = {"prepare_batch", "prepare_sample", "select_template", "prepare_live"}
    _REQUIRED_DETAILS = {
        "attach_evidence": "evidence", "reassign": "assignee", "prepare_batch": "batch",
        "prepare_sample": "sample", "select_template": "template", "schedule": "schedule",
        "prepare_live": "liveControl", "return": "returnReason",
    }

    def __init__(self, task_store: TaskAuthority | None = None, brief_store: BriefAuthority | None = None, receipt_reader: Callable[[TenantScope, str, str], str | None] | None = None) -> None:
        self._tasks = task_store or AipTaskStore()
        self._briefs = brief_store or AipProductionContractStore()
        self._receipt_reader = receipt_reader or self._receipt

    def execute(self, scope: TenantScope, actor: str, idempotency_key: str, body: MediaInternalWorkflowCommandRequest) -> MediaInternalWorkflowCommandResponse:
        key = idempotency_key.strip()
        if not key or len(key) > 120:
            raise MediaInternalWorkflowConflict("Idempotency-Key must be 1..120 characters")
        operation = "task_brief.create" if body.command == "create" else "task_brief.revise"
        receipt_key = f"{key}:media-brief"
        replay = self._receipt_reader(scope, operation, receipt_key) is not None
        try:
            if body.command == "create":
                details = self._merge_details({}, body.details, body.media_type, body.command)
                task = self._tasks.create_task(scope, actor, f"{key}:media-task", CreateTaskRequest(
                    type="ecommerce.workshop.media_internal_task",
                    title=body.title,
                    description="多媒体内容生产工作台内部准备与协作任务。",
                    goal={"mediaType": body.media_type, "externalEffectsAllowed": False},
                ))
                draft = self._briefs.create_brief(scope, actor, receipt_key, CreateBriefRequest(
                    task_id=task.id,
                    brief_type="media_internal_workflow",
                    schema_ref=self._schema_ref(),
                    spec=self._spec(body, details, "draft"),
                ))
                task_id = task.id
            else:
                assert body.draft_ref is not None and body.expected_version is not None
                current = self._briefs.get_brief(
                    scope,
                    body.draft_ref.resource_id,
                    body.draft_ref.revision if replay else None,
                )
                self._require_media_brief(current)
                if replay:
                    self._require_replay_exact(
                        current, body.draft_ref, body.expected_version
                    )
                else:
                    self._require_exact(current, body.draft_ref, body.expected_version)
                current_status = current.spec["status"]
                self._require_transition(current_status, body.command)
                if current.spec["mediaType"] != body.media_type:
                    raise MediaInternalWorkflowConflict("media workflow mediaType is immutable")
                self._require_command_payload(body.command, body.details)
                details = self._merge_details(current.spec.get("details", {}), body.details, body.media_type, body.command)
                next_status = self._next_status(current_status, body.command, details)
                draft = self._briefs.revise_brief(scope, actor, current.brief_id, receipt_key, ReviseBriefRequest(
                    expected_version=body.expected_version,
                    brief_type="media_internal_workflow",
                    schema_ref=self._schema_ref(),
                    spec=self._spec(body, details, next_status),
                ))
                task_id = draft.task_id
        except (ProductionContractError, AipTaskStoreError, ValueError, KeyError) as exc:
            raise MediaInternalWorkflowConflict(str(exc)) from exc
        receipt_id = self._receipt_reader(scope, operation, receipt_key)
        if receipt_id is None:
            raise MediaInternalWorkflowError("canonical Brief Receipt is unavailable")
        messages = {
            "create": "内部生产任务已创建。", "save_input": "业务输入已保存。",
            "attach_evidence": "生产证据已补充。", "pause": "内部生产任务已暂停。",
            "resume": "内部生产任务已继续。", "return": "任务已退回调整。",
            "reassign": "负责人已改派。", "prepare_batch": "批量生产准备已保存。",
            "prepare_sample": "样片准备已保存。", "select_template": "模板选择已保存。",
            "schedule": "生产排期已保存。", "prepare_live": "直播控制准备已保存。",
        }
        return MediaInternalWorkflowCommandResponse(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            command=body.command,
            task_id=task_id,
            draft=self._draft(
                draft,
                version=(1 if body.command == "create" else body.expected_version + 1)
                if replay
                else None,
            ),
            receipt=MediaInternalWorkflowReceipt(receipt_id=receipt_id, operation=operation, idempotency_key=receipt_key, replay=replay),
            side_effects=MediaInternalWorkflowSideEffects(),
            message=messages[body.command],
        )

    def history(self, scope: TenantScope, brief_id: str) -> MediaInternalWorkflowHistoryResponse:
        try:
            current = self._briefs.get_brief(scope, brief_id)
            self._require_media_brief(current)
            items = []
            for revision in range(1, current.revision + 1):
                value = self._briefs.get_brief(scope, brief_id, revision)
                self._require_media_brief(value)
                items.append(self._draft(value, version=revision))
        except (ProductionContractError, ValueError, KeyError) as exc:
            raise MediaInternalWorkflowConflict(str(exc)) from exc
        return MediaInternalWorkflowHistoryResponse(tenant=self._tenant(scope), items=items, count=len(items))

    def list(self, scope: TenantScope) -> MediaInternalWorkflowListResponse:
        try:
            items = []
            for value in self._briefs.list_briefs(scope).items:
                if value.brief_type != "media_internal_workflow":
                    continue
                self._require_media_brief(value)
                items.append(self._draft(value))
            items.sort(key=lambda item: (item.title, item.resource_id))
        except (ProductionContractError, ValueError, KeyError) as exc:
            raise MediaInternalWorkflowConflict(str(exc)) from exc
        return MediaInternalWorkflowListResponse(tenant=self._tenant(scope), items=items, count=len(items))

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _schema_ref() -> ResourceRef:
        return ResourceRef(resource_type="MediaInternalWorkflowSchema", resource_id="schema://aos/ecommerce/media-internal-workflow/v1", revision="1", authority="aos://ecommerce-workshop/media-studio")

    @staticmethod
    def _spec(body: MediaInternalWorkflowCommandRequest, details: dict, status: str) -> dict:
        return {"mediaType": body.media_type, "title": body.title, "summary": body.summary, "details": details, "status": status, "externalEffectsAllowed": False}

    @classmethod
    def _merge_details(cls, current: dict, patch: dict, media_type: str, command: str) -> dict:
        if not isinstance(current, dict) or not isinstance(patch, dict):
            raise MediaInternalWorkflowConflict("media workflow details must be objects")
        unsupported = (set(current) | set(patch)) - ALLOWED_DETAIL_KEYS
        if unsupported:
            raise MediaInternalWorkflowConflict("media workflow details contain unsupported fields")
        details = deepcopy(current)
        details.update(deepcopy(patch))
        details["mediaType"] = media_type
        details["lastCommand"] = command
        return details

    @classmethod
    def _require_command_payload(cls, command: str, details: dict) -> None:
        required = cls._REQUIRED_DETAILS.get(command)
        if required is None:
            return
        value = details.get(required)
        if value in (None, "", [], {}):
            raise MediaInternalWorkflowConflict(f"{command} requires non-empty {required}")

    @classmethod
    def _next_status(cls, current_status: str, command: str, details: dict) -> str:
        if command in cls._PATCH_COMMANDS:
            return "draft" if current_status == "returned" else current_status
        if command in cls._PREPARE_COMMANDS:
            return "prepared"
        if command == "schedule":
            return "scheduled"
        if command == "pause":
            details["pausedFromStatus"] = current_status
            return "paused"
        if command == "resume":
            restored = details.pop("pausedFromStatus", None)
            if restored not in {"draft", "prepared", "scheduled"}:
                raise MediaInternalWorkflowConflict("pausedFromStatus is invalid")
            return restored
        if command == "return":
            details.pop("pausedFromStatus", None)
            return "returned"
        raise MediaInternalWorkflowConflict(f"unsupported command {command}")

    @classmethod
    def _require_media_brief(cls, value) -> None:
        if value.brief_type != "media_internal_workflow" or value.schema_ref != cls._schema_ref():
            raise MediaInternalWorkflowConflict("task brief is not a media internal workflow")
        spec = value.spec
        if not isinstance(spec, dict) or spec.get("externalEffectsAllowed") is not False:
            raise MediaInternalWorkflowConflict("media workflow safety marker is invalid")
        if spec.get("mediaType") not in cls._MEDIA_TYPES or spec.get("status") not in cls._STATUSES:
            raise MediaInternalWorkflowConflict("media workflow state is invalid")
        if not isinstance(spec.get("title"), str) or not isinstance(spec.get("summary"), str) or not isinstance(spec.get("details"), dict):
            raise MediaInternalWorkflowConflict("media workflow content is invalid")
        if set(spec["details"]) - ALLOWED_DETAIL_KEYS or spec["details"].get("mediaType") != spec["mediaType"]:
            raise MediaInternalWorkflowConflict("media workflow details are invalid")

    @staticmethod
    def _require_exact(current, exact, expected_version: int) -> None:
        if current.brief_id != exact.resource_id or current.revision != exact.revision or current.content_hash != exact.content_hash or current.version != expected_version:
            raise MediaInternalWorkflowConflict("draft exact ref or expectedVersion is stale")

    @staticmethod
    def _require_replay_exact(current, exact, expected_version: int) -> None:
        if (
            current.brief_id != exact.resource_id
            or current.revision != exact.revision
            or current.content_hash != exact.content_hash
            or expected_version != exact.revision
        ):
            raise MediaInternalWorkflowConflict(
                "draft exact ref or expectedVersion is stale"
            )

    @staticmethod
    def _require_transition(status: str, command: str) -> None:
        allowed = {
            "save_input": {"draft", "prepared", "returned", "scheduled"},
            "attach_evidence": {"draft", "prepared", "returned", "scheduled"},
            "reassign": {"draft", "prepared", "returned", "scheduled"},
            "prepare_batch": {"draft", "prepared", "returned"},
            "prepare_sample": {"draft", "prepared", "returned"},
            "select_template": {"draft", "prepared", "returned"},
            "prepare_live": {"draft", "prepared", "returned"},
            "schedule": {"draft", "prepared", "returned", "scheduled"},
            "pause": {"draft", "prepared", "scheduled"},
            "resume": {"paused"},
            "return": {"prepared", "paused", "scheduled"},
        }
        if status not in allowed[command]:
            raise MediaInternalWorkflowConflict(f"command {command} is not allowed from status {status}")

    @staticmethod
    def _draft(value, *, version: int | None = None) -> MediaInternalWorkflowDraft:
        return MediaInternalWorkflowDraft(
            resource_id=value.brief_id, revision=value.revision, version=version or value.version,
            content_hash=value.content_hash, media_type=value.spec["mediaType"], title=value.spec["title"],
            summary=value.spec["summary"], details=value.spec["details"], status=value.spec["status"],
        )

    @staticmethod
    def _receipt(scope: TenantScope, operation: str, key: str) -> str | None:
        with connect_read_only(scope) as conn:
            row = conn.execute("SELECT receipt_id FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s", (*scope.key, operation, key)).fetchone()
        return str(row["receipt_id"]) if row else None
