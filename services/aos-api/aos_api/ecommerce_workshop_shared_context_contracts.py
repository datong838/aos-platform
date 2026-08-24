"""Strict contracts for reconstructable Workshop shared context projections."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext

SHARED_CONTEXT_SCHEMA_VERSION = "aos.ecommerce-workshop.shared-context/v1"


class WorkshopSharedRef(AipContractModel):
    authority: str = Field(min_length=1, max_length=120)
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str | None = Field(default=None, min_length=1, max_length=200)


class WorkshopSharedBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class WorkshopSharedContext(AipContractModel):
    context_id: str = Field(pattern=r"^[A-Za-z0-9_-]{32,128}$")
    status: Literal["ready", "blocked", "expired", "forbidden", "stale", "unknown"]
    source_module_id: str | None = Field(default=None, pattern=r"^ecommerce[.][a-z0-9]+(?:[.-][a-z0-9]+)*$")
    source_view_id: str | None = Field(default=None, min_length=1, max_length=120)
    source_route: str | None = Field(default=None, pattern=r"^/workshop/[a-z0-9]+(?:-[a-z0-9]+)*$")
    primary_ref: WorkshopSharedRef | None = None
    related_refs: list[WorkshopSharedRef] = Field(default_factory=list, max_length=100)
    purpose: str | None = Field(default=None, min_length=1, max_length=160)
    permission_decision_ref: WorkshopSharedRef | None = None
    disclosure_policy_ref: WorkshopSharedRef | None = None
    markings: list[str] = Field(default_factory=list, max_length=20)
    disclosure: Literal["allowed", "blocked", "unknown"]
    evaluated_at: datetime
    data_cutoff: datetime | None = None
    expires_at: datetime
    freshness: Literal["fresh", "stale", "unknown"]
    readiness: Literal["ready", "blocked", "unknown"]
    filter_summary: str | None = Field(default=None, min_length=1, max_length=240)
    lineage_refs: list[WorkshopSharedRef] = Field(default_factory=list, max_length=100)
    blockers: list[WorkshopSharedBlocker] = Field(default_factory=list, max_length=20)

    @field_validator("evaluated_at", "data_cutoff", "expires_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("shared context timestamps require timezone")
        return value

    @model_validator(mode="after")
    def _honest(self) -> WorkshopSharedContext:
        ready_fields = (self.source_module_id, self.source_view_id, self.source_route, self.primary_ref, self.purpose, self.permission_decision_ref, self.disclosure_policy_ref, self.data_cutoff)
        if self.status == "ready" and (not all(ready_fields) or not self.markings or self.disclosure != "allowed" or self.freshness != "fresh" or self.readiness != "ready" or self.blockers or self.expires_at <= self.evaluated_at):
            raise ValueError("ready shared context requires exact fresh disclosed authority")
        if self.status != "ready" and not self.blockers:
            raise ValueError("non-ready shared context requires blockers")
        if self.status in {"forbidden", "expired", "unknown"} and any((self.source_module_id, self.source_view_id, self.source_route, self.primary_ref, self.related_refs, self.lineage_refs, self.permission_decision_ref, self.disclosure_policy_ref, self.markings, self.filter_summary)):
            raise ValueError("non-disclosing shared context cannot reveal target facts")
        identities = [(item.authority, item.resource_type, item.resource_id, item.revision, item.content_hash) for item in [*self.related_refs, *self.lineage_refs]]
        if len(identities) != len(set(identities)):
            raise ValueError("shared context refs must be unique")
        if len(self.markings) != len(set(self.markings)) or any(not item.strip() or len(item) > 120 for item in self.markings):
            raise ValueError("shared context markings must be unique bounded labels")
        return self


class WorkshopTimelineEvent(AipContractModel):
    event_key: str = Field(min_length=1, max_length=200)
    event_type: Literal["task", "handoff", "action", "evidence", "receipt", "usage", "effect"]
    source_ref: WorkshopSharedRef
    authority_sequence: int = Field(ge=0)
    occurred_at: datetime
    recorded_at: datetime
    actor_kind: Literal["system", "human", "agent"]
    safe_summary: str = Field(min_length=1, max_length=500)
    status: str = Field(min_length=1, max_length=80)
    reason_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    causation_ref: str | None = Field(default=None, min_length=1, max_length=200)
    correlation_ref: str | None = Field(default=None, min_length=1, max_length=200)
    attempt: int | None = Field(default=None, ge=1)
    receipt_ref: WorkshopSharedRef | None = None
    original_refs: list[WorkshopSharedRef] = Field(default_factory=list, max_length=100)
    late: bool = False
    duplicate: bool = False
    superseded: bool = False
    unknown: bool = False
    reconciled: bool = False
    stale: bool = False

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def _aware_event_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("timeline timestamps require timezone")
        return value

    @model_validator(mode="after")
    def _preserve_uncertainty(self) -> WorkshopTimelineEvent:
        if self.reconciled and not self.unknown:
            raise ValueError("reconciled timeline events must retain unknown history")
        identities = [(item.authority, item.resource_type, item.resource_id, item.revision, item.content_hash) for item in self.original_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("timeline originals must be unique")
        return self


class WorkshopNavigationTarget(AipContractModel):
    target_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,128}$")
    status: Literal["available", "forbidden", "expired", "uninstalled", "disabled", "stale", "unresolved"]
    module_id: str | None = Field(default=None, pattern=r"^ecommerce[.][a-z0-9]+(?:[.-][a-z0-9]+)*$")
    view_id: str | None = Field(default=None, min_length=1, max_length=120)
    route: str | None = Field(default=None, pattern=r"^/workshop/[a-z0-9]+(?:-[a-z0-9]+)*$")
    subject_ref: WorkshopSharedRef | None = None
    filter_summary: str | None = Field(default=None, min_length=1, max_length=240)
    focus_anchor: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,119}$")
    scroll_anchor: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,119}$")
    blockers: list[WorkshopSharedBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _server_resolved(self) -> WorkshopNavigationTarget:
        details = (self.module_id, self.view_id, self.route, self.subject_ref)
        if self.status == "available" and (not all(details) or self.blockers):
            raise ValueError("available navigation requires exact server-resolved target")
        if self.status != "available" and (any(details) or not self.blockers or any((self.filter_summary, self.focus_anchor, self.scroll_anchor))):
            raise ValueError("unavailable navigation must fail closed without target disclosure")
        return self


class WorkshopSharedContextPage(AipContractModel):
    limit: Literal[100] = 100
    count: int = Field(ge=0, le=100)
    has_more: Literal[False] = False
    next_cursor: None = None


class WorkshopSharedContextEnvelope(AipContractModel):
    schema_version: Literal[SHARED_CONTEXT_SCHEMA_VERSION] = SHARED_CONTEXT_SCHEMA_VERSION
    tenant: TenantContext
    context: WorkshopSharedContext
    timeline: list[WorkshopTimelineEvent] = Field(default_factory=list, max_length=100)
    navigation_targets: list[WorkshopNavigationTarget] = Field(default_factory=list, max_length=20)
    page: WorkshopSharedContextPage

    @model_validator(mode="after")
    def _canonical_projection(self) -> WorkshopSharedContextEnvelope:
        identities = [(item.source_ref.authority, item.source_ref.resource_type, item.source_ref.resource_id, item.authority_sequence, item.event_key) for item in self.timeline]
        if len(identities) != len(set(identities)):
            raise ValueError("timeline event identities must be unique")
        ordering = [(item.authority_sequence, item.occurred_at, item.recorded_at, item.event_key) for item in self.timeline]
        if ordering != sorted(ordering):
            raise ValueError("timeline must use canonical stable order")
        target_ids = [item.target_id for item in self.navigation_targets]
        if len(target_ids) != len(set(target_ids)) or self.page.count != len(self.timeline):
            raise ValueError("shared context page or target identities drifted")
        if self.context.status != "ready" and (self.timeline or self.navigation_targets):
            raise ValueError("non-ready shared context cannot disclose timeline or targets")
        return self


__all__ = ["SHARED_CONTEXT_SCHEMA_VERSION", "WorkshopNavigationTarget", "WorkshopSharedBlocker", "WorkshopSharedContext", "WorkshopSharedContextEnvelope", "WorkshopSharedContextPage", "WorkshopSharedRef", "WorkshopTimelineEvent"]
