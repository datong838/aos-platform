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


class BusinessInvestigationUncertainCommand(AipContractModel):
    command_id: str = Field(min_length=1, max_length=200)
    operation: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,119}$")
    request_hash: str = Field(pattern=SHA256)


class BusinessInvestigationRunStateRevision(AipContractModel):
    schema_version: str = "aos.ecommerce.business-investigation-run-state/v1"
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    prior_ref: InvestigationExactRef | None = None
    lifecycle: Literal[
        BusinessInvestigationRunLifecycle.PREPARING,
        BusinessInvestigationRunLifecycle.WAITING_DATA,
    ]
    control: Literal[
        BusinessInvestigationRunControl.RUNNING,
        BusinessInvestigationRunControl.PAUSED,
        BusinessInvestigationRunControl.UNKNOWN,
        BusinessInvestigationRunControl.RECONCILING,
        BusinessInvestigationRunControl.CANCELLED,
    ]
    event_sequence: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256)
    pending_requirement_ref: InvestigationExactRef | None = None
    uncertain_command: BusinessInvestigationUncertainCommand | None = None
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
            if (
                self.prior_ref is not None
                or self.lifecycle is not BusinessInvestigationRunLifecycle.PREPARING
                or self.control is not BusinessInvestigationRunControl.RUNNING
                or self.pending_requirement_ref is not None
                or self.uncertain_command is not None
            ):
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
        if self.lifecycle is BusinessInvestigationRunLifecycle.WAITING_DATA:
            if (
                self.pending_requirement_ref is None
                or self.pending_requirement_ref.resource_type != "DataRequirementRevision"
                or not isinstance(self.pending_requirement_ref.revision, int)
            ):
                raise ValueError("WAITING_DATA requires exact DataRequirementRevision")
        elif self.pending_requirement_ref is not None:
            raise ValueError("PREPARING cannot carry pendingRequirementRef")
        if self.control in {
            BusinessInvestigationRunControl.UNKNOWN,
            BusinessInvestigationRunControl.RECONCILING,
        }:
            if self.uncertain_command is None:
                raise ValueError("UNKNOWN/RECONCILING requires uncertainCommand")
        elif self.uncertain_command is not None:
            raise ValueError("stable Run control cannot carry uncertainCommand")
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


def _strict_state_authority(
    raw: Any, *, error: str
) -> BusinessInvestigationRunStateRevision:
    authority = BusinessInvestigationRunStateRevision.model_validate(raw)
    if (
        _canonical_hash(raw)
        != _canonical_hash(authority.model_dump(by_alias=True, mode="json"))
        or authority.calculated_content_hash() != authority.content_hash
    ):
        raise BusinessInvestigationRunConflict(error)
    return authority


def _strict_legacy_state_authority(
    raw: Any, *, error: str
) -> BusinessInvestigationRunStateRevision:
    """Validate BIW4 state JSON with its two known serialization differences."""
    if (
        type(raw) is not dict
        or type(raw.get("version")) is not int
        or type(raw.get("eventSequence")) is not int
    ):
        raise BusinessInvestigationRunConflict(error)
    authority = BusinessInvestigationRunStateRevision.model_validate(raw)
    canonical = authority.model_dump(by_alias=True, mode="json")
    normalized_raw = {**raw, "createdAt": canonical["createdAt"]}
    normalized_canonical = canonical
    raw_prior = raw.get("priorRef")
    if (
        type(raw_prior) is dict
        and "receiptId" not in raw_prior
        and canonical.get("priorRef", {}).get("receiptId") is None
    ):
        normalized_canonical = {
            **canonical,
            "priorRef": {
                key: value
                for key, value in canonical["priorRef"].items()
                if key != "receiptId"
            },
        }
    if (
        _canonical_hash(normalized_raw) != _canonical_hash(normalized_canonical)
        or authority.calculated_content_hash() != authority.content_hash
    ):
        raise BusinessInvestigationRunConflict(error)
    return authority


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
                    FROM public.ecommerce_investigation_run r
                    JOIN public.ecommerce_investigation_run_state_head s
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

    def read_state_exact(
        self, scope: TenantScope, state_ref: InvestigationExactRef
    ) -> BusinessInvestigationRunStateRevision | None:
        """Read one immutable Run state revision and recompute its authority hash."""
        if (
            state_ref.resource_type != "BusinessInvestigationRunStateRevision"
            or type(state_ref.revision) is not int
        ):
            raise BusinessInvestigationRunConflict("exact Run state ref is required")
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT authority_data FROM public.ecommerce_investigation_run_state_revision
                    WHERE org_id=%s AND project_id=%s AND run_id=%s AND version=%s""",
                (*scope.key, state_ref.resource_id, state_ref.revision),
            ).fetchone()
        if row is None:
            return None
        authority = _strict_legacy_state_authority(
            row["authority_data"], error="historical Run state authority drifted"
        )
        if (
            (authority.tenant.org_id, authority.tenant.project_id) != scope.key
            or authority.run_id != state_ref.resource_id
            or authority.version != state_ref.revision
            or authority.content_hash != state_ref.content_hash
        ):
            raise BusinessInvestigationRunConflict(
                "historical Run state exact ref drifted"
            )
        return authority

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

    def read_data_request_receipt(
        self, scope: TenantScope, run_id: str, requirement_ref: InvestigationExactRef,
        *, expected_version: int, idempotency_key: str,
    ) -> BusinessInvestigationRunStateRevision | None:
        """Verify a historical request-data transition without current runtime state."""
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT run_id,expected_version,authority_data
                    FROM public.ecommerce_investigation_run_state_transition_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='business_investigation_run.request_data' AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        authority = BusinessInvestigationRunStateRevision.model_validate(row["authority_data"])
        if (row["run_id"] != run_id or int(row["expected_version"]) != expected_version
                or (authority.tenant.org_id, authority.tenant.project_id) != scope.key
                or authority.run_id != run_id or authority.version != expected_version + 1
                or authority.lifecycle is not BusinessInvestigationRunLifecycle.WAITING_DATA
                or authority.control is not BusinessInvestigationRunControl.RUNNING
                or authority.pending_requirement_ref != requirement_ref
                or authority.uncertain_command is not None
                or authority.calculated_content_hash() != authority.content_hash):
            raise BusinessInvestigationRunConflict("historical data-request Receipt drifted")
        return authority

    def request_data(
        self,
        scope: TenantScope,
        run_id: str,
        requirement_ref: InvestigationExactRef,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateWrite:
        if (
            requirement_ref.resource_type != "DataRequirementRevision"
            or not isinstance(requirement_ref.revision, int)
        ):
            raise BusinessInvestigationRunConflict(
                "request-data requires exact DataRequirementRevision"
            )
        return self._transition_extended(
            scope,
            run_id,
            operation="business_investigation_run.request_data",
            target_lifecycle=BusinessInvestigationRunLifecycle.WAITING_DATA,
            target_control=BusinessInvestigationRunControl.RUNNING,
            pending_requirement_ref=requirement_ref,
            uncertain_command=None,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )

    def read_data_resume_receipt(
        self, scope: TenantScope, run_id: str, requirement_ref: InvestigationExactRef,
        *, expected_version: int, idempotency_key: str,
    ) -> BusinessInvestigationRunStateRevision | None:
        """Verify a historical data-resume transition without consulting the head."""
        expected_request_hash = _canonical_hash(
            {
                "runId": run_id,
                "expectedVersion": expected_version,
                "operation": "business_investigation_run.resume_after_data",
                "requirementRef": requirement_ref.model_dump(by_alias=True, mode="json"),
            }
        )
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT run_id,expected_version,request_hash,authority_data
                    FROM public.ecommerce_investigation_run_state_transition_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='business_investigation_run.resume_after_data'
                      AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        authority = _strict_state_authority(
            row["authority_data"], error="historical data-resume Receipt drifted"
        )
        if (
            row["run_id"] != run_id
            or int(row["expected_version"]) != expected_version
            or row["request_hash"] != expected_request_hash
            or (authority.tenant.org_id, authority.tenant.project_id) != scope.key
            or authority.run_id != run_id
            or authority.version != expected_version + 1
            or authority.lifecycle is not BusinessInvestigationRunLifecycle.PREPARING
            or authority.control is not BusinessInvestigationRunControl.RUNNING
            or authority.pending_requirement_ref is not None
            or authority.uncertain_command is not None
        ):
            raise BusinessInvestigationRunConflict("historical data-resume Receipt drifted")
        return authority

    def resume_after_data(
        self,
        scope: TenantScope,
        run_id: str,
        requirement_ref: InvestigationExactRef,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateWrite:
        if (
            requirement_ref.resource_type != "DataRequirementRevision"
            or type(requirement_ref.revision) is not int
        ):
            raise BusinessInvestigationRunConflict(
                "data resume requires exact DataRequirementRevision"
            )
        if expected_version < 1:
            raise BusinessInvestigationRunConflict("expected version must be positive")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise BusinessInvestigationRunConflict("idempotency key must be non-empty and bounded")
        replay = self.read_data_resume_receipt(
            scope,
            run_id,
            requirement_ref,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            return BusinessInvestigationRunStateWrite(authority=replay, replayed=True)
        previous = self.get(scope, run_id).state
        if previous.version != expected_version:
            raise BusinessInvestigationRunConflict("Run expected version conflict")
        if (
            previous.lifecycle is not BusinessInvestigationRunLifecycle.WAITING_DATA
            or previous.control is not BusinessInvestigationRunControl.RUNNING
            or previous.pending_requirement_ref != requirement_ref
            or previous.uncertain_command is not None
        ):
            raise BusinessInvestigationRunConflict("Run data-resume authority rejected")
        requirement_payload = requirement_ref.model_dump(by_alias=True, mode="json")
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
            "control": BusinessInvestigationRunControl.RUNNING.value,
            "eventSequence": previous.event_sequence + 1,
            "contentHash": "sha256:" + "0" * 64,
            "pendingRequirementRef": None,
            "uncertainCommand": None,
            "createdBy": actor,
            "createdAt": occurred_at.isoformat(),
        }
        successor = BusinessInvestigationRunStateRevision.model_validate(payload)
        payload = successor.model_dump(by_alias=True, mode="json")
        payload["contentHash"] = successor.calculated_content_hash()
        request_hash = _canonical_hash(
            {
                "runId": run_id,
                "expectedVersion": expected_version,
                "operation": "business_investigation_run.resume_after_data",
                "requirementRef": requirement_payload,
            }
        )
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT authority_data,replayed
                    FROM public.ecommerce_investigation_run_data_resume_ar2_011(%s,%s,%s,%s,%s,%s)""",
                    (
                        run_id,
                        expected_version,
                        idempotency_key,
                        request_hash,
                        Jsonb(requirement_payload),
                        Jsonb(payload),
                    ),
                ).fetchone()
                if row is None:
                    raise BusinessInvestigationRunConflict(
                        "canonical Run data resume returned no Receipt"
                    )
                authority = _strict_state_authority(
                    row["authority_data"], error="canonical Run data resume drifted"
                )
                conn.commit()
        except psycopg.Error as exc:
            raise BusinessInvestigationRunConflict(
                "canonical Run data resume failed closed"
            ) from exc
        return BusinessInvestigationRunStateWrite(
            authority=authority,
            replayed=bool(row["replayed"]),
        )

    def mark_unknown(
        self,
        scope: TenantScope,
        run_id: str,
        uncertain_command: BusinessInvestigationUncertainCommand,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateWrite:
        previous = self.get(scope, run_id).state
        return self._transition_extended(
            scope,
            run_id,
            operation="business_investigation_run.mark_unknown",
            target_lifecycle=previous.lifecycle,
            target_control=BusinessInvestigationRunControl.UNKNOWN,
            pending_requirement_ref=previous.pending_requirement_ref,
            uncertain_command=uncertain_command,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
            previous=previous,
        )

    def begin_reconcile(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateWrite:
        previous = self.get(scope, run_id).state
        if previous.uncertain_command is None:
            raise BusinessInvestigationRunConflict("reconcile requires prior uncertainCommand")
        return self._transition_extended(
            scope,
            run_id,
            operation="business_investigation_run.begin_reconcile",
            target_lifecycle=previous.lifecycle,
            target_control=BusinessInvestigationRunControl.RECONCILING,
            pending_requirement_ref=previous.pending_requirement_ref,
            uncertain_command=previous.uncertain_command,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
            previous=previous,
        )

    def read_reconcile_receipt(
        self,
        scope: TenantScope,
        observed_unknown: BusinessInvestigationRunStateRevision,
        *,
        idempotency_key: str,
    ) -> BusinessInvestigationRunStateRevision | None:
        """Verify the immutable UNKNOWN -> RECONCILING transition Receipt."""
        if (
            (observed_unknown.tenant.org_id, observed_unknown.tenant.project_id)
            != scope.key
            or observed_unknown.control is not BusinessInvestigationRunControl.UNKNOWN
            or observed_unknown.uncertain_command is None
            or observed_unknown.calculated_content_hash()
            != observed_unknown.content_hash
            or not idempotency_key.strip()
            or len(idempotency_key) > 200
        ):
            raise BusinessInvestigationRunConflict(
                "historical reconcile predecessor drifted"
            )
        expected_request_hash = _canonical_hash(
            {
                "runId": observed_unknown.run_id,
                "expectedVersion": observed_unknown.version,
                "operation": "business_investigation_run.begin_reconcile",
                "pendingRequirementRef": (
                    observed_unknown.pending_requirement_ref.model_dump(
                        by_alias=True, mode="json"
                    )
                    if observed_unknown.pending_requirement_ref
                    else None
                ),
                "uncertainCommand": observed_unknown.uncertain_command.model_dump(
                    by_alias=True, mode="json"
                ),
            }
        )
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT run_id,expected_version,request_hash,authority_data
                    FROM public.ecommerce_investigation_run_state_transition_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='business_investigation_run.begin_reconcile'
                      AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        authority = _strict_legacy_state_authority(
            row["authority_data"], error="historical reconcile Receipt drifted"
        )
        expected_prior = InvestigationExactRef(
            resource_type="BusinessInvestigationRunStateRevision",
            resource_id=observed_unknown.run_id,
            revision=observed_unknown.version,
            content_hash=observed_unknown.content_hash,
        )
        if (
            row["run_id"] != observed_unknown.run_id
            or int(row["expected_version"]) != observed_unknown.version
            or row["request_hash"] != expected_request_hash
            or (authority.tenant.org_id, authority.tenant.project_id) != scope.key
            or authority.run_id != observed_unknown.run_id
            or authority.version != observed_unknown.version + 1
            or authority.prior_ref != expected_prior
            or authority.lifecycle is not observed_unknown.lifecycle
            or authority.control is not BusinessInvestigationRunControl.RECONCILING
            or authority.pending_requirement_ref
            != observed_unknown.pending_requirement_ref
            or authority.uncertain_command != observed_unknown.uncertain_command
        ):
            raise BusinessInvestigationRunConflict(
                "historical reconcile Receipt drifted"
            )
        return authority

    def _transition_extended(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        operation: str,
        target_lifecycle: BusinessInvestigationRunLifecycle,
        target_control: BusinessInvestigationRunControl,
        pending_requirement_ref: InvestigationExactRef | None,
        uncertain_command: BusinessInvestigationUncertainCommand | None,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
        previous: BusinessInvestigationRunStateRevision | None = None,
    ) -> BusinessInvestigationRunStateWrite:
        if expected_version < 1:
            raise BusinessInvestigationRunConflict("expected version must be positive")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise BusinessInvestigationRunConflict("idempotency key must be non-empty and bounded")
        try:
            with self._connect_factory(scope) as conn:
                replay = conn.execute(
                    """SELECT run_id,expected_version,authority_data
                    FROM public.ecommerce_investigation_run_state_transition_receipt
                    WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s""",
                    (*scope.key, operation, idempotency_key),
                ).fetchone()
        except psycopg.Error as exc:
            raise BusinessInvestigationRunConflict(
                "canonical Run state replay query failed closed"
            ) from exc
        if replay is not None:
            authority = BusinessInvestigationRunStateRevision.model_validate(
                replay["authority_data"]
            )
            if (
                replay["run_id"] != run_id
                or int(replay["expected_version"]) != expected_version
                or authority.lifecycle is not target_lifecycle
                or authority.control is not target_control
                or authority.pending_requirement_ref != pending_requirement_ref
                or authority.uncertain_command != uncertain_command
            ):
                raise BusinessInvestigationRunConflict("Run state idempotency conflict")
            return BusinessInvestigationRunStateWrite(authority=authority, replayed=True)
        previous = previous or self.get(scope, run_id).state
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
            "lifecycle": target_lifecycle.value,
            "control": target_control.value,
            "eventSequence": previous.event_sequence + 1,
            "contentHash": "sha256:" + "0" * 64,
            "pendingRequirementRef": (
                pending_requirement_ref.model_dump(by_alias=True, mode="json")
                if pending_requirement_ref
                else None
            ),
            "uncertainCommand": (
                uncertain_command.model_dump(by_alias=True, mode="json")
                if uncertain_command
                else None
            ),
            "createdBy": actor,
            "createdAt": occurred_at.isoformat(),
        }
        successor = BusinessInvestigationRunStateRevision.model_validate(payload)
        payload["contentHash"] = successor.calculated_content_hash()
        request_hash = _canonical_hash(
            {
                "runId": run_id,
                "expectedVersion": expected_version,
                "operation": operation,
                "pendingRequirementRef": payload["pendingRequirementRef"],
                "uncertainCommand": payload["uncertainCommand"],
            }
        )
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT authority_data,replayed
                    FROM public.ecommerce_investigation_run_state_transition_biw4_007(%s,%s,%s,%s,%s,%s)""",
                    (
                        run_id,
                        expected_version,
                        operation,
                        idempotency_key,
                        request_hash,
                        Jsonb(payload),
                    ),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise BusinessInvestigationRunConflict(
                "canonical Run state transition failed closed"
            ) from exc
        if row is None:
            raise BusinessInvestigationRunConflict(
                "canonical Run state transition returned no Receipt"
            )
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
    "BusinessInvestigationUncertainCommand",
]
