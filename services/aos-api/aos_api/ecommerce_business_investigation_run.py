"""BI-W4-02 ecommerce BusinessInvestigationRun request authority."""

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
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationAnalysisType
from aos_api.tenant_scope import TenantScope


RUN_SCHEMA = "aos.ecommerce.business-investigation-run/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


class BusinessInvestigationRunLifecycle(StrEnum):
    PREPARING = "PREPARING"
    WAITING_DATA = "WAITING_DATA"
    PORTRAIT = "PORTRAIT"
    DIAGNOSIS = "DIAGNOSIS"
    SOLUTION_DESIGN = "SOLUTION_DESIGN"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BusinessInvestigationRunControl(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"
    CANCELLED = "CANCELLED"


class BusinessInvestigationTriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    TOPIC = "topic"
    RECOVERY = "recovery"


class BusinessInvestigationRunRequestOutcome(StrEnum):
    CREATED = "CREATED"
    SKIPPED_OVERLAP = "SKIPPED_OVERLAP"


class BusinessInvestigationRunStateRevision(AipContractModel):
    schema_version: str = "aos.ecommerce.business-investigation-run-state/v1"
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    prior_ref: InvestigationExactRef | None = None
    lifecycle: Literal[BusinessInvestigationRunLifecycle.PREPARING]
    control: Literal[
        BusinessInvestigationRunControl.RUNNING,
        BusinessInvestigationRunControl.PAUSED,
        BusinessInvestigationRunControl.CANCELLED,
    ]
    event_sequence: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _state_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("createdAt must include timezone")
        return value

    @model_validator(mode="after")
    def _state_integrity(self) -> Self:
        if self.schema_version != "aos.ecommerce.business-investigation-run-state/v1":
            raise ValueError("unsupported Run state schema")
        if self.event_sequence != self.version:
            raise ValueError("Run state version/event sequence drifted")
        if self.version == 1:
            if self.prior_ref is not None or self.control is not BusinessInvestigationRunControl.RUNNING:
                raise ValueError("Run state r1 must be RUNNING without priorRef")
        else:
            if self.prior_ref is None:
                raise ValueError("Run state successor requires priorRef")
            if (
                self.prior_ref.resource_type != "BusinessInvestigationRunStateRevision"
                or self.prior_ref.resource_id != self.run_id
                or self.prior_ref.revision != self.version - 1
            ):
                raise ValueError("Run state priorRef must bind preceding revision")
        return self

    def calculated_content_hash(self) -> str:
        payload = self.model_dump(by_alias=True, mode="json")
        payload.pop("contentHash")
        return _canonical_hash(payload)


def _canonical_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


class BusinessInvestigationRunRecord(AipContractModel):
    schema_version: str = RUN_SCHEMA
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    version: Literal[1]
    content_hash: str = Field(pattern=SHA256)
    case_ref: InvestigationExactRef
    analysis_type: BusinessInvestigationAnalysisType
    trigger_kind: BusinessInvestigationTriggerKind
    trigger_key: str = Field(min_length=1, max_length=240)
    lifecycle: Literal[BusinessInvestigationRunLifecycle.PREPARING]
    control: Literal[BusinessInvestigationRunControl.RUNNING]
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
        if self.schema_version != RUN_SCHEMA:
            raise ValueError("unsupported Run schema")
        if self.case_ref.resource_type != "BusinessInvestigationCaseRevision" or not isinstance(
            self.case_ref.revision, int
        ):
            raise ValueError("caseRef must reference numeric BusinessInvestigationCaseRevision")
        return self

    def calculated_content_hash(self) -> str:
        payload = self.model_dump(by_alias=True, mode="json")
        payload.pop("contentHash")
        return _canonical_hash(payload)


class BusinessInvestigationRunView(AipContractModel):
    authority: BusinessInvestigationRunRecord
    state: BusinessInvestigationRunStateRevision


@dataclass(frozen=True, slots=True)
class BusinessInvestigationRunWrite:
    authority: BusinessInvestigationRunRecord
    outcome: BusinessInvestigationRunRequestOutcome
    replayed: bool


@dataclass(frozen=True, slots=True)
class BusinessInvestigationRunStateWrite:
    authority: BusinessInvestigationRunStateRevision
    replayed: bool


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BusinessInvestigationRunConflict(RuntimeError):
    pass


class BusinessInvestigationRunNotFound(RuntimeError):
    pass


class BusinessInvestigationRunStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def request(
        self,
        scope: TenantScope,
        run: BusinessInvestigationRunRecord,
        *,
        idempotency_key: str,
    ) -> BusinessInvestigationRunWrite:
        if (run.tenant.org_id, run.tenant.project_id) != scope.key:
            raise BusinessInvestigationRunConflict("Run tenant does not match Principal scope")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise BusinessInvestigationRunConflict("idempotency key must be non-empty and bounded")
        if run.calculated_content_hash() != run.content_hash:
            raise BusinessInvestigationRunConflict("Run content hash drifted")
        payload = run.model_dump(by_alias=True, mode="json")
        request_hash = _canonical_hash(payload)
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    "SELECT authority_data,outcome,replayed FROM ecommerce_investigation_run_request_biw4_003(%s,%s,%s,%s)",
                    (run.run_id, idempotency_key, request_hash, Jsonb(payload)),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise BusinessInvestigationRunConflict("canonical Run request failed closed") from exc
        if row is None:
            raise BusinessInvestigationRunConflict("canonical Run request returned no Receipt")
        return BusinessInvestigationRunWrite(
            authority=BusinessInvestigationRunRecord.model_validate(row["authority_data"]),
            outcome=BusinessInvestigationRunRequestOutcome(row["outcome"]),
            replayed=bool(row["replayed"]),
        )

    def get(self, scope: TenantScope, run_id: str) -> BusinessInvestigationRunView:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT r.authority_data AS run_authority,s.authority_data AS state_authority
                    FROM ecommerce_investigation_run r
                    JOIN ecommerce_investigation_run_state_head s
                      ON s.org_id=r.org_id AND s.project_id=r.project_id AND s.run_id=r.run_id
                    WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s""",
                    (*scope.key, run_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise BusinessInvestigationRunConflict("canonical Run query failed closed") from exc
        if row is None:
            raise BusinessInvestigationRunNotFound("BusinessInvestigationRun is not visible")
        return BusinessInvestigationRunView(
            authority=BusinessInvestigationRunRecord.model_validate(row["run_authority"]),
            state=BusinessInvestigationRunStateRevision.model_validate(row["state_authority"]),
        )

    def list_for_case(
        self,
        scope: TenantScope,
        case_id: str,
        *,
        limit: int = 50,
    ) -> list[BusinessInvestigationRunView]:
        if limit < 1 or limit > 200:
            raise BusinessInvestigationRunConflict("Run query limit must be 1..200")
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """SELECT r.authority_data AS run_authority,s.authority_data AS state_authority
                    FROM ecommerce_investigation_run r
                    JOIN ecommerce_investigation_run_state_head s
                      ON s.org_id=r.org_id AND s.project_id=r.project_id AND s.run_id=r.run_id
                    WHERE r.org_id=%s AND r.project_id=%s AND r.case_id=%s
                    ORDER BY r.created_at DESC,r.run_id ASC LIMIT %s""",
                    (*scope.key, case_id, limit),
                ).fetchall()
        except psycopg.Error as exc:
            raise BusinessInvestigationRunConflict("canonical Run list failed closed") from exc
        return [
            BusinessInvestigationRunView(
                authority=BusinessInvestigationRunRecord.model_validate(row["run_authority"]),
                state=BusinessInvestigationRunStateRevision.model_validate(row["state_authority"]),
            )
            for row in rows
        ]

    def transition_control(
        self,
        scope: TenantScope,
        run_id: str,
        target: BusinessInvestigationRunControl,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateWrite:
        if expected_version < 1:
            raise BusinessInvestigationRunConflict("expected version must be positive")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise BusinessInvestigationRunConflict("idempotency key must be non-empty and bounded")
        if target not in {
            BusinessInvestigationRunControl.RUNNING,
            BusinessInvestigationRunControl.PAUSED,
            BusinessInvestigationRunControl.CANCELLED,
        }:
            raise BusinessInvestigationRunConflict("Run control is outside BI-W4-06 scope")
        try:
            with self._connect_factory(scope) as conn:
                replay = conn.execute(
                    """SELECT run_id,expected_version,authority_data
                    FROM ecommerce_investigation_run_control_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='business_investigation_run.control' AND idempotency_key=%s""",
                    (*scope.key, idempotency_key),
                ).fetchone()
        except psycopg.Error as exc:
            raise BusinessInvestigationRunConflict("canonical Run control replay query failed closed") from exc
        if replay is not None:
            authority = BusinessInvestigationRunStateRevision.model_validate(replay["authority_data"])
            if (
                replay["run_id"] != run_id
                or int(replay["expected_version"]) != expected_version
                or authority.control is not target
            ):
                raise BusinessInvestigationRunConflict("Run control idempotency conflict")
            return BusinessInvestigationRunStateWrite(authority=authority, replayed=True)
        previous = self.get(scope, run_id).state
        if previous.version != expected_version:
            raise BusinessInvestigationRunConflict("Run expected version conflict")
        payload = {
            "schemaVersion": "aos.ecommerce.business-investigation-run-state/v1",
            "tenant": previous.tenant.model_dump(by_alias=True, mode="json"),
            "runId": run_id,
            "version": expected_version + 1,
            "priorRef": {
                "resourceType": "BusinessInvestigationRunStateRevision",
                "resourceId": run_id,
                "revision": expected_version,
                "contentHash": previous.content_hash,
            },
            "lifecycle": BusinessInvestigationRunLifecycle.PREPARING.value,
            "control": target.value,
            "eventSequence": previous.event_sequence + 1,
            "contentHash": "sha256:" + "0" * 64,
            "createdBy": actor,
            "createdAt": occurred_at.isoformat(),
        }
        successor = BusinessInvestigationRunStateRevision.model_validate(payload)
        payload["contentHash"] = successor.calculated_content_hash()
        request_hash = _canonical_hash(
            {"runId": run_id, "expectedVersion": expected_version, "targetControl": target.value}
        )
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT authority_data,replayed
                    FROM ecommerce_investigation_run_control_biw4_006(%s,%s,%s,%s,%s)""",
                    (run_id, expected_version, idempotency_key, request_hash, Jsonb(payload)),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise BusinessInvestigationRunConflict("canonical Run control failed closed") from exc
        if row is None:
            raise BusinessInvestigationRunConflict("canonical Run control returned no Receipt")
        return BusinessInvestigationRunStateWrite(
            authority=BusinessInvestigationRunStateRevision.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )


__all__ = [
    "BusinessInvestigationRunConflict",
    "BusinessInvestigationRunControl",
    "BusinessInvestigationRunLifecycle",
    "BusinessInvestigationRunNotFound",
    "BusinessInvestigationRunRecord",
    "BusinessInvestigationRunRequestOutcome",
    "BusinessInvestigationRunStore",
    "BusinessInvestigationRunStateRevision",
    "BusinessInvestigationRunStateWrite",
    "BusinessInvestigationRunView",
    "BusinessInvestigationRunWrite",
    "BusinessInvestigationTriggerKind",
]
