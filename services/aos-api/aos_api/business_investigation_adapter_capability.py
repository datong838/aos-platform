"""Generic disabled-by-default capability contract for investigation AdapterPacks."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.business_investigation_shared_contracts import InvestigationExactRef


MATRIX_SCHEMA = "aos.business-investigation.adapter-capability-matrix/v1"
ACCEPTANCE_SCHEMA = "aos.business-investigation.adapter-capability-acceptance/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


class AdapterPlatform(StrEnum):
    NIUSHOP = "niushop"
    WECHAT_STORE = "wechat_store"
    DOUYIN_STORE = "douyin_store"


class AdapterLifecycleState(StrEnum):
    DECLARED = "declared"
    INSTALLED = "installed"
    CONFIGURED = "configured"
    SESSION_READY = "session_ready"
    CONTRACT_TESTED = "contract_tested"
    RUNTIME_VERIFIED = "runtime_verified"
    BLOCKED = "blocked"


class AdapterCapabilityMode(StrEnum):
    BROWSER_OBSERVATION = "browser_observation"
    CONTROLLED_EXPORT = "controlled_export"
    GOVERNED_API = "governed_api"
    READONLY_DATABASE = "readonly_database"


class AdapterAvailabilityState(StrEnum):
    DISABLED_TERMS_UNVERIFIED = "disabled_terms_unverified"
    DISABLED_NOT_INSTALLED = "disabled_not_installed"
    DISABLED_NOT_CONFIGURED = "disabled_not_configured"
    BLOCKED_SESSION_NOT_READY = "blocked_session_not_ready"
    BLOCKED_CONTRACT_NOT_TESTED = "blocked_contract_not_tested"
    BLOCKED_RUNTIME_UNVERIFIED = "blocked_runtime_unverified"
    BLOCKED_PERMISSION = "blocked_permission"
    BLOCKED_PAGE_DRIFT = "blocked_page_drift"
    PARTIAL_COVERAGE = "partial_coverage"
    UNKNOWN_RECONCILE = "unknown_reconcile"
    BLOCKED_ACTIVATION_NOT_AUTHORIZED = "blocked_activation_not_authorized"


BASELINE_ALLOWED_OPERATIONS = {
    "navigate",
    "wait",
    "scroll",
    "filter",
    "open_detail",
    "read",
}
CONDITIONALLY_ALLOWED_OPERATIONS = {"export_read", "schema_discover"}
FORBIDDEN_OPERATIONS = {
    "create",
    "update",
    "delete",
    "publish",
    "send",
    "reprice",
    "approve",
    "execute",
    "captcha_solve",
    "secret_resolve",
}


def _canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _exact(ref: InvestigationExactRef, expected: str, field: str) -> None:
    if ref.resource_type != expected:
        raise ValueError(f"{field} must reference {expected}")


class AdapterCapabilityEntry(AipContractModel):
    entry_id: str = Field(min_length=1, max_length=160)
    platform: AdapterPlatform
    capability_id: Literal["store.operation.read"]
    enabled: Literal[False]
    activation_allowed: Literal[False]
    risk_class: Literal["R0_READ_ONLY"]
    lifecycle_states: list[AdapterLifecycleState] = Field(min_length=1, max_length=7)
    modes: list[AdapterCapabilityMode] = Field(min_length=1, max_length=4)
    supported_facts: list[str] = Field(max_length=0)
    supported_entities: list[str] = Field(max_length=0)
    required_human_assistance: list[Literal["pre_authenticated_session"]]
    baseline_allowed_operations: list[str]
    conditionally_allowed_operations: list[str]
    forbidden_operations: list[str]
    output_schema_ref: InvestigationExactRef
    contract_suite_ref: InvestigationExactRef
    automatic_retry: Literal[False]
    empty_observed: Literal[False]
    external_effect: Literal[False]
    non_claims: list[str] = Field(min_length=1, max_length=20)
    entry_hash: str = Field(pattern=SHA256)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.lifecycle_states != [AdapterLifecycleState.DECLARED]:
            raise ValueError("disabled capability lifecycle must remain declared only")
        if self.modes != [AdapterCapabilityMode.BROWSER_OBSERVATION]:
            raise ValueError("BI-W9-01 exposes only the generic browser observation mode")
        if set(self.baseline_allowed_operations) != BASELINE_ALLOWED_OPERATIONS:
            raise ValueError("generic baseline operations drifted")
        if set(self.conditionally_allowed_operations) != CONDITIONALLY_ALLOWED_OPERATIONS:
            raise ValueError("generic conditional operations drifted")
        if not FORBIDDEN_OPERATIONS <= set(self.forbidden_operations):
            raise ValueError("generic forbidden operations are incomplete")
        operation_count = (
            len(self.baseline_allowed_operations)
            + len(self.conditionally_allowed_operations)
            + len(self.forbidden_operations)
        )
        if operation_count != len(
            set(self.baseline_allowed_operations)
            | set(self.conditionally_allowed_operations)
            | set(self.forbidden_operations)
        ):
            raise ValueError("operation groups must be unique and disjoint")
        _exact(self.output_schema_ref, "PlatformObservationReceiptSchemaRevision", "outputSchemaRef")
        _exact(self.contract_suite_ref, "AdapterContractSuiteRevision", "contractSuiteRef")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("entryHash")
        return _canonical_hash(value)


class AdapterCapabilityMatrix(AipContractModel):
    schema_version: str = MATRIX_SCHEMA
    matrix_id: str = Field(min_length=1, max_length=160)
    revision: Literal[1]
    content_hash: str = Field(pattern=SHA256)
    entries: list[AdapterCapabilityEntry] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != MATRIX_SCHEMA:
            raise ValueError("unsupported Adapter capability matrix schema")
        if len({item.entry_id for item in self.entries}) != len(self.entries):
            raise ValueError("Adapter capability entry IDs must be unique")
        if set(item.platform for item in self.entries) != set(AdapterPlatform):
            raise ValueError("Adapter capability matrix must cover all three platforms")
        if len({item.capability_id for item in self.entries}) != 1:
            raise ValueError("platforms must consume one generic capability ID")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        return _canonical_hash(value)


class AdapterReadinessProbe(AipContractModel):
    terms_verified: bool = False
    installed: bool = False
    configured: bool = False
    session_ready: bool = False
    contract_tested: bool = False
    runtime_verified: bool = False
    permission_granted: bool = True
    page_contract_current: bool = True
    coverage_complete: bool = True
    external_result_known: bool = True
    activation_authorized: Literal[False] = False
    automatic_retry: Literal[False] = False
    empty_observed: Literal[False] = False


class AdapterReadinessDecision(AipContractModel):
    state: AdapterAvailabilityState
    enabled: Literal[False]
    blocker_code: str
    retry_scheduled: Literal[False]
    empty_observed: Literal[False]
    external_effect: Literal[False]


class AdapterCapabilityAcceptanceReceipt(AipContractModel):
    schema_version: str = ACCEPTANCE_SCHEMA
    matrix_ref: InvestigationExactRef
    entry_count: Literal[3]
    platforms: list[AdapterPlatform]
    status: Literal["passed"]
    non_claims: list[str] = Field(min_length=1)


def evaluate_adapter_readiness(probe: AdapterReadinessProbe) -> AdapterReadinessDecision:
    gates = (
        (not probe.terms_verified, AdapterAvailabilityState.DISABLED_TERMS_UNVERIFIED, "PLATFORM_TERMS_UNVERIFIED"),
        (not probe.installed, AdapterAvailabilityState.DISABLED_NOT_INSTALLED, "ADAPTER_NOT_INSTALLED"),
        (not probe.configured, AdapterAvailabilityState.DISABLED_NOT_CONFIGURED, "ADAPTER_NOT_CONFIGURED"),
        (not probe.session_ready, AdapterAvailabilityState.BLOCKED_SESSION_NOT_READY, "SESSION_NOT_READY"),
        (not probe.contract_tested, AdapterAvailabilityState.BLOCKED_CONTRACT_NOT_TESTED, "CONTRACT_NOT_TESTED"),
        (not probe.runtime_verified, AdapterAvailabilityState.BLOCKED_RUNTIME_UNVERIFIED, "RUNTIME_NOT_VERIFIED"),
        (not probe.permission_granted, AdapterAvailabilityState.BLOCKED_PERMISSION, "BLOCKED_PERMISSION"),
        (not probe.page_contract_current, AdapterAvailabilityState.BLOCKED_PAGE_DRIFT, "PAGE_CONTRACT_DRIFTED"),
        (not probe.coverage_complete, AdapterAvailabilityState.PARTIAL_COVERAGE, "COVERAGE_INCOMPLETE"),
        (not probe.external_result_known, AdapterAvailabilityState.UNKNOWN_RECONCILE, "UNKNOWN_RECONCILE"),
    )
    state = AdapterAvailabilityState.BLOCKED_ACTIVATION_NOT_AUTHORIZED
    blocker = "ACTIVATION_NOT_AUTHORIZED"
    for failed, candidate, code in gates:
        if failed:
            state, blocker = candidate, code
            break
    return AdapterReadinessDecision(
        state=state,
        enabled=False,
        blockerCode=blocker,
        retryScheduled=False,
        emptyObserved=False,
        externalEffect=False,
    )


def evaluate_adapter_capability_matrix(matrix: AdapterCapabilityMatrix) -> AdapterCapabilityAcceptanceReceipt:
    for item in matrix.entries:
        if item.calculated_hash() != item.entry_hash:
            raise ValueError(f"entry hash drifted: {item.entry_id}")
    if matrix.calculated_hash() != matrix.content_hash:
        raise ValueError("matrix content hash drifted")
    return AdapterCapabilityAcceptanceReceipt(
        matrixRef={
            "resourceType": "AdapterCapabilityMatrixRevision",
            "resourceId": matrix.matrix_id,
            "revision": matrix.revision,
            "contentHash": matrix.content_hash,
        },
        entryCount=3,
        platforms=sorted((item.platform for item in matrix.entries), key=lambda value: value.value),
        status="passed",
        nonClaims=[
            "NO_ADAPTER_INSTALLATION",
            "NO_PLATFORM_TERMS_CLAIM",
            "NO_SOURCE_READINESS_CLAIM",
            "NO_REAL_PLATFORM_ACCESS",
            "NO_EXTERNAL_EFFECT",
        ],
    )
