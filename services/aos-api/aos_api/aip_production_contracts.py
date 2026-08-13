"""Strict W2 production contract DTOs."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import Field, field_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext


class BriefLifecycle(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"


class Coverage(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ExactRevisionRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreateBriefRequest(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    brief_type: str = Field(min_length=1, max_length=160)
    schema_ref: ResourceRef
    spec: dict[str, Any]


class ReviseBriefRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    brief_type: str = Field(min_length=1, max_length=160)
    schema_ref: ResourceRef
    spec: dict[str, Any]


class TaskBriefRevision(AipContractModel):
    tenant: TenantContext
    brief_id: str
    task_id: str
    revision: int
    version: int
    brief_type: str
    schema_ref: ResourceRef
    spec: dict[str, Any]
    content_hash: str
    lifecycle: BriefLifecycle
    created_by: str
    created_at: datetime


class TaskBriefListResponse(AipContractModel):
    tenant: TenantContext
    items: list[TaskBriefRevision]
    count: int = Field(ge=0)


class CreateEvidenceBundleRequest(AipContractModel):
    brief_ref: ExactRevisionRef
    subject_refs: list[ResourceRef] = Field(default_factory=list)
    cutoff_at: datetime
    item_refs: list[ExactRevisionRef] = Field(min_length=1)
    coverage: Coverage
    missing: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    uncertainties: list[dict[str, Any]] = Field(default_factory=list)
    freshness: Freshness
    marking: list[str] = Field(default_factory=list)
    license_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("marking")
    @classmethod
    def _marking_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not value.strip() for value in values):
            raise ValueError("marking must be unique and non-blank")
        return values


class EvidenceBundleRevision(AipContractModel):
    tenant: TenantContext
    bundle_id: str
    revision: int
    brief_ref: ExactRevisionRef
    subject_refs: list[ResourceRef]
    cutoff_at: datetime
    item_refs: list[ExactRevisionRef]
    coverage: Coverage
    missing: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    uncertainties: list[dict[str, Any]]
    freshness: Freshness
    marking: list[str]
    license_summary: dict[str, Any]
    content_hash: str
    lifecycle: BriefLifecycle
    created_by: str
    created_at: datetime


class EvidenceBundleListResponse(AipContractModel):
    tenant: TenantContext
    items: list[EvidenceBundleRevision]
    count: int = Field(ge=0)
