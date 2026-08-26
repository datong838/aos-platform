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


@dataclass(frozen=True, slots=True)
class BusinessInvestigationRunWrite:
    authority: BusinessInvestigationRunRecord
    outcome: BusinessInvestigationRunRequestOutcome
    replayed: bool


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BusinessInvestigationRunConflict(RuntimeError):
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


__all__ = [
    "BusinessInvestigationRunConflict",
    "BusinessInvestigationRunControl",
    "BusinessInvestigationRunLifecycle",
    "BusinessInvestigationRunRecord",
    "BusinessInvestigationRunRequestOutcome",
    "BusinessInvestigationRunStore",
    "BusinessInvestigationRunWrite",
    "BusinessInvestigationTriggerKind",
]
