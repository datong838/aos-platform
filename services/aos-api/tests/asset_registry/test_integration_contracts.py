from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_CASE_DETAIL_ADAPTER,
    INTEGRATION_EVIDENCE_ADAPTER,
    STAGE_POLICY_VERSION,
    CreateIntegrationCaseRequest,
    CreateIntegrationEvidenceSnapshotRequest,
    EvidenceType,
    IntegrationCaseListResponse,
    IntegrationCaseTimelineResponse,
    IntegrationEvidenceSnapshot,
    IntegrationEvidenceSnapshotResponse,
    IntegrationStage,
)
from pydantic import ValidationError

UUID_1 = "00000000-0000-4000-8000-000000000001"
UUID_2 = "00000000-0000-4000-8000-000000000002"
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
UTC = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


CLAIMS = {
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
        "schemaHash": HASH_A,
        "rowCount": 10,
    },
    "data_quality": {
        "datasetRef": "dataset:orders",
        "checkSetHash": HASH_A,
        "requiredPassed": True,
        "failedChecks": [],
    },
    "ontology_revision": {
        "ontologyRef": "ontology:commerce",
        "revision": "revision:1",
        "schemaHash": HASH_A,
    },
    "mapping_validation": {
        "mappingRef": "mapping:orders",
        "coverage": 1.0,
        "linkValidationPassed": True,
    },
    "logic_publication": {
        "logicRef": "logic:pricing",
        "immutableRevision": "revision:1",
        "publicationHash": HASH_A,
    },
    "logic_eval": {
        "logicRef": "logic:pricing",
        "evalSuiteHash": HASH_A,
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
        "policySetHash": HASH_A,
        "requiredChecksPassed": True,
    },
    "runtime_health": {
        "deploymentRef": "deployment:primary",
        "runId": "run:health:1",
        "healthy": True,
        "latencyMs": 25,
    },
}


def evidence_payload(evidence_type: str = "source_connection") -> dict[str, object]:
    return {
        "evidenceId": UUID_1,
        "revision": 1,
        "evidenceType": evidence_type,
        "seriesKey": f"series:{evidence_type}",
        "subjectRef": "case:subject",
        "artifactRef": "artifact:immutable:1",
        "artifactHash": HASH_A,
        "outcome": "valid",
        "observedAt": UTC,
        "expiresAt": None,
        "revokedAt": None,
        "requiredMarkings": ["marking:internal"],
        "producer": "producer:trusted",
        "claims": deepcopy(CLAIMS[evidence_type]),
        "evidenceHash": HASH_B,
        "recordedAt": UTC,
    }


def list_item() -> dict[str, object]:
    return {
        "caseId": UUID_1,
        "scope": "current",
        "displayName": "Primary integration",
        "owner": "owner:operations",
        "installationId": UUID_2,
        "overlayRevision": "overlay:1",
        "computedStage": "planned",
        "snapshotRevision": None,
        "cutoffAt": None,
        "blockerCount": 0,
        "etagVersion": 1,
        "createdAt": UTC,
        "updatedAt": UTC,
    }


def metric(aggregation: str = "count") -> dict[str, object]:
    return {
        "value": 1,
        "aggregation": aggregation,
        "measuredCaseCount": 1,
        "eligibleCaseCount": 1,
        "cutoffAt": UTC,
    }


def statistics() -> dict[str, object]:
    return {
        "caseCount": metric(),
        "productionActiveCount": metric(),
        "connectorCount": metric(),
        "pipelineCount": metric("distinct_count"),
        "datasetRowCount": metric("sum"),
        "latencyMs": metric("max"),
    }


def detail_metrics() -> dict[str, object]:
    result = statistics()
    result.pop("caseCount")
    result.pop("productionActiveCount")
    return result


@pytest.mark.parametrize("evidence_type", list(CLAIMS))
def test_all_typed_evidence_claims_are_discriminated(evidence_type: str) -> None:
    envelope = INTEGRATION_EVIDENCE_ADAPTER.validate_python(
        evidence_payload(evidence_type)
    )
    assert envelope.evidence_type == EvidenceType(evidence_type)
    assert envelope.claims.__class__.__name__.endswith("Claims")


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("revision",), "1"),
        (("claims", "readProbe"), 1),
        (("evidenceId",), "00000000-0000-4000-8000-00000000000A"),
        (("artifactHash",), "A" * 64),
        (("observedAt",), UTC.replace(tzinfo=None)),
        (("seriesKey",), " token=do-not-store"),
        (("subjectRef",), "person@example.com"),
    ],
)
def test_envelope_rejects_coercion_noncanonical_and_sensitive_values(
    path: tuple[str, ...], value: object
) -> None:
    payload = evidence_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[assignment,index]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValidationError):
        INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload)


def test_claims_are_closed_and_cannot_carry_metadata_or_secrets() -> None:
    for forbidden in ("metadata", "password", "phone", "email"):
        payload = evidence_payload()
        payload["claims"][forbidden] = "forbidden"  # type: ignore[index]
        with pytest.raises(ValidationError):
            INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload)

    action = evidence_payload("action_safety")
    del action["claims"]["installationApplyVerified"]  # type: ignore[index]
    with pytest.raises(ValidationError):
        INTEGRATION_EVIDENCE_ADAPTER.validate_python(action)


def test_envelope_lifecycle_is_fail_closed() -> None:
    payload = evidence_payload()
    payload["outcome"] = "revoked"
    with pytest.raises(ValidationError):
        INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload)

    payload["revokedAt"] = UTC
    assert INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload).revoked_at == UTC


def test_create_case_and_snapshot_commands_are_minimal() -> None:
    request = CreateIntegrationCaseRequest.model_validate(
        {
            "installationId": UUID_1,
            "overlayRevision": "overlay:1",
            "displayName": "Primary integration",
        }
    )
    assert request.installation_id == UUID_1
    assert CreateIntegrationEvidenceSnapshotRequest.model_validate({})

    for forbidden in ("stage", "evidence", "cutoffAt", "metrics", "producer"):
        with pytest.raises(ValidationError):
            CreateIntegrationCaseRequest.model_validate(
                {
                    "installationId": UUID_1,
                    "overlayRevision": "overlay:1",
                    "displayName": "Primary integration",
                    forbidden: "forged",
                }
            )
        with pytest.raises(ValidationError):
            CreateIntegrationEvidenceSnapshotRequest.model_validate({forbidden: True})


def test_wire_contract_rejects_snake_case_aliases() -> None:
    with pytest.raises(ValidationError):
        CreateIntegrationCaseRequest.model_validate(
            {
                "installation_id": UUID_1,
                "overlay_revision": "overlay:1",
                "display_name": "Primary integration",
            }
        )

    payload = evidence_payload()
    payload["evidence_id"] = payload.pop("evidenceId")
    with pytest.raises(ValidationError):
        INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload)


def test_case_list_detail_snapshot_and_timeline_contracts() -> None:
    item = list_item()
    assert IntegrationCaseListResponse.model_validate(
        {
            "items": [item],
            "scope": "current",
            "total": 1,
            "limit": 20,
            "offset": 0,
            "stats": statistics(),
        }
    ).total == 1

    detail = {
        **item,
        "installationRevision": 1,
        "compositionId": UUID_2,
        "lockRevision": 1,
        "lockHash": HASH_A,
        "stageGates": [
            {
                "stage": stage.value,
                "status": "satisfied" if stage == IntegrationStage.PLANNED else "not_evaluated",
                "evidenceRefs": [],
                "reasonRefs": [],
            }
            for stage in IntegrationStage
        ],
        "latestEvidence": [
            {
                "evidenceId": UUID_1,
                "revision": 1,
                "evidenceType": "source_connection",
                "subjectRef": "case:subject",
                "outcome": "valid",
                "observedAt": UTC,
                "expiresAt": None,
                "revokedAt": None,
                "artifactHash": HASH_A,
                "evidenceHash": HASH_B,
                "recordedAt": UTC,
            }
        ],
        "blockers": [],
        "nextProjectionAt": None,
        "metrics": detail_metrics(),
    }
    assert INTEGRATION_CASE_DETAIL_ADAPTER.validate_python(detail).metrics is not None

    snapshot = {
        "caseId": UUID_1,
        "snapshotRevision": 1,
        "instanceRevision": 1,
        "cutoffAt": UTC,
        "computedStage": "planned",
        "stagePolicyVersion": STAGE_POLICY_VERSION,
        "snapshotHash": HASH_A,
    }
    assert IntegrationEvidenceSnapshot.model_validate(
        {**snapshot, "evidence": [evidence_payload()]}
    ).evidence[0].claims.read_probe
    assert IntegrationEvidenceSnapshotResponse.model_validate(
        {
                **snapshot,
                "nextProjectionAt": None,
                "evidenceCount": 1,
            "stageGates": detail["stageGates"],
            "blockerRefs": [],
            "etagVersion": 1,
            "createdAt": UTC,
        }
    ).evidence_count == 1

    event = {
        "sequence": 1,
        "snapshotRevision": 1,
        "oldStage": None,
        "newStage": "planned",
        "cause": "created",
        "reasonRefs": ["instance:valid"],
        "createdAt": UTC,
    }
    assert IntegrationCaseTimelineResponse.model_validate(
        {
            "caseId": UUID_1,
            "scope": "current",
            "items": [event],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
    ).items[0].sequence == 1


def test_current_and_reference_case_shapes_are_isolated() -> None:
    current = list_item()
    reference = {
        **current,
        "scope": "reference",
        "owner": None,
        "installationId": None,
        "overlayRevision": None,
    }
    response = IntegrationCaseListResponse.model_validate(
        {
            "items": [reference],
            "scope": "reference",
            "total": 1,
            "limit": 20,
            "offset": 0,
            "stats": None,
        }
    )
    assert response.items[0].owner is None

    forged_reference = {**reference, "owner": "owner:leaked"}
    with pytest.raises(ValidationError):
        IntegrationCaseListResponse.model_validate(
            {
                "items": [forged_reference],
                "scope": "reference",
                "total": 1,
                "limit": 20,
                "offset": 0,
                "stats": None,
            }
        )

    forged_current = {**current, "installationId": None}
    with pytest.raises(ValidationError):
        IntegrationCaseListResponse.model_validate(
            {
                "items": [forged_current],
                "scope": "current",
                "total": 1,
                "limit": 20,
                "offset": 0,
                "stats": statistics(),
            }
        )

    with pytest.raises(ValidationError):
        IntegrationCaseListResponse.model_validate(
            {
                "items": [{**current, "installationRevision": 1}],
                "scope": "current",
                "total": 1,
                "limit": 20,
                "offset": 0,
                "stats": statistics(),
            }
        )

    gates = [
        {
            "stage": stage.value,
            "status": "not_evaluated",
            "evidenceRefs": [],
            "reasonRefs": [],
        }
        for stage in IntegrationStage
    ]
    reference_detail = {
        **reference,
        "installationRevision": None,
        "compositionId": None,
        "lockRevision": None,
        "lockHash": None,
        "stageGates": gates,
        "latestEvidence": [],
        "blockers": [],
        "nextProjectionAt": None,
        "metrics": None,
    }
    assert INTEGRATION_CASE_DETAIL_ADAPTER.validate_python(reference_detail).metrics is None


@pytest.mark.parametrize("aggregation", ["count_distinct", "sum_deduplicated"])
def test_legacy_metric_aggregations_are_rejected(aggregation: str) -> None:
    invalid = metric(aggregation)
    with pytest.raises(ValidationError):
        IntegrationCaseListResponse.model_validate(
            {
                "items": [],
                "scope": "current",
                "total": 0,
                "limit": 20,
                "offset": 0,
                "stats": {**statistics(), "caseCount": invalid},
            }
        )


def test_public_snapshot_and_timeline_reject_raw_or_private_fields() -> None:
    snapshot = {
        "caseId": UUID_1,
        "snapshotRevision": 1,
        "instanceRevision": 1,
        "cutoffAt": UTC,
        "computedStage": "planned",
        "stagePolicyVersion": STAGE_POLICY_VERSION,
        "snapshotHash": HASH_A,
        "nextProjectionAt": None,
        "evidenceCount": 0,
        "stageGates": [
            {
                "stage": stage.value,
                "status": "not_evaluated",
                "evidenceRefs": [],
                "reasonRefs": [],
            }
            for stage in IntegrationStage
        ],
        "blockerRefs": [],
        "etagVersion": 1,
        "createdAt": UTC,
        "claims": {},
    }
    with pytest.raises(ValidationError):
        IntegrationEvidenceSnapshotResponse.model_validate(snapshot)

    event = {
        "sequence": 1,
        "snapshotRevision": 1,
        "oldStage": None,
        "newStage": "planned",
        "cause": "created",
        "reasonRefs": [],
        "createdAt": UTC,
        "actor": "internal-user",
    }
    with pytest.raises(ValidationError):
        IntegrationCaseTimelineResponse.model_validate(
            {
                "caseId": UUID_1,
                "scope": "current",
                "items": [event],
                "total": 1,
                "limit": 20,
                "offset": 0,
            }
        )


def test_budgets_and_metric_truth_semantics_are_enforced() -> None:
    payload = evidence_payload("data_quality")
    payload["claims"]["failedChecks"] = [f"check:{index}" for index in range(129)]  # type: ignore[index]
    with pytest.raises(ValidationError):
        INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload)

    invalid_metric = metric()
    invalid_metric["measuredCaseCount"] = 2
    with pytest.raises(ValidationError):
        IntegrationCaseListResponse.model_validate(
            {
                "items": [],
                "scope": "current",
                "total": 0,
                "limit": 20,
                "offset": 0,
                "stats": {
                    **statistics(),
                    "connectorCount": invalid_metric,
                },
            }
        )
