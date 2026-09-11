"""Explicit A0-V text authority publication; no implicit Provider execution."""
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path

from a0v_text_eval_evidence import read_verified_text_evidence
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_eval_contracts import (
    AssetRevisionRef, AssetType, DatasetRevisionRef, EvalDatasetManifest,
    EvalCaseDefinition, EvalSuiteRevision, JudgeRevisionRef,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_eval_runner import AipEvalRunner, ResolvedArtifact, TargetExecution, JudgeExecution
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.aip_release_publication_models import DeriveReleaseGateRequest
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevisionCreate
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore, materialize_policy
from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision, RegisteredModelRevision, RuntimePolicyRevision, ModelRouteRevision
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, canonical_hash, evaluation_candidate_ref
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')
ACTOR = 'a0v-formal-text-model'
MODEL_ID = 'a0v-agnes-2-5-flash-readonly-dev'
ROUTE_ID = 'a0v-ecommerce-text-readonly-v1'
PRICE_ID = 'a0v-agnes-2-5-flash-development-deferred-v1'
PROVIDER_ID = 'a0v-agnes-text-readonly-dev'
PROVIDER_MODEL = 'agnes-2.5-flash'
NETWORK_ID = 'a0v-ecommerce-network-v1'
POLICY_ID = 'a0v-ecommerce-runtime-policy-v1'
APPROVAL = 'approval:AOS-000573:A0-V-development-cost-deferred'
PROBE_APPROVAL = 'approval:AOS-000573:A0-V-local-readonly'
PLACEHOLDER = dict(assetType='EvalGateDecision', assetId='a0v-pending-eval', revision=1, contentHash='0'*64)
EVIDENCE_DIR = Path(__file__).resolve().parents[2] / '.aos-recovery-20260910/state/a0v-exact-text-live-eval'


def exact(kind, item, field):
    return VersionedAssetRef(assetType=kind, assetId=getattr(item, field), revision=item.revision, contentHash=item.content_hash)


def rehash(model, body):
    item = model.model_validate({**body, 'contentHash': '0'*64})
    value = item.model_dump(mode='json', by_alias=True)
    value['contentHash'] = canonical_hash({k: v for k, v in value.items() if k not in AipModelRuntimeStore._META_FIELDS})
    return model.model_validate(value)


def evidence(connect, *, checked_at=None):
    runtime = AipModelRuntimeStore(connect)
    provider = runtime.get_provider(SCOPE, PROVIDER_ID)
    network = AipNetworkPolicyStore(connect).get(SCOPE, NETWORK_ID)
    now = checked_at or datetime.now(UTC)
    if (provider.lifecycle.value != 'active' or network.lifecycle.value != 'active'
            or not network.effective_from <= now < network.effective_until):
        raise ValueError('FORMAL_MODEL_CURRENT_DEPENDENCY_INACTIVE')
    return read_verified_text_evidence(EVIDENCE_DIR,
        provider=exact('ProviderInstanceRevision', provider, 'provider_instance_id'),
        network=exact('NetworkPolicyRevision', network, 'policy_id'),
        provider_model_id=PROVIDER_MODEL, approval_ref=PROBE_APPROVAL,
        checked_at=now)


def freeze_plan(connect, state_dir):
    state_dir = Path(state_dir)
    path = state_dir / 'plan.json'
    if path.exists():
        plan = json.loads(path.read_text())
        if canonical_hash({k: v for k, v in plan.items() if k != 'planHash'}) != plan['planHash']:
            raise ValueError('FORMAL_MODEL_PLAN_DRIFT')
        return plan
    now = datetime.now(UTC)
    source = evidence(connect, checked_at=now)
    runtime = AipModelRuntimeStore(connect)
    governance = AipModelGovernancePolicyStore(connect)
    current_policy = runtime.get_policy(SCOPE, POLICY_ID)
    quota, _ = governance.get_quota_head(SCOPE, current_policy.quota_policy_ref.asset_id)
    budget, budget_version = governance.get_budget_head(SCOPE, current_policy.budget_policy_ref.asset_id)
    oldest = min(datetime.fromisoformat(row['observedAt']) for row in source['cases'])
    end = min(oldest+timedelta(hours=24), budget.effective_until, quota.effective_until)
    if end <= now:
        raise ValueError('FORMAL_MODEL_AUTHORIZATION_WINDOW_EMPTY')
    auth = dict(tenant={'orgId': SCOPE.org_id, 'projectId': SCOPE.project_id},
        provider=source['provider'], providerModelId=PROVIDER_MODEL, approvalRef=APPROVAL,
        effectiveFrom=now.isoformat(), effectiveUntil=end.isoformat())
    budget_body = budget.model_dump(mode='json', by_alias=True, exclude={'tenant', 'content_hash', 'created_by', 'created_at'})
    budget_body.update(revision=budget.revision+1, approvalRef=APPROVAL,
        effectiveFrom=now.isoformat(), effectiveUntil=end.isoformat(), developmentCostAuthorization=auth)
    budget_create = BudgetPolicyRevisionCreate.model_validate(budget_body)
    budget_next = materialize_policy(SCOPE, ACTOR, budget_create, created_at=now)
    price = rehash(ModelPriceSnapshotRevision, dict(tenant=auth['tenant'], priceSnapshotId=PRICE_ID,
        revision=1, currency='CNY', lifecycle='active', effectiveFrom=auth['effectiveFrom'],
        effectiveUntil=auth['effectiveUntil'], createdBy=ACTOR, createdAt=now.isoformat(),
        developmentCostAuthorization=auth))
    policy_body = current_policy.model_dump(mode='json', by_alias=True)
    policy_body.update(revision=current_policy.revision+1,
        budgetPolicyRef=exact('BudgetPolicyRevision', budget_next, 'policy_id'),
        quotaPolicyRef=exact('QuotaPolicyRevision', quota, 'policy_id'),
        maxAttempts=1, allowedFallbackReasons=[], createdBy=ACTOR, createdAt=now.isoformat())
    policy = rehash(RuntimePolicyRevision, policy_body)
    model = rehash(RegisteredModelRevision, dict(tenant=auth['tenant'], registeredModelId=MODEL_ID,
        revision=1, provider=source['provider'], providerModelId=PROVIDER_MODEL,
        inputModalities=['text'], outputModalities=['text'], capabilities=['llm', 'chat'],
        contextWindow=min(8000, quota.max_input_tokens), quotaPolicyRef=policy.quota_policy_ref,
        budgetPolicyRef=policy.budget_policy_ref, priceSnapshotRef=exact('ModelPriceSnapshotRevision', price, 'price_snapshot_id'),
        evalGateRef=PLACEHOLDER, lifecycle='active', createdBy=ACTOR, createdAt=now.isoformat()))
    with connect(SCOPE) as conn:
        head = conn.execute('SELECT version FROM aip_runtime_policy_head WHERE org_id=%s AND project_id=%s AND runtime_policy_id=%s', (*SCOPE.key, POLICY_ID)).fetchone()
    plan = dict(schemaVersion='a0v.formal-text-model-plan/v1', createdAt=now.isoformat(),
        source=source, budgetExpectedVersion=budget_version, policyExpectedVersion=head['version'],
        budget=budget_create.model_dump(mode='json', by_alias=True),
        price=price.model_dump(mode='json', by_alias=True), policy=policy.model_dump(mode='json', by_alias=True),
        modelCandidate=model.model_dump(mode='json', by_alias=True))
    plan['planHash'] = canonical_hash(plan)
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state_dir, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(state_dir, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return plan


def _artifact(identifier, kind, value):
    return ArtifactRef(artifactId=identifier, artifactType=kind, revision='1', contentHash=canonical_hash(value))


def _derive(connect, plan, candidate, mode, check_current):
    target_ref = evaluation_candidate_ref(candidate)
    target = AssetRevisionRef(assetType=AssetType.REGISTERED_MODEL if mode == 'model' else AssetType.MODEL_ROUTE,
        assetId=target_ref.asset_id, revision=str(target_ref.revision), contentHash=target_ref.content_hash)
    prefix = 'a0v-'+mode+'-'+target_ref.content_hash[:24]
    source = plan['source']
    source_hash = source['sourceHash']
    policy = RuntimePolicyRevision.model_validate(plan['policy'])
    dataset = DatasetRevisionRef(datasetId='a0v-prior-text-'+source_hash[:24], revision=1,
        contentHash=canonical_hash({'sourceHash': source_hash, 'caseCount': 3}), sourceHash=source_hash,
        redactionPolicy=AssetRevisionRef(assetType=AssetType.POLICY,
            assetId=policy.data_classification_policy_ref.asset_id,
            revision=str(policy.data_classification_policy_ref.revision),
            contentHash=policy.data_classification_policy_ref.content_hash))
    manifest = EvalDatasetManifest(sourceKind='artifact_snapshot', sourceId='a0v-verified-prior-text-probes',
        sourceRevision='1', sourceHash=source_hash,
        fieldsAllowlist=['caseId', 'requestHash', 'evidenceHash', 'observedAt', 'promptTokens', 'completionTokens', 'totalTokens', 'latencyMs'],
        redactionReceipt=_artifact('a0v-text-metadata-'+source_hash[:24], 'redaction_receipt', {'fields': 'metadata-only', 'sourceHash': source_hash}),
        piiState='none', caseCount=3, capturedAt=min(datetime.fromisoformat(row['observedAt']) for row in source['cases']))
    registry = AipEvalPackRegistry(connect)
    registry.register_dataset_revision(SCOPE, dataset, manifest, actor=ACTOR)
    values, definitions = {}, []
    cases = source['cases'] if mode == 'model' else [
        dict(caseId='text-answer', taskType='chat.answer', modality='text', expected=True),
        dict(caseId='video-rejected', taskType='video.compose', modality='video', expected=False),
        dict(caseId='speech-rejected', taskType='speech.synthesize', modality='audio', expected=False),
    ]
    for case in cases:
        identifier = prefix+'-'+case['caseId']
        expected = {'evidenceHash': case['evidenceHash'], 'source': 'verified_prior_probe_metadata'} if mode == 'model' else case['expected']
        input_ref = _artifact(identifier+'-in', 'eval_input', case)
        expected_ref = _artifact(identifier+'-expected', 'eval_expected', expected)
        definitions.append(EvalCaseDefinition(caseId=case['caseId'], kind='positive' if mode == 'model' or case['expected'] else 'negative', inputArtifact=input_ref, expectedArtifact=expected_ref, timeoutMs=60000))
        values[input_ref.artifact_id] = case
        values[expected_ref.artifact_id] = expected
    suite = EvalSuiteRevision(suiteId=prefix, revision=1, contentHash='0'*64, target=target, dataset=dataset,
        judge=JudgeRevisionRef(judgeId='a0v-prior-evidence-exact-v1', revision=1, contentHash=canonical_hash('a0v-prior-evidence-exact-v1')),
        cases=definitions, gateThreshold=1.0)
    suite.content_hash = compute_eval_suite_hash(suite)
    registry.register_suite_revision(SCOPE, suite, actor=ACTOR)
    runner = AipEvalRunner(connect)
    with connect(SCOPE) as conn:
        prior = conn.execute('SELECT r.run_id,p.report_id,p.revision FROM aip_eval_run r LEFT JOIN aip_eval_report_revision p ON p.org_id=r.org_id AND p.project_id=r.project_id AND p.run_id=r.run_id WHERE r.org_id=%s AND r.project_id=%s AND r.idempotency_key=%s', (*SCOPE.key, prefix)).fetchone()
    def execute(actual_target, case):
        if actual_target != target:
            raise ValueError('FORMAL_EVAL_TARGET_DRIFT')
        current = check_current()
        if mode == 'model':
            record = next(row for row in current['cases'] if row['caseId'] == case['caseId'])
            actual = {'evidenceHash': record['evidenceHash'], 'source': 'verified_prior_probe_metadata'}
        else:
            actual = case['taskType'] in candidate.task_types and case['modality'] == candidate.required_input_modality.value
        return TargetExecution(target=actual_target, value=actual)
    if prior:
        if prior['report_id'] is None:
            raise ValueError('FORMAL_EVAL_RUNNING_WITHOUT_REPORT_RECONCILE_REQUIRED')
        report = runner.get_report(SCOPE, prior['report_id'], prior['revision'])
        if report.target != target or report.suite_ref.content_hash != suite.content_hash:
            raise ValueError('FORMAL_EVAL_REPORT_DRIFT')
    else:
        report = runner.run(SCOPE, suite_id=suite.suite_id, suite_revision=1, idempotency_key=prefix,
            actor=ACTOR, resolve_artifact=lambda ref: ResolvedArtifact(reference=ref, value=values[ref.artifact_id]),
            execute_target=execute,
            execute_judge=lambda ref, actual, expected: JudgeExecution(judge=ref, passed=actual == expected, detail_code='verified_prior_evidence_exact' if mode == 'model' else 'route_configuration_contract'))
    gate = AipReleasePublicationService(connect).derive_gate(SCOPE, actor=ACTOR,
        request=DeriveReleaseGateRequest(reportId=report.report_id, reportRevision=report.revision,
            reportHash=report.content_hash, idempotencyKey=prefix+'-gate'))
    if gate.status.value != 'passed':
        raise ValueError('FORMAL_EVAL_GATE_NOT_PASSED')
    return VersionedAssetRef(assetType='EvalGateDecision', assetId=gate.decision_id, revision=1, contentHash=gate.decision_hash)


def apply_plan(connect, plan):
    if canonical_hash({k: v for k, v in plan.items() if k != 'planHash'}) != plan['planHash']:
        raise ValueError('FORMAL_MODEL_PLAN_DRIFT')
    runtime = AipModelRuntimeStore(connect)
    governance = AipModelGovernancePolicyStore(connect)
    model = RegisteredModelRevision.model_validate(plan['modelCandidate'])
    price = ModelPriceSnapshotRevision.model_validate(plan['price'])
    policy = RuntimePolicyRevision.model_validate(plan['policy'])
    source = evidence(connect)
    if source['sourceHash'] != plan['source']['sourceHash']:
        raise ValueError('FORMAL_MODEL_EVIDENCE_DRIFT')
    price.development_cost_authorization.require_scope(scope=SCOPE, provider=model.provider,
        provider_model_id=model.provider_model_id, approval_ref=APPROVAL, now=datetime.now(UTC))
    budget = governance.publish_budget(SCOPE, ACTOR, 'a0v-formal-text-budget-v1', BudgetPolicyRevisionCreate.model_validate(plan['budget']), expected_version=plan['budgetExpectedVersion'])
    if exact('BudgetPolicyRevision', budget, 'policy_id') != model.budget_policy_ref:
        raise ValueError('FORMAL_MODEL_BUDGET_DRIFT')
    runtime.publish_price_snapshot(SCOPE, ACTOR, 'a0v-formal-text-price-v1', price)
    runtime.publish_policy(SCOPE, ACTOR, 'a0v-formal-text-policy-v1', policy, expected_version=plan['policyExpectedVersion'])
    def check_current():
        current = evidence(connect)
        if current['sourceHash'] != plan['source']['sourceHash']:
            raise ValueError('FORMAL_MODEL_EVIDENCE_DRIFT')
        runtime.require_model_governance(SCOPE, model, price)
        governance.require_runtime_policy_dependencies(SCOPE, policy)
        return current
    check_current()
    model_gate = _derive(connect, plan, model, 'model', check_current)
    model = rehash(RegisteredModelRevision, {**model.model_dump(mode='json', by_alias=True), 'evalGateRef': model_gate})
    saved_model = runtime.publish_model(SCOPE, ACTOR, 'a0v-formal-text-model-v1', model)
    route = rehash(ModelRouteRevision, dict(tenant={'orgId': SCOPE.org_id, 'projectId': SCOPE.project_id},
        routeId=ROUTE_ID, revision=1, taskTypes=['chat.answer'], requiredInputModality='text',
        requiredOutputModality='text', requiredCapabilities=['llm', 'chat'],
        candidates=[{'model': exact('RegisteredModelRevision', saved_model, 'registered_model_id')}], strategy='failover',
        runtimePolicyRef=exact('RuntimePolicyRevision', policy, 'policy_id'), evalGateRef=PLACEHOLDER,
        lifecycle='active', createdBy=ACTOR, createdAt=plan['createdAt']))
    route_gate = _derive(connect, plan, route, 'route', check_current)
    route = rehash(ModelRouteRevision, {**route.model_dump(mode='json', by_alias=True), 'evalGateRef': route_gate})
    saved_route = runtime.publish_route(SCOPE, ACTOR, 'a0v-formal-text-route-v1', route)
    return dict(planHash=plan['planHash'], model=exact('RegisteredModelRevision', saved_model, 'registered_model_id').model_dump(mode='json'),
        route=exact('ModelRouteRevision', saved_route, 'route_id').model_dump(mode='json'),
        modelGate=model_gate.model_dump(mode='json'), routeGate=route_gate.model_dump(mode='json'),
        providerCalls=0, businessRuns=0, readiness='NOT_CHECKED')
