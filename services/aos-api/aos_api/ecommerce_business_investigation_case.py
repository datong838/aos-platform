"""BI-W4-01 ecommerce BusinessInvestigationCase draft authority."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

import psycopg
from psycopg.types.json import Jsonb
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


CASE_SCHEMA = "aos.ecommerce.business-investigation-case/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


class BusinessInvestigationCaseLifecycle(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    CLOSED = "CLOSED"


class BusinessInvestigationAnalysisType(StrEnum):
    INITIAL_STORE_ANALYSIS = "initial_store_analysis"
    WEEKLY_BUSINESS_REVIEW = "weekly_business_review"
    EXPERIENCE_GROWTH = "experience_growth"
    CREATOR_SALES = "creator_sales"
    PRODUCT_STRUCTURE = "product_structure"


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return value


def _exact_type(ref: InvestigationExactRef, expected: str, name: str) -> None:
    if ref.resource_type != expected or not isinstance(ref.revision, int):
        raise ValueError(f"{name} must reference numeric {expected}")


def _canonical_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


class BusinessInvestigationCaseRevision(AipContractModel):
    schema_version: str = CASE_SCHEMA
    tenant: TenantContext
    case_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    prior_ref: InvestigationExactRef | None = None
    content_hash: str = Field(pattern=SHA256)
    lifecycle: BusinessInvestigationCaseLifecycle
    analysis_type: BusinessInvestigationAnalysisType
    title: str = Field(min_length=1, max_length=500)
    purpose_code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,119}$")
    channel_ref: InvestigationExactRef
    business_entity_ref: InvestigationExactRef
    entity_channel_binding_ref: InvestigationExactRef
    investigation_profile_ref: InvestigationExactRef
    scope_ref: InvestigationExactRef
    schedule_policy_ref: InvestigationExactRef | None = None
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != CASE_SCHEMA or self.version != self.revision:
            raise ValueError("unsupported Case schema or version/revision drift")
        _exact_type(self.channel_ref, "ChannelRevision", "channelRef")
        _exact_type(self.business_entity_ref, "BusinessEntityRevision", "businessEntityRef")
        _exact_type(
            self.entity_channel_binding_ref,
            "BusinessEntityChannelBindingRevision",
            "entityChannelBindingRef",
        )
        _exact_type(self.investigation_profile_ref, "InvestigationProfileRevision", "investigationProfileRef")
        _exact_type(self.scope_ref, "InvestigationScopeRevision", "scopeRef")
        if self.schedule_policy_ref is not None:
            _exact_type(self.schedule_policy_ref, "SchedulePolicyRevision", "schedulePolicyRef")
        if self.revision == 1:
            if self.prior_ref is not None or self.lifecycle is not BusinessInvestigationCaseLifecycle.DRAFT:
                raise ValueError("Case r1 must be DRAFT without priorRef")
        else:
            if self.prior_ref is None:
                raise ValueError("Case successor requires priorRef")
            _exact_type(self.prior_ref, "BusinessInvestigationCaseRevision", "priorRef")
            if self.prior_ref.resource_id != self.case_id or self.prior_ref.revision != self.revision - 1:
                raise ValueError("priorRef must retain Case identity and preceding revision")
        return self

    def calculated_content_hash(self) -> str:
        payload = self.model_dump(by_alias=True, mode="json")
        payload.pop("contentHash")
        return _canonical_hash(payload)

    def validate_successor(self, previous: "BusinessInvestigationCaseRevision") -> None:
        if self.tenant != previous.tenant:
            raise ValueError("Case successor tenant must remain unchanged")
        if self.prior_ref is None or (
            self.prior_ref.resource_type != "BusinessInvestigationCaseRevision"
            or self.prior_ref.resource_id != previous.case_id
            or self.prior_ref.revision != previous.revision
            or self.prior_ref.content_hash != previous.content_hash
        ):
            raise ValueError("Case successor must bind the exact prior revision")
        if (
            self.analysis_type != previous.analysis_type
            or self.channel_ref.resource_id != previous.channel_ref.resource_id
            or self.business_entity_ref.resource_id != previous.business_entity_ref.resource_id
            or self.entity_channel_binding_ref.resource_id != previous.entity_channel_binding_ref.resource_id
        ):
            raise ValueError("Case successor cannot change channel or business entity identity")
        allowed = {
            BusinessInvestigationCaseLifecycle.DRAFT: {BusinessInvestigationCaseLifecycle.ACTIVE},
            BusinessInvestigationCaseLifecycle.ACTIVE: {
                BusinessInvestigationCaseLifecycle.ARCHIVED,
                BusinessInvestigationCaseLifecycle.CLOSED,
            },
            BusinessInvestigationCaseLifecycle.ARCHIVED: {
                BusinessInvestigationCaseLifecycle.ACTIVE,
                BusinessInvestigationCaseLifecycle.CLOSED,
            },
            BusinessInvestigationCaseLifecycle.CLOSED: set(),
        }
        if self.lifecycle not in allowed[previous.lifecycle]:
            raise ValueError("Case lifecycle transition is not allowed")


@dataclass(frozen=True, slots=True)
class BusinessInvestigationCaseWrite:
    authority: BusinessInvestigationCaseRevision
    replayed: bool


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BusinessInvestigationCaseError(RuntimeError):
    pass


class BusinessInvestigationCaseConflict(BusinessInvestigationCaseError):
    pass


class BusinessInvestigationCaseStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create_draft(
        self,
        scope: TenantScope,
        case: BusinessInvestigationCaseRevision,
        *,
        idempotency_key: str,
    ) -> BusinessInvestigationCaseWrite:
        if (case.tenant.org_id, case.tenant.project_id) != scope.key:
            raise BusinessInvestigationCaseConflict("Case tenant does not match Principal scope")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise BusinessInvestigationCaseConflict("idempotency key must be non-empty and bounded")
        if case.lifecycle is not BusinessInvestigationCaseLifecycle.DRAFT or case.revision != 1:
            raise BusinessInvestigationCaseConflict("BI-W4-01 creates DRAFT r1 only")
        if case.calculated_content_hash() != case.content_hash:
            raise BusinessInvestigationCaseConflict("Case content hash drifted")
        payload = case.model_dump(by_alias=True, mode="json")
        request_hash = _canonical_hash(payload)
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    "SELECT authority_data,replayed FROM ecommerce_investigation_case_create_biw4_001(%s,%s,%s,%s)",
                    (case.case_id, idempotency_key, request_hash, Jsonb(payload)),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise BusinessInvestigationCaseConflict("canonical Case create failed closed") from exc
        if row is None:
            raise BusinessInvestigationCaseConflict("canonical Case create returned no Receipt")
        return BusinessInvestigationCaseWrite(
            authority=BusinessInvestigationCaseRevision.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )


__all__ = [
    "BusinessInvestigationAnalysisType",
    "BusinessInvestigationCaseConflict",
    "BusinessInvestigationCaseLifecycle",
    "BusinessInvestigationCaseRevision",
    "BusinessInvestigationCaseStore",
    "BusinessInvestigationCaseWrite",
]
