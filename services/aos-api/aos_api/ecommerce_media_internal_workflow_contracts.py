"""Contracts for the tenant-safe media internal production workflow."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef

MediaWorkflowCommand = Literal[
    "create", "save_input", "attach_evidence", "pause", "resume", "return",
    "reassign", "prepare_batch", "prepare_sample", "select_template", "schedule",
    "prepare_live",
]
MediaWorkflowMediaType = Literal["planting_copy", "short_video", "digital_human_live"]
MediaWorkflowStatus = Literal["draft", "prepared", "paused", "returned", "scheduled"]

ALLOWED_DETAIL_KEYS = {
    "mediaType", "businessObject", "objective", "assignee", "evidence", "batch",
    "sample", "template", "schedule", "liveControl", "pausedFromStatus",
    "returnReason", "lastCommand",
}

_EVIDENCE_ITEM_KEYS = {"source", "reference", "description"}
_SENSITIVE_DETAIL_KEYS = {
    "apikey", "authorization", "baseurl", "cookie", "credential", "credentials",
    "databaseurl", "dsn", "endpoint", "model", "modelid", "password", "provider",
    "providerid", "providerparams", "providertoken", "query", "secret", "sql",
    "statement", "token",
}
_SQL_PREFIXES = (
    "select ", "insert ", "update ", "delete ", "drop ", "alter ",
    "create ", "truncate ", "grant ", "revoke ",
)


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _validate_safe_detail_value(value: Any, *, path: str, depth: int = 0) -> None:
    if depth > 6:
        raise ValueError(f"{path} nesting is too deep")
    if isinstance(value, dict):
        if len(value) > 50:
            raise ValueError(f"{path} has too many fields")
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 80:
                raise ValueError(f"{path} contains an invalid field name")
            if _normalized_key(key) in _SENSITIVE_DETAIL_KEYS:
                raise ValueError(f"{path} contains sensitive or external provider parameters")
            _validate_safe_detail_value(item, path=f"{path}.{key}", depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > 100:
            raise ValueError(f"{path} has too many items")
        for index, item in enumerate(value):
            _validate_safe_detail_value(item, path=f"{path}[{index}]", depth=depth + 1)
        return
    if isinstance(value, str):
        if len(value) > 2000:
            raise ValueError(f"{path} text is too long")
        if value.strip().casefold().startswith(_SQL_PREFIXES):
            raise ValueError(f"{path} must not contain SQL")
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        raise ValueError(f"{path} contains an unsupported value")


def _validate_evidence(value: Any) -> None:
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError("evidence must be a list of business source descriptions or references")
    for item in value:
        if isinstance(item, str):
            if not item.strip() or len(item) > 500 or item.strip().casefold().startswith(_SQL_PREFIXES):
                raise ValueError("evidence contains an invalid business source description")
            continue
        if not isinstance(item, dict) or not item or set(item) - _EVIDENCE_ITEM_KEYS:
            raise ValueError("evidence items only accept source, reference and description")
        if any(not isinstance(entry, str) or not entry.strip() or len(entry) > 500 for entry in item.values()):
            raise ValueError("evidence source fields must be non-empty text")


class MediaInternalWorkflowCommandRequest(AipContractModel):
    command: MediaWorkflowCommand
    media_type: MediaWorkflowMediaType
    title: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=2, max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)
    draft_ref: ExactRevisionRef | None = None
    expected_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _workflow_contract(self) -> "MediaInternalWorkflowCommandRequest":
        revising = self.command != "create"
        if revising != (self.draft_ref is not None and self.expected_version is not None):
            raise ValueError("revision commands require draftRef and expectedVersion")
        if self.draft_ref and self.draft_ref.resource_type != "TaskBriefRevision":
            raise ValueError("draftRef must reference TaskBriefRevision")
        unsupported = sorted(set(self.details) - ALLOWED_DETAIL_KEYS)
        if unsupported:
            raise ValueError(f"unsupported media workflow details: {', '.join(unsupported)}")
        if "evidence" in self.details:
            _validate_evidence(self.details["evidence"])
        _validate_safe_detail_value(self.details, path="details")
        return self


class MediaInternalWorkflowDraft(ExactRevisionRef):
    resource_type: Literal["TaskBriefRevision"] = "TaskBriefRevision"
    version: int = Field(ge=1)
    media_type: MediaWorkflowMediaType
    title: str
    summary: str
    details: dict[str, Any]
    status: MediaWorkflowStatus


class MediaInternalWorkflowReceipt(AipContractModel):
    receipt_id: str
    operation: Literal["task_brief.create", "task_brief.revise"]
    idempotency_key: str
    replay: bool


class MediaInternalWorkflowSideEffects(AipContractModel):
    provider_invocation_count: Literal[0] = 0
    external_generation_count: Literal[0] = 0
    fee_charge_count: Literal[0] = 0
    publication_count: Literal[0] = 0
    business_mutation_count: Literal[0] = 0


class MediaInternalWorkflowCommandResponse(AipContractModel):
    tenant: TenantContext
    command: MediaWorkflowCommand
    task_id: str
    draft: MediaInternalWorkflowDraft
    receipt: MediaInternalWorkflowReceipt
    side_effects: MediaInternalWorkflowSideEffects
    message: str


class MediaInternalWorkflowHistoryResponse(AipContractModel):
    tenant: TenantContext
    items: list[MediaInternalWorkflowDraft]
    count: int = Field(ge=0)


class MediaInternalWorkflowListResponse(MediaInternalWorkflowHistoryResponse):
    pass
