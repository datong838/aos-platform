from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.asset_registry.integration_contracts import INTEGRATION_EVIDENCE_ADAPTER
from aos_api.asset_registry.integration_stage_policy import (
    STAGE_ORDER,
    STAGE_POLICY_VERSION,
    ActionSafetyClaims,
    DataQualityClaims,
    DatasetRevisionClaims,
    IntegrationEvidenceOutcome,
    IntegrationEvidenceType,
    IntegrationStage,
    LogicEvalClaims,
    LogicPublicationClaims,
    MappingValidationClaims,
    OntologyRevisionClaims,
    OperationsReadinessClaims,
    PipelineRunClaims,
    PlannedBasis,
    RuntimeHealthClaims,
    SecurityValidationClaims,
    SourceConnectionClaims,
    StageBlockerCode,
    StageEvidence,
    StagePolicyIntegrityError,
    TenantIsolationClaims,
    WorkshopValidationClaims,
    evaluate_contract_stage_policy,
    evaluate_stage_policy,
    optional_measurement,
)

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)
COMPLETE_BASIS = PlannedBasis(
    exact_instance_revision=True,
    active_installation_revision=True,
    composition_lock_valid=True,
    composition_hash_valid=True,
)


def _claims() -> dict[IntegrationEvidenceType, object]:
    return {
        IntegrationEvidenceType.SOURCE_CONNECTION: SourceConnectionClaims(True, True),
        IntegrationEvidenceType.TENANT_ISOLATION: TenantIsolationClaims(
            True, True, True
        ),
        IntegrationEvidenceType.PIPELINE_RUN: PipelineRunClaims(True, True, True),
        IntegrationEvidenceType.DATASET_REVISION: DatasetRevisionClaims(True, True, 0),
        IntegrationEvidenceType.DATA_QUALITY: DataQualityClaims(True),
        IntegrationEvidenceType.ONTOLOGY_REVISION: OntologyRevisionClaims(True, True),
        IntegrationEvidenceType.MAPPING_VALIDATION: MappingValidationClaims(True, True),
        IntegrationEvidenceType.LOGIC_PUBLICATION: LogicPublicationClaims(True, True),
        IntegrationEvidenceType.LOGIC_EVAL: LogicEvalClaims(True),
        IntegrationEvidenceType.WORKSHOP_VALIDATION: WorkshopValidationClaims(
            True, True, True, True
        ),
        IntegrationEvidenceType.ACTION_SAFETY: ActionSafetyClaims(
            True, True, True, True, True
        ),
        IntegrationEvidenceType.OPERATIONS_READINESS: OperationsReadinessClaims(
            True, True, True, True
        ),
        IntegrationEvidenceType.SECURITY_VALIDATION: SecurityValidationClaims(True),
        IntegrationEvidenceType.RUNTIME_HEALTH: RuntimeHealthClaims(True, None),
    }


def _evidence(
    evidence_type: IntegrationEvidenceType,
    *,
    revision: int = 1,
    outcome: IntegrationEvidenceOutcome = IntegrationEvidenceOutcome.VALID,
    observed_at: datetime = NOW - timedelta(hours=1),
    expires_at: datetime | None = NOW + timedelta(days=1),
    revoked_at: datetime | None = None,
) -> StageEvidence:
    return StageEvidence(
        evidence_id=f"evidence-{evidence_type.value}-{revision}",
        revision=revision,
        evidence_type=evidence_type,
        producer="platform-producer",
        series_key=evidence_type.value,
        outcome=outcome,
        observed_at=observed_at,
        expires_at=expires_at,
        revoked_at=revoked_at,
        claims=_claims()[evidence_type],
    )


def _full_evidence() -> list[StageEvidence]:
    return [_evidence(evidence_type) for evidence_type in IntegrationEvidenceType]


def _gate(result, stage: IntegrationStage):
    return next(item for item in result.gates if item.stage == stage)


def test_policy_v1_has_eight_ordered_continuous_stages() -> None:
    assert STAGE_POLICY_VERSION == "aos.integration-stage/v1"
    assert STAGE_ORDER == (
        IntegrationStage.PLANNED,
        IntegrationStage.CONNECTION_VERIFIED,
        IntegrationStage.DATA_VERIFIED,
        IntegrationStage.ONTOLOGY_VERIFIED,
        IntegrationStage.LOGIC_VERIFIED,
        IntegrationStage.WORKSHOP_VERIFIED,
        IntegrationStage.PRODUCTION_READY,
        IntegrationStage.PRODUCTION_ACTIVE,
    )


def test_full_valid_evidence_reaches_active_and_uses_earliest_expiry() -> None:
    evidence = _full_evidence()
    source = next(
        item
        for item in evidence
        if item.evidence_type == IntegrationEvidenceType.SOURCE_CONNECTION
    )
    evidence[evidence.index(source)] = replace(
        source, expires_at=NOW + timedelta(minutes=30)
    )

    result = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=list(reversed(evidence)),
        cutoff_at=NOW,
    )

    assert result.policy_version == STAGE_POLICY_VERSION
    assert result.stage == IntegrationStage.PRODUCTION_ACTIVE
    assert result.next_projection_at == NOW + timedelta(minutes=30)
    assert result.blockers == ()
    assert all(gate.gate_satisfied for gate in result.gates)
    assert all(gate.continuous_satisfied for gate in result.gates)


def test_canonical_contract_evidence_is_the_executable_policy_input() -> None:
    hash_value = "sha256:" + "a" * 64
    claims_by_type = {
        "source_connection": {
            "connectionRef": "connection:primary",
            "authMode": "oauth",
            "readProbe": True,
            "tenantBinding": True,
        },
        "tenant_isolation": {
            "positiveTenant": "tenant:positive",
            "negativeTenant": "tenant:negative",
            "crossTenantDenied": True,
        },
        "pipeline_run": {
            "pipelineRef": "pipeline:orders",
            "runId": "run:1",
            "result": "succeeded",
            "inputRevision": "input:1",
            "outputRevision": "output:1",
        },
        "dataset_revision": {
            "datasetRef": "dataset:orders",
            "revision": "revision:1",
            "schemaHash": hash_value,
            "rowCount": 0,
        },
        "data_quality": {
            "datasetRef": "dataset:orders",
            "checkSetHash": hash_value,
            "requiredPassed": True,
            "failedChecks": [],
        },
        "ontology_revision": {
            "ontologyRef": "ontology:commerce",
            "revision": "revision:1",
            "schemaHash": hash_value,
        },
        "mapping_validation": {
            "mappingRef": "mapping:orders",
            "coverage": 1.0,
            "linkValidationPassed": True,
        },
        "logic_publication": {
            "logicRef": "logic:pricing",
            "immutableRevision": "revision:1",
            "publicationHash": hash_value,
        },
        "logic_eval": {
            "logicRef": "logic:pricing",
            "evalSuiteHash": hash_value,
            "requiredPassed": True,
        },
        "workshop_validation": {
            "workshopRef": "workshop:operations",
            "realSource": True,
            "emptyStatePassed": True,
            "permissionPassed": True,
            "mainFlowPassed": True,
        },
        "action_safety": {
            "actionRef": "action:approve",
            "approvalControlPassed": True,
            "rollbackControlPassed": True,
            "idempotencyControlPassed": True,
            "installationApplyVerified": True,
            "installationVerifyVerified": True,
        },
        "operations_readiness": {
            "runbookRef": "runbook:primary",
            "alertRef": "alert:primary",
            "ownerRef": "owner:operations",
            "requiredChecksPassed": True,
        },
        "security_validation": {
            "policySetHash": hash_value,
            "requiredChecksPassed": True,
        },
        "runtime_health": {
            "deploymentRef": "deployment:primary",
            "runId": "run:health:1",
            "healthy": True,
            "latencyMs": 0,
        },
    }
    canonical = []
    for index, (evidence_type, claims) in enumerate(claims_by_type.items(), start=1):
        canonical.append(
            INTEGRATION_EVIDENCE_ADAPTER.validate_python(
                {
                    "evidenceId": f"00000000-0000-4000-8000-{index:012d}",
                    "revision": 1,
                    "evidenceType": evidence_type,
                    "seriesKey": f"series:{evidence_type}",
                    "subjectRef": "case:subject",
                    "artifactRef": f"artifact:{evidence_type}",
                    "artifactHash": hash_value,
                    "outcome": "valid",
                    "observedAt": NOW - timedelta(hours=1),
                    "expiresAt": NOW + timedelta(hours=1),
                    "revokedAt": None,
                    "requiredMarkings": ["marking:internal"],
                    "producer": "producer:trusted",
                    "claims": claims,
                    "evidenceHash": hash_value,
                    "recordedAt": NOW,
                }
            )
        )

    result = evaluate_contract_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=canonical,
        cutoff_at=NOW,
    )

    assert result.stage is IntegrationStage.PRODUCTION_ACTIVE
    assert result.policy_version == STAGE_POLICY_VERSION
    assert result.next_projection_at == NOW + timedelta(hours=1)


def test_incomplete_planned_basis_returns_no_claimed_stage() -> None:
    result = evaluate_stage_policy(
        planned_basis=replace(COMPLETE_BASIS, composition_hash_valid=False),
        evidence=_full_evidence(),
        cutoff_at=NOW,
    )

    assert result.stage is None
    assert result.next_projection_at is None
    assert result.gates[0].blockers[0].code == (
        StageBlockerCode.PLANNED_BASIS_INCOMPLETE
    )
    assert all(not gate.continuous_satisfied for gate in result.gates)


def test_missing_earlier_gate_prevents_jump_even_when_later_gates_pass() -> None:
    evidence = [
        item
        for item in _full_evidence()
        if item.evidence_type != IntegrationEvidenceType.SOURCE_CONNECTION
    ]

    result = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=evidence,
        cutoff_at=NOW,
    )

    assert result.stage == IntegrationStage.PLANNED
    connection = _gate(result, IntegrationStage.CONNECTION_VERIFIED)
    data = _gate(result, IntegrationStage.DATA_VERIFIED)
    assert connection.gate_satisfied is False
    assert connection.blockers[0].code == StageBlockerCode.MISSING_EVIDENCE
    assert data.gate_satisfied is True
    assert data.continuous_satisfied is False


@pytest.mark.parametrize(
    ("outcome", "revoked_at", "expected_code"),
    [
        (
            IntegrationEvidenceOutcome.INVALID,
            None,
            StageBlockerCode.LATEST_INVALID,
        ),
        (
            IntegrationEvidenceOutcome.REVOKED,
            NOW,
            StageBlockerCode.LATEST_REVOKED,
        ),
    ],
)
def test_latest_negative_series_head_never_falls_back_to_old_valid(
    outcome: IntegrationEvidenceOutcome,
    revoked_at: datetime | None,
    expected_code: StageBlockerCode,
) -> None:
    old = _evidence(IntegrationEvidenceType.SOURCE_CONNECTION)
    latest = replace(
        old,
        revision=2,
        outcome=outcome,
        revoked_at=revoked_at,
    )
    evidence = _full_evidence()
    evidence.append(latest)

    result = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=evidence,
        cutoff_at=NOW,
    )

    assert result.stage == IntegrationStage.PLANNED
    connection = _gate(result, IntegrationStage.CONNECTION_VERIFIED)
    assert connection.blockers[0].code == expected_code
    assert connection.blockers[0].evidence_ref == latest.reference


def test_observed_and_expiry_cutoff_boundaries_are_fail_closed() -> None:
    future = _evidence(
        IntegrationEvidenceType.SOURCE_CONNECTION,
        observed_at=NOW + timedelta(microseconds=1),
        expires_at=NOW + timedelta(hours=1),
    )
    future_result = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=[future],
        cutoff_at=NOW,
    )
    assert StageBlockerCode.NOT_YET_OBSERVED in {
        blocker.code
        for blocker in _gate(
            future_result, IntegrationStage.CONNECTION_VERIFIED
        ).blockers
    }

    evidence = _full_evidence()
    source = next(
        item
        for item in evidence
        if item.evidence_type == IntegrationEvidenceType.SOURCE_CONNECTION
    )
    evidence[evidence.index(source)] = replace(source, expires_at=NOW)
    at_expiry = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=evidence,
        cutoff_at=NOW,
    )
    assert at_expiry.stage == IntegrationStage.PLANNED
    assert StageBlockerCode.EXPIRED in {
        blocker.code
        for blocker in _gate(at_expiry, IntegrationStage.CONNECTION_VERIFIED).blockers
    }

    before_expiry = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=evidence,
        cutoff_at=NOW - timedelta(microseconds=1),
    )
    assert before_expiry.stage == IntegrationStage.PRODUCTION_ACTIVE


def test_failed_typed_claim_blocks_every_stage_that_requires_it() -> None:
    evidence = _full_evidence()
    tenant = next(
        item
        for item in evidence
        if item.evidence_type == IntegrationEvidenceType.TENANT_ISOLATION
    )
    evidence[evidence.index(tenant)] = replace(
        tenant,
        claims=TenantIsolationClaims(True, True, False),
    )

    result = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=evidence,
        cutoff_at=NOW,
    )

    assert result.stage == IntegrationStage.PLANNED
    assert _gate(result, IntegrationStage.CONNECTION_VERIFIED).blockers[0].code == (
        StageBlockerCode.CLAIM_FAILED
    )
    assert StageBlockerCode.CLAIM_FAILED in {
        blocker.code
        for blocker in _gate(result, IntegrationStage.DATA_VERIFIED).blockers
    }


def test_open_blocker_caps_an_otherwise_valid_case_at_production_ready() -> None:
    result = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=_full_evidence(),
        cutoff_at=NOW,
        open_blockers=["blocker-1"],
    )

    assert result.stage == IntegrationStage.PRODUCTION_READY
    active = _gate(result, IntegrationStage.PRODUCTION_ACTIVE)
    assert active.gate_satisfied is False
    assert StageBlockerCode.OPEN_BLOCKER in {
        blocker.code for blocker in active.blockers
    }


def test_null_is_unmeasured_while_explicit_zero_is_measured() -> None:
    assert optional_measurement(None).value is None
    assert optional_measurement(None).measured is False
    assert optional_measurement(0).value == 0
    assert optional_measurement(0).measured is True
    assert optional_measurement(8).measured is True
    with pytest.raises(StagePolicyIntegrityError):
        optional_measurement(-1)
    with pytest.raises(StagePolicyIntegrityError):
        optional_measurement(True)

    result = evaluate_stage_policy(
        planned_basis=COMPLETE_BASIS,
        evidence=_full_evidence(),
        cutoff_at=NOW,
    )
    assert result.stage == IntegrationStage.PRODUCTION_ACTIVE


def test_structural_corruption_fails_closed() -> None:
    source = _evidence(IntegrationEvidenceType.SOURCE_CONNECTION)
    with pytest.raises(StagePolicyIntegrityError, match="typed claims"):
        evaluate_stage_policy(
            planned_basis=COMPLETE_BASIS,
            evidence=[replace(source, claims=DataQualityClaims(True))],
            cutoff_at=NOW,
        )
    with pytest.raises(StagePolicyIntegrityError, match="series revision"):
        evaluate_stage_policy(
            planned_basis=COMPLETE_BASIS,
            evidence=[source, source],
            cutoff_at=NOW,
        )
    with pytest.raises(StagePolicyIntegrityError, match="series identity"):
        evaluate_stage_policy(
            planned_basis=COMPLETE_BASIS,
            evidence=[
                source,
                replace(source, evidence_id="different-id", revision=2),
            ],
            cutoff_at=NOW,
        )
    with pytest.raises(StagePolicyIntegrityError, match="timezone-aware"):
        evaluate_stage_policy(
            planned_basis=COMPLETE_BASIS,
            evidence=[],
            cutoff_at=NOW.replace(tzinfo=None),
        )
