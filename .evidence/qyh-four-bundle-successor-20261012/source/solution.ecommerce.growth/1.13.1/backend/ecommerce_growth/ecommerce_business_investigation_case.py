"""Package-owned BusinessInvestigationCase contracts without platform imports."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping

from .sdk_ports import ExactRef, TenantRef

CASE_SCHEMA = "aos.ecommerce.business-investigation-case/v1"


class CaseLifecycle(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    CLOSED = "CLOSED"


class AnalysisType(StrEnum):
    INITIAL_STORE_ANALYSIS = "initial_store_analysis"
    WEEKLY_BUSINESS_REVIEW = "weekly_business_review"
    EXPERIENCE_GROWTH = "experience_growth"
    CREATOR_SALES = "creator_sales"
    PRODUCT_STRUCTURE = "product_structure"


def canonical_hash(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _ref_payload(ref: ExactRef | None) -> dict[str, object] | None:
    if ref is None:
        return None
    return {
        "resourceType": ref.resource_type,
        "resourceId": ref.resource_id,
        "revision": ref.revision,
        "contentHash": ref.content_hash,
        "receiptId": ref.receipt_id,
    }


def _ref_from_payload(value: Mapping[str, Any] | None) -> ExactRef | None:
    if value is None:
        return None
    return ExactRef(
        str(value["resourceType"]),
        str(value["resourceId"]),
        int(value["revision"]),
        str(value["contentHash"]),
        None if value.get("receiptId") is None else str(value["receiptId"]),
    )


def _json_datetime(value: datetime) -> str:
    rendered = value.isoformat()
    return rendered[:-6] + "Z" if rendered.endswith("+00:00") else rendered


@dataclass(frozen=True, slots=True)
class BusinessInvestigationCase:
    schema_version: str
    tenant: TenantRef
    case_id: str
    revision: int
    version: int
    lifecycle: CaseLifecycle
    analysis_type: AnalysisType
    title: str
    purpose_code: str
    channel_ref: ExactRef
    business_entity_ref: ExactRef
    entity_channel_binding_ref: ExactRef
    investigation_profile_ref: ExactRef
    scope_ref: ExactRef
    schedule_policy_ref: ExactRef | None
    prior_ref: ExactRef | None
    created_by: str
    created_at: datetime
    content_hash: str

    def __post_init__(self) -> None:
        if (
            self.schema_version != CASE_SCHEMA
            or self.version != self.revision
            or not 1 <= len(self.case_id.strip()) <= 200
            or self.revision <= 0
            or not 1 <= len(self.title.strip()) <= 500
            or not 1 <= len(self.created_by.strip()) <= 200
        ):
            raise ValueError("case identity, revision, title and creator are required")
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include timezone")
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,119}", self.purpose_code):
            raise ValueError("invalid purpose code")
        expected_types = (
            (self.channel_ref, "ChannelRevision"),
            (self.business_entity_ref, "BusinessEntityRevision"),
            (self.entity_channel_binding_ref, "BusinessEntityChannelBindingRevision"),
            (self.investigation_profile_ref, "InvestigationProfileRevision"),
            (self.scope_ref, "InvestigationScopeRevision"),
        )
        if any(ref.resource_type != expected for ref, expected in expected_types):
            raise ValueError("case contains an invalid exact reference type")
        if self.schedule_policy_ref is not None and self.schedule_policy_ref.resource_type != "SchedulePolicyRevision":
            raise ValueError("schedule_policy_ref must bind an exact SchedulePolicyRevision")
        if self.revision == 1 and (self.prior_ref is not None or self.lifecycle is not CaseLifecycle.DRAFT):
            raise ValueError("case revision 1 must be a draft without prior_ref")
        if self.revision > 1 and (
            self.prior_ref is None
            or self.prior_ref.resource_type != "BusinessInvestigationCaseRevision"
            or self.prior_ref.resource_id != self.case_id
            or self.prior_ref.revision != self.revision - 1
        ):
            raise ValueError("case successor must bind its exact predecessor")
        if self.content_hash != self.calculated_content_hash():
            raise ValueError("case content hash drifted")

    def calculated_content_hash(self) -> str:
        return canonical_hash(self.authority_payload(include_hash=False))

    def authority_payload(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": self.schema_version,
            "tenant": {"orgId": self.tenant.org_id, "projectId": self.tenant.project_id},
            "caseId": self.case_id,
            "revision": self.revision,
            "version": self.version,
            "priorRef": _ref_payload(self.prior_ref),
            "lifecycle": self.lifecycle.value,
            "analysisType": self.analysis_type.value,
            "title": self.title,
            "purposeCode": self.purpose_code,
            "channelRef": _ref_payload(self.channel_ref),
            "businessEntityRef": _ref_payload(self.business_entity_ref),
            "entityChannelBindingRef": _ref_payload(self.entity_channel_binding_ref),
            "investigationProfileRef": _ref_payload(self.investigation_profile_ref),
            "scopeRef": _ref_payload(self.scope_ref),
            "schedulePolicyRef": _ref_payload(self.schedule_policy_ref),
            "createdBy": self.created_by,
            "createdAt": _json_datetime(self.created_at),
        }
        if include_hash:
            payload["contentHash"] = self.content_hash
        return payload

    @classmethod
    def from_authority(cls, payload: Mapping[str, Any]) -> "BusinessInvestigationCase":
        tenant = payload["tenant"]
        return cls(
            schema_version=str(payload["schemaVersion"]),
            tenant=TenantRef(str(tenant["orgId"]), str(tenant["projectId"])),
            case_id=str(payload["caseId"]), revision=int(payload["revision"]), version=int(payload["version"]),
            prior_ref=_ref_from_payload(payload.get("priorRef")), content_hash=str(payload["contentHash"]),
            lifecycle=CaseLifecycle(str(payload["lifecycle"])), analysis_type=AnalysisType(str(payload["analysisType"])),
            title=str(payload["title"]), purpose_code=str(payload["purposeCode"]),
            channel_ref=_ref_from_payload(payload["channelRef"]),
            business_entity_ref=_ref_from_payload(payload["businessEntityRef"]),
            entity_channel_binding_ref=_ref_from_payload(payload["entityChannelBindingRef"]),
            investigation_profile_ref=_ref_from_payload(payload["investigationProfileRef"]),
            scope_ref=_ref_from_payload(payload["scopeRef"]),
            schedule_policy_ref=_ref_from_payload(payload.get("schedulePolicyRef")),
            created_by=str(payload["createdBy"]), created_at=datetime.fromisoformat(str(payload["createdAt"])),
        )

    def validate_successor(self, previous: "BusinessInvestigationCase") -> None:
        if self.tenant != previous.tenant:
            raise ValueError("case successor tenant must remain unchanged")
        if self.prior_ref is None or (
            self.prior_ref.resource_type != "BusinessInvestigationCaseRevision"
            or self.prior_ref.resource_id != previous.case_id
            or self.prior_ref.revision != previous.revision
            or self.prior_ref.content_hash != previous.content_hash
        ):
            raise ValueError("case successor must bind the exact prior revision")
        if (
            self.analysis_type != previous.analysis_type
            or self.channel_ref.resource_id != previous.channel_ref.resource_id
            or self.business_entity_ref.resource_id != previous.business_entity_ref.resource_id
            or self.entity_channel_binding_ref.resource_id != previous.entity_channel_binding_ref.resource_id
        ):
            raise ValueError("case successor cannot change channel or business entity identity")
        allowed = {
            CaseLifecycle.DRAFT: {CaseLifecycle.ACTIVE},
            CaseLifecycle.ACTIVE: {CaseLifecycle.ARCHIVED, CaseLifecycle.CLOSED},
            CaseLifecycle.ARCHIVED: {CaseLifecycle.ACTIVE, CaseLifecycle.CLOSED},
            CaseLifecycle.CLOSED: set(),
        }
        schedule_rebind = (
            self.lifecycle is previous.lifecycle
            and self.schedule_policy_ref is not None
            and self.schedule_policy_ref != previous.schedule_policy_ref
        )
        if not schedule_rebind and self.lifecycle not in allowed[previous.lifecycle]:
            raise ValueError("case lifecycle transition is not allowed")


__all__ = ["AnalysisType", "BusinessInvestigationCase", "CASE_SCHEMA", "CaseLifecycle", "canonical_hash"]
