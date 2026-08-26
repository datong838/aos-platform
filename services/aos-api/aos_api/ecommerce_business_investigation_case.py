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
        schedule_rebind = (
            self.lifecycle is previous.lifecycle
            and self.schedule_policy_ref is not None
            and self.schedule_policy_ref != previous.schedule_policy_ref
        )
        if not schedule_rebind and self.lifecycle not in allowed[previous.lifecycle]:
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


class BusinessInvestigationCaseNotFound(BusinessInvestigationCaseError):
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

    def get(self, scope: TenantScope, case_id: str) -> BusinessInvestigationCaseRevision:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT r.authority_data FROM ecommerce_investigation_case_head h
                    JOIN ecommerce_investigation_case_revision r
                      ON r.org_id=h.org_id AND r.project_id=h.project_id
                     AND r.case_id=h.case_id AND r.revision=h.current_revision
                    WHERE h.org_id=%s AND h.project_id=%s AND h.case_id=%s""",
                    (*scope.key, case_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise BusinessInvestigationCaseError("canonical Case query failed closed") from exc
        if row is None:
            raise BusinessInvestigationCaseNotFound("BusinessInvestigationCase is not visible")
        return BusinessInvestigationCaseRevision.model_validate(row["authority_data"])

    def list(
        self,
        scope: TenantScope,
        *,
        business_entity_id: str | None = None,
        limit: int = 50,
    ) -> list[BusinessInvestigationCaseRevision]:
        if limit < 1 or limit > 200:
            raise BusinessInvestigationCaseConflict("Case query limit must be 1..200")
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """SELECT r.authority_data FROM ecommerce_investigation_case_head h
                    JOIN ecommerce_investigation_case_revision r
                      ON r.org_id=h.org_id AND r.project_id=h.project_id
                     AND r.case_id=h.case_id AND r.revision=h.current_revision
                    WHERE h.org_id=%s AND h.project_id=%s
                      AND (%s::text IS NULL OR h.business_entity_id=%s)
                    ORDER BY h.updated_at DESC,h.case_id ASC LIMIT %s""",
                    (*scope.key, business_entity_id, business_entity_id, limit),
                ).fetchall()
        except psycopg.Error as exc:
            raise BusinessInvestigationCaseError("canonical Case list failed closed") from exc
        return [BusinessInvestigationCaseRevision.model_validate(row["authority_data"]) for row in rows]

    def transition(
        self,
        scope: TenantScope,
        case_id: str,
        target: BusinessInvestigationCaseLifecycle,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationCaseWrite:
        if expected_version < 1:
            raise BusinessInvestigationCaseConflict("expected version must be positive")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise BusinessInvestigationCaseConflict("idempotency key must be non-empty and bounded")
        try:
            with self._connect_factory(scope) as conn:
                replay = conn.execute(
                    """SELECT case_id,expected_version,authority_data
                    FROM ecommerce_investigation_case_lifecycle_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='business_investigation_case.transition' AND idempotency_key=%s""",
                    (*scope.key, idempotency_key),
                ).fetchone()
        except psycopg.Error as exc:
            raise BusinessInvestigationCaseError("canonical Case lifecycle replay query failed closed") from exc
        if replay is not None:
            authority = BusinessInvestigationCaseRevision.model_validate(replay["authority_data"])
            if (
                replay["case_id"] != case_id
                or int(replay["expected_version"]) != expected_version
                or authority.lifecycle is not target
            ):
                raise BusinessInvestigationCaseConflict("Case lifecycle idempotency conflict")
            return BusinessInvestigationCaseWrite(authority=authority, replayed=True)
        previous = self.get(scope, case_id)
        if previous.version != expected_version:
            raise BusinessInvestigationCaseConflict("Case expected version conflict")
        payload = previous.model_dump(by_alias=True, mode="json")
        payload.update(
            revision=expected_version + 1,
            version=expected_version + 1,
            priorRef={
                "resourceType": "BusinessInvestigationCaseRevision",
                "resourceId": previous.case_id,
                "revision": previous.revision,
                "contentHash": previous.content_hash,
            },
            lifecycle=target.value,
            contentHash="sha256:" + "0" * 64,
            createdBy=actor,
            createdAt=occurred_at.isoformat(),
        )
        successor = BusinessInvestigationCaseRevision.model_validate(payload)
        payload["contentHash"] = successor.calculated_content_hash()
        successor = BusinessInvestigationCaseRevision.model_validate(payload)
        successor.validate_successor(previous)
        request_hash = _canonical_hash(
            {"caseId": case_id, "expectedVersion": expected_version, "targetLifecycle": target.value}
        )
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT authority_data,replayed
                    FROM ecommerce_investigation_case_transition_biw4_006(%s,%s,%s,%s,%s)""",
                    (case_id, expected_version, idempotency_key, request_hash, Jsonb(payload)),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise BusinessInvestigationCaseConflict("canonical Case lifecycle failed closed") from exc
        if row is None:
            raise BusinessInvestigationCaseConflict("canonical Case lifecycle returned no Receipt")
        return BusinessInvestigationCaseWrite(
            authority=BusinessInvestigationCaseRevision.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )


__all__ = [
    "BusinessInvestigationAnalysisType",
    "BusinessInvestigationCaseConflict",
    "BusinessInvestigationCaseLifecycle",
    "BusinessInvestigationCaseNotFound",
    "BusinessInvestigationCaseRevision",
    "BusinessInvestigationCaseStore",
    "BusinessInvestigationCaseWrite",
]
