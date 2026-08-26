"""BI-W8-02 versioned SchedulePolicy and canonical scheduled trigger contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

import psycopg
from psycopg.types.json import Jsonb
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationAnalysisType,
    BusinessInvestigationCaseRevision,
)
from aos_api.tenant_scope import TenantScope


SCHEDULE_SCHEMA = "aos.ecommerce.business-investigation-schedule-policy/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


class BusinessInvestigationScheduleKind(StrEnum):
    INITIAL_CHECKUP = "initial_checkup"
    WEEKLY_REVIEW = "weekly_review"
    TOPIC_ANALYSIS = "topic_analysis"


class BusinessInvestigationScheduleCadence(StrEnum):
    ONCE = "once"
    WEEKLY = "weekly"
    ON_DEMAND = "on_demand"


def _canonical_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


class BusinessInvestigationSchedulePolicyRevision(AipContractModel):
    schema_version: str = SCHEDULE_SCHEMA
    tenant: TenantContext
    schedule_policy_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    prior_ref: InvestigationExactRef | None = None
    content_hash: str = Field(pattern=SHA256)
    case_ref: InvestigationExactRef
    analysis_type: BusinessInvestigationAnalysisType
    policy_kind: BusinessInvestigationScheduleKind
    cadence: BusinessInvestigationScheduleCadence
    enabled: bool
    overlap_policy: Literal["skip"] = "skip"
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    weekly_day: int | None = Field(default=None, ge=1, le=7)
    local_time: str | None = Field(default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("createdAt must include timezone")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != SCHEDULE_SCHEMA or self.version != self.revision:
            raise ValueError("unsupported SchedulePolicy schema or version/revision drift")
        if self.case_ref.resource_type != "BusinessInvestigationCaseRevision" or not isinstance(
            self.case_ref.revision, int
        ):
            raise ValueError("caseRef must be exact BusinessInvestigationCaseRevision")
        expected = {
            BusinessInvestigationScheduleKind.INITIAL_CHECKUP: (
                BusinessInvestigationScheduleCadence.ONCE,
                {BusinessInvestigationAnalysisType.INITIAL_STORE_ANALYSIS},
            ),
            BusinessInvestigationScheduleKind.WEEKLY_REVIEW: (
                BusinessInvestigationScheduleCadence.WEEKLY,
                {BusinessInvestigationAnalysisType.WEEKLY_BUSINESS_REVIEW},
            ),
            BusinessInvestigationScheduleKind.TOPIC_ANALYSIS: (
                BusinessInvestigationScheduleCadence.ON_DEMAND,
                {
                    BusinessInvestigationAnalysisType.EXPERIENCE_GROWTH,
                    BusinessInvestigationAnalysisType.CREATOR_SALES,
                    BusinessInvestigationAnalysisType.PRODUCT_STRUCTURE,
                },
            ),
        }
        cadence, analysis_types = expected[self.policy_kind]
        if self.cadence is not cadence or self.analysis_type not in analysis_types:
            raise ValueError("SchedulePolicy kind/cadence/analysisType mismatch")
        if self.cadence is BusinessInvestigationScheduleCadence.WEEKLY:
            if self.weekly_day is None or self.local_time is None:
                raise ValueError("weekly policy requires weeklyDay and localTime")
        elif self.weekly_day is not None or self.local_time is not None:
            raise ValueError("once/on-demand policy cannot carry weekly fields")
        if self.revision == 1:
            if self.prior_ref is not None:
                raise ValueError("SchedulePolicy r1 cannot carry priorRef")
        elif self.prior_ref is None or (
            self.prior_ref.resource_type != "SchedulePolicyRevision"
            or self.prior_ref.resource_id != self.schedule_policy_id
            or self.prior_ref.revision != self.revision - 1
        ):
            raise ValueError("SchedulePolicy successor must bind preceding revision")
        return self

    def calculated_content_hash(self) -> str:
        payload = self.model_dump(by_alias=True, mode="json")
        payload.pop("contentHash")
        return _canonical_hash(payload)

    def validate_successor(self, previous: "BusinessInvestigationSchedulePolicyRevision") -> None:
        if (
            self.tenant != previous.tenant
            or self.schedule_policy_id != previous.schedule_policy_id
            or self.case_ref.resource_id != previous.case_ref.resource_id
            or self.analysis_type is not previous.analysis_type
            or self.policy_kind is not previous.policy_kind
            or self.cadence is not previous.cadence
        ):
            raise ValueError("SchedulePolicy successor cannot change identity or type")
        if self.prior_ref is None or self.prior_ref.content_hash != previous.content_hash:
            raise ValueError("SchedulePolicy successor must bind exact prior hash")


class PutBusinessInvestigationSchedulePolicyRequest(AipContractModel):
    schedule_policy_id: str = Field(min_length=1, max_length=200)
    case_ref: InvestigationExactRef
    analysis_type: BusinessInvestigationAnalysisType
    policy_kind: BusinessInvestigationScheduleKind
    cadence: BusinessInvestigationScheduleCadence
    enabled: bool = False
    overlap_policy: Literal["skip"] = "skip"
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    weekly_day: int | None = Field(default=None, ge=1, le=7)
    local_time: str | None = Field(default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


class TriggerBusinessInvestigationScheduleRequest(AipContractModel):
    run_id: str = Field(min_length=1, max_length=200)
    schedule_policy_ref: InvestigationExactRef
    scheduled_at: datetime

    @field_validator("scheduled_at")
    @classmethod
    def _utc_seconds(cls, value: datetime) -> datetime:
        if value.utcoffset() is None or value.utcoffset().total_seconds() != 0 or value.microsecond:
            raise ValueError("scheduledAt must be UTC with second precision")
        return value


@dataclass(frozen=True, slots=True)
class BusinessInvestigationSchedulePolicyWrite:
    authority: BusinessInvestigationSchedulePolicyRevision
    case_authority: BusinessInvestigationCaseRevision
    replayed: bool


@dataclass(frozen=True, slots=True)
class BusinessInvestigationSchedulePolicyPutReceipt:
    authority: BusinessInvestigationSchedulePolicyRevision
    case_authority: BusinessInvestigationCaseRevision
    expected_policy_revision: int
    expected_case_version: int


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BusinessInvestigationScheduleConflict(RuntimeError):
    pass


class BusinessInvestigationScheduleNotFound(RuntimeError):
    pass


class BusinessInvestigationScheduleStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def get(self, scope: TenantScope, schedule_policy_id: str) -> BusinessInvestigationSchedulePolicyRevision:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT authority_data FROM ecommerce_investigation_schedule_policy_head
                    WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s""",
                    (*scope.key, schedule_policy_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise BusinessInvestigationScheduleConflict("SchedulePolicy query failed closed") from exc
        if row is None:
            raise BusinessInvestigationScheduleNotFound("SchedulePolicy is not visible")
        return BusinessInvestigationSchedulePolicyRevision.model_validate(row["authority_data"])

    def find_put_receipt(
        self, scope: TenantScope, idempotency_key: str
    ) -> BusinessInvestigationSchedulePolicyPutReceipt | None:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT policy_authority,case_authority,expected_policy_revision,expected_case_version
                    FROM ecommerce_investigation_schedule_policy_command_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='business_investigation_schedule_policy.put' AND idempotency_key=%s""",
                    (*scope.key, idempotency_key),
                ).fetchone()
        except psycopg.Error as exc:
            raise BusinessInvestigationScheduleConflict(
                "SchedulePolicy Receipt query failed closed"
            ) from exc
        if row is None:
            return None
        return BusinessInvestigationSchedulePolicyPutReceipt(
            authority=BusinessInvestigationSchedulePolicyRevision.model_validate(
                row["policy_authority"]
            ),
            case_authority=BusinessInvestigationCaseRevision.model_validate(row["case_authority"]),
            expected_policy_revision=int(row["expected_policy_revision"]),
            expected_case_version=int(row["expected_case_version"]),
        )

    def put_and_bind_case(
        self,
        scope: TenantScope,
        policy: BusinessInvestigationSchedulePolicyRevision,
        case: BusinessInvestigationCaseRevision,
        *,
        expected_policy_revision: int,
        expected_case_version: int,
        idempotency_key: str,
    ) -> BusinessInvestigationSchedulePolicyWrite:
        if (policy.tenant.org_id, policy.tenant.project_id) != scope.key or case.tenant != policy.tenant:
            raise BusinessInvestigationScheduleConflict("SchedulePolicy tenant does not match Principal")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise BusinessInvestigationScheduleConflict("idempotency key must be non-empty and bounded")
        if policy.calculated_content_hash() != policy.content_hash or case.calculated_content_hash() != case.content_hash:
            raise BusinessInvestigationScheduleConflict("SchedulePolicy or Case content hash drifted")
        request_hash = _canonical_hash(
            {
                "schedulePolicyId": policy.schedule_policy_id,
                "caseRef": policy.case_ref.model_dump(by_alias=True, mode="json"),
                "analysisType": policy.analysis_type.value,
                "policyKind": policy.policy_kind.value,
                "cadence": policy.cadence.value,
                "enabled": policy.enabled,
                "overlapPolicy": policy.overlap_policy,
                "timezone": policy.timezone,
                "weeklyDay": policy.weekly_day,
                "localTime": policy.local_time,
                "expectedPolicyRevision": expected_policy_revision,
                "expectedCaseVersion": expected_case_version,
            }
        )
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT policy_authority,case_authority,replayed
                    FROM ecommerce_investigation_schedule_policy_put_biw8_001(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        policy.schedule_policy_id,
                        expected_policy_revision,
                        case.case_id,
                        expected_case_version,
                        idempotency_key,
                        request_hash,
                        Jsonb(policy.model_dump(by_alias=True, mode="json")),
                        Jsonb(case.model_dump(by_alias=True, mode="json")),
                    ),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise BusinessInvestigationScheduleConflict("SchedulePolicy write failed closed") from exc
        if row is None:
            raise BusinessInvestigationScheduleConflict("SchedulePolicy write returned no Receipt")
        return BusinessInvestigationSchedulePolicyWrite(
            authority=BusinessInvestigationSchedulePolicyRevision.model_validate(row["policy_authority"]),
            case_authority=BusinessInvestigationCaseRevision.model_validate(row["case_authority"]),
            replayed=bool(row["replayed"]),
        )


def scheduled_trigger_key(policy: BusinessInvestigationSchedulePolicyRevision, scheduled_at: datetime) -> str:
    material = {
        "caseId": policy.case_ref.resource_id,
        "scheduleRevision": policy.revision,
        "scheduledAt": scheduled_at.isoformat().replace("+00:00", "Z"),
        "analysisType": policy.analysis_type.value,
    }
    return "schedule:" + hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


__all__ = [
    "BusinessInvestigationScheduleCadence",
    "BusinessInvestigationScheduleConflict",
    "BusinessInvestigationScheduleKind",
    "BusinessInvestigationScheduleNotFound",
    "BusinessInvestigationSchedulePolicyRevision",
    "BusinessInvestigationSchedulePolicyPutReceipt",
    "BusinessInvestigationSchedulePolicyWrite",
    "BusinessInvestigationScheduleStore",
    "PutBusinessInvestigationSchedulePolicyRequest",
    "TriggerBusinessInvestigationScheduleRequest",
    "scheduled_trigger_key",
]
