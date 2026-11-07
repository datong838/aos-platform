"""Untrusted model output must remain sourced proposals, never authority."""
import json

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_analyst_growth_plan_draft import parse_growth_plan_answer
from aos_api.ecommerce_analyst_authority_contracts import GrowthPlanRevision
from test_ecommerce_analyst_authority_contracts import plan, ref


def answer():
    return dict(objective="核查复购下降", constraints=["先核实样本"],
                expectedEffect="识别可验证的改善机会", confidence=0.6,
                stopConditions=["来源过期即停止"],
                items=[dict(title="检查回购间隔", objective="比较同口径人群",
                            sourceIndices=[0])])


def test_valid_answer_retains_readable_text_and_source_indices():
    parsed = parse_growth_plan_answer(json.dumps(answer()), source_count=1)
    assert parsed.items[0].title == "检查回购间隔"
    assert parsed.items[0].source_indices == [0]


def method_answer():
    from test_ecommerce_analyst_authority_contracts import sales_weapon_method
    method = sales_weapon_method()
    method.pop('sourceCutoffAt')
    method.pop('evidenceRefs')
    statements = [method['audienceHypothesis'], method['scenario'], *method['fitFor'],
                  *method['notFitFor'], *method['proposedValueClaims']]
    for statement in statements:
        statement.pop('evidenceRefs')
        statement['sourceIndices'] = [0]
    return dict(answer(), salesWeaponMethod=method)


def test_method_proposal_accepts_only_indexed_candidate_content():
    parsed = parse_growth_plan_answer(json.dumps(method_answer()), source_count=1)
    assert parsed.sales_weapon_method.audience_hypothesis.source_indices == [0]


@pytest.mark.parametrize('change', ['out_of_range', 'duplicate', 'bool', 'ref', 'cutoff'])
def test_method_proposal_rejects_unbound_or_model_supplied_authority(change):
    payload = method_answer()
    statement = payload['salesWeaponMethod']['scenario']
    if change == 'ref': statement['evidenceRefs'] = [ref('EvidenceBundleRevision', 'invented')]
    elif change == 'cutoff': payload['salesWeaponMethod']['sourceCutoffAt'] = '2026-11-05T00:00:00Z'
    else: statement['sourceIndices'] = {'out_of_range': [1], 'duplicate': [0, 0], 'bool': [True]}[change]
    with pytest.raises(ValueError): parse_growth_plan_answer(json.dumps(payload), source_count=1)


def test_v2_method_compiles_with_trusted_cutoff_and_exact_decision_evidence():
    from hashlib import sha256
    from aos_api.ecommerce_analyst_growth_plan_draft import growth_plan_prompt, draft_from_completed_generation
    from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
    from aos_api.aip_agent_run_executor import AipAgentRunExecutor
    from aos_api.ecommerce_analyst_authority_store import canonical_hash
    decision, attempt, _ = generation()
    raw = json.dumps(method_answer(), ensure_ascii=False)
    cutoff = decision.created_at
    query, system = growth_plan_prompt(decision, budget='100', task_type='analysis', source_cutoff_at=cutoff)
    assert json.loads(query)['protocol'] == 'aos.growth-plan-proposal/v2'
    assert json.loads(query)['sourceCutoffAt'] == cutoff.isoformat()
    request = ExecuteAgentRunRequest(expectedAgentRunVersion=attempt.agent_run_version, attemptId=attempt.attempt_id,
        attemptNo=attempt.attempt_no, budgetRef=attempt.budget_ref, capacityReservationRef=attempt.capacity_reservation_ref,
        query=query, systemPrompt=system, dataClassification=attempt.data_classification)
    attempt = attempt.model_copy(update={'request_hash': AipAgentRunExecutor._request_hash(attempt.agent_run_id, request),
        'output_artifact_ref': attempt.output_artifact_ref.model_copy(update={'content_hash': sha256(raw.encode()).hexdigest()})})
    compiled = draft_from_completed_generation(decision=decision, attempt=attempt, answer=raw, budget='100',
        task_type='analysis', actor='compiler', source_cutoff_at=cutoff)
    method = compiled.sales_weapon_method
    assert method.source_cutoff_at == cutoff and method.evidence_refs == decision.evidence_refs
    assert method.scenario.evidence_refs == decision.evidence_refs
    assert compiled.lifecycle.value == 'draft' and compiled.approved_at is None
    assert canonical_hash(compiled.model_dump(mode='json', by_alias=True, exclude={'content_hash'})) == compiled.content_hash
    assert GrowthPlanRevision.model_validate(compiled.model_dump(mode='json', by_alias=True)) == compiled


def test_v1_recovery_with_current_cutoff_preserves_original_plan_hash():
    from aos_api.ecommerce_analyst_growth_plan_draft import draft_from_completed_generation
    decision, attempt, raw = generation()
    kwargs = dict(decision=decision, attempt=attempt, answer=raw, budget='100', task_type='analysis', actor='compiler')
    assert draft_from_completed_generation(**kwargs, source_cutoff_at=decision.created_at) == draft_from_completed_generation(**kwargs)


def test_v1_request_cannot_acquire_new_method_fields():
    from hashlib import sha256
    from aos_api.ecommerce_analyst_growth_plan_draft import draft_from_completed_generation
    decision, attempt, _ = generation()
    raw = json.dumps(method_answer(), ensure_ascii=False)
    attempt = attempt.model_copy(update={'output_artifact_ref': attempt.output_artifact_ref.model_copy(update={'content_hash': sha256(raw.encode()).hexdigest()})})
    with pytest.raises(ValueError, match='v2'):
        draft_from_completed_generation(decision=decision, attempt=attempt, answer=raw, budget='100',
            task_type='analysis', actor='compiler', source_cutoff_at=decision.created_at)


@pytest.mark.parametrize("key,value", [("lifecycle", "approved"), ("budget", "0"),
    ("tenant", {}), ("approvedAt", "2026-09-11"), ("contentHash", "a" * 64)])
def test_model_cannot_supply_authority(key, value):
    payload = answer()
    payload[key] = value
    with pytest.raises(ValueError):
        parse_growth_plan_answer(json.dumps(payload), source_count=1)


@pytest.mark.parametrize("indices", [[], [1], [-1], [0, 0], [True], ["0"]])
def test_sources_must_be_unique_in_range_integer_indices(indices):
    payload = answer()
    payload["items"][0]["sourceIndices"] = indices
    with pytest.raises(ValueError):
        parse_growth_plan_answer(json.dumps(payload), source_count=1)


@pytest.mark.parametrize("field,value", [("objective", "  "), ("constraints", ["\n"]),
    ("confidence", float("nan")), ("confidence", float("inf")),
    ("confidence", "0.6"), ("confidence", True), ("items", []),
    ("stopConditions", [])])
def test_rejects_empty_or_coerced_or_nonfinite_values(field, value):
    payload = answer()
    payload[field] = value
    with pytest.raises(ValueError):
        parse_growth_plan_answer(json.dumps(payload), source_count=1)


def test_rejects_duplicate_keys_and_unbounded_payloads():
    raw = json.dumps(answer())
    for invalid in [raw.replace('"confidence": 0.6', '"confidence": 0.6, "confidence": 0.7'),
                    ' ' * 131073, '[]', '```json\n' + raw + '\n```']:
        with pytest.raises(ValueError):
            parse_growth_plan_answer(invalid, source_count=1)
    with pytest.raises(ValueError):
        parse_growth_plan_answer(raw, source_count=0)


def test_legacy_plan_serialization_has_no_new_empty_fields():
    legacy = GrowthPlanRevision.model_validate(plan(lifecycle="draft"))
    for aliases in [True, False]:
        payload = legacy.model_dump(mode="json", by_alias=aliases)
        assert "generationArtifactRef" not in payload and "generation_artifact_ref" not in payload
        assert "evidenceRefs" not in payload["items"][0]
        assert "evidence_refs" not in payload["items"][0]


def test_new_provenance_roundtrips_and_enforces_reference_types():
    payload = plan(lifecycle="draft")
    payload["generationArtifactRef"] = ref("Artifact", "generated-1")
    payload["items"][0]["evidenceRefs"] = [ref("EvidenceBundleRevision", "bundle-1")]
    parsed = GrowthPlanRevision.model_validate(payload)
    assert parsed.model_dump(mode="json", by_alias=True)["generationArtifactRef"] == payload["generationArtifactRef"]
    assert parsed.items[0].evidence_refs[0].resource_id == "bundle-1"
    payload["items"][0]["evidenceRefs"] *= 2
    with pytest.raises(ValidationError):
        GrowthPlanRevision.model_validate(payload)
    payload["items"][0]["evidenceRefs"] = [ref("Task", "wrong")]
    with pytest.raises(ValidationError):
        GrowthPlanRevision.model_validate(payload)
    payload["items"][0]["evidenceRefs"] = []
    payload["generationArtifactRef"] = ref("GrowthPlanRevision", "wrong")
    with pytest.raises(ValidationError):
        GrowthPlanRevision.model_validate(payload)


def generation(*, source_cutoff_at=None, with_method=False):
    from hashlib import sha256
    from aos_api.aip_agent_run_execution_contracts import AgentRunExecutionAttempt, ExecuteAgentRunRequest
    from aos_api.aip_agent_run_executor import AipAgentRunExecutor
    from aos_api.ecommerce_analyst_authority_contracts import DecisionSummaryRevision
    from aos_api.ecommerce_analyst_authority_store import canonical_hash
    from aos_api.ecommerce_analyst_growth_plan_draft import growth_plan_prompt
    from test_ecommerce_analyst_authority_contracts import TENANT, NOW
    decision = DecisionSummaryRevision(tenant=TENANT, decisionId="decision-1", revision=1, version=1,
        insightRef=ref("InsightRevision", "insight-1"), conclusion="复购下降需要核验",
        evidenceRefs=[ref("EvidenceBundleRevision", "bundle-1")], attributionPath=["同口径趋势"],
        uncertainty="未证实因果", contentHash="0" * 64, createdBy="analyst", createdAt=NOW)
    decision = decision.model_copy(update={"content_hash": canonical_hash(decision.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
    query, system = growth_plan_prompt(decision, budget="100", task_type="analysis", source_cutoff_at=source_cutoff_at)
    asset = lambda kind: dict(assetType=kind, assetId=kind.lower(), revision=1, contentHash="a" * 64)
    request = ExecuteAgentRunRequest(expectedAgentRunVersion=2, attemptId="attempt-draft", attemptNo=1,
        budgetRef=asset("BudgetRevision"), capacityReservationRef=dict(resourceType="CapacityReservation", resourceId="capacity-1", authority="postgresql", revision="1"),
        query=query, systemPrompt=system, dataClassification="internal")
    raw = json.dumps(method_answer() if with_method else answer(), ensure_ascii=False)
    attempt = AgentRunExecutionAttempt(tenant=TENANT, attemptId=request.attempt_id, agentRunId="run-draft", agentRunVersion=2, attemptNo=1,
        routeRef=asset("ModelRouteRevision"), policyRef=asset("RuntimePolicyRevision"), modelRef=asset("RegisteredModelRevision"),
        providerRef=asset("ProviderInstanceRevision"), priceSnapshotRef=asset("ModelPriceSnapshotRevision"),
        budgetRef=request.budget_ref, capacityReservationRef=request.capacity_reservation_ref,
        dataClassification="internal", lineageId="lineage-1", requestHash=AipAgentRunExecutor._request_hash("run-draft", request),
        status="succeeded", providerReceiptId="provider-1", usageReceiptIds=["usage-1"],
        outputArtifactRef=dict(artifactId="artifact-1", artifactType="agent_text_output", revision="1", contentHash=sha256(raw.encode()).hexdigest()),
        version=3, preparedAt=NOW, completedAt=NOW, createdBy="compiler", updatedAt=NOW)
    return decision, attempt, raw


def test_bound_generation_is_stable_readable_draft_with_sources():
    from aos_api.ecommerce_analyst_growth_plan_draft import draft_from_completed_generation
    decision, attempt, raw = generation()
    kwargs = dict(decision=decision, attempt=attempt, answer=raw, budget="100", task_type="analysis", actor="compiler")
    first = draft_from_completed_generation(**kwargs)
    assert first == draft_from_completed_generation(**kwargs)
    assert first.lifecycle.value == "draft" and first.approved_at is None
    assert first.items[0].evidence_refs == decision.evidence_refs
    assert first.budget == "100" and first.generation_artifact_ref.resource_id == "artifact-1"


@pytest.mark.parametrize("change", ["unknown", "answer", "budget", "task_type", "tenant", "request", "decision", "artifact", "time"])
def test_bound_generation_rejects_wrong_or_incomplete_evidence(change):
    from aos_api.ecommerce_analyst_growth_plan_draft import draft_from_completed_generation
    decision, attempt, raw = generation()
    budget, task_type = "100", "analysis"
    if change == "unknown":
        attempt = attempt.model_copy(update={"status": "unknown"})
    elif change == "answer":
        raw += " "
    elif change == "budget":
        budget = "101"
    elif change == "task_type":
        task_type = "content"
    elif change == "tenant":
        attempt = attempt.model_copy(update={"tenant": attempt.tenant.model_copy(update={"org_id": "dev-org"})})
    elif change == "request":
        attempt = attempt.model_copy(update={"request_hash": "b" * 64})
    elif change == "decision":
        decision = decision.model_copy(update={"conclusion": "伪造结论"})
    elif change == "artifact":
        attempt = attempt.model_copy(update={"output_artifact_ref": None})
    else:
        attempt = attempt.model_copy(update={"completed_at": None})
    with pytest.raises(ValueError):
        draft_from_completed_generation(decision=decision, attempt=attempt, answer=raw, budget=budget, task_type=task_type, actor="compiler")


@pytest.mark.parametrize("budget", [None, "", "-1", "NaN", "01", "0.0000001", 100])
def test_prompt_requires_explicit_valid_plan_budget(budget):
    from aos_api.ecommerce_analyst_growth_plan_draft import growth_plan_prompt
    decision, _, _ = generation()
    with pytest.raises(ValueError):
        growth_plan_prompt(decision, budget=budget, task_type="analysis")


def test_prompt_rejects_oversize_context_without_silently_dropping_sources():
    from aos_api.ecommerce_analyst_growth_plan_draft import growth_plan_prompt
    from aos_api.ecommerce_analyst_authority_store import canonical_hash
    decision, _, _ = generation()
    decision = decision.model_copy(update={"key_assumptions": ["长" * 2000] * 10})
    decision = decision.model_copy(update={"content_hash": canonical_hash(decision.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
    with pytest.raises(ValueError, match="query limit"):
        growth_plan_prompt(decision, budget="100", task_type="analysis")


def test_human_approval_preserves_generated_provenance():
    from aos_api.ecommerce_analyst_growth_plan_approval import EcommerceAnalystGrowthPlanApprovalService
    from test_ecommerce_analyst_growth_plan_approval import FakeStore, SCOPE, NOW, request, plan as old_plan
    from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
    draft = old_plan()
    evidence = AnalystExactRef.model_validate(ref("EvidenceBundleRevision", "bundle-1"))
    artifact = AnalystExactRef.model_validate(ref("Artifact", "artifact-1"))
    draft = draft.model_copy(update={"generation_artifact_ref": artifact,
        "items": [draft.items[0].model_copy(update={"evidence_refs": [evidence]})]})
    store = FakeStore(draft)
    result = EcommerceAnalystGrowthPlanApprovalService(store, clock=lambda: NOW).approve(
        SCOPE, "plan-1", request(), expected_version=1, idempotency_key="approve-sourced", actor="user:reviewer")
    approved = store.publish_calls[0][2]
    assert approved.generation_artifact_ref == artifact
    assert approved.items[0].evidence_refs == [evidence]
    assert result.external_effects_allowed is False
