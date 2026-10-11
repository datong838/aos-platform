"""Package-owned schedule policy and natural-slot contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .ecommerce_business_investigation_case import (
    AnalysisType,
    _json_datetime,
    _ref_from_payload,
    _ref_payload,
    canonical_hash,
)
from .sdk_ports import ExactRef, TenantRef

SCHEDULE_SCHEMA = "aos.ecommerce.business-investigation-schedule-policy/v1"


class ScheduleKind(StrEnum):
    INITIAL_CHECKUP = "initial_checkup"
    WEEKLY_REVIEW = "weekly_review"
    TOPIC_ANALYSIS = "topic_analysis"


class ScheduleCadence(StrEnum):
    ONCE = "once"
    WEEKLY = "weekly"
    ON_DEMAND = "on_demand"


@dataclass(frozen=True, slots=True)
class SchedulePolicy:
    schema_version: str
    tenant: TenantRef
    policy_id: str
    revision: int
    version: int
    prior_ref: ExactRef | None
    content_hash: str
    case_ref: ExactRef
    analysis_type: AnalysisType
    policy_kind: ScheduleKind
    cadence: ScheduleCadence
    enabled: bool
    overlap_policy: str
    timezone: str
    weekly_day: int | None
    local_time: str | None
    created_by: str
    created_at: datetime

    def __post_init__(self) -> None:
        if (
            self.schema_version != SCHEDULE_SCHEMA
            or self.version != self.revision
            or not 1 <= len(self.policy_id.strip()) <= 200
            or self.revision <= 0
            or not 1 <= len(self.created_by.strip()) <= 200
        ):
            raise ValueError("policy identity and positive revisions are required")
        if self.case_ref.resource_type != "BusinessInvestigationCaseRevision":
            raise ValueError("policy must bind an exact case revision")
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include timezone")
        if self.overlap_policy != "skip" or self.timezone != "Asia/Shanghai":
            raise ValueError("unsupported overlap policy or timezone")
        expected = {
            ScheduleKind.INITIAL_CHECKUP: (ScheduleCadence.ONCE, {AnalysisType.INITIAL_STORE_ANALYSIS}),
            ScheduleKind.WEEKLY_REVIEW: (ScheduleCadence.WEEKLY, {AnalysisType.WEEKLY_BUSINESS_REVIEW}),
            ScheduleKind.TOPIC_ANALYSIS: (
                ScheduleCadence.ON_DEMAND,
                {AnalysisType.EXPERIENCE_GROWTH, AnalysisType.CREATOR_SALES, AnalysisType.PRODUCT_STRUCTURE},
            ),
        }
        cadence, analysis_types = expected[self.policy_kind]
        if self.cadence is not cadence or self.analysis_type not in analysis_types:
            raise ValueError("schedule kind/cadence/analysis type mismatch")
        if self.cadence is ScheduleCadence.WEEKLY:
            if self.weekly_day not in range(1, 8) or self.local_time is None:
                raise ValueError("weekly policy requires weekday and local time")
            if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", self.local_time):
                raise ValueError("local_time must use strict HH:MM")
        elif self.weekly_day is not None or self.local_time is not None:
            raise ValueError("non-weekly policy cannot carry weekly fields")
        if self.revision == 1 and self.prior_ref is not None:
            raise ValueError("schedule policy revision 1 cannot carry prior_ref")
        if self.revision > 1 and (
            self.prior_ref is None
            or self.prior_ref.resource_type != "SchedulePolicyRevision"
            or self.prior_ref.resource_id != self.policy_id
            or self.prior_ref.revision != self.revision - 1
        ):
            raise ValueError("schedule successor must bind its predecessor")
        if self.content_hash != self.calculated_content_hash():
            raise ValueError("schedule policy content hash drifted")

    def calculated_content_hash(self) -> str:
        return canonical_hash(self.authority_payload(include_hash=False))

    def authority_payload(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": self.schema_version,
            "tenant": {"orgId": self.tenant.org_id, "projectId": self.tenant.project_id},
            "schedulePolicyId": self.policy_id,
            "revision": self.revision,
            "version": self.version,
            "priorRef": _ref_payload(self.prior_ref),
            "caseRef": _ref_payload(self.case_ref),
            "analysisType": self.analysis_type.value,
            "policyKind": self.policy_kind.value,
            "cadence": self.cadence.value,
            "enabled": self.enabled,
            "overlapPolicy": self.overlap_policy,
            "timezone": self.timezone,
            "weeklyDay": self.weekly_day,
            "localTime": self.local_time,
            "createdBy": self.created_by,
            "createdAt": _json_datetime(self.created_at),
        }
        if include_hash:
            payload["contentHash"] = self.content_hash
        return payload

    @classmethod
    def from_authority(cls, payload: Mapping[str, Any]) -> "SchedulePolicy":
        tenant = payload["tenant"]
        return cls(
            schema_version=str(payload["schemaVersion"]),
            tenant=TenantRef(str(tenant["orgId"]), str(tenant["projectId"])),
            policy_id=str(payload["schedulePolicyId"]), revision=int(payload["revision"]),
            version=int(payload["version"]), prior_ref=_ref_from_payload(payload.get("priorRef")),
            content_hash=str(payload["contentHash"]), case_ref=_ref_from_payload(payload["caseRef"]),
            analysis_type=AnalysisType(str(payload["analysisType"])),
            policy_kind=ScheduleKind(str(payload["policyKind"])), cadence=ScheduleCadence(str(payload["cadence"])),
            enabled=bool(payload["enabled"]), overlap_policy=str(payload["overlapPolicy"]),
            timezone=str(payload["timezone"]), weekly_day=payload.get("weeklyDay"),
            local_time=payload.get("localTime"), created_by=str(payload["createdBy"]),
            created_at=datetime.fromisoformat(str(payload["createdAt"])),
        )

    def validate_successor(self, previous: "SchedulePolicy") -> None:
        if (
            self.tenant != previous.tenant
            or self.policy_id != previous.policy_id
            or self.case_ref.resource_id != previous.case_ref.resource_id
            or self.analysis_type is not previous.analysis_type
            or self.policy_kind is not previous.policy_kind
            or self.cadence is not previous.cadence
        ):
            raise ValueError("schedule successor cannot change identity or type")
        if self.prior_ref is None or self.prior_ref.content_hash != previous.content_hash:
            raise ValueError("schedule successor must bind exact prior hash")

    def slot_at(self, local_date: datetime) -> datetime:
        if self.cadence is not ScheduleCadence.WEEKLY or self.local_time is None:
            raise ValueError("only weekly policy owns natural time slots")
        hour, minute = (int(part) for part in self.local_time.split(":"))
        local = local_date.astimezone(ZoneInfo("Asia/Shanghai")).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return local.astimezone(UTC)


__all__ = ["SCHEDULE_SCHEMA", "ScheduleCadence", "ScheduleKind", "SchedulePolicy"]
