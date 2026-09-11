from copy import deepcopy
from hashlib import sha256
import json

import pytest

from aos_api.ecommerce_analyst_diagnosis_generation import diagnosis_prompt, decision_from_completed_generation
from aos_api.ecommerce_analyst_authority_contracts import InsightRevision
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.aip_agent_run_executor import AipAgentRunExecutor
from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
from test_ecommerce_analyst_authority_contracts import insight, NOW
from test_ecommerce_analyst_growth_plan_draft import generation
from test_ecommerce_analyst_analysis_proposal import diagnosis


def fixture():
    source = InsightRevision.model_validate(insight())
    source = source.model_copy(update={"content_hash": canonical_hash(source.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
    payload = {"metric": "repeat_rate", "value": 0.2, "marking": ["internal"]}
    material = dict(bundleRef=source.evidence_refs[0].model_dump(mode="json", by_alias=True), cutoffAt=NOW.isoformat(), items=[dict(
        evidenceRef=dict(resourceType="Evidence", resourceId="raw-1", revision=1, contentHash=canonical_hash(payload)),
        disclosureRef=dict(resourceType="EvidenceDisclosureDecision", resourceId="grant-1", revision=1, contentHash="b" * 64),
        expiresAt=NOW.isoformat(), payload=payload)])
    query, system = diagnosis_prompt(source, [material])
    _, attempt, _ = generation()
    answer = json.dumps(diagnosis(), ensure_ascii=False)
    artifact = attempt.output_artifact_ref.model_copy(update={"content_hash": sha256(answer.encode()).hexdigest()})
    attempt = attempt.model_copy(update={"agent_run_id": "run-diagnosis", "output_artifact_ref": artifact})
    request = ExecuteAgentRunRequest(expectedAgentRunVersion=attempt.agent_run_version, attemptId=attempt.attempt_id, attemptNo=attempt.attempt_no,
        budgetRef=attempt.budget_ref, capacityReservationRef=attempt.capacity_reservation_ref, query=query, systemPrompt=system, dataClassification=attempt.data_classification)
    attempt = attempt.model_copy(update={"request_hash": AipAgentRunExecutor._request_hash(attempt.agent_run_id, request)})
    return source, [material], attempt, answer


def test_sourced_completed_answer_becomes_stable_provenanced_decision():
    source, materials, attempt, answer = fixture()
    first = decision_from_completed_generation(insight=source, materials=materials, attempt=attempt, answer=answer, actor="compiler")
    assert first == decision_from_completed_generation(insight=source, materials=materials, attempt=attempt, answer=answer, actor="compiler")
    assert first.conclusion == diagnosis()["conclusion"] and first.insight_ref.content_hash == source.content_hash
    assert first.evidence_refs == source.evidence_refs and first.generation_artifact_ref.resource_id == attempt.output_artifact_ref.artifact_id
    assert first.content_hash == canonical_hash(first.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))


def test_original_authorization_metadata_does_not_change_model_request():
    source, materials, _, _ = fixture()
    original = diagnosis_prompt(source, materials)
    materials[0]["items"][0]["disclosureRef"]["resourceId"] = "renewed-grant"
    materials[0]["items"][0]["expiresAt"] = "2026-09-12T12:00:00+00:00"
    assert diagnosis_prompt(source, materials) == original
    assert "grant-1" not in original[0] and "expiresAt" not in original[0]


@pytest.mark.parametrize("drift", ["insight", "missing", "duplicate", "bundle", "body", "evidence_kind", "future_cutoff", "oversize"])
def test_invalid_source_context_is_rejected(drift):
    source, materials, _, _ = fixture()
    if drift == "insight": source = source.model_copy(update={"summary": "changed"})
    elif drift == "missing": materials.clear()
    elif drift == "duplicate": materials.append(deepcopy(materials[0]))
    elif drift == "bundle": materials[0]["bundleRef"]["contentHash"] = "c" * 64
    elif drift == "body": materials[0]["items"][0]["payload"]["value"] = 999
    elif drift == "evidence_kind": materials[0]["items"][0]["evidenceRef"]["resourceType"] = "Task"
    elif drift == "future_cutoff": materials[0]["cutoffAt"] = "2026-09-12T12:00:00+00:00"
    elif drift == "oversize":
        item = materials[0]["items"][0]
        item["payload"]["large"] = "字" * 16000
        item["evidenceRef"]["contentHash"] = canonical_hash(item["payload"])
    with pytest.raises(ValueError): diagnosis_prompt(source, materials)


@pytest.mark.parametrize("drift", ["unknown", "answer", "request", "receipt", "usage", "tenant", "artifact", "actor"])
def test_unproven_generation_is_rejected(drift):
    source, materials, attempt, answer = fixture()
    actor = "compiler"
    if drift == "unknown": attempt = attempt.model_copy(update={"status": "unknown"})
    elif drift == "answer": answer += " "
    elif drift == "request": attempt = attempt.model_copy(update={"request_hash": "c" * 64})
    elif drift == "receipt": attempt = attempt.model_copy(update={"provider_receipt_id": None})
    elif drift == "usage": attempt = attempt.model_copy(update={"usage_receipt_ids": []})
    elif drift == "tenant": attempt = attempt.model_copy(update={"tenant": attempt.tenant.model_copy(update={"org_id": "other"})})
    elif drift == "artifact": attempt = attempt.model_copy(update={"output_artifact_ref": None})
    elif drift == "actor": actor = "other"
    with pytest.raises(ValueError):
        decision_from_completed_generation(insight=source, materials=materials, attempt=attempt, answer=answer, actor=actor)


def test_legacy_decision_omits_empty_generation_ref():
    decision, _, _ = generation()
    assert "generationArtifactRef" not in decision.model_dump(mode="json", by_alias=True)
    assert "generation_artifact_ref" not in decision.model_dump(mode="json")
