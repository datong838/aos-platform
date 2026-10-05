"""First Model Eval request needs an exact, non-executable application identity."""

from datetime import UTC, datetime, timedelta
import json
import uuid

import pytest
import psycopg

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_models import (
    AcquireExecutionLeaseRequest, CreateActionProposalRequest, DecideActionProposalRequest,
)
from aos_api.aip_action_adapters import ActionAdapterRegistry
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_eval_action import (
    ModelEvalActionBlocked, propose_model_eval_request, decide_model_eval_request,
)
from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevisionCreate, QuotaPolicyRevisionCreate,
)
from aos_api.aip_model_runtime_store import evaluation_candidate_ref
from aos_api.aip_model_eval_request_store import (
    AipModelEvalRequestStore, ModelEvalRequestBlocked, ModelEvalRequestConflict,
)
from aos_api.db import connect, get_dsn
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope
from tests.aip._budget_test_fixture import seed_isolated_active_budget
from tests.aip._model_governance_history_fixture import seed_historical_model_policy
from tests.aip.test_aip7_model_runtime_store import rehashed
from tests.aip.test_model_eval_authorization import CurrentCandidateStore


NOW = datetime(2026, 10, 2, tzinfo=UTC)


def _ref(kind: str, asset_id: str, revision: int, digest: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=kind, assetId=asset_id, revision=revision, contentHash=digest * 64,
    )


def _request(**changes):
    payload = dict(
        tenant={"orgId": "org-org", "projectId": "dev-project"},
        sourceRef=_ref("RegisteredModelRevision", "model", 1, "1"),
        targetRef=_ref("RegisteredModelRevision", "model", 2, "2"),
        expectedHeadVersion=7,
        evalContractRef=_ref("EvalContractRevision", "contract", 1, "3"),
        suiteRef=_ref("EvalSuiteRevision", "suite", 1, "4"),
        providerRef=_ref("ProviderInstanceRevision", "provider", 1, "5"),
        priceRef=_ref("ModelPriceSnapshotRevision", "price", 1, "6"),
        quotaPolicyRef=_ref("QuotaPolicyRevision", "quota", 1, "7"),
        budgetPolicyRef=_ref("BudgetPolicyRevision", "budget", 1, "8"),
        purpose="quality-eval", currency="CNY", upperBoundMinor=200,
        expiresAt=NOW + timedelta(hours=1),
    )
    payload.update(changes)
    return payload


def test_model_eval_request_is_exact_and_not_an_execution_grant():
    request = ModelEvalRequestCreate.model_validate(_request())
    assert request.source_ref.revision == 1
    assert request.target_ref.revision == 2
    assert request.upper_bound_minor == 200
    assert "executionAllowed" not in request.model_dump(mode="json", by_alias=True)


@pytest.mark.parametrize("change", [
    {"purpose": "business-runtime"},
    {"currency": "USD"},
    {"upperBoundMinor": 0},
    {"expectedHeadVersion": 0},
    {"expiresAt": datetime(2026, 10, 2)},
    {"targetRef": _ref("RegisteredModelRevision", "other", 2, "2")},
    {"targetRef": _ref("RegisteredModelRevision", "model", 3, "2")},
    {"sourceRef": _ref("ModelRouteRevision", "model", 1, "1")},
    {"suiteRef": _ref("RegisteredModelRevision", "suite", 1, "4")},
])
def test_model_eval_request_rejects_wrong_scope_or_authority_shape(change):
    with pytest.raises(ValueError):
        ModelEvalRequestCreate.model_validate(_request(**change))


def test_model_eval_action_has_explicit_approval_without_execution():
    risk = classify_action_risk(
        "aip_request_model_eval",
        {"id": "aip_request_model_eval", "name": "Model Eval"},
        {"requestId": "eval-request-1", "priceRef": {"assetId": "price"}},
        None,
    )
    assert risk.floor is ActionRiskLevel.R2
    assert risk.level is ActionRiskLevel.R2
    assert risk.approval_policy == {
        "makerChecker": True,
        "minimumApprovals": 1,
        "executionAllowed": False,
        "draftOnly": False,
    }


def test_generic_action_store_rejects_model_eval_without_dedicated_guard():
    snapshot = {"id": "aip_request_model_eval", "revisionHash": "a" * 64}
    payload = {"requestId": "model-eval-request-1", "requestHash": "b" * 64}
    body = CreateActionProposalRequest(
        actionTypeId="aip_request_model_eval", purpose="quality-eval", payload=payload,
    )
    risk = classify_action_risk(body.action_type_id, snapshot, payload, None)
    with pytest.raises(AipActionTransitionBlocked, match="MODEL_EVAL_ACTION_GUARD_REQUIRED"):
        AipActionStore()._internal_request_binding(
            None, TenantScope("org-org", "dev-project"), "maker", body, snapshot, risk,
        )


def test_model_eval_request_rejects_missing_current_model_without_writing():
    with psycopg.connect(get_dsn()) as owner:
        owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test org') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO meta_org(id,name) VALUES('org-org','test org') ON CONFLICT DO NOTHING")
        owner.execute("""INSERT INTO twa_workspace(org_id,project_id,name)
            VALUES('org-org','dev-project','test workspace') ON CONFLICT DO NOTHING""")
        owner.execute("""INSERT INTO meta_workspace(org_id,project_id,name)
            VALUES('org-org','dev-project','test workspace') ON CONFLICT DO NOTHING""")
        owner.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
            VALUES('org-org','dev-project','test-maker','owner') ON CONFLICT DO NOTHING""")
        owner.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
            VALUES('org-org','dev-project','test-checker','admin') ON CONFLICT DO NOTHING""")
    request = ModelEvalRequestCreate.model_validate(_request(
        expiresAt=datetime.now(UTC) + timedelta(hours=1),
    ))
    store = AipModelEvalRequestStore()
    with connect(TenantScope("org-org", "dev-project")) as conn:
        previous = conn.execute("SELECT count(*) AS n FROM aip_model_eval_request").fetchone()["n"]
    with pytest.raises(ModelEvalRequestBlocked):
        store.create(TenantScope("org-org", "dev-project"),
                     "test-maker", "missing-model-test", request)
    with connect(TenantScope("org-org", "dev-project")) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_model_eval_request").fetchone()["n"] == previous


def _register_original_model_eval_contract(scope, target, suffix):
    """Original governance publication plus unexecuted model Suite and legal freeze.

    The content gate certifies only the governance fixture Graph. This produces
    request inputs, never a model quality result, model gate or execution grant.
    """
    from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
    from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import CreateEvalContractRequest
    from tests.extension_runtime.test_ecommerce_content_review_pending_pg import _register_current_content_eval_gate
    contracts = AipProductionContractStore()
    with connect(scope) as conn:
        row = conn.execute("SELECT h.contract_id,h.current_revision FROM aip_eval_contract_head h "
            "JOIN aip_eval_contract_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id "
            "AND r.contract_id=h.contract_id AND r.revision=h.current_revision "
            "WHERE h.org_id=%s AND h.project_id=%s AND r.gate_policy->>'subjectKind'='ecommerce_content' "
            "ORDER BY h.contract_id LIMIT 1", scope.key).fetchone()
    if row is None:
        exact, _, _ = _register_current_content_eval_gate(connect)
        governance = contracts.get_eval_contract(scope, exact.resource_id, exact.revision)
    else:
        governance = contracts.get_eval_contract(scope, row['contract_id'], row['current_revision'])
    assert governance.readiness.value == 'ready' and not governance.blockers
    registry = AipEvalPackRegistry()
    base = registry.get_suite_revision(scope, governance.suite_ref.resource_id,
                                       governance.suite_ref.revision)
    suite = base.model_copy(update={'suite_id': 'model-suite-' + suffix,
        'target': AssetRevisionRef(asset_type=AssetType.REGISTERED_MODEL, asset_id=target.asset_id,
            revision=str(target.revision), content_hash=target.content_hash)})
    suite = suite.model_copy(update={'content_hash': compute_eval_suite_hash(suite)})
    registry.register_suite_revision(scope, suite, actor='test-maker')
    body = CreateEvalContractRequest(
        suiteRef={'resourceType': 'EvalSuiteRevision', 'resourceId': suite.suite_id,
                  'revision': suite.revision, 'contentHash': suite.content_hash},
        publicationRef=governance.publication_ref, releaseGateRef=governance.release_gate_ref,
        artifactSchemaRef=governance.artifact_schema_ref,
        severityThresholds={'critical': 1.0},
        gatePolicy={'subjectKind': 'model_eval', 'executionAllowed': False},
        returnMapping={'critical': 'blocked'}, overridePolicy={'allowed': False})
    draft = contracts.create_eval_contract(scope, 'test-maker', 'model-contract-' + suffix, body)
    frozen = contracts.freeze_eval_contract(scope, 'test-maker', draft.contract_id,
                                            draft.version, 'model-freeze-' + suffix)
    original = contracts.get_eval_contract(scope, frozen.contract_id, frozen.revision)
    assert original.lifecycle.value == 'frozen' and original.readiness.value == 'ready'
    assert not original.blockers
    with connect(scope) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_release_gate_decision "
            "WHERE org_id=%s AND project_id=%s AND target_ref->>'assetId'=%s",
            (*scope.key, target.asset_id)).fetchone()['n'] == 0
    return suite, frozen


def seeded_approved_model_eval_request(*, stop_after_approval: bool = False,
                                      formal_sources=None, upper_bound_minor: int = 200,
                                      provider_model_id: str = "m",
                                      expiry_after: timedelta = timedelta(minutes=30)):
    suffix = uuid.uuid4().hex[:10]
    expiry = datetime.now(UTC) + expiry_after
    since = datetime.now(UTC) - timedelta(hours=1)
    until = datetime.now(UTC) + timedelta(days=2)
    with psycopg.connect(get_dsn()) as owner:
        owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test org') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO meta_org(id,name) VALUES('org-org','test org') ON CONFLICT DO NOTHING")
        owner.execute("""INSERT INTO twa_workspace(org_id,project_id,name)
            VALUES('org-org','dev-project','test workspace') ON CONFLICT DO NOTHING""")
        owner.execute("""INSERT INTO meta_workspace(org_id,project_id,name)
            VALUES('org-org','dev-project','test workspace') ON CONFLICT DO NOTHING""")
        owner.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
            VALUES('org-org','dev-project','test-maker','owner') ON CONFLICT DO NOTHING""")
        owner.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
            VALUES('org-org','dev-project','test-checker','admin') ON CONFLICT DO NOTHING""")
    scope = TenantScope("org-org", "dev-project")
    if formal_sources is None:
        budget = seed_isolated_active_budget(scope, "test-maker", BudgetRevisionCreate(
            budgetId=f"budget-{suffix}", revision=1, environment="development",
            currency="CNY", dailyLimitMinor=500, monthlyLimitMinor=5000,
            alertThresholdPct=80, hardStop=True, unknownUsageBehavior="block",
            effectiveFrom=since, effectiveUntil=until, owner="test-maker",
            overBudgetApprover="test-maker", lifecycle="active",
        ))
    else:
        budget, budget_policy, provider, price = formal_sources
        expiry = min(expiry, budget_policy.effective_until, price.effective_until)
        assert expiry > datetime.now(UTC) + timedelta(minutes=1)
    quota = seed_historical_model_policy(scope, "test-maker", QuotaPolicyRevisionCreate(
        policyId=f"quota-{suffix}", revision=1, environment="development",
        effectiveFrom=since, effectiveUntil=until, owner="test-maker",
        approvalRef=f"approval-{suffix}", lifecycle="active", maxConcurrency=2,
        maxInputTokens=8000, maxOutputTokens=2000, hourlyRequestLimit=50,
        dailyRequestLimit=200, reservationLeaseSeconds=60,
        overflowBehavior="queue", allowPublicProviderFallback=False, allowAutoScale=False,
    ))
    if formal_sources is None:
        budget_policy = seed_historical_model_policy(scope, "test-maker", BudgetPolicyRevisionCreate(
            policyId=f"budget-policy-{suffix}", revision=1, environment="development",
            effectiveFrom=since, effectiveUntil=until, owner="test-maker",
            approvalRef=f"approval-{suffix}", lifecycle="active",
            budgetRevisionRef=VersionedAssetRef(
                assetType="BudgetRevision", assetId=budget.budget_id,
                revision=budget.revision, contentHash=budget.content_hash),
            currency="CNY", hardStop=True, unknownUsageBehavior="block",
            unknownPriceBehavior="block", allowZeroPrice=False,
        ))
        provider = rehashed(CurrentCandidateStore().provider,
                            providerInstanceId=f"provider-{suffix}")
        price = rehashed(CurrentCandidateStore().price,
                         priceSnapshotId=f"price-{suffix}", effectiveFrom=since)
    model = rehashed(CurrentCandidateStore().model,
        registeredModelId=f"model-{suffix}",
        providerModelId=provider_model_id,
        provider={"assetType": "ProviderInstanceRevision",
                  "assetId": provider.provider_instance_id, "revision": provider.revision,
                  "contentHash": provider.content_hash},
        priceSnapshotRef={"assetType": "ModelPriceSnapshotRevision",
                          "assetId": price.price_snapshot_id, "revision": price.revision,
                          "contentHash": price.content_hash},
        quotaPolicyRef={"assetType": "QuotaPolicyRevision", "assetId": quota.policy_id,
                        "revision": quota.revision, "contentHash": quota.content_hash},
        budgetPolicyRef={"assetType": "BudgetPolicyRevision", "assetId": budget_policy.policy_id,
                         "revision": budget_policy.revision, "contentHash": budget_policy.content_hash})
    source = VersionedAssetRef(assetType="RegisteredModelRevision",
        assetId=model.registered_model_id, revision=model.revision,
        contentHash=model.content_hash)
    target = evaluation_candidate_ref(model.model_copy(update={
        "revision": model.revision + 1, "lifecycle": type(model.lifecycle).ACTIVE,
        "eval_gate_ref": None,
    }))
    with psycopg.connect(get_dsn()) as owner:
        owner.execute("""INSERT INTO aip_registered_model_head
            (org_id,project_id,registered_model_id,current_revision,version)
            VALUES('org-org','dev-project',%s,1,7)""", (source.asset_id,))
        owner.execute("""INSERT INTO aip_registered_model_revision
            (org_id,project_id,registered_model_id,revision,content_hash,lifecycle,payload,created_by)
            VALUES('org-org','dev-project',%s,1,%s,'validated',%s::jsonb,'test-maker')""",
            (source.asset_id, source.content_hash,
             json.dumps(model.model_dump(mode="json", by_alias=True))))
        for prefix, column, ref, payload in (() if formal_sources is not None else (
            ("aip_provider_instance", "provider_instance_id", model.provider,
             provider.model_dump(mode="json", by_alias=True)),
            ("aip_model_price_snapshot", "model_price_snapshot_id", model.price_snapshot_ref,
             price.model_dump(mode="json", by_alias=True)),
        )):
            owner.execute(f"""INSERT INTO {prefix}_head
                (org_id,project_id,{column},current_revision,version)
                VALUES('org-org','dev-project',%s,1,1)""", (ref.asset_id,))
            owner.execute(f"""INSERT INTO {prefix}_revision
                (org_id,project_id,{column},revision,content_hash,lifecycle,payload,created_by)
                VALUES('org-org','dev-project',%s,1,%s,'active',%s::jsonb,'test-maker')""",
                (ref.asset_id, ref.content_hash, json.dumps(payload)))
    suite, contract = _register_original_model_eval_contract(scope, target, suffix)
    eval_tables = ("aip_eval_run", "aip_eval_report_revision", "aip_release_gate_decision")
    with connect(scope) as conn:
        governance_baseline = {table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
                               for table in eval_tables}
    request = ModelEvalRequestCreate.model_validate(_request(
        sourceRef=source, targetRef=target, expectedHeadVersion=7,
        evalContractRef=VersionedAssetRef(assetType="EvalContractRevision", assetId=contract.contract_id,
            revision=contract.revision, contentHash=contract.content_hash),
        suiteRef=VersionedAssetRef(assetType="EvalSuiteRevision", assetId=suite.suite_id,
            revision=suite.revision, contentHash=suite.content_hash),
        providerRef=model.provider, priceRef=model.price_snapshot_ref,
        quotaPolicyRef=model.quota_policy_ref, budgetPolicyRef=model.budget_policy_ref,
        expiresAt=expiry, upperBoundMinor=upper_bound_minor,
    ))
    store = AipModelEvalRequestStore()
    first = store.create(scope, "test-maker", f"eval-{suffix}", request)
    replay = store.create(scope, "test-maker", f"eval-{suffix}", request)
    assert replay["request_id"] == first["request_id"]
    with pytest.raises(ModelEvalRequestConflict):
        store.create(scope, "test-maker", f"eval-{suffix}",
                     request.model_copy(update={"upper_bound_minor": 201}))
    with pytest.raises(ModelEvalRequestBlocked):
        store.create(TenantScope("dev-org", "dev-project"), "test-maker",
                     f"canary-{suffix}", request)
    maker = Principal(subject="test-maker", org_id=scope.org_id,
                      project_id=scope.project_id, roles=["owner"], token_kind="oidc")
    checker = Principal(subject="test-checker", org_id=scope.org_id,
                        project_id=scope.project_id, roles=["admin"], token_kind="oidc")
    proposal = propose_model_eval_request(maker, first["request_id"],
                                          f"proposal-{suffix}", expiry)
    assert proposal.proposal.status.value == "drafted"
    with pytest.raises(AipActionTransitionBlocked, match="MODEL_EVAL_ACTION_GUARD_REQUIRED"):
        AipActionStore()._internal_proposal_guard(None, scope, "test-checker",
            {"action_type_id": "aip_request_model_eval",
             "action_type_snapshot": {"id": "aip_request_model_eval"}}, checker=True)
    approve = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": proposal.proposal.version,
        "expectedProposalHash": proposal.proposal.proposal_hash,
        "decision": "approved", "reason": "isolated formal application",
        "approvalExpiresAt": expiry,
    })
    with pytest.raises(ModelEvalActionBlocked, match="INDEPENDENT_CHECKER"):
        decide_model_eval_request(maker, proposal.proposal.id, f"self-{suffix}", approve)
    approved = decide_model_eval_request(
        checker, proposal.proposal.id, f"approve-{suffix}", approve)
    assert approved.proposal.status.value == "approved"
    assert approved.proposal.policy_snapshot["executionAllowed"] is False
    assert len(approved.approvals) == 1
    if stop_after_approval:
        return scope, first, request, proposal, approved, budget, budget_policy, price
    with pytest.raises(ModelEvalActionBlocked, match="MAKER_OR_EXPIRY_DRIFTED"):
        propose_model_eval_request(checker, first["request_id"],
                                   f"wrong-maker-{suffix}", expiry)
    with psycopg.connect(get_dsn()) as owner:
        owner.execute("""UPDATE meta_action_type SET name='tampered'
            WHERE id='aip_request_model_eval'""")
    with pytest.raises(ModelEvalActionBlocked, match="ACTION_TYPE_DRIFTED"):
        propose_model_eval_request(maker, first["request_id"],
                                   f"metadata-drift-{suffix}", expiry)
    with psycopg.connect(get_dsn()) as owner:
        owner.execute("""UPDATE meta_action_type SET name='申请模型首次评测'
            WHERE id='aip_request_model_eval'""")
    executor = Principal(subject="test-executor", org_id=scope.org_id,
                         project_id=scope.project_id, roles=["executor"], token_kind="oidc")
    with pytest.raises(AipActionTransitionBlocked, match="MODEL_EVAL_APPLICATION_NOT_EXECUTABLE"):
        AipActionExecutionService(AipActionStore(), ActionAdapterRegistry()).acquire_lease(
            executor, proposal.proposal.id, f"lease-{suffix}",
            AcquireExecutionLeaseRequest.model_validate({
                "expectedProposalVersion": approved.proposal.version,
                "expectedProposalHash": approved.proposal.proposal_hash,
            }),
        )
    with connect(scope) as conn:
        row = conn.execute("""SELECT request_hash,request_json FROM aip_model_eval_request
            WHERE request_id=%s""", (first["request_id"],)).fetchone()
        assert row["request_hash"] == first["request_hash"]
        assert row["request_json"]["purpose"] == "quality-eval"
        assert conn.execute("SELECT count(*) AS n FROM aip_model_eval_request WHERE request_id=%s",
                            (first["request_id"],)).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM aip_action_execution_lease").fetchone()["n"] == 0
        for table in eval_tables:
            assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == governance_baseline[table]
        assert conn.execute("SELECT count(*) AS n FROM aip_release_gate_decision "
            "WHERE org_id=%s AND project_id=%s AND target_ref->>'assetId'=%s",
            (*scope.key, target.asset_id)).fetchone()["n"] == 0
    with psycopg.connect(get_dsn()) as owner:
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="AIP4_APPEND_ONLY"):
            owner.execute("""UPDATE aip_model_eval_request SET upper_bound_minor=1
                WHERE org_id='org-org' AND project_id='dev-project' AND request_id=%s""",
                (first["request_id"],))
        owner.rollback()
        owner.execute("""UPDATE aip_registered_model_head SET version=version+1
            WHERE org_id='org-org' AND project_id='dev-project' AND registered_model_id=%s""",
            (model.registered_model_id,))
    with pytest.raises(ModelEvalRequestBlocked, match="current Model Eval candidate"):
        store.create(scope, "test-maker", f"drift-{suffix}", request)


def test_model_eval_request_is_exact_immutable_and_idempotent_on_disposable_pg():
    seeded_approved_model_eval_request()


def test_model_eval_request_rejects_original_dynamic_blocked_frozen_contract():
    """Maintenance negative; frozen flag alone is not an authoritative source."""
    from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
    from aos_api.aip_production_contracts import CreateEvalContractRequest, BriefLifecycle
    scope, _, request, _, _, _, _, _ = seeded_approved_model_eval_request(stop_after_approval=True)
    identity = "broken-model-contract-" + uuid.uuid4().hex
    body = CreateEvalContractRequest(
        suiteRef={"resourceType": "EvalSuiteRevision", "resourceId": request.suite_ref.asset_id,
                  "revision": request.suite_ref.revision, "contentHash": request.suite_ref.content_hash},
        artifactSchemaRef={"resourceType": "Schema", "resourceId": "maintenance-negative",
                           "revision": "1", "authority": "aip"},
        severityThresholds={"critical": 1.0}, gatePolicy={"mode": "all"},
        returnMapping={"critical": "blocked"}, overridePolicy={"allowed": False})
    digest = canonical_hash(body.model_dump(mode="json", by_alias=True))
    contracts = AipProductionContractStore()
    with psycopg.connect(get_dsn()) as owner:
        owner.execute("INSERT INTO aip_eval_contract_head(org_id,project_id,contract_id,current_revision,version) "
                      "VALUES(%s,%s,%s,1,1)", (*scope.key, identity))
        contracts._insert_eval(owner, scope, identity, 1, "maintenance-negative", body,
                               digest, BriefLifecycle.FROZEN)
    broken = request.model_copy(update={"eval_contract_ref": VersionedAssetRef(
        assetType="EvalContractRevision", assetId=identity, revision=1, contentHash=digest)})
    original = contracts.get_eval_contract(scope, identity, 1)
    assert original.lifecycle.value == "frozen" and original.readiness.value == "blocked"
    assert original.blockers
    with connect(scope) as conn:
        before = conn.execute("SELECT count(*) AS n FROM aip_model_eval_request").fetchone()["n"]
    with pytest.raises(ModelEvalRequestBlocked, match="ready frozen Eval Contract"):
        AipModelEvalRequestStore().create(scope, "test-maker", "broken-" + uuid.uuid4().hex, broken)
    with connect(scope) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_model_eval_request").fetchone()["n"] == before
