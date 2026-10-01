"""First-content contract gates; these are not current business-source proofs."""
import pytest

from aos_api.aip_action_models import CreateActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
ACTION = "ecommerce_growth_content_generate"
SNAPSHOT = {"id": ACTION, "name": "Content", "objectType": "Task"}
PAYLOAD = {"firstContentReviewKey": "review-1", "firstContentSources": {},
           "budgetUpperBoundMinor": 500}


def test_explicit_first_content_has_server_r2_without_client_hint():
    risk = classify_action_risk(ACTION, SNAPSHOT, PAYLOAD, None)
    assert risk.floor is ActionRiskLevel.R2
    assert risk.approval_policy == dict(makerChecker=True, minimumApprovals=1,
                                       executionAllowed=True, draftOnly=False)


@pytest.mark.parametrize("payload", [PAYLOAD, {"firstContentSources": {}},
                                   {"firstContentReviewKey": "review-1"}])
def test_generic_store_cannot_create_first_content_binding(payload):
    body = CreateActionProposalRequest(actionTypeId=ACTION, payload=payload,
                                      purpose="First content")
    risk = classify_action_risk(ACTION, SNAPSHOT, payload, None)
    with pytest.raises(AipActionTransitionBlocked, match="FIRST_CONTENT_PRODUCER_REQUIRED"):
        AipActionStore()._internal_request_binding(None, SCOPE, "maker", body, SNAPSHOT, risk)


def test_generic_checker_cannot_decide_first_content():
    row = dict(action_type_id=ACTION, action_type_snapshot=SNAPSHOT, payload=PAYLOAD)
    with pytest.raises(AipActionTransitionBlocked, match="FIRST_CONTENT_PRODUCER_REQUIRED"):
        AipActionStore()._internal_proposal_guard(None, SCOPE, "checker", row, checker=True)


def test_ordinary_unbound_content_keeps_legacy_draft_risk():
    risk = classify_action_risk(ACTION, SNAPSHOT, {"budgetUpperBoundMinor": 500}, None)
    assert risk.level is ActionRiskLevel.R1


def test_dev_mode_cannot_reach_database(monkeypatch):
    import aos_api.ecommerce_content_first_action_binding as binding
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "1")
    monkeypatch.setattr(binding, "connect_serializable", lambda *_: pytest.fail("DB reached"))
    with pytest.raises(AipActionTransitionBlocked, match="EXTERNAL_IDENTITY_REQUIRED"):
        binding.preview_first_content(SCOPE, "Bearer dev", "review-1", 500, None)


def test_dedicated_producer_cannot_fall_through_to_generic_action(monkeypatch):
    import aos_api.ecommerce_content_first_action_binding as binding
    monkeypatch.setattr(binding, "connect_serializable", lambda *_: pytest.fail("DB reached"))
    body = CreateActionProposalRequest(actionTypeId=ACTION, payload={"budgetUpperBoundMinor": 500}, purpose="ordinary")
    with pytest.raises(AipActionTransitionBlocked, match="EXACT_PROPOSAL_REQUIRED"):
        binding.propose_first_content(SCOPE, "Bearer dev", "key", body)


def test_arbitrary_guard_cannot_open_store():
    with pytest.raises(TypeError, match="exact first content guard"):
        AipActionStore(first_content_guard=object())


def test_first_content_cost_approval_cannot_enter_generic_external_executor():
    from aos_api.aip_action_execution import AipActionExecutionService
    with pytest.raises(AipActionTransitionBlocked, match="NATURAL_OWNER_REQUIRED"):
        AipActionExecutionService._reject_bootstrap_action(dict(
            action_type_id=ACTION, action_type_snapshot=SNAPSHOT, payload=PAYLOAD))


def test_client_hint_cannot_lower_first_content_risk():
    risk = classify_action_risk(ACTION, SNAPSHOT, PAYLOAD, ActionRiskLevel.R0)
    assert risk.level is ActionRiskLevel.R2
    raised = classify_action_risk(ACTION, SNAPSHOT, PAYLOAD, ActionRiskLevel.R3)
    assert raised.level is ActionRiskLevel.R3


def test_source_envelope_excludes_observation_time_and_pins_runtime_and_model(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from uuid import uuid4
    from dataclasses import replace
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.ecommerce_growth_host_ports import HostTransaction, EcommerceGrowthDispatchSnapshot
    import aos_api.ecommerce_content_first_action_binding as binding
    now = datetime.now(timezone.utc)
    ref = lambda kind: VersionedAssetRef(assetType=kind, assetId=kind, revision=1, contentHash="a" * 64)
    model_ref, provider, price = (ref(k) for k in (
        "RegisteredModelRevision", "ProviderInstanceRevision", "ModelPriceSnapshotRevision"))
    model = SimpleNamespace(content_hash=model_ref.content_hash, provider=provider,
        price_snapshot_ref=price, provider_model_id="exact-provider-model")
    monkeypatch.setattr("aos_api.aip_model_runtime_store.AipModelRuntimeStore.get_model", lambda *a: model)
    request = SimpleNamespace(model_dump=lambda **kw: {"taskRunRef": {"resourceId": "run-1"}},
        run=SimpleNamespace(plan_ref=SimpleNamespace(resource_id="plan-1", revision="1")))
    sources = SimpleNamespace(snapshot=EcommerceGrowthDispatchSnapshot(
        ACTION, 1, uuid4(), uuid4(), 3, uuid4(), 2, 4, now),
        action_context=SimpleNamespace(request=request, response={"receiptRef": {"resourceId": "review-receipt"}},
            agent_run_id="agent-run-1", resolution=SimpleNamespace(selected_model=model_ref,
                selected_provider=provider, selected_price_snapshot=price, policy=ref("RuntimePolicyRevision")),
            runtime_policy=SimpleNamespace(quota_policy_ref=ref("QuotaPolicyRevision"),
                budget_policy_ref=ref("BudgetPolicyRevision")),
            capacity={"expires_at": now + timedelta(minutes=1)},
            budget_policy=SimpleNamespace(effective_until=now + timedelta(hours=1))),
        quota=SimpleNamespace(effective_until=now + timedelta(hours=1), max_input_tokens=100, max_output_tokens=100),
        authorities={"task": {"resourceId": "task-1"}}, source_artifact_refs=[{"resourceId": "artifact"}],
        fact_source_refs=[{"resourceId": "facts"}])
    sources.task_ref = SimpleNamespace(resource_id="task-1")
    transaction = HostTransaction(SimpleNamespace(execute=lambda *a:
        SimpleNamespace(fetchone=lambda: {"content_hash": "d" * 64})))
    original = binding.source_envelope(transaction, SCOPE, "review-1", sources)
    sources.snapshot = replace(sources.snapshot, checked_at=now + timedelta(seconds=1))
    assert binding.source_envelope(transaction, SCOPE, "review-1", sources) == original
    assert original["providerModelId"] == "exact-provider-model"
    assert original["reviewReceipt"]["resourceId"] == "review-receipt"
    assert original["runtime"]["execution_epoch"] == 3
    assert original["planRef"]["contentHash"] == "sha256:" + "d" * 64
    sources.snapshot = replace(sources.snapshot, execution_epoch=4)
    assert binding.source_envelope(transaction, SCOPE, "review-1", sources) != original
    model.provider = ref("OtherProvider")
    with pytest.raises(AipActionTransitionBlocked, match="MODEL_PROVIDER_DRIFTED"):
        binding.source_envelope(transaction, SCOPE, "review-1", sources)
