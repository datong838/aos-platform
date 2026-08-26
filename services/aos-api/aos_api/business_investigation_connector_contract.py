"""Disabled-fixture connector failure and restart contract acceptance."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef


MATRIX_SCHEMA = "aos.business-investigation.connector-failure-fixture-matrix/v1"
ACCEPTANCE_SCHEMA = "aos.business-investigation.connector-contract-acceptance/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


class ConnectorPlatform(StrEnum):
    NIUSHOP = "niushop"
    WECHAT_STORE = "wechat_store"
    DOUYIN_STORE = "douyin_store"


class FixtureSourceKind(StrEnum):
    SYNTHETIC = "synthetic"
    HISTORICAL_REDACTED = "historical_redacted"


class ConnectorScenario(StrEnum):
    CAPTCHA_REQUIRED = "captcha_required"
    PERMISSION_DENIED = "permission_denied"
    PAGE_DRIFT = "page_drift"
    LOADING_TIMEOUT = "loading_timeout"
    PAGINATION_INCOMPLETE = "pagination_incomplete"
    RATE_LIMITED = "rate_limited"
    SESSION_REVOKED = "session_revoked"
    SESSION_EXPIRED = "session_expired"
    PROCESS_RESTART = "process_restart"
    EXTERNAL_RESULT_UNKNOWN = "external_result_unknown"


class ConnectorOutcomeStatus(StrEnum):
    BLOCKED_HUMAN_ASSISTANCE = "blocked_human_assistance"
    BLOCKED_PERMISSION = "blocked_permission"
    BLOCKED_PAGE_DRIFT = "blocked_page_drift"
    PARTIAL_LOADING_TIMEOUT = "partial_loading_timeout"
    PARTIAL_PAGINATION = "partial_pagination"
    BLOCKED_RATE_LIMIT = "blocked_rate_limit"
    BLOCKED_SESSION_REVOKED = "blocked_session_revoked"
    BLOCKED_SESSION_EXPIRED = "blocked_session_expired"
    RESUMED_FROM_CHECKPOINT = "resumed_from_checkpoint"
    UNKNOWN_RECONCILE = "unknown_reconcile"


EXPECTED_OUTCOME = {
    ConnectorScenario.CAPTCHA_REQUIRED: ConnectorOutcomeStatus.BLOCKED_HUMAN_ASSISTANCE,
    ConnectorScenario.PERMISSION_DENIED: ConnectorOutcomeStatus.BLOCKED_PERMISSION,
    ConnectorScenario.PAGE_DRIFT: ConnectorOutcomeStatus.BLOCKED_PAGE_DRIFT,
    ConnectorScenario.LOADING_TIMEOUT: ConnectorOutcomeStatus.PARTIAL_LOADING_TIMEOUT,
    ConnectorScenario.PAGINATION_INCOMPLETE: ConnectorOutcomeStatus.PARTIAL_PAGINATION,
    ConnectorScenario.RATE_LIMITED: ConnectorOutcomeStatus.BLOCKED_RATE_LIMIT,
    ConnectorScenario.SESSION_REVOKED: ConnectorOutcomeStatus.BLOCKED_SESSION_REVOKED,
    ConnectorScenario.SESSION_EXPIRED: ConnectorOutcomeStatus.BLOCKED_SESSION_EXPIRED,
    ConnectorScenario.PROCESS_RESTART: ConnectorOutcomeStatus.RESUMED_FROM_CHECKPOINT,
    ConnectorScenario.EXTERNAL_RESULT_UNKNOWN: ConnectorOutcomeStatus.UNKNOWN_RECONCILE,
}

EXPECTED_BLOCKER = {
    ConnectorScenario.CAPTCHA_REQUIRED: "CAPTCHA_REQUIRED",
    ConnectorScenario.PERMISSION_DENIED: "BLOCKED_PERMISSION",
    ConnectorScenario.PAGE_DRIFT: "PAGE_CONTRACT_DRIFTED",
    ConnectorScenario.LOADING_TIMEOUT: "LOADING_TIMEOUT",
    ConnectorScenario.PAGINATION_INCOMPLETE: "PAGINATION_INCOMPLETE",
    ConnectorScenario.RATE_LIMITED: "RATE_LIMITED",
    ConnectorScenario.SESSION_REVOKED: "SESSION_REVOKED",
    ConnectorScenario.SESSION_EXPIRED: "SESSION_EXPIRED",
    ConnectorScenario.EXTERNAL_RESULT_UNKNOWN: "UNKNOWN_RECONCILE",
}


def _exact(ref: InvestigationExactRef, expected: str, name: str) -> None:
    if ref.resource_type != expected:
        raise ValueError(f"{name} must reference {expected}")


def _canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class ConnectorCoverage(AipContractModel):
    pages_expected: int = Field(ge=0)
    pages_observed: int = Field(ge=0)
    rows_expected: int = Field(ge=0)
    rows_observed: int = Field(ge=0)

    @model_validator(mode="after")
    def _bounded(self) -> Self:
        if self.pages_observed > self.pages_expected or self.rows_observed > self.rows_expected:
            raise ValueError("observed coverage cannot exceed expected coverage")
        return self


class ConnectorFailureFixture(AipContractModel):
    scenario_id: str = Field(min_length=1, max_length=160)
    tenant: TenantContext
    platform: ConnectorPlatform
    source_kind: FixtureSourceKind
    enabled: Literal[False]
    fixture_hash: str = Field(pattern=SHA256)
    adapter_pack_ref: InvestigationExactRef
    capability_ref: InvestigationExactRef
    session_ref: InvestigationExactRef
    observation_plan_ref: InvestigationExactRef
    step_ref: InvestigationExactRef
    scenario: ConnectorScenario
    outcome_status: ConnectorOutcomeStatus
    blockers: list[str] = Field(default_factory=list, max_length=20)
    coverage: ConnectorCoverage
    empty_observed: Literal[False]
    retry_scheduled: Literal[False]
    external_effect: Literal[False]
    captcha_auto_solved: Literal[False]
    attempt_number: Literal[1]
    checkpoint_session_ref: InvestigationExactRef | None = None
    resume_checkpoint_ref: InvestigationExactRef | None = None
    continuation_receipt_ref: InvestigationExactRef | None = None
    required_human_assistance: bool
    non_claims: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        _exact(self.adapter_pack_ref, "AdapterPackRevision", "adapterPackRef")
        _exact(self.capability_ref, "CapabilityRevision", "capabilityRef")
        _exact(self.session_ref, "ObservationSessionLeaseRevision", "sessionRef")
        _exact(self.observation_plan_ref, "ObservationPlanRevision", "observationPlanRef")
        _exact(self.step_ref, "ObservationPlanStepRevision", "stepRef")
        if self.outcome_status is not EXPECTED_OUTCOME[self.scenario]:
            raise ValueError("scenario outcome status drifted")
        expected_blocker = EXPECTED_BLOCKER.get(self.scenario)
        if expected_blocker is not None and expected_blocker not in self.blockers:
            raise ValueError("scenario blocker is missing")
        if self.scenario is ConnectorScenario.PROCESS_RESTART:
            if (
                self.blockers
                or self.checkpoint_session_ref is None
                or self.resume_checkpoint_ref is None
                or self.continuation_receipt_ref is None
            ):
                raise ValueError("restart requires exact checkpoint continuation without failure blockers")
            _exact(self.checkpoint_session_ref, "ObservationSessionLeaseRevision", "checkpointSessionRef")
            _exact(self.resume_checkpoint_ref, "ObservationCheckpointRevision", "resumeCheckpointRef")
            _exact(self.continuation_receipt_ref, "ObservationContinuationReceipt", "continuationReceiptRef")
            if self.checkpoint_session_ref != self.session_ref:
                raise ValueError("restart checkpoint must belong to the same observation session")
        elif (
            self.checkpoint_session_ref is not None
            or self.resume_checkpoint_ref is not None
            or self.continuation_receipt_ref is not None
        ):
            raise ValueError("only restart fixture may carry continuation refs")
        if self.required_human_assistance is not (self.scenario is ConnectorScenario.CAPTCHA_REQUIRED):
            raise ValueError("human assistance is required only for captcha fixture")
        if self.scenario in {ConnectorScenario.LOADING_TIMEOUT, ConnectorScenario.PAGINATION_INCOMPLETE}:
            if self.coverage.pages_observed >= self.coverage.pages_expected:
                raise ValueError("partial fixture must preserve incomplete coverage")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("fixtureHash")
        return _canonical_hash(value)


class ConnectorFailureFixtureMatrix(AipContractModel):
    schema_version: str = MATRIX_SCHEMA
    matrix_id: str = Field(min_length=1, max_length=160)
    revision: Literal[1]
    content_hash: str = Field(pattern=SHA256)
    cases: list[ConnectorFailureFixture] = Field(min_length=10, max_length=100)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != MATRIX_SCHEMA:
            raise ValueError("unsupported connector fixture matrix schema")
        if len({case.scenario_id for case in self.cases}) != len(self.cases):
            raise ValueError("scenario IDs must be unique")
        if len({(case.tenant.org_id, case.tenant.project_id) for case in self.cases}) != 1:
            raise ValueError("fixture matrix cases must belong to one tenant boundary")
        if set(case.platform for case in self.cases) != set(ConnectorPlatform):
            raise ValueError("fixture matrix must cover all connector platforms")
        if set(case.scenario for case in self.cases) != set(ConnectorScenario):
            raise ValueError("fixture matrix must cover every failure and restart scenario")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        return _canonical_hash(value)


class ConnectorContractAcceptanceReceipt(AipContractModel):
    schema_version: str = ACCEPTANCE_SCHEMA
    matrix_ref: InvestigationExactRef
    fixture_hash: str = Field(pattern=SHA256)
    platforms: list[ConnectorPlatform]
    scenario_count: int = Field(ge=1)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    outcome_counts: dict[ConnectorOutcomeStatus, int]
    status: Literal["passed"]
    non_claims: list[str] = Field(min_length=1)


def evaluate_connector_fixture_matrix(matrix: ConnectorFailureFixtureMatrix) -> ConnectorContractAcceptanceReceipt:
    for case in matrix.cases:
        if case.calculated_hash() != case.fixture_hash:
            raise ValueError(f"fixture hash drifted: {case.scenario_id}")
    if matrix.calculated_hash() != matrix.content_hash:
        raise ValueError("fixture matrix content hash drifted")
    outcome_counts = {outcome: 0 for outcome in ConnectorOutcomeStatus}
    for case in matrix.cases:
        outcome_counts[case.outcome_status] += 1
    return ConnectorContractAcceptanceReceipt(
        matrixRef={
            "resourceType": "ConnectorFailureFixtureMatrixRevision",
            "resourceId": matrix.matrix_id,
            "revision": matrix.revision,
            "contentHash": matrix.content_hash,
        },
        fixtureHash=matrix.content_hash,
        platforms=sorted(set(case.platform for case in matrix.cases), key=lambda item: item.value),
        scenarioCount=len(matrix.cases),
        passedCount=len(matrix.cases),
        failedCount=0,
        outcomeCounts=outcome_counts,
        status="passed",
        nonClaims=[
            "NO_REAL_PLATFORM_ACCESS",
            "NO_ADAPTER_INSTALLATION",
            "NO_SOURCE_READINESS_CLAIM",
            "NO_AUTOMATIC_RETRY",
            "NO_EXTERNAL_EFFECT",
        ],
    )
