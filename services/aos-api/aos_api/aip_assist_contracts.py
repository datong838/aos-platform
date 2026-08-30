"""Strict AIP-8 Assist contracts.

Client requests contain subject references only. Tenant, actor and every
runtime authority are resolved by the server and returned as exact refs.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext


def _require_exact(ref: ResourceRef, *, field: str) -> None:
    if not ref.revision:
        raise ValueError(f"{field} requires an exact revision")


def _require_exact_list(refs: list[ResourceRef], *, field: str) -> None:
    identities: list[tuple[str, str, str, str]] = []
    for ref in refs:
        _require_exact(ref, field=field)
        identities.append(
            (ref.resource_type, ref.resource_id, ref.revision or "", ref.authority)
        )
    if len(identities) != len(set(identities)):
        raise ValueError(f"{field} must not contain duplicates")


class AssistEventType(StrEnum):
    START = "start"
    CONTEXT = "context"
    BLOCKED = "blocked"
    DELTA = "delta"
    PROPOSAL = "proposal"
    DONE = "done"
    ERROR = "error"


class AssistThreadStatus(StrEnum):
    OPEN = "open"
    BLOCKED = "blocked"
    CLOSED = "closed"


class AssistBlocker(AipContractModel):
    code: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=500)
    dependency_ref: ResourceRef | None = None
    retryable: bool = False

    @model_validator(mode="after")
    def _exact_dependency(self) -> "AssistBlocker":
        if self.dependency_ref is not None:
            _require_exact(self.dependency_ref, field="dependencyRef")
        return self


class AssistSubjectRefs(AipContractModel):
    task_ref: ResourceRef
    task_run_ref: ResourceRef
    agent_run_ref: ResourceRef
    selection_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    cutoff_at: datetime

    @model_validator(mode="after")
    def _exact_subject(self) -> "AssistSubjectRefs":
        expected = (
            (self.task_ref, "Task", "taskRef"),
            (self.task_run_ref, "TaskRun", "taskRunRef"),
            (self.agent_run_ref, "AgentRun", "agentRunRef"),
        )
        for ref, resource_type, field in expected:
            _require_exact(ref, field=field)
            if ref.resource_type != resource_type:
                raise ValueError(f"{field} must reference {resource_type}")
        _require_exact_list(self.selection_refs, field="selectionRefs")
        return self


class CreateAssistThreadRequest(AssistSubjectRefs):
    title: str | None = Field(default=None, min_length=1, max_length=240)


class CreateAssistTurnRequest(AipContractModel):
    message: str = Field(min_length=2, max_length=8_000)
    attachment_refs: list[ResourceRef] = Field(default_factory=list, max_length=20)
    reference_refs: list[ResourceRef] = Field(default_factory=list, max_length=50)
    expected_thread_version: int = Field(ge=1)
    cutoff_at: datetime

    @field_validator("message")
    @classmethod
    def _clean_message(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("assist message is too short")
        return cleaned

    @model_validator(mode="after")
    def _exact_message_refs(self) -> "CreateAssistTurnRequest":
        _require_exact_list(self.attachment_refs, field="attachmentRefs")
        _require_exact_list(self.reference_refs, field="referenceRefs")
        return self


class AssistAuthorityContext(AipContractModel):
    """Internal snapshot returned by canonical authority readers."""

    tenant: TenantContext
    task_ref: ResourceRef
    task_run_ref: ResourceRef
    plan_ref: ResourceRef
    agent_run_ref: ResourceRef
    agent_instance_ref: ResourceRef
    skill_ref: ResourceRef
    logic_ref: ResourceRef
    model_route_ref: ResourceRef
    policy_ref: ResourceRef
    eval_ref: ResourceRef
    skill_binding_ref: ResourceRef
    capability_binding_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    selection_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    knowledge_citation_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    markings: list[str] = Field(min_length=1, max_length=32)
    cutoff_at: datetime
    readiness_blockers: list[AssistBlocker] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _all_refs_exact(self) -> "AssistAuthorityContext":
        for field in (
            "task_ref",
            "task_run_ref",
            "plan_ref",
            "agent_run_ref",
            "agent_instance_ref",
            "skill_ref",
            "logic_ref",
            "model_route_ref",
            "policy_ref",
            "eval_ref",
            "skill_binding_ref",
        ):
            _require_exact(getattr(self, field), field=field)
        for field in (
            "capability_binding_refs",
            "selection_refs",
            "knowledge_citation_refs",
        ):
            _require_exact_list(getattr(self, field), field=field)
        if len(self.markings) != len(set(self.markings)):
            raise ValueError("markings must not contain duplicates")
        return self


class AssistContextSnapshot(AssistAuthorityContext):
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class AssistThreadSnapshot(AipContractModel):
    tenant: TenantContext
    thread_id: str = Field(min_length=1, max_length=240)
    subject: AssistSubjectRefs
    status: AssistThreadStatus
    version: int = Field(ge=1)
    created_by: str = Field(min_length=1, max_length=240)
    created_at: datetime


class AssistStreamEvent(AipContractModel):
    event_type: AssistEventType
    thread_id: str = Field(min_length=1, max_length=240)
    turn_id: str = Field(min_length=1, max_length=240)
    sequence: int = Field(ge=1)
    occurred_at: datetime
    context: AssistContextSnapshot | None = None
    blocker: AssistBlocker | None = None
    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    proposal_ref: ResourceRef | None = None
    usage_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    lineage_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _payload_matches_event_type(self) -> "AssistStreamEvent":
        if self.proposal_ref is not None:
            _require_exact(self.proposal_ref, field="proposalRef")
        _require_exact_list(self.usage_refs, field="usageRefs")
        _require_exact_list(self.lineage_refs, field="lineageRefs")

        payloads = {
            "context": self.context is not None,
            "blocker": self.blocker is not None,
            "content": self.content is not None,
            "proposal": self.proposal_ref is not None,
        }
        allowed: dict[AssistEventType, set[str]] = {
            AssistEventType.START: set(),
            AssistEventType.CONTEXT: {"context"},
            AssistEventType.BLOCKED: {"blocker"},
            AssistEventType.DELTA: {"content"},
            AssistEventType.PROPOSAL: {"proposal"},
            AssistEventType.DONE: set(),
            AssistEventType.ERROR: {"blocker"},
        }
        present = {name for name, enabled in payloads.items() if enabled}
        required = allowed[self.event_type]
        if present != required:
            raise ValueError(f"{self.event_type.value} event requires only {sorted(required)}")
        if self.event_type not in {AssistEventType.DONE, AssistEventType.ERROR} and (
            self.usage_refs or self.lineage_refs
        ):
            raise ValueError("usage/lineage refs are allowed on done/error events only")
        return self


class AssistTurnRecord(AipContractModel):
    thread: AssistThreadSnapshot
    events: list[AssistStreamEvent] = Field(min_length=2, max_length=10_000)

    @model_validator(mode="after")
    def _ordered_terminal_stream(self) -> "AssistTurnRecord":
        turn_ids = {event.turn_id for event in self.events}
        if len(turn_ids) != 1:
            raise ValueError("events must belong to one turn")
        for sequence, event in enumerate(self.events, start=1):
            if event.thread_id != self.thread.thread_id:
                raise ValueError("event thread does not match snapshot")
            if event.sequence != sequence:
                raise ValueError("event sequences must be contiguous")
            if event.event_type in {
                AssistEventType.BLOCKED,
                AssistEventType.DONE,
                AssistEventType.ERROR,
            } and sequence != len(self.events):
                raise ValueError("terminal event must be last")
        if self.events[-1].event_type not in {
            AssistEventType.BLOCKED,
            AssistEventType.DONE,
            AssistEventType.ERROR,
        }:
            raise ValueError("turn record requires a terminal event")
        return self


class AssistHistoryTurn(AipContractModel):
    turn_id: str = Field(min_length=1, max_length=240)
    turn_sequence: int = Field(ge=1)
    message: str = Field(min_length=2, max_length=8_000)
    attachment_refs: list[ResourceRef] = Field(default_factory=list, max_length=20)
    reference_refs: list[ResourceRef] = Field(default_factory=list, max_length=50)
    created_by: str = Field(min_length=1, max_length=240)
    created_at: datetime
    events: list[AssistStreamEvent] = Field(default_factory=list, max_length=10_000)

    @model_validator(mode="after")
    def _exact_history_refs(self) -> "AssistHistoryTurn":
        _require_exact_list(self.attachment_refs, field="attachmentRefs")
        _require_exact_list(self.reference_refs, field="referenceRefs")
        for sequence, event in enumerate(self.events, start=1):
            if event.turn_id != self.turn_id or event.sequence != sequence:
                raise ValueError("history events must be contiguous and belong to the turn")
        return self


class AssistThreadHistory(AipContractModel):
    thread: AssistThreadSnapshot
    participants: list[str] = Field(min_length=1, max_length=100)
    turns: list[AssistHistoryTurn] = Field(default_factory=list, max_length=1_000)
    event_cursor: str = Field(min_length=3, max_length=80)


class AssistSubjectOption(AipContractModel):
    subject: AssistSubjectRefs
    task_title: str = Field(min_length=1, max_length=500)
    task_description: str = Field(default="", max_length=8_000)
    owner: str = Field(min_length=1, max_length=240)
    task_status: str = Field(min_length=1, max_length=80)
    run_status: str = Field(min_length=1, max_length=80)
    agent_status: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=160)
    updated_at: datetime


class AssistSubjectOptionList(AipContractModel):
    tenant: TenantContext
    items: list[AssistSubjectOption] = Field(default_factory=list, max_length=200)
    count: int = Field(ge=0, le=200)


__all__ = [
    "AssistAuthorityContext",
    "AssistBlocker",
    "AssistContextSnapshot",
    "AssistEventType",
    "AssistStreamEvent",
    "AssistSubjectRefs",
    "AssistSubjectOption",
    "AssistSubjectOptionList",
    "AssistHistoryTurn",
    "AssistThreadHistory",
    "AssistThreadSnapshot",
    "AssistThreadStatus",
    "AssistTurnRecord",
    "CreateAssistThreadRequest",
    "CreateAssistTurnRequest",
]
