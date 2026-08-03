"""Pure M4 integration-case stage projection policy v1.

This module deliberately owns only the deterministic policy.  Persistence,
public DTOs, authorization, canonical hashing, and HTTP error projection are
implemented by later M4 waves.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TypeAlias

STAGE_POLICY_VERSION = "integration-stage-policy/v1"


class IntegrationStage(StrEnum):
    PLANNED = "planned"
    CONNECTION_VERIFIED = "connection_verified"
    DATA_VERIFIED = "data_verified"
    ONTOLOGY_VERIFIED = "ontology_verified"
    LOGIC_VERIFIED = "logic_verified"
    WORKSHOP_VERIFIED = "workshop_verified"
    PRODUCTION_READY = "production_ready"
    PRODUCTION_ACTIVE = "production_active"


STAGE_ORDER = (
    IntegrationStage.PLANNED,
    IntegrationStage.CONNECTION_VERIFIED,
    IntegrationStage.DATA_VERIFIED,
    IntegrationStage.ONTOLOGY_VERIFIED,
    IntegrationStage.LOGIC_VERIFIED,
    IntegrationStage.WORKSHOP_VERIFIED,
    IntegrationStage.PRODUCTION_READY,
    IntegrationStage.PRODUCTION_ACTIVE,
)


class IntegrationEvidenceType(StrEnum):
    SOURCE_CONNECTION = "source_connection"
    TENANT_ISOLATION = "tenant_isolation"
    PIPELINE_RUN = "pipeline_run"
    DATASET_REVISION = "dataset_revision"
    DATA_QUALITY = "data_quality"
    ONTOLOGY_REVISION = "ontology_revision"
    MAPPING_VALIDATION = "mapping_validation"
    LOGIC_PUBLICATION = "logic_publication"
    LOGIC_EVAL = "logic_eval"
    WORKSHOP_VALIDATION = "workshop_validation"
    ACTION_SAFETY = "action_safety"
    OPERATIONS_READINESS = "operations_readiness"
    SECURITY_VALIDATION = "security_validation"
    RUNTIME_HEALTH = "runtime_health"


class IntegrationEvidenceOutcome(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    REVOKED = "revoked"


class StageBlockerCode(StrEnum):
    PLANNED_BASIS_INCOMPLETE = "planned_basis_incomplete"
    MISSING_EVIDENCE = "missing_evidence"
    LATEST_INVALID = "latest_invalid"
    LATEST_REVOKED = "latest_revoked"
    NOT_YET_OBSERVED = "not_yet_observed"
    EXPIRED = "expired"
    CLAIM_FAILED = "claim_failed"
    OPEN_BLOCKER = "open_blocker"


class StagePolicyIntegrityError(ValueError):
    """The supplied canonical policy input is structurally inconsistent."""


@dataclass(frozen=True, slots=True)
class OptionalMeasurement:
    """Preserve the material distinction between unmeasured and measured zero."""

    value: int | None
    measured: bool


def optional_measurement(value: int | None) -> OptionalMeasurement:
    if value is None:
        return OptionalMeasurement(value=None, measured=False)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StagePolicyIntegrityError(
            "optional measurement must be null or a non-negative integer"
        )
    return OptionalMeasurement(value=value, measured=True)


@dataclass(frozen=True, slots=True)
class SourceConnectionClaims:
    read_probe_passed: bool
    tenant_binding_valid: bool


@dataclass(frozen=True, slots=True)
class TenantIsolationClaims:
    positive_tenant_bound: bool
    negative_tenant_tested: bool
    cross_tenant_denied: bool


@dataclass(frozen=True, slots=True)
class PipelineRunClaims:
    succeeded: bool
    input_revision_valid: bool
    output_revision_valid: bool


@dataclass(frozen=True, slots=True)
class DatasetRevisionClaims:
    revision_valid: bool
    schema_hash_valid: bool
    row_count: int | None

    def __post_init__(self) -> None:
        optional_measurement(self.row_count)


@dataclass(frozen=True, slots=True)
class DataQualityClaims:
    required_passed: bool


@dataclass(frozen=True, slots=True)
class OntologyRevisionClaims:
    revision_valid: bool
    schema_hash_valid: bool


@dataclass(frozen=True, slots=True)
class MappingValidationClaims:
    coverage_complete: bool
    link_validation_passed: bool


@dataclass(frozen=True, slots=True)
class LogicPublicationClaims:
    immutable_revision: bool
    publication_hash_valid: bool


@dataclass(frozen=True, slots=True)
class LogicEvalClaims:
    required_passed: bool


@dataclass(frozen=True, slots=True)
class WorkshopValidationClaims:
    real_source: bool
    empty_state_passed: bool
    permission_passed: bool
    main_flow_passed: bool


@dataclass(frozen=True, slots=True)
class ActionSafetyClaims:
    approval_control: bool
    rollback_control: bool
    idempotency_control: bool
    installation_apply_verified: bool
    installation_verify_verified: bool


@dataclass(frozen=True, slots=True)
class OperationsReadinessClaims:
    runbook_present: bool
    alerting_present: bool
    owner_present: bool
    required_checks_passed: bool


@dataclass(frozen=True, slots=True)
class SecurityValidationClaims:
    required_checks_passed: bool


@dataclass(frozen=True, slots=True)
class RuntimeHealthClaims:
    healthy: bool
    latency_ms: int | None

    def __post_init__(self) -> None:
        optional_measurement(self.latency_ms)


IntegrationStageClaims: TypeAlias = (
    SourceConnectionClaims
    | TenantIsolationClaims
    | PipelineRunClaims
    | DatasetRevisionClaims
    | DataQualityClaims
    | OntologyRevisionClaims
    | MappingValidationClaims
    | LogicPublicationClaims
    | LogicEvalClaims
    | WorkshopValidationClaims
    | ActionSafetyClaims
    | OperationsReadinessClaims
    | SecurityValidationClaims
    | RuntimeHealthClaims
)


@dataclass(frozen=True, slots=True)
class PlannedBasis:
    exact_instance_revision: bool
    active_installation_revision: bool
    composition_lock_valid: bool
    composition_hash_valid: bool

    @property
    def complete(self) -> bool:
        return _all_true(
            self.exact_instance_revision,
            self.active_installation_revision,
            self.composition_lock_valid,
            self.composition_hash_valid,
        )


@dataclass(frozen=True, slots=True)
class StageEvidence:
    evidence_id: str
    revision: int
    evidence_type: IntegrationEvidenceType
    producer: str
    series_key: str
    outcome: IntegrationEvidenceOutcome
    observed_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    claims: IntegrationStageClaims

    @property
    def reference(self) -> str:
        return f"{self.evidence_id}@{self.revision}"


@dataclass(frozen=True, slots=True)
class StageBlocker:
    stage: IntegrationStage
    code: StageBlockerCode
    evidence_type: IntegrationEvidenceType | None = None
    evidence_ref: str | None = None
    series_key: str | None = None


@dataclass(frozen=True, slots=True)
class StageGateDecision:
    stage: IntegrationStage
    gate_satisfied: bool
    continuous_satisfied: bool
    evidence_refs: tuple[str, ...]
    blockers: tuple[StageBlocker, ...]


@dataclass(frozen=True, slots=True)
class StagePolicyResult:
    policy_version: str
    stage: IntegrationStage | None
    cutoff_at: datetime
    next_projection_at: datetime | None
    gates: tuple[StageGateDecision, ...]
    blockers: tuple[StageBlocker, ...]


def _claims_pass(claims: IntegrationStageClaims) -> bool:
    if isinstance(claims, SourceConnectionClaims):
        return _all_true(claims.read_probe_passed, claims.tenant_binding_valid)
    if isinstance(claims, TenantIsolationClaims):
        return _all_true(
            claims.positive_tenant_bound,
            claims.negative_tenant_tested,
            claims.cross_tenant_denied,
        )
    if isinstance(claims, PipelineRunClaims):
        return _all_true(
            claims.succeeded,
            claims.input_revision_valid,
            claims.output_revision_valid,
        )
    if isinstance(claims, DatasetRevisionClaims):
        return _all_true(claims.revision_valid, claims.schema_hash_valid)
    if isinstance(claims, DataQualityClaims):
        return claims.required_passed is True
    if isinstance(claims, OntologyRevisionClaims):
        return _all_true(claims.revision_valid, claims.schema_hash_valid)
    if isinstance(claims, MappingValidationClaims):
        return _all_true(claims.coverage_complete, claims.link_validation_passed)
    if isinstance(claims, LogicPublicationClaims):
        return _all_true(claims.immutable_revision, claims.publication_hash_valid)
    if isinstance(claims, LogicEvalClaims):
        return claims.required_passed is True
    if isinstance(claims, WorkshopValidationClaims):
        return _all_true(
            claims.real_source,
            claims.empty_state_passed,
            claims.permission_passed,
            claims.main_flow_passed,
        )
    if isinstance(claims, ActionSafetyClaims):
        return _all_true(
            claims.approval_control,
            claims.rollback_control,
            claims.idempotency_control,
            claims.installation_apply_verified,
            claims.installation_verify_verified,
        )
    if isinstance(claims, OperationsReadinessClaims):
        return _all_true(
            claims.runbook_present,
            claims.alerting_present,
            claims.owner_present,
            claims.required_checks_passed,
        )
    if isinstance(claims, SecurityValidationClaims):
        return claims.required_checks_passed is True
    if isinstance(claims, RuntimeHealthClaims):
        return claims.healthy is True
    raise StagePolicyIntegrityError("unsupported integration evidence claims")


def _all_true(*values: object) -> bool:
    return all(value is True for value in values)


_CLAIMS_TYPE_BY_EVIDENCE = {
    IntegrationEvidenceType.SOURCE_CONNECTION: SourceConnectionClaims,
    IntegrationEvidenceType.TENANT_ISOLATION: TenantIsolationClaims,
    IntegrationEvidenceType.PIPELINE_RUN: PipelineRunClaims,
    IntegrationEvidenceType.DATASET_REVISION: DatasetRevisionClaims,
    IntegrationEvidenceType.DATA_QUALITY: DataQualityClaims,
    IntegrationEvidenceType.ONTOLOGY_REVISION: OntologyRevisionClaims,
    IntegrationEvidenceType.MAPPING_VALIDATION: MappingValidationClaims,
    IntegrationEvidenceType.LOGIC_PUBLICATION: LogicPublicationClaims,
    IntegrationEvidenceType.LOGIC_EVAL: LogicEvalClaims,
    IntegrationEvidenceType.WORKSHOP_VALIDATION: WorkshopValidationClaims,
    IntegrationEvidenceType.ACTION_SAFETY: ActionSafetyClaims,
    IntegrationEvidenceType.OPERATIONS_READINESS: OperationsReadinessClaims,
    IntegrationEvidenceType.SECURITY_VALIDATION: SecurityValidationClaims,
    IntegrationEvidenceType.RUNTIME_HEALTH: RuntimeHealthClaims,
}

_STAGE_REQUIREMENTS = {
    IntegrationStage.CONNECTION_VERIFIED: (
        IntegrationEvidenceType.SOURCE_CONNECTION,
        IntegrationEvidenceType.TENANT_ISOLATION,
    ),
    IntegrationStage.DATA_VERIFIED: (
        IntegrationEvidenceType.PIPELINE_RUN,
        IntegrationEvidenceType.DATASET_REVISION,
        IntegrationEvidenceType.DATA_QUALITY,
        IntegrationEvidenceType.TENANT_ISOLATION,
    ),
    IntegrationStage.ONTOLOGY_VERIFIED: (
        IntegrationEvidenceType.ONTOLOGY_REVISION,
        IntegrationEvidenceType.MAPPING_VALIDATION,
    ),
    IntegrationStage.LOGIC_VERIFIED: (
        IntegrationEvidenceType.LOGIC_PUBLICATION,
        IntegrationEvidenceType.LOGIC_EVAL,
    ),
    IntegrationStage.WORKSHOP_VERIFIED: (IntegrationEvidenceType.WORKSHOP_VALIDATION,),
    IntegrationStage.PRODUCTION_READY: (
        IntegrationEvidenceType.ACTION_SAFETY,
        IntegrationEvidenceType.OPERATIONS_READINESS,
        IntegrationEvidenceType.SECURITY_VALIDATION,
    ),
    IntegrationStage.PRODUCTION_ACTIVE: (IntegrationEvidenceType.RUNTIME_HEALTH,),
}


def evaluate_stage_policy(
    *,
    planned_basis: PlannedBasis,
    evidence: tuple[StageEvidence, ...] | list[StageEvidence],
    cutoff_at: datetime,
    open_blockers: tuple[str, ...] | list[str] = (),
) -> StagePolicyResult:
    """Evaluate the highest continuously satisfied M4 stage at one cutoff."""

    _require_aware_time(cutoff_at, label="cutoff_at")
    heads = _latest_series_heads(evidence)
    blockers_by_stage: dict[IntegrationStage, tuple[StageBlocker, ...]] = {}
    evidence_by_stage: dict[IntegrationStage, tuple[StageEvidence, ...]] = {}

    if planned_basis.complete:
        blockers_by_stage[IntegrationStage.PLANNED] = ()
    else:
        blockers_by_stage[IntegrationStage.PLANNED] = (
            StageBlocker(
                stage=IntegrationStage.PLANNED,
                code=StageBlockerCode.PLANNED_BASIS_INCOMPLETE,
            ),
        )
    evidence_by_stage[IntegrationStage.PLANNED] = ()

    for stage in STAGE_ORDER[1:]:
        stage_evidence: list[StageEvidence] = []
        stage_blockers: list[StageBlocker] = []
        for evidence_type in _STAGE_REQUIREMENTS[stage]:
            type_heads = tuple(
                item for item in heads if item.evidence_type == evidence_type
            )
            if not type_heads:
                stage_blockers.append(
                    StageBlocker(
                        stage=stage,
                        code=StageBlockerCode.MISSING_EVIDENCE,
                        evidence_type=evidence_type,
                    )
                )
                continue
            valid_heads: list[StageEvidence] = []
            for item in type_heads:
                blocker = _evidence_blocker(item, stage=stage, cutoff_at=cutoff_at)
                if blocker is None:
                    valid_heads.append(item)
                else:
                    stage_blockers.append(blocker)
            if valid_heads:
                stage_evidence.extend(valid_heads)
            else:
                continue
        if stage == IntegrationStage.PRODUCTION_ACTIVE and open_blockers:
            stage_blockers.append(
                StageBlocker(
                    stage=stage,
                    code=StageBlockerCode.OPEN_BLOCKER,
                )
            )
        blockers_by_stage[stage] = tuple(_sorted_blockers(stage_blockers))
        evidence_by_stage[stage] = tuple(_sorted_evidence(stage_evidence))

    gates: list[StageGateDecision] = []
    highest: IntegrationStage | None = None
    continuous = True
    participating: list[StageEvidence] = []
    for stage in STAGE_ORDER:
        gate_satisfied = not blockers_by_stage[stage]
        continuous = continuous and gate_satisfied
        stage_evidence = evidence_by_stage[stage]
        if continuous:
            highest = stage
            participating.extend(stage_evidence)
        gates.append(
            StageGateDecision(
                stage=stage,
                gate_satisfied=gate_satisfied,
                continuous_satisfied=continuous,
                evidence_refs=tuple(item.reference for item in stage_evidence),
                blockers=blockers_by_stage[stage],
            )
        )

    next_projection_at = min(
        (
            item.expires_at
            for item in participating
            if item.expires_at is not None and item.expires_at > cutoff_at
        ),
        default=None,
    )
    unresolved = tuple(
        blocker
        for gate in gates
        if not gate.continuous_satisfied
        for blocker in gate.blockers
    )
    return StagePolicyResult(
        policy_version=STAGE_POLICY_VERSION,
        stage=highest,
        cutoff_at=cutoff_at,
        next_projection_at=next_projection_at,
        gates=tuple(gates),
        blockers=unresolved,
    )


def _latest_series_heads(
    evidence: tuple[StageEvidence, ...] | list[StageEvidence],
) -> tuple[StageEvidence, ...]:
    heads: dict[tuple[str, str], StageEvidence] = {}
    revisions: set[tuple[str, str, int]] = set()
    for item in evidence:
        _validate_evidence(item)
        revision_key = (item.producer, item.series_key, item.revision)
        if revision_key in revisions:
            raise StagePolicyIntegrityError(
                "integration evidence series revision must be unique"
            )
        revisions.add(revision_key)
        key = (item.producer, item.series_key)
        current = heads.get(key)
        if current is not None and (
            item.evidence_id != current.evidence_id
            or item.evidence_type != current.evidence_type
        ):
            raise StagePolicyIntegrityError(
                "integration evidence series identity must remain immutable"
            )
        if current is None or item.revision > current.revision:
            heads[key] = item
    return tuple(_sorted_evidence(heads.values()))


def _validate_evidence(item: StageEvidence) -> None:
    if not isinstance(item, StageEvidence):
        raise StagePolicyIntegrityError("evidence must be a StageEvidence record")
    if not item.evidence_id or not item.producer or not item.series_key:
        raise StagePolicyIntegrityError("evidence identity must be non-empty")
    if isinstance(item.revision, bool) or not isinstance(item.revision, int):
        raise StagePolicyIntegrityError("evidence revision must be a positive integer")
    if item.revision < 1:
        raise StagePolicyIntegrityError("evidence revision must be a positive integer")
    if not isinstance(item.evidence_type, IntegrationEvidenceType):
        raise StagePolicyIntegrityError("evidence type is invalid")
    if not isinstance(item.outcome, IntegrationEvidenceOutcome):
        raise StagePolicyIntegrityError("evidence outcome is invalid")
    _require_aware_time(item.observed_at, label="observed_at")
    if item.expires_at is not None:
        _require_aware_time(item.expires_at, label="expires_at")
        if item.expires_at <= item.observed_at:
            raise StagePolicyIntegrityError("expires_at must follow observed_at")
    if item.outcome == IntegrationEvidenceOutcome.REVOKED:
        if item.revoked_at is None:
            raise StagePolicyIntegrityError("revoked evidence requires revoked_at")
        _require_aware_time(item.revoked_at, label="revoked_at")
        if item.revoked_at < item.observed_at:
            raise StagePolicyIntegrityError("revoked_at must not precede observed_at")
    elif item.revoked_at is not None:
        raise StagePolicyIntegrityError("revoked_at is only valid for revoked evidence")
    expected_claims = _CLAIMS_TYPE_BY_EVIDENCE[item.evidence_type]
    if not isinstance(item.claims, expected_claims):
        raise StagePolicyIntegrityError("evidence type and typed claims do not match")


def _evidence_blocker(
    item: StageEvidence,
    *,
    stage: IntegrationStage,
    cutoff_at: datetime,
) -> StageBlocker | None:
    common = {
        "stage": stage,
        "evidence_type": item.evidence_type,
        "evidence_ref": item.reference,
        "series_key": item.series_key,
    }
    if item.observed_at > cutoff_at:
        return StageBlocker(code=StageBlockerCode.NOT_YET_OBSERVED, **common)
    if item.outcome == IntegrationEvidenceOutcome.REVOKED:
        return StageBlocker(code=StageBlockerCode.LATEST_REVOKED, **common)
    if item.outcome == IntegrationEvidenceOutcome.INVALID:
        return StageBlocker(code=StageBlockerCode.LATEST_INVALID, **common)
    if item.expires_at is not None and cutoff_at >= item.expires_at:
        return StageBlocker(code=StageBlockerCode.EXPIRED, **common)
    if not _claims_pass(item.claims):
        return StageBlocker(code=StageBlockerCode.CLAIM_FAILED, **common)
    return None


def _require_aware_time(value: datetime, *, label: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise StagePolicyIntegrityError(f"{label} must be timezone-aware")


def _sorted_evidence(items: Iterable[StageEvidence]) -> list[StageEvidence]:
    return sorted(
        items,
        key=lambda item: (
            item.evidence_type.value,
            item.producer,
            item.series_key,
            item.revision,
            item.evidence_id,
        ),
    )


def _sorted_blockers(items: list[StageBlocker]) -> list[StageBlocker]:
    return sorted(
        items,
        key=lambda item: (
            item.code.value,
            item.evidence_type.value if item.evidence_type else "",
            item.series_key or "",
            item.evidence_ref or "",
        ),
    )
