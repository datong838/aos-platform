"""Full-migration, disposable-DB composition for a content review candidate.

Each assertion below is only a staged subproof; no test Provider is a live call.
"""

from datetime import UTC, datetime, timedelta
from copy import deepcopy
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_effect_review import CreateEffectReviewRequest, EffectMaturityStatus
from aos_api.aip_effect_review_store import AipEffectReviewStore
from aos_api.aip_budget_reservation_contracts import BudgetExactRef, ReserveBudgetRequest
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, canonical_hash
from aos_api.aip_contracts import ActionRiskLevel, ApprovalDecision, ExactContractRef, PlanStep, ResourceRef
from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_eval_contracts import (
    AssetRevisionRef, AssetType, EvalGatePolicyRef, EvalStageAttemptRef,
    EvalSubjectArtifactRef,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from aos_api.aip_eval_runner import AipEvalRunner, JudgeExecution, ResolvedArtifact
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import (
    CreateBriefRequest, CreateEvalContractRequest, CreateResponsibilityPlanRequest,
    CreateReviewIssueRequest, ExactArtifactRef, ExactRevisionRef,
    RegisterReviewRuleRevisionRequest, ResolveReviewIssueRequest, ReturnReviewIssueRequest,
    ReviseBriefRequest,
    ResponsibilitySlot,
)
from aos_api.aip_assignee_resolution import ResolveAssigneeRequest
from aos_api.aip_assignee_resolution_store import AipAssigneeResolutionStore
from aos_api.ecommerce_business_investigation_review_command import review_issue_exact_ref
from aos_api.aip_release_publication_models import DeriveReleaseGateRequest, PublishReleaseRequest
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.ecommerce_content_execution_journal import (
    ContentExecutionConflict, ContentExecutionJournal, _payload,
)
from aos_api.ecommerce_content_review_pending import (
    ContentReviewPendingBlocked, ContentReviewPendingReader,
)
from aos_api.ecommerce_content_execution_composition import CurrentContentPreparation
from aos_api.ecommerce_content_execution_composition import CurrentContentStatusReader
from aos_api.ecommerce_content_pre_review_eval import (
    build_content_pre_review_graph, execute_content_pre_review_target,
)
from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
from aos_api.ecommerce_content_pre_review_authority import require_current_content_pre_review_gate
from aos_api.ecommerce_content_execution_worker import ContentExecutionWorker, PreparedContentInvocation
from aos_api.ecommerce_content_result_consumer import ContentResultConsumer
from aos_api.ecommerce_content_step_owner import (
    ContentGenerationStepOwner, ContentGenerationStepSource, ContentStepConflict,
)
from aos_api.ecommerce_content_review_step_owner import (
    ContentReviewStepConflict, ContentReviewStepOwner, ContentReviewStepSource,
)
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthDispatchSnapshot, HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService, ContentReviewHostService, _analysis_command_hash,
    _strict_content_generate_command,
)
from aos_api.ecommerce_growth_runtime_store import BoundEcommerceGrowthRuntimeStore
from aos_api.ecommerce_growth_feedback_consumer import CurrentFeedbackConsumer
from aos_api.ecommerce_growth_daily_review_target import DailyReviewFeedbackWorker
from aos_api.ecommerce_growth_improvement_target import CurrentImprovementConsumer, ImprovementFeedbackWorker
from aos_api.ecommerce_growth_effect_review_owner import CurrentEffectReviewConsumer, EffectReviewOwner
from aos_api.ecommerce_growth_memory_candidate_target import (
    CurrentMemoryCandidateConsumer, MemoryCandidateFeedbackWorker,
)
from aos_api.ecommerce_growth_content_return_target import (
    BoundContentReturnTarget, ContentReturnFeedbackWorker, CurrentContentReturnConsumer,
)
from aos_api.ecommerce_content_repair_brief_authority import (
    require_repair_brief, require_frozen_repair_brief,
)
from aos_api.ecommerce_workshop_feedback_read_model import EcommerceWorkshopFeedbackReadModel
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_full_graph import SCOPE, disposable_database, insert


def _upgrade_test_clone_to_head(connect):
    """Upgrade only the exact disposable clone, never the current business DB."""
    with connect(SCOPE) as conn:
        params = conn.info.get_parameters()
        database = conn.info.dbname
        assert database.startswith("a0v_growth_graph_test_")
        url = URL.create("postgresql+psycopg", username=params["user"],
            password=conn.info.password, host=params["host"],
            port=int(params["port"]), database=database)
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    engine = create_engine(url)
    try:
        with engine.begin() as sqlalchemy_conn:
            cfg.attributes["connection"] = sqlalchemy_conn
            command.upgrade(cfg, "head")
    finally:
        engine.dispose()
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "a0v_111"
        assert conn.execute("SELECT to_regprocedure(%s) AS procedure",
            ("public.extension_dispatch_lock_group_a0v_028(uuid)",)).fetchone()["procedure"] is not None


@contextmanager
def _runtime_role_connection(connect, scope):
    """Use this disposable clone's non-superuser runtime role and serializable scope."""
    with connect(scope) as conn:
        conn.execute("SET SESSION AUTHORIZATION aos_runtime")
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
        identity = conn.execute("""SELECT session_user AS session_user,
            current_setting('role') AS role_name,
            current_setting('transaction_isolation') AS isolation,
            (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=session_user)
              AS elevated""").fetchone()
        assert identity == {"session_user": "aos_runtime", "role_name": "aos_runtime",
            "isolation": "serializable", "elevated": False}
        yield conn


def _register_current_content_eval_gate(connect):
    """Formal isolated Graph/Suite/release/contract authority, not production install."""
    graph = LogicGraphStore(lambda: connect(SCOPE)).create(
        *SCOPE.key, "fixture", build_content_pre_review_graph())
    target = AssetRevisionRef(asset_type=AssetType.LOGIC_GRAPH, asset_id=graph.id,
        revision=str(graph.revision), content_hash=graph.graph_hash)
    governance, subject = build_content_pre_review_eval_packs(target)
    registry = AipEvalPackRegistry(connect_factory=connect)
    with connect(SCOPE) as conn:
        for pack in (governance, subject):
            conn.execute(
                """INSERT INTO aip_artifact
                   (org_id,project_id,artifact_id,artifact_type,content_hash,created_by)
                   VALUES (%s,%s,%s,'eval_dataset_snapshot',%s,'fixture'),
                          (%s,%s,%s,'redaction_receipt',%s,'fixture')""",
                (*SCOPE.key, pack.manifest.source_id, pack.manifest.source_hash,
                 *SCOPE.key, pack.manifest.redaction_receipt.artifact_id,
                 pack.manifest.redaction_receipt.content_hash),
            )
        conn.commit()
    for pack in (governance, subject):
        registry.register_dataset_revision(SCOPE, pack.dataset, pack.manifest, actor="fixture")
        registry.register_suite_revision(SCOPE, pack.suite, actor="fixture")
    report = AipEvalRunner(connect_factory=connect).run(
        SCOPE, suite_id=governance.suite.suite_id, suite_revision=1,
        idempotency_key="content-p2g-governance", actor="fixture",
        resolve_artifact=lambda ref: ResolvedArtifact(
            reference=ref, value=governance.artifacts[(ref.artifact_id, ref.revision)]),
        execute_target=lambda ref, value: execute_content_pre_review_target(ref, graph, value),
        execute_judge=lambda ref, actual, expected: JudgeExecution(
            judge=ref, passed=actual is expected, detail_code="exact_bool_match"))
    assert report.gate_passed
    release = AipReleasePublicationService(connect)
    gate = release.derive_gate(SCOPE, actor="fixture", request=DeriveReleaseGateRequest(
        report_id=report.report_id, report_revision=report.revision,
        report_hash=report.content_hash, idempotency_key="content-p2g-gate"))
    published = release.publish(SCOPE, actor="fixture", request=PublishReleaseRequest(
        release_gate_decision_id=gate.decision_id, reason_hash="d" * 64,
        idempotency_key="content-p2g-published"))
    with connect(SCOPE) as conn:
        row = conn.execute("""SELECT * FROM aip_publication_event
            WHERE org_id=%s AND project_id=%s AND event_id=%s""",
            (*SCOPE.key, published.event_id)).fetchone()
        publication_hash = canonical_hash(AipProductionContractStore._publication_snapshot(row))
    body = CreateEvalContractRequest(
        suite_ref=ExactRevisionRef(resource_type="EvalSuiteRevision",
            resource_id=subject.suite.suite_id, revision=subject.suite.revision,
            content_hash=subject.suite.content_hash),
        publication_ref=ExactRevisionRef(resource_type="PublicationEvent",
            resource_id=published.event_id, revision=1, content_hash=publication_hash),
        release_gate_ref=ExactRevisionRef(resource_type="ReleaseGateDecision",
            resource_id=gate.decision_id, revision=1, content_hash=gate.decision_hash),
        artifact_schema_ref=ResourceRef(resource_type="Schema",
            resource_id="ecommerce-readable-content-v1", revision="1", authority="aip"),
        severity_thresholds={"critical": 1.0},
        gate_policy={"subjectKind": "ecommerce_content",
            "subjectInputMode": "ecommerce-readable-content/v1",
            "requiresHumanDecision": True},
        return_mapping={"critical": "content_generate"},
        override_policy={"allowed": False})
    contracts = AipProductionContractStore(connect_factory=connect)
    draft = contracts.create_eval_contract(
        SCOPE, "fixture", "content-p2g-subject-contract", body)
    frozen = contracts.freeze_eval_contract(SCOPE, "fixture", draft.contract_id,
        draft.version, "content-p2g-subject-freeze")
    with connect(SCOPE) as conn:
        exact = require_current_content_pre_review_gate(conn, SCOPE)
    assert exact.resource_id == frozen.contract_id
    assert exact.content_hash == frozen.content_hash
    return exact, graph, subject


def _seed_original_run_and_budget(connect, *, eval_gate=None):
    """Seed only external authorities in the owned clone; use public Task/Budget APIs."""
    now = datetime.now(UTC)
    store = AipTaskStore(connect)
    task = store.create_task(SCOPE, "fixture", "content-p2g-task", CreateTaskRequest(
        type="analysis", title="栖月汇玫瑰面霜内容策划"))
    plan = store.create_plan(SCOPE, "fixture", task.id, "content-p2g-plan",
        CreatePlanRevisionRequest(expected_task_version=task.version, steps=[
            PlanStep(step_key="content_generate", title="Generate"),
            PlanStep(step_key="content_review", title="Review",
                gate_refs=[] if eval_gate is None else [eval_gate]),
        ], dependencies=[{"fromStepKey": "content_generate", "toStepKey": "content_review"}]))
    task = store.get_task(SCOPE, task.id)
    store.approve_plan(SCOPE, "fixture", task.id, plan.revision, task.version, plan.content_hash)
    task = store.get_task(SCOPE, task.id)
    run = store.create_run(SCOPE, "fixture", task.id, "content-p2g-run",
        CreateTaskRunRequest(plan_revision_id=plan.id, expected_task_version=task.version))
    store.start_run(SCOPE, run.id, expected_run_version=run.version,
        expected_task_version=store.timeline(SCOPE, run.id).task.version,
        actor="fixture", idempotency_key="content-p2g-start")

    budget_hash = "1" * 64
    price_content = {
        "priceSnapshotId": "content-p2g-price", "currency": "CNY",
        "inputTokenPrice": 0.0025, "outputTokenPrice": 0.005,
        "cachedTokenPrice": 0.001, "tokenUnit": 1000,
        "effectiveFrom": (now - timedelta(days=1)).isoformat(),
        "effectiveUntil": (now + timedelta(days=7)).isoformat(),
        "lifecycle": "active",
    }
    price_hash = canonical_hash(price_content)
    price_payload = {"tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "revision": 1, "contentHash": price_hash, **price_content,
        "createdBy": "fixture", "createdAt": now.isoformat()}
    action_type = {"id": "ecommerce_growth_content_generate"}
    policy = {"minimumApprovals": 1}
    upper = 400
    proposal_id = "content-p2g-proposal"
    approval_id = "content-p2g-approval"
    expires = now + timedelta(days=2)
    binding_hash = "5" * 64
    stable = {
        "tenantScope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "createdBy": "fixture", "actionType": action_type,
        "taskId": task.id, "runId": run.id, "objectRef": None,
        "purpose": "receipt-first content generation", "riskLevel": "R1",
        "policy": policy, "approvalPolicyHash": canonical_hash(policy),
        "payload": {"budgetUpperBoundMinor": upper}, "diff": {}, "evidenceRefs": [],
        "impactPreviewRef": None, "actionBindingHash": binding_hash,
        "sourceDraftRef": None, "expiresAt": expires.isoformat(),
    }
    proposal_hash = canonical_hash(stable)
    with connect(SCOPE) as conn:
        assert conn.info.dbname.startswith("a0v_growth_graph_test_")
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "a0v_111"
        assert conn.execute("""SELECT count(*) AS n FROM pg_trigger
            WHERE tgrelid='public.aip_budget_revision'::regclass
              AND tgname='aip_budget_active_insert_guard'""").fetchone()["n"] == 1
        insert(conn, "aip_budget_head", budget_id="content-p2g-budget", current_revision=1)
        # Historical active reader seed in this disposable clone only. The
        # transactional DDL rolls back if insertion or re-enabling fails.
        conn.execute("ALTER TABLE public.aip_budget_revision DISABLE TRIGGER aip_budget_active_insert_guard")
        insert(conn, "aip_budget_revision", budget_id="content-p2g-budget", revision=1,
            content_hash=budget_hash, lifecycle="active", environment="development",
            currency="CNY", daily_limit_minor=500, monthly_limit_minor=900,
            alert_threshold_pct=80, hard_stop=True, unknown_usage_behavior="block",
            effective_from=now - timedelta(days=1), effective_until=now + timedelta(days=7),
            owner="fixture", over_budget_approver="reviewer", payload={}, created_by="fixture")
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.execute("ALTER TABLE public.aip_budget_revision ENABLE TRIGGER aip_budget_active_insert_guard")
    with connect(SCOPE) as conn:
        insert(conn, "aip_model_price_snapshot_head", model_price_snapshot_id="content-p2g-price",
            current_revision=1)
        insert(conn, "aip_model_price_snapshot_revision", model_price_snapshot_id="content-p2g-price",
            revision=1, content_hash=price_hash, lifecycle="active", payload=price_payload,
            created_by="fixture")
        insert(conn, "aip_action_proposal", proposal_id=proposal_id,
            action_type_id="ecommerce_growth_content_generate",
            action_type_revision_hash="a" * 64, action_type_snapshot=action_type,
            task_id=task.id, run_id=run.id, purpose="receipt-first content generation",
            risk_level="R1", policy_snapshot=policy, payload=stable["payload"],
            action_binding_hash=binding_hash, approval_policy_hash=canonical_hash(policy),
            proposal_hash=proposal_hash, status="approved", expires_at=expires,
            idempotency_key="content-p2g-proposal", request_hash="b" * 64,
            created_by="fixture")
        insert(conn, "aip_action_draft", draft_id="content-p2g-draft",
            proposal_id=proposal_id, proposal_version=1, proposal_hash=proposal_hash,
            snapshot=stable, approval_policy=policy, status="approved", created_by="fixture")
        insert(conn, "aip_action_approval_event", approval_event_id=approval_id,
            proposal_id=proposal_id, proposal_version=1, proposal_hash=proposal_hash,
            decision="approved", actor_id="reviewer", reason="内部内容生成",
            expires_at=expires, action_binding_hash=binding_hash,
            idempotency_key="content-p2g-approval", request_hash="c" * 64)
        task_row = conn.execute("""SELECT task_type,title,description,status,priority,goal,
            selection_ref,policy_revision,request_hash,current_plan_revision_id
            FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s""",
            (*SCOPE.key, task.id)).fetchone()
        approval_row = conn.execute("""SELECT approval_event_id,proposal_id,proposal_version,
            proposal_hash,decision,actor_id,reason,expires_at,created_at,action_binding_hash
            FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s
            AND approval_event_id=%s""", (*SCOPE.key, approval_id)).fetchone()
    creation = {"type": task_row["task_type"], "title": task_row["title"],
        "description": task_row["description"], "priority": task_row["priority"],
        "goal": task_row["goal"], "selectionRef": task_row["selection_ref"],
        "policyRevision": task_row["policy_revision"]}
    assert task_row["request_hash"] == canonical_hash(creation)
    request = ReserveBudgetRequest(operationId="ecommerce_growth_content_generate",
        invocationKey="content-p2g-invoke",
        taskRef=BudgetExactRef(resourceType="Task", resourceId=task.id,
            revision=1, contentHash="sha256:" + canonical_hash(creation)),
        policyRef=BudgetExactRef(resourceType="BudgetRevision", resourceId="content-p2g-budget",
            revision=1, contentHash="sha256:" + budget_hash),
        pricingRef=BudgetExactRef(resourceType="ModelPriceSnapshotRevision",
            resourceId="content-p2g-price", revision=1, contentHash="sha256:" + price_hash),
        approvalRef=BudgetExactRef(resourceType="ActionApprovalEvent", resourceId=approval_id,
            revision=1, contentHash=canonical_hash(dict(approval_row), prefixed=True)),
        currency="CNY", upperBoundMinor=upper)
    reservation = AipBudgetReservationStore(connect).reserve(SCOPE, request, actor="fixture")
    return {"task_id": task.id, "run_id": run.id, "request": request,
        "reservation": reservation}


def _seed_formal_brief_sources(connect, proof, command):
    """Create four exact source Artifacts and one draft Brief before command enqueue."""
    store = AipTaskStore(connect)
    sources = []
    for sequence in range(1, 5):
        identity = store.record_artifact(SCOPE, proof["run_id"], "fixture",
            "ecommerce_analysis_source", {"metadata": {
                "sourceKind": "controlled_test_source", "sequence": sequence}})
        with connect(SCOPE) as conn:
            row = conn.execute("""SELECT content_hash FROM aip_artifact
                WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
                (*SCOPE.key, identity)).fetchone()
        sources.append({"resourceType": "ArtifactRevision", "resourceId": identity,
            "revision": 1, "contentHash": "sha256:" + row["content_hash"]})
    command["sourceArtifactRefs"] = sources
    authorities = command["authorityRefs"]
    brief = AipProductionContractStore(connect_factory=connect).create_brief(
        SCOPE, "fixture", "content-p2g-formal-brief", CreateBriefRequest(
            taskId=proof["task_id"], briefType="content_campaign",
            schemaRef=ResourceRef(resource_type="ContentCampaignBriefSchema",
                resource_id="schema://aos/ecommerce/content-campaign-brief/v1",
                revision="1", authority="aos://ecommerce-workshop/content-campaign"),
            spec={"taskRef": authorities["task"],
                "growthPlanRef": authorities["growth_plan"],
                "artifactRefs": sources, "externalPublicationRequested": False}))
    authorities["brief"] = {"resourceType": "TaskBriefRevision",
        "resourceId": brief.brief_id, "revision": brief.revision,
        "contentHash": "sha256:" + brief.content_hash}
    command["requestHash"] = _analysis_command_hash(
        {key: value for key, value in command.items() if key != "requestHash"})
    return command


def _seed_current_command_receipt(connect, proof, *, formal_brief_sources=False):
    """Only an isolated installation; use the formal immutable Receipt owner."""
    fixture_path = Path(__file__).resolve().parents[1] / "aip/test_aip_budget_reservation_pg.py"
    spec = importlib.util.spec_from_file_location("content_budget_command_fixture", fixture_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    command = module.content_generate_command(proof["request"])
    if formal_brief_sources:
        command = _seed_formal_brief_sources(connect, proof, command)
    reservation_id = proof["reservation"].reservation_ref.resource_id
    journal = ContentExecutionJournal()
    with connect(SCOPE) as conn:
        assert journal.enqueue(conn, SCOPE, reservation_id,
            budget_request_hash=proof["request"].request_hash(), command=command) == command
        assert journal.enqueue(conn, SCOPE, reservation_id,
            budget_request_hash=proof["request"].request_hash(), command=command) == command
    generation, group = uuid4(), uuid4()
    with connect(SCOPE) as conn:
        installations = conn.execute("""SELECT installation_id,current_revision
            FROM bundle_installation WHERE org_id=%s AND project_id=%s""",
            SCOPE.key).fetchall()
        assert len(installations) == 1
        installation = installations[0]["installation_id"]
        insert(conn, "extension_runtime_binding", installation_id=installation,
            generation=generation, installation_revision=installations[0]["current_revision"],
            package_lock_ref={},
            profile_ref="internal-python-v1", config_ref={}, execution_epoch=3,
            desired_state="enabled", observed_state="ready", enabled=True,
            operation_fence=False)
        insert(conn, "extension_operation_dispatch_binding",
            operation_id="ecommerce_growth_content_generate", handler_kind="extension",
            installation_id=installation, generation=generation, execution_epoch=3,
            operation_fence=False, revision=5, cutover_group_id=group,
            cutover_group_revision=11, updated_by="fixture")
        conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
        dispatch = EcommerceGrowthDispatchSnapshot(
            operation_id="ecommerce_growth_content_generate", dispatch_revision=5,
            installation_id=installation, generation=generation, execution_epoch=3,
            cutover_group_id=group, cutover_group_revision=11, runtime_revision=1,
            checked_at=datetime.now(UTC))
        response = ContentGenerateHostService._pending_receipt(
            command, proof["reservation"], proof["request"], replayed=False)
        runtime = BoundEcommerceGrowthRuntimeStore(HostTransaction(conn), SCOPE)
        first = runtime.put(operation_id=dispatch.operation_id,
            idempotency_key=command["idempotencyKey"],
            request_hash="sha256:" + _payload(command)[1], dispatch=dispatch,
            response=response, target_receipt_ref=response["receiptRef"],
            actor="fixture", occurred_at=dispatch.checked_at)
        assert first.replayed is False and first.response == response
        second = runtime.put(operation_id=dispatch.operation_id,
            idempotency_key=command["idempotencyKey"],
            request_hash="sha256:" + _payload(command)[1], dispatch=dispatch,
            response=response, target_receipt_ref=response["receiptRef"],
            actor="fixture", occurred_at=dispatch.checked_at)
        assert second.replayed is True and second.response == response
    return command


def _run_controlled_result_and_consume(connect, proof, command, *, consume=True):
    """Controlled test seams: no external Provider or live business context read."""
    reservation_id = proof["reservation"].reservation_ref.resource_id
    with connect(SCOPE) as conn:
        providers = conn.execute("""SELECT provider_instance_id,revision,content_hash
            FROM aip_provider_instance_revision
            WHERE org_id=%s AND project_id=%s AND lifecycle='active'""",
            SCOPE.key).fetchall()
    assert len(providers) == 1
    provider = providers[0]
    ref = lambda kind, identity, digest="a" * 64: VersionedAssetRef(
        assetType=kind, assetId=identity, revision=1, contentHash=digest)
    resolution = ModelRouteResolution(
        tenant={"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        route=ref("ModelRouteRevision", "controlled-route"),
        policy=ref("RuntimePolicyRevision", "controlled-policy"),
        readiness=ModelRuntimeReadiness.READY,
        selectedModel=ref("RegisteredModelRevision", "controlled-model"),
        selectedProvider=VersionedAssetRef(assetType="ProviderInstanceRevision",
            assetId=provider["provider_instance_id"], revision=provider["revision"],
            contentHash=provider["content_hash"]),
        selectedPriceSnapshot=ref("ModelPriceSnapshotRevision",
            proof["request"].pricing_ref.resource_id,
            proof["request"].pricing_ref.content_hash.removeprefix("sha256:")),
        resolvedAt=datetime.now(UTC))
    calls = []
    def controlled_prepare(_conn, scope, saved_command):
        assert scope == SCOPE and saved_command == command
        return PreparedContentInvocation(resolution, "受控测试事实", "approved_internal_knowledge")
    def controlled_response(_resolution, _prompt, _classification):
        calls.append(1)
        observed = datetime.now(UTC).isoformat()
        def measured(kind, quantity):
            return {"usageKind": kind, "quantity": quantity, "unit": "token",
                "quality": "measured", "sourceHash": canonical_hash(
                    {"kind": kind, "quantity": quantity}), "observedAt": observed}
        return {"answer": "玫瑰面霜草稿，事实待人工核对。",
            "provider": provider["provider_instance_id"], "model": "controlled-model",
            "tokens": 12, "promptTokens": 7, "completionTokens": 5,
            "route": "controlled-route", "providerReceiptId": "controlled-response-1",
            "usageReceipts": [measured("input_token", 7), measured("output_token", 5)],
            "modality": "text"}
    worker = ContentExecutionWorker(connect, prepare=controlled_prepare,
        invoke=controlled_response)
    recorded = worker.run_one(SCOPE, reservation_id)
    assert recorded["status"] == "RESULT_RECORDED"
    assert worker.run_one(SCOPE, reservation_id) == recorded
    assert calls == [1]
    consumer = ContentResultConsumer(context_reader=lambda _conn, scope, saved_command: (
        {"runId": proof["run_id"], "productNames": ["玫瑰面霜"],
         "channels": ["微信小店"], "constraintChecks": ["事实待核"]}
        if scope == SCOPE and saved_command == command else None))
    if not consume:
        return consumer
    with connect(SCOPE) as conn:
        consumed = consumer.consume(conn, SCOPE, reservation_id)
    with connect(SCOPE) as conn:
        replay = consumer.consume(conn, SCOPE, reservation_id)
    assert replay["reservation"].replayed
    assert replay["artifact"] == consumed["artifact"]
    return consumed


def test_original_content_run_can_hold_formal_budget_in_one_full_database():
    with disposable_database() as connect:
        _upgrade_test_clone_to_head(connect)
        proof = _seed_original_run_and_budget(connect)
        assert proof["reservation"].state.value == "held"
        assert proof["reservation"].task_ref.resource_id == proof["task_id"]
        replay = AipBudgetReservationStore(connect).reserve(
            SCOPE, proof["request"], actor="fixture")
        assert replay.replayed
        assert replay.reservation_ref.resource_id == proof["reservation"].reservation_ref.resource_id
        with connect(SCOPE) as conn:
            assert conn.execute("""SELECT count(*) AS n FROM aip_budget_reservation
                WHERE org_id=%s AND project_id=%s AND task_ref->>'resourceId'=%s""",
                (*SCOPE.key, proof["task_id"])).fetchone()["n"] == 1
            assert conn.execute("""SELECT count(*) AS n FROM aip_usage_receipt
                WHERE org_id=%s AND project_id=%s""", SCOPE.key).fetchone()["n"] == 0


def test_original_plan_binds_one_formally_published_content_eval_gate():
    with disposable_database() as connect:
        _upgrade_test_clone_to_head(connect)
        gate, _, _ = _register_current_content_eval_gate(connect)
        proof = _seed_original_run_and_budget(connect, eval_gate=gate)
        with connect(SCOPE) as conn:
            original = conn.execute("""SELECT p.steps,p.approval_status
                FROM aip_task_run r JOIN aip_plan_revision p
                  ON p.org_id=r.org_id AND p.project_id=r.project_id
                 AND p.plan_revision_id=r.plan_revision_id AND p.task_id=r.task_id
                WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s""",
                (*SCOPE.key, proof["run_id"])).fetchone()
            assert original["approval_status"] == "approved"
            assert original["steps"][1]["gateRefs"] == [gate.model_dump(mode="json", by_alias=True)]
            assert require_current_content_pre_review_gate(conn, SCOPE) == gate


def test_original_held_content_command_has_one_formal_current_runtime_receipt(monkeypatch):
    with disposable_database() as connect:
        _upgrade_test_clone_to_head(connect)
        proof = _seed_original_run_and_budget(connect)
        command = _seed_current_command_receipt(connect, proof)
        reservation_id = proof["reservation"].reservation_ref.resource_id
        with connect(SCOPE) as conn:
            assert ContentExecutionJournal().list_held(conn, SCOPE) == [reservation_id]
            assert ContentExecutionJournal().read(conn, SCOPE, reservation_id)["command"] == command
            ContentReviewPendingReader._current_dispatch(conn, SCOPE, command)
            with pytest.raises(ContentReviewPendingBlocked, match="dispatch"):
                ContentReviewPendingReader._current_dispatch(conn, SCOPE,
                    {**command, "upperBoundFen": command["upperBoundFen"] + 1})
            with monkeypatch.context() as patch:
                patch.setattr(CurrentContentPreparation, "_lock_dispatch",
                    staticmethod(lambda *_args: SimpleNamespace(runtime_revision=1)))
                ContentGenerationStepOwner._current_dispatch(conn, SCOPE, reservation_id)
            class ReachedDispatch(Exception):
                pass
            def reached_dispatch(*_args):
                raise ReachedDispatch
            with monkeypatch.context() as patch:
                patch.setattr(CurrentContentPreparation, "_lock_dispatch",
                    staticmethod(reached_dispatch))
                with pytest.raises(ReachedDispatch):
                    CurrentContentPreparation()(conn, SCOPE, command)
            with pytest.raises(ContentExecutionConflict, match="replay drifted"):
                ContentExecutionJournal().enqueue(conn, SCOPE, reservation_id,
                    budget_request_hash=proof["request"].request_hash(),
                    command={**command, "upperBoundFen": command["upperBoundFen"] + 1})
            assert conn.execute("""SELECT count(*) AS n
                FROM ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_generate'""",
                SCOPE.key).fetchone()["n"] == 1
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE extension_runtime_binding
                SET desired_state='disabled',observed_state='stopped',
                    enabled=false,operation_fence=true
                WHERE org_id=%s AND project_id=%s AND generation=(
                    SELECT generation FROM extension_operation_dispatch_binding
                    WHERE org_id=%s AND project_id=%s
                      AND operation_id='ecommerce_growth_content_generate')""",
                (*SCOPE.key, *SCOPE.key))
            with pytest.raises(ContentReviewPendingBlocked, match="dispatch"):
                ContentReviewPendingReader._current_dispatch(conn, SCOPE, command)
            conn.rollback()


def test_controlled_result_settles_original_reservation_with_measured_artifact():
    with disposable_database() as connect:
        _upgrade_test_clone_to_head(connect)
        proof = _seed_original_run_and_budget(connect)
        command = _seed_current_command_receipt(connect, proof)
        result = _run_controlled_result_and_consume(connect, proof, command)
        assert result["reservation"].state.value == "settled"
        assert result["artifact"]["taskRef"]["resourceId"] == proof["task_id"]
        reservation_id = proof["reservation"].reservation_ref.resource_id
        with connect(SCOPE) as conn:
            assert CurrentContentStatusReader()(conn, SCOPE, reservation_id) == "COMPLETED"
            row = conn.execute("""SELECT invocation_id,state,provider_request_receipt_ref,
                provider_receipt_ref,usage_receipt_refs FROM aip_budget_reservation
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
                (*SCOPE.key, reservation_id)).fetchone()
            assert row["state"] == "settled"
            assert row["provider_request_receipt_ref"]["resourceType"] == "CapabilityProviderRequestReceipt"
            assert row["provider_receipt_ref"]["resourceType"] == "CapabilityProviderReceipt"
            assert len(row["usage_receipt_refs"]) == 2
            assert conn.execute("""SELECT count(*) AS n FROM aip_usage_receipt
                WHERE org_id=%s AND project_id=%s AND lineage_id=%s""",
                (*SCOPE.key, str(row["invocation_id"]))).fetchone()["n"] == 2
            artifact = conn.execute("""SELECT run_id,artifact_type,content_hash,source
                FROM aip_artifact WHERE org_id=%s AND project_id=%s
                AND artifact_id=%s""",
                (*SCOPE.key, result["artifact"]["artifactRef"]["resourceId"])).fetchone()
            assert artifact["run_id"] == proof["run_id"]
            assert artifact["artifact_type"] == "ecommerce_content"
            assert artifact["source"]["invocationId"] == str(row["invocation_id"])
            source = ContentGenerationStepSource(context_reader=lambda *_args: {
                "runId": proof["run_id"]})
            settled = source.read(conn, SCOPE, reservation_id)
            assert settled.run_id == proof["run_id"]
            assert settled.artifact_id == result["artifact"]["artifactRef"]["resourceId"]
            assert len(settled.usage_receipt_refs) == 2


def test_controlled_result_settlement_failure_keeps_result_without_artifact(monkeypatch):
    with disposable_database() as connect:
        _upgrade_test_clone_to_head(connect)
        proof = _seed_original_run_and_budget(connect)
        command = _seed_current_command_receipt(connect, proof)
        consumer = _run_controlled_result_and_consume(connect, proof, command, consume=False)
        reservation_id = proof["reservation"].reservation_ref.resource_id
        def fail_settlement(*_args, **_kwargs):
            raise RuntimeError("isolated settlement failure")
        monkeypatch.setattr(AipBudgetReservationStore, "settle", fail_settlement)
        with pytest.raises(RuntimeError, match="isolated settlement failure"):
            with connect(SCOPE) as conn:
                consumer.consume(conn, SCOPE, reservation_id)
        with connect(SCOPE) as conn:
            assert CurrentContentStatusReader()(conn, SCOPE, reservation_id) == "RESULT_RECORDED_UNSETTLED"
            assert conn.execute("""SELECT state FROM aip_budget_reservation
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
                (*SCOPE.key, reservation_id)).fetchone()["state"] == "submitted"
            for table in ("aip_artifact", "aip_usage_receipt", "aip_lineage_event"):
                assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND project_id=%s",
                    SCOPE.key).fetchone()["n"] == 0
            assert conn.execute("""SELECT count(*) AS n FROM ecommerce_content_execution_result
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
                (*SCOPE.key, reservation_id)).fetchone()["n"] == 1


def test_original_settled_result_completes_one_generation_step_and_checkpoint():
    with disposable_database() as connect:
        _upgrade_test_clone_to_head(connect)
        proof = _seed_original_run_and_budget(connect)
        command = _seed_current_command_receipt(connect, proof)
        consumed = _run_controlled_result_and_consume(connect, proof, command)
        reservation_id = proof["reservation"].reservation_ref.resource_id
        wrong_run_source = ContentGenerationStepSource(
            context_reader=lambda _conn, _scope, _command: {"runId": "wrong-run"})
        with connect(SCOPE) as conn:
            with pytest.raises(ContentStepConflict, match="original Run output"):
                wrong_run_source.read(conn, SCOPE, reservation_id)
            assert conn.execute("""SELECT count(*) AS n FROM aip_step_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*SCOPE.key, proof["run_id"])).fetchone()["n"] == 0
        source = ContentGenerationStepSource(context_reader=lambda _conn, scope, saved_command: (
            {"runId": proof["run_id"]} if scope == SCOPE and saved_command == command else None))
        owner = ContentGenerationStepOwner(source=source, connect_write=connect,
            connect_read=connect)
        with connect(SCOPE) as conn:
            settled = source.read(conn, SCOPE, reservation_id)
            checkpoint_id = owner._complete_transaction(conn, SCOPE, settled)
        assert checkpoint_id is not None
        with connect(SCOPE) as conn:
            readback = owner._readback(conn, SCOPE, settled, checkpoint_id)
            assert readback["status"] == "GENERATION_STEP_SUCCEEDED"
            assert readback["runId"] == proof["run_id"]
            assert readback["checkpointId"] == checkpoint_id
            assert owner._complete_transaction(conn, SCOPE, settled) is None
        with connect(SCOPE) as conn:
            steps = conn.execute("""SELECT step_run_id,status,attempt,
                think_ref,action_ref,verify_ref,observe_ref FROM aip_step_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND step_key='content_generate'""",
                (*SCOPE.key, proof["run_id"])).fetchall()
            assert len(steps) == 1
            assert steps[0]["step_run_id"] == readback["stepRunId"]
            assert steps[0]["status"] == "succeeded" and steps[0]["attempt"] == 1
            assert all(steps[0][key] is not None for key in (
                "think_ref", "action_ref", "verify_ref", "observe_ref"))
            observed = conn.execute("""SELECT payload FROM aip_evidence
                WHERE org_id=%s AND project_id=%s AND evidence_id=%s
                  AND evidence_type='taor.observe'""",
                (*SCOPE.key, steps[0]["observe_ref"]["evidenceId"])).fetchone()["payload"]
            assert observed["payload"]["reservationId"] == reservation_id
            assert observed["payload"]["artifactRef"] == consumed["artifact"]["artifactRef"]


@pytest.mark.parametrize("review_decision", ("ACCEPT", "RETURN"))
def test_original_settled_artifact_runs_current_content_subject_eval(review_decision):
    with disposable_database() as connect:
        _upgrade_test_clone_to_head(connect)
        gate, graph, subject_pack = _register_current_content_eval_gate(connect)
        proof = _seed_original_run_and_budget(connect, eval_gate=gate)
        command = _seed_current_command_receipt(connect, proof, formal_brief_sources=True)
        consumed = _run_controlled_result_and_consume(connect, proof, command)
        reservation_id = proof["reservation"].reservation_ref.resource_id
        source = ContentGenerationStepSource(context_reader=lambda _conn, scope, saved_command: (
            {"runId": proof["run_id"]} if scope == SCOPE and saved_command == command else None))
        owner = ContentGenerationStepOwner(source=source, connect_write=connect,
            connect_read=connect)
        with connect(SCOPE) as conn:
            settled = source.read(conn, SCOPE, reservation_id)
            checkpoint_id = owner._complete_transaction(conn, SCOPE, settled)
        with connect(SCOPE) as conn:
            owner._readback(conn, SCOPE, settled, checkpoint_id)
            step = conn.execute("""SELECT step_run_id,attempt,input_hash
                FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND step_key='content_generate'""",
                (*SCOPE.key, proof["run_id"])).fetchone()
        artifact_ref = EvalSubjectArtifactRef(resourceId=settled.artifact_id,
            contentHash=settled.artifact_hash)
        attempt_ref = EvalStageAttemptRef(runId=proof["run_id"],
            stepKey="content_generate", stepRunId=step["step_run_id"],
            attempt=step["attempt"], inputHash=step["input_hash"])
        policy_ref = EvalGatePolicyRef(resourceType="EvalContractRevision",
            resourceId=gate.resource_id, revision=gate.revision,
            contentHash=gate.content_hash)
        runner = AipEvalRunner(connect_factory=connect,
            production_contract_store=AipProductionContractStore(connect_factory=connect))
        def resolve(ref):
            return ResolvedArtifact(reference=ref,
                value=subject_pack.artifacts[(ref.artifact_id, ref.revision)])
        actual_inputs = []
        def execute_target(ref, value):
            actual_inputs.append(value)
            assert value["content"] == consumed["artifact"]
            return execute_content_pre_review_target(ref, graph, value)
        report = runner.run_by_contract(SCOPE, contract_id=gate.resource_id,
            contract_revision=gate.revision, contract_content_hash=gate.content_hash,
            idempotency_key="content-p2g-original-subject-eval", actor="fixture",
            resolve_artifact=resolve, execute_target=execute_target,
            execute_judge=lambda ref, actual, expected: JudgeExecution(
                judge=ref, passed=actual == expected, detail_code="exact_bool_match"),
            subject_artifact_ref=artifact_ref, stage_attempt_ref=attempt_ref,
            gate_policy_ref=policy_ref, evidence_cutoff_at=datetime.now(UTC))
        assert report.gate_passed and len(actual_inputs) == 1
        assert report.subject_artifact_ref == artifact_ref
        assert report.stage_attempt_ref == attempt_ref
        assert report.eval_contract_ref.model_dump(mode="json", by_alias=True) == (
            policy_ref.model_dump(mode="json", by_alias=True))
        assert consumed["artifact"]["body"] not in report.model_dump_json()
        assert runner.get_report(SCOPE, report.report_id) == report
        with connect(SCOPE) as conn:
            saved = conn.execute("""SELECT status,eval_contract_ref,
                subject_artifact_ref,stage_attempt_ref FROM aip_eval_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*SCOPE.key, report.run_id)).fetchone()
            assert saved["status"] == "succeeded"
            assert saved["eval_contract_ref"] == policy_ref.model_dump(mode="json", by_alias=True)
            assert saved["subject_artifact_ref"] == artifact_ref.model_dump(mode="json", by_alias=True)
            assert saved["stage_attempt_ref"] == attempt_ref.model_dump(mode="json", by_alias=True)
            assert conn.execute("""SELECT count(*) AS n FROM aip_eval_report_revision
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*SCOPE.key, report.run_id)).fetchone()["n"] == 1
        reader = ContentReviewPendingReader(source=source, connect_read=connect)
        first = reader.read_one(SCOPE, reservation_id)
        assert first is not None
        assert (first.reservation_id, first.run_id, first.task_id,
            first.artifact_id, first.artifact_hash, first.step_run_id,
            first.report_id, first.report_revision, first.report_hash) == (
            reservation_id, proof["run_id"], proof["task_id"],
            settled.artifact_id, settled.artifact_hash, step["step_run_id"],
            report.report_id, report.revision, report.content_hash)
        assert reader.read_one(SCOPE, reservation_id) == first
        other_scope = type(SCOPE)("dev-org", "dev-project")
        with connect(SCOPE) as conn:
            with pytest.raises(ContentExecutionConflict, match="reservation unavailable"):
                source.read(conn, other_scope, reservation_id)
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE extension_operation_dispatch_binding
                SET operation_fence=true WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_generate'""", SCOPE.key)
        with pytest.raises(ContentReviewPendingBlocked, match="dispatch"):
            reader.read_one(SCOPE, reservation_id)
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE extension_operation_dispatch_binding
                SET operation_fence=false WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_generate'""", SCOPE.key)
        assert reader.read_one(SCOPE, reservation_id) == first
        with connect(SCOPE) as conn:
            assert conn.execute("""SELECT count(*) AS n FROM aip_review_issue
                WHERE org_id=%s AND project_id=%s""", SCOPE.key).fetchone()["n"] == 0
            assert conn.execute("""SELECT count(*) AS n FROM aip_eval_run
                WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*SCOPE.key, "content-p2g-original-subject-eval")).fetchone()["n"] == 1
            assert conn.execute("""SELECT count(*) AS n FROM aip_eval_report_revision
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*SCOPE.key, report.run_id)).fetchone()["n"] == 1
            assert conn.execute("""SELECT count(*) AS n FROM aip_step_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND step_key='content_generate'""",
                (*SCOPE.key, proof["run_id"])).fetchone()["n"] == 1
        contracts = AipProductionContractStore(connect_factory=connect)
        rule = contracts.register_review_rule_revision(SCOPE, "fixture",
            "content-p2g-review-rule", RegisterReviewRuleRevisionRequest(
                ruleId="content-p2g-review-rule", revision=1,
                spec={"subjectKind": "ecommerce_content",
                    "checks": ["facts", "prohibited_claims"]}))
        issue_request = CreateReviewIssueRequest(
            ruleRef=ExactRevisionRef(resourceType="EvalRuleRevision",
                resourceId=rule.rule_id, revision=rule.revision,
                contentHash=rule.content_hash),
            severity="warning",
            artifactRef=ExactArtifactRef(artifactId=first.artifact_id,
                contentHash=first.artifact_hash),
            evalReportRef=ExactRevisionRef(resourceType="EvalReportRevision",
                resourceId=first.report_id, revision=first.report_revision,
                contentHash=first.report_hash),
            location={"stage": "content_generate"},
            suggestedFix="请人工核对内容事实", returnStage="content_generate")
        issue = contracts.create_review_issue(
            SCOPE, "fixture", "content-p2g-original-issue", issue_request)
        assert contracts.create_review_issue(
            SCOPE, "fixture", "content-p2g-original-issue", issue_request) == issue
        with connect(SCOPE) as conn:
            saved_issue = conn.execute("""SELECT artifact_id,artifact_hash,
                eval_report_id,eval_report_revision,eval_report_hash,status
                FROM aip_review_issue WHERE org_id=%s AND project_id=%s
                  AND issue_id=%s""", (*SCOPE.key, issue.issue_id)).fetchone()
            assert saved_issue == {
                "artifact_id": first.artifact_id,
                "artifact_hash": first.artifact_hash,
                "eval_report_id": first.report_id,
                "eval_report_revision": first.report_revision,
                "eval_report_hash": first.report_hash,
                "status": "open",
            }
            assert conn.execute("""SELECT count(*) AS n FROM aip_review_issue
                WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
                (*SCOPE.key, first.artifact_id)).fetchone()["n"] == 1
        assert reader.read_one(SCOPE, reservation_id) is None
        review_command = {"decision": "ACCEPT",
            "artifactRef": consumed["artifact"]["artifactRef"],
            "reviewIssueRef": review_issue_exact_ref(issue).model_dump(
                mode="json", by_alias=True, exclude_none=True)}
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError, match="exact lineage drifted"):
                ContentReviewHostService._issue_authority(
                    HostTransaction(conn), SCOPE, review_command)
        if review_decision == "ACCEPT":
            resolution = ResolveReviewIssueRequest(expectedVersion=issue.version,
                reason="隔离测试 reviewer 已核对事实与禁止表达",
                resolutionRefs=[ExactRevisionRef(resourceType="Artifact",
                    resourceId=first.artifact_id, revision=1,
                    contentHash=first.artifact_hash)])
            resolved = contracts.resolve_review_issue(SCOPE, "fixture-reviewer",
                issue.issue_id, "content-p2g-original-accept", resolution)
            assert contracts.resolve_review_issue(SCOPE, "fixture-reviewer",
                issue.issue_id, "content-p2g-original-accept", resolution) == resolved
            assert resolved.status.value == "resolved" and resolved.version == 2
        else:
            return_request = ReturnReviewIssueRequest(expectedVersion=issue.version,
                runId=proof["run_id"], targetStage="content_generate",
                reason="人工要求重新核对商品事实并修改内容",
                attemptIdempotencyKey="content-p2g-original-return-attempt")
            decision = contracts.return_review_issue(SCOPE, "fixture-reviewer",
                issue.issue_id, "content-p2g-original-return", return_request)
            assert contracts.return_review_issue(SCOPE, "fixture-reviewer",
                issue.issue_id, "content-p2g-original-return", return_request) == decision
            assert decision.attempt == 2 and decision.step_key == "content_generate"
            resolved = contracts.get_review_issue(SCOPE, issue.issue_id)
            assert resolved.status.value == "returned" and resolved.version == 2
        review_command["decision"] = review_decision
        review_command["reviewIssueRef"] = review_issue_exact_ref(resolved).model_dump(
            mode="json", by_alias=True, exclude_none=True)
        review_command.update({name: consumed["artifact"][name] for name in (
            "taskRef", "briefRef", "growthPlanRef", "sourceArtifactRefs")})
        with connect(SCOPE) as conn:
            conn.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
                VALUES(%s,%s,'fixture-reviewer','member') ON CONFLICT DO NOTHING""",
                SCOPE.key)
        assignee = {"kind": "human_principal", "resourceId": "fixture-reviewer", "version": 1}
        resolution_receipt = AipAssigneeResolutionStore(connect).resolve(
            SCOPE, ResolveAssigneeRequest(subjectId="content.review", assignee=assignee),
            "fixture-reviewer", now=datetime.now(UTC))
        slot = ResponsibilitySlot.model_validate({
            "slotId": "content.review", "responsibilityType": "independent_review",
            "requiredCapabilityIds": [],
            "inputSchemaRef": {"resourceType": "Schema", "resourceId": "content-review-input",
                "revision": "1", "authority": "postgresql"},
            "outputSchemaRef": {"resourceType": "Schema", "resourceId": "content-review-output",
                "revision": "1", "authority": "postgresql"},
            "returnStage": "content_generation", "assignee": assignee,
            "assigneeResolutionReceiptId": resolution_receipt.receipt_id,
        })
        # Isolated template resolver is a test seam, not a signed installed Bundle.
        responsibility_store = AipProductionContractStore(connect_factory=connect,
            responsibility_template_resolver=lambda _scope, _ref: True)
        draft = responsibility_store.create_responsibility_plan(SCOPE, "fixture-reviewer",
            "content-p2g-review-responsibility", CreateResponsibilityPlanRequest(
                profile="TEST_HUMAN_REVIEW", templateRef={
                    "resourceType": "ResponsibilityTemplateRevision", "resourceId": "test-template",
                    "revision": 1, "contentHash": "a" * 64}, slots=[slot]))
        frozen = responsibility_store.freeze_responsibility_plan(SCOPE, "fixture-reviewer",
            draft.plan_id, draft.version, "content-p2g-freeze-review-responsibility")
        reviewer_projection = {
            "responsibilityPlanRef": {"resourceType": "ResponsibilityPlanRevision",
                "resourceId": frozen.plan_id, "revision": frozen.revision,
                "contentHash": "sha256:" + frozen.content_hash},
            "slotId": slot.slot_id, "responsibilityType": slot.responsibility_type,
            "requiredCapabilityIds": slot.required_capability_ids,
            "assignee": slot.assignee.model_dump(mode="json", by_alias=True),
            "assigneeResolutionReceiptId": slot.assignee_resolution_receipt_id,
        }
        review_command["reviewerAuthorityRef"] = {
            "resourceType": "ReviewerAuthorityRevision",
            "resourceId": f"{frozen.plan_id}/content.review",
            "revision": frozen.revision,
            "contentHash": canonical_hash(reviewer_projection, prefixed=True),
        }
        with connect(SCOPE) as conn:
            ContentReviewHostService._issue_authority(
                HostTransaction(conn), SCOPE, review_command)
            ContentReviewHostService._reviewer_authority(
                HostTransaction(conn), SCOPE, review_command)
            artifact_body = ContentReviewHostService._artifact_authority(
                HostTransaction(conn), SCOPE, review_command)
            assert artifact_body == consumed["artifact"]
            assert ContentReviewHostService._task_brief_authority(
                HostTransaction(conn), SCOPE, review_command) == "栖月汇玫瑰面霜内容策划"
            wrong_source = {**review_command, "sourceArtifactRefs": [
                {**review_command["sourceArtifactRefs"][0],
                    "contentHash": "sha256:" + "f" * 64},
                *review_command["sourceArtifactRefs"][1:]]}
            with pytest.raises(ValueError, match="Artifact exact projection drifted"):
                ContentReviewHostService._artifact_authority(
                    HostTransaction(conn), SCOPE, wrong_source)
            wrong_brief = {**review_command, "briefRef": {
                **review_command["briefRef"], "contentHash": "sha256:" + "f" * 64}}
            with pytest.raises(ValueError, match="TaskBrief exact lineage drifted"):
                ContentReviewHostService._task_brief_authority(
                    HostTransaction(conn), SCOPE, wrong_brief)
            event = conn.execute("""SELECT event_type,issue_version,actor,payload
                FROM aip_review_issue_event WHERE org_id=%s AND project_id=%s
                  AND issue_id=%s AND sequence=2""",
                (*SCOPE.key, issue.issue_id)).fetchone()
            assert event["event_type"] == ("resolved" if review_decision == "ACCEPT" else "returned")
            assert event["issue_version"] == 2
            assert event["actor"] == "fixture-reviewer"
            if review_decision == "ACCEPT":
                assert event["payload"]["resolutionRefs"] == [
                    resolution.resolution_refs[0].model_dump(mode="json", by_alias=True)]
                assert conn.execute("""SELECT count(*) AS n
                    FROM aip_production_contract_receipt
                    WHERE org_id=%s AND project_id=%s
                      AND operation='review_issue.resolve'
                      AND idempotency_key='content-p2g-original-accept'""",
                    SCOPE.key).fetchone()["n"] == 1
            else:
                assert event["payload"]["decisionHash"] == decision.decision_hash
                assert event["payload"]["stepRunId"] == decision.step_run_id
        review_command.update({
            "operation": "content.review",
            "artifactContentHash": review_command["artifactRef"]["contentHash"],
            "returnStage": None if review_decision == "ACCEPT" else "content_generation",
            "idempotencyKey": "content-p2g-original-review-receipt",
        })
        review_command["requestHash"] = _analysis_command_hash(review_command)
        service = ContentReviewHostService()
        with connect(SCOPE) as conn:
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
            binding = conn.execute("""SELECT installation_id,generation,execution_epoch,
                cutover_group_id,cutover_group_revision FROM extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_generate'""",
                SCOPE.key).fetchone()
            insert(conn, "extension_operation_dispatch_binding",
                operation_id="ecommerce_growth_content_review", handler_kind="extension",
                installation_id=binding["installation_id"], generation=binding["generation"],
                execution_epoch=binding["execution_epoch"], operation_fence=False,
                revision=6, cutover_group_id=binding["cutover_group_id"],
                cutover_group_revision=binding["cutover_group_revision"],
                updated_by="fixture")
            snapshot = EcommerceGrowthDispatchSnapshot(
                operation_id="ecommerce_growth_content_review", dispatch_revision=6,
                installation_id=binding["installation_id"], generation=binding["generation"],
                execution_epoch=binding["execution_epoch"],
                cutover_group_id=binding["cutover_group_id"],
                cutover_group_revision=binding["cutover_group_revision"],
                runtime_revision=1, checked_at=datetime.now(UTC))
            dispatch_ref = SimpleNamespace(org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                operation_id=snapshot.operation_id, dispatch_revision=snapshot.dispatch_revision,
                installation_id=snapshot.installation_id, generation=snapshot.generation,
                execution_epoch=snapshot.execution_epoch,
                cutover_group_id=snapshot.cutover_group_id,
                cutover_group_revision=snapshot.cutover_group_revision)
            service.revalidate(transaction=HostTransaction(conn), scope=SCOPE,
                dispatch=snapshot, command=review_command)
            review_receipt = service.execute(transaction=HostTransaction(conn), scope=SCOPE,
                dispatch_ref=dispatch_ref, command=review_command,
                checked_at=snapshot.checked_at, occurred_at=None)
            assert service.verify_receipt(transaction=HostTransaction(conn), scope=SCOPE,
                dispatch=snapshot, command=review_command,
                receipt=review_receipt) == review_receipt
        with connect(SCOPE) as conn:
            assert conn.execute("""SELECT count(*) AS n
                FROM ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_review'
                  AND idempotency_key='content-p2g-original-review-receipt'""",
                SCOPE.key).fetchone()["n"] == 1
            assert conn.execute("""SELECT count(*) AS n FROM ecommerce_growth_feedback_command
                WHERE org_id=%s AND project_id=%s AND review_receipt_ref=%s::jsonb""",
                (*SCOPE.key, json.dumps(review_receipt["receiptRef"]))).fetchone()["n"] == 1
        if review_decision == "RETURN":
            runtime_connect = lambda scope: _runtime_role_connection(connect, scope)
            worker = ContentReturnFeedbackWorker(
                connect=runtime_connect, connect_read=runtime_connect)
            with connect(SCOPE) as conn:
                feedback_id = conn.execute("""SELECT command_id
                    FROM ecommerce_growth_feedback_command WHERE org_id=%s AND project_id=%s
                      AND review_receipt_ref=%s::jsonb""",
                    (*SCOPE.key, json.dumps(review_receipt["receiptRef"]))).fetchone()["command_id"]
            with pytest.raises(Exception, match="feedback current origin could not be proven"):
                worker.run_one(SCOPE, feedback_id)
            with connect(SCOPE) as conn:
                for operation in (
                    "ecommerce_growth_investigation_describe", "ecommerce_growth_case_put",
                    "ecommerce_growth_schedule_put", "ecommerce_growth_schedule_trigger",
                    "ecommerce_growth_data_fulfill", "ecommerce_growth_analysis_advance",
                    "ecommerce_growth_review_advance",
                ):
                    insert(conn, "extension_operation_dispatch_binding",
                        operation_id=operation, handler_kind="extension",
                        installation_id=binding["installation_id"], generation=binding["generation"],
                        execution_epoch=binding["execution_epoch"], operation_fence=False,
                        revision=5, cutover_group_id=binding["cutover_group_id"],
                        cutover_group_revision=binding["cutover_group_revision"],
                        updated_by="fixture")
            with runtime_connect(SCOPE) as conn:
                target_id = conn.execute("""SELECT target_id FROM ecommerce_growth_feedback_segment
                    WHERE org_id=%s AND project_id=%s AND command_id=%s AND sequence=1""",
                    (*SCOPE.key, feedback_id)).fetchone()["target_id"]
                assert BoundContentReturnTarget(
                    HostTransaction(conn), SCOPE)._source(target_id, require_queued=True)[
                        "decision_id"] == decision.decision_id
            consumer = CurrentContentReturnConsumer(connect=runtime_connect, worker=worker)
            assert consumer.list_pending(SCOPE) == [feedback_id]
            other_scope = TenantScope("dev-org", "dev-project")
            with runtime_connect(SCOPE) as conn:
                with pytest.raises(Exception, match="unique durable return target unavailable"):
                    BoundContentReturnTarget(HostTransaction(conn), other_scope)._source(target_id)
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE extension_operation_dispatch_binding SET operation_fence=true
                    WHERE org_id=%s AND project_id=%s
                      AND operation_id='ecommerce_growth_content_review'""", SCOPE.key)
                conn.commit()
            try:
                assert consumer.list_pending(SCOPE) == []
                with pytest.raises(Exception):
                    worker.run_one(SCOPE, feedback_id)
            finally:
                with connect(SCOPE) as conn:
                    conn.execute("""UPDATE extension_operation_dispatch_binding SET operation_fence=false
                        WHERE org_id=%s AND project_id=%s
                          AND operation_id='ecommerce_growth_content_review'""", SCOPE.key)
                    conn.commit()
            with connect(SCOPE) as conn:
                conn.execute("SAVEPOINT return_decision_drift")
                with pytest.raises(Exception, match="AIP4_APPEND_ONLY"):
                    conn.execute("""UPDATE aip_return_decision SET decision_hash=%s
                        WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                        ("f" * 64, *SCOPE.key, decision.decision_id))
                conn.execute("ROLLBACK TO SAVEPOINT return_decision_drift")
            result = worker.run_one(SCOPE, feedback_id)
            assert result["status"] == "CONTENT_RETURN_ACKED"
            assert consumer.list_pending(SCOPE) == []
            assert worker.run_one(SCOPE, feedback_id)["status"] == "ALREADY_ACKED"
            with connect(SCOPE) as conn:
                checkpoint = conn.execute("""SELECT completed_sequence FROM ecommerce_growth_feedback_checkpoint
                    WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                    (*SCOPE.key, feedback_id)).fetchone()
                assert checkpoint["completed_sequence"] == 1
                segment = conn.execute("""SELECT state,attempt,target_receipt_ref
                    FROM ecommerce_growth_feedback_segment WHERE org_id=%s AND project_id=%s
                      AND command_id=%s AND sequence=1""",
                    (*SCOPE.key, feedback_id)).fetchone()
                assert segment["state"] == "acked" and segment["attempt"] == 1
                assert segment["target_receipt_ref"] == result["receiptRef"]
                assert conn.execute("""SELECT count(*) AS n FROM aip_step_run
                    WHERE org_id=%s AND project_id=%s AND run_id=%s
                      AND step_key='content_generate' AND attempt=2 AND status='queued'""",
                    (*SCOPE.key, proof["run_id"])).fetchone()["n"] == 1
            prior_brief_ref = consumed["artifact"]["briefRef"]
            original_brief = contracts.get_brief(SCOPE, prior_brief_ref["resourceId"])
            decision_ref = {"resourceType": "ReturnDecision",
                "resourceId": decision.decision_id, "revision": 1,
                "contentHash": "sha256:" + decision.decision_hash}
            artifact_source = {"resourceType": "Artifact",
                "resourceId": settled.artifact_id, "contentHash": settled.artifact_hash}
            revised_spec = {**original_brief.spec, "repair": {
                "returnDecisionRef": decision_ref, "priorArtifactRef": artifact_source,
                "humanReason": decision.reason}}
            revised = contracts.revise_brief(SCOPE, "fixture-reviewer",
                original_brief.brief_id, "content-p2g-original-repair-brief",
                ReviseBriefRequest(expectedVersion=original_brief.version,
                    briefType=original_brief.brief_type,
                    schemaRef=original_brief.schema_ref, spec=revised_spec))
            assert revised.revision == prior_brief_ref["revision"] + 1
            revised_ref = {"resourceType": "TaskBriefRevision",
                "resourceId": revised.brief_id, "revision": revised.revision,
                "contentHash": "sha256:" + revised.content_hash}
            with runtime_connect(SCOPE) as conn:
                require_repair_brief(conn, SCOPE, revised_ref, prior_brief_ref,
                    decision_ref, artifact_source, task_id=proof["task_id"],
                    reason=decision.reason)
                with pytest.raises(ValueError):
                    require_repair_brief(conn, SCOPE, prior_brief_ref, prior_brief_ref,
                        decision_ref, artifact_source, task_id=proof["task_id"],
                        reason=decision.reason)
            frozen = contracts.freeze_brief(SCOPE, "fixture-reviewer",
                revised.brief_id, revised.version, "content-p2g-original-freeze-repair-brief")
            assert frozen.revision == revised.revision + 1
            frozen_ref = {"resourceType": "TaskBriefRevision",
                "resourceId": frozen.brief_id, "revision": frozen.revision,
                "contentHash": "sha256:" + frozen.content_hash}
            with runtime_connect(SCOPE) as conn:
                require_frozen_repair_brief(conn, SCOPE, frozen_ref, prior_brief_ref,
                    decision_ref, artifact_source, task_id=proof["task_id"],
                    reason=decision.reason)
            task_store = AipTaskStore(connect)
            running_task = task_store.get_task(SCOPE, proof["task_id"])
            with connect(SCOPE) as conn:
                before_plans = conn.execute("""SELECT count(*) AS n FROM aip_plan_revision
                    WHERE org_id=%s AND project_id=%s AND task_id=%s""",
                    (*SCOPE.key, proof["task_id"])).fetchone()["n"]
            with pytest.raises(AipTaskTransitionBlocked, match="cannot create a plan"):
                task_store.create_plan(SCOPE, "fixture", proof["task_id"],
                    "content-p2g-repair-preview-plan-probe",
                    CreatePlanRevisionRequest(expectedTaskVersion=running_task.version,
                        steps=[PlanStep(stepKey="content_generate", title="Repair")],
                        risk={"productionContract": {
                            "productionContextRef": frozen_ref}}))
            with connect(SCOPE) as conn:
                assert conn.execute("""SELECT count(*) AS n FROM aip_plan_revision
                    WHERE org_id=%s AND project_id=%s AND task_id=%s""",
                    (*SCOPE.key, proof["task_id"])).fetchone()["n"] == before_plans
            with connect(SCOPE) as conn:
                conn.execute("""INSERT INTO meta_action_type
                    (id,name,object_type,parameters,required_markings,submission_criteria)
                    VALUES (%s,%s,%s,'[]','[]','[]')""",
                    ("ecommerce_growth_content_generate", "内部内容返工生成", "Task"))
            action_store = AipActionStore(connect_factory=connect)
            action_snapshot = action_store.action_type_snapshot(
                SCOPE, "ecommerce_growth_content_generate")
            repair_payload = {
                "returnDecisionRef": decision_ref, "briefRef": frozen_ref,
                "priorArtifactRef": artifact_source,
                "installationBindingRef": {
                    "installationId": str(binding["installation_id"]),
                    "generation": str(binding["generation"]),
                    "executionEpoch": binding["execution_epoch"],
                    "cutoverGroupId": str(binding["cutover_group_id"]),
                    "cutoverGroupRevision": binding["cutover_group_revision"],
                    "dispatchRevision": 5,
                },
                "capabilityRef": command["authorityRefs"]["capability"],
                "budgetUpperBoundMinor": command["upperBoundFen"],
            }
            proposal_request = CreateActionProposalRequest(
                actionTypeId="ecommerce_growth_content_generate",
                taskId=proof["task_id"], runId=proof["run_id"],
                purpose="人工退回后的新版内容生成", riskHint=ActionRiskLevel.R2,
                payload=repair_payload)
            risk = classify_action_risk(proposal_request.action_type_id,
                action_snapshot, repair_payload, proposal_request.risk_hint)
            proposed = action_store.create_proposal(SCOPE, "fixture-maker",
                "content-p2g-repair-action-proposal", proposal_request,
                action_snapshot, risk)
            assert proposed.proposal.action_binding_hash is not None
            decided = action_store.decide(SCOPE, "fixture-checker",
                proposed.proposal.id, "content-p2g-repair-action-approve",
                DecideActionProposalRequest(
                    expectedProposalVersion=proposed.proposal.version,
                    expectedProposalHash=proposed.proposal.proposal_hash,
                    decision=ApprovalDecision.APPROVED,
                    reason="隔离测试 checker 核对返工方案"), actor_roles=("admin",))
            assert decided.proposal.status.value == "approved"
            repair_command = deepcopy(command)
            repair_command["authorityRefs"]["brief"] = frozen_ref
            repair_command["returnDecisionRef"] = decision_ref
            repair_command["idempotencyKey"] = decision.attempt_idempotency_key
            repair_command["requestHash"] = _analysis_command_hash({
                key: value for key, value in repair_command.items()
                if key != "requestHash"})
            with runtime_connect(SCOPE) as conn:
                with pytest.raises(ValueError, match="fresh approval drifted"):
                    ContentGenerateHostService._return_authority(
                        HostTransaction(conn), SCOPE, repair_command,
                        _strict_content_generate_command(repair_command),
                        dispatch=SimpleNamespace(
                            operation_id="ecommerce_growth_content_generate",
                            installation_id=binding["installation_id"],
                            generation=binding["generation"],
                            execution_epoch=binding["execution_epoch"],
                            cutover_group_id=binding["cutover_group_id"],
                            cutover_group_revision=binding["cutover_group_revision"],
                            dispatch_revision=5, checked_at=datetime.now(UTC)))
            return
        with connect(SCOPE) as conn:
            review_proof = ContentReviewStepSource().read(
                conn, SCOPE, review_receipt["receiptRef"]["resourceId"])
            assert review_proof.run_id == proof["run_id"]
            assert review_proof.command == review_command
            conn.execute("SAVEPOINT review_dispatch_drift")
            conn.execute("""UPDATE extension_operation_dispatch_binding SET operation_fence=true
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_review'""", SCOPE.key)
            with pytest.raises(ContentReviewStepConflict, match="Receipt unavailable"):
                ContentReviewStepSource().read(conn, SCOPE, review_proof.receipt_id)
            conn.execute("ROLLBACK TO SAVEPOINT review_dispatch_drift")
            conn.execute("SAVEPOINT review_decision_drift")
            conn.execute("""UPDATE ecommerce_growth_runtime_command_receipt
                SET response=jsonb_set(response,'{decision}','\"RETURN\"'::jsonb)
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_review'
                  AND idempotency_key='content-p2g-original-review-receipt'""", SCOPE.key)
            with pytest.raises(ContentReviewStepConflict):
                ContentReviewStepSource().read(conn, SCOPE, review_proof.receipt_id)
            conn.execute("ROLLBACK TO SAVEPOINT review_decision_drift")
        terminal_owner = ContentReviewStepOwner(connect_read=connect, connect_write=connect)
        assert terminal_owner.list_pending(SCOPE) == [review_proof.receipt_id]
        with pytest.raises(Exception, match="scoped runtime dispatch lock required"):
            terminal_owner.run_one(SCOPE, review_proof.receipt_id)
        with connect(SCOPE) as conn:
            assert conn.execute("""SELECT count(*) AS n FROM aip_step_run WHERE
                org_id=%s AND project_id=%s AND run_id=%s AND step_key='content_review'""",
                (*SCOPE.key, review_proof.run_id)).fetchone()["n"] == 0
            for operation in (
                "ecommerce_growth_investigation_describe", "ecommerce_growth_case_put",
                "ecommerce_growth_schedule_put", "ecommerce_growth_schedule_trigger",
                "ecommerce_growth_data_fulfill", "ecommerce_growth_analysis_advance",
                "ecommerce_growth_review_advance",
            ):
                insert(conn, "extension_operation_dispatch_binding",
                    operation_id=operation, handler_kind="extension",
                    installation_id=binding["installation_id"], generation=binding["generation"],
                    execution_epoch=binding["execution_epoch"], operation_fence=False,
                    revision=5, cutover_group_id=binding["cutover_group_id"],
                    cutover_group_revision=binding["cutover_group_revision"],
                    updated_by="fixture")
        runtime_connect = lambda scope: _runtime_role_connection(connect, scope)
        runtime_owner = ContentReviewStepOwner(
            connect_read=runtime_connect, connect_write=runtime_connect)
        assert CurrentFeedbackConsumer(connect=runtime_connect).list_pending(SCOPE) == []
        natural_batch = runtime_owner.run_once(SCOPE)
        assert natural_batch == [{"receiptId": review_proof.receipt_id,
            "status": "CONTENT_REVIEW_RUN_SUCCEEDED"}]
        terminal = runtime_owner.run_one(SCOPE, review_proof.receipt_id)
        assert terminal["status"] == "CONTENT_REVIEW_RUN_SUCCEEDED"
        assert terminal["runId"] == proof["run_id"]
        assert runtime_owner.list_pending(SCOPE) == []
        assert runtime_owner.run_one(SCOPE, review_proof.receipt_id) == terminal
        with connect(SCOPE) as conn:
            with pytest.raises(Exception, match="attempt already exists"):
                terminal_owner._complete_transaction(conn, SCOPE, review_proof)
            assert conn.execute("""SELECT count(*) AS n FROM aip_step_run WHERE
                org_id=%s AND project_id=%s AND run_id=%s AND step_key='content_review'""",
                (*SCOPE.key, review_proof.run_id)).fetchone()["n"] == 1
        feedback_worker = DailyReviewFeedbackWorker(connect=runtime_connect)
        feedback_consumer = CurrentFeedbackConsumer(
            connect=runtime_connect, worker=feedback_worker)
        assert feedback_consumer.list_pending(SCOPE) == [review_proof.feedback_command_id]
        improvement_read_connections = []
        @contextmanager
        def improvement_independent_read(scope):
            improvement_read_connections.append(scope)
            with runtime_connect(scope) as read_conn:
                yield read_conn

        improvement_worker = ImprovementFeedbackWorker(
            connect=runtime_connect, connect_read=improvement_independent_read)
        improvement = CurrentImprovementConsumer(connect=runtime_connect,
            worker=improvement_worker)
        assert improvement.list_pending(SCOPE) == []
        with pytest.raises(Exception, match="pristine after daily review"):
            improvement_worker.run_one(SCOPE, review_proof.feedback_command_id)
        assert feedback_consumer.run_once(SCOPE) == [{
            "commandId": review_proof.feedback_command_id, "status": "DAILY_REVIEW_ACKED"}]
        assert feedback_consumer.list_pending(SCOPE) == []
        with connect(SCOPE) as conn:
            target = conn.execute("""SELECT target_id,command_id,receipt_ref,body,
                'sha256:'||encode(digest(convert_to(body::text,'UTF8'),'sha256'),'hex')
                  AS computed_hash
                FROM ecommerce_growth_daily_review_target WHERE org_id=%s AND project_id=%s""",
                SCOPE.key).fetchall()
            assert len(target) == 1
            assert target[0]["command_id"] == review_proof.feedback_command_id
            assert target[0]["receipt_ref"]["contentHash"] == target[0]["computed_hash"]
            assert target[0]["receipt_ref"]["resourceType"] == "DailyReviewReceipt"
            segments = conn.execute("""SELECT sequence,kind,state,attempt,target_receipt_ref
                FROM ecommerce_growth_feedback_segment WHERE org_id=%s AND project_id=%s
                  AND command_id=%s ORDER BY sequence""",
                (*SCOPE.key, review_proof.feedback_command_id)).fetchall()
            assert [(row["sequence"], row["state"], row["attempt"]) for row in segments] == [
                (1, "acked", 1), (2, "pending", 0), (3, "pending", 0)]
            assert segments[0]["target_receipt_ref"] == target[0]["receipt_ref"]
            assert segments[1]["target_receipt_ref"] is None
            assert segments[2]["target_receipt_ref"] is None
            checkpoint = conn.execute("""SELECT completed_sequence FROM
                ecommerce_growth_feedback_checkpoint WHERE org_id=%s AND project_id=%s
                  AND command_id=%s""", (*SCOPE.key, review_proof.feedback_command_id)).fetchone()
            assert checkpoint["completed_sequence"] == 1
        assert feedback_worker.run_one(SCOPE, review_proof.feedback_command_id)["status"] == "ALREADY_ACKED"
        with connect(SCOPE) as conn:
            assert conn.execute("""SELECT count(*) AS n FROM ecommerce_growth_daily_review_target
                WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*SCOPE.key, review_proof.feedback_command_id)).fetchone()["n"] == 1
        assert improvement.list_pending(SCOPE) == [review_proof.feedback_command_id]
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE extension_operation_dispatch_binding SET operation_fence=true
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_review'""", SCOPE.key)
            conn.commit()
        try:
            assert improvement.list_pending(SCOPE) == []
            with pytest.raises(Exception):
                improvement_worker.run_one(SCOPE, review_proof.feedback_command_id)
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE extension_operation_dispatch_binding SET operation_fence=false
                    WHERE org_id=%s AND project_id=%s
                      AND operation_id='ecommerce_growth_content_review'""", SCOPE.key)
                conn.commit()
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE aip_task_run SET status='running'
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*SCOPE.key, proof["run_id"]))
            conn.commit()
        try:
            assert improvement.list_pending(SCOPE) == []
            with pytest.raises(Exception):
                improvement_worker.run_one(SCOPE, review_proof.feedback_command_id)
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE aip_task_run SET status='succeeded'
                    WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                    (*SCOPE.key, proof["run_id"]))
                conn.commit()
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE ecommerce_growth_daily_review_target
                SET body=jsonb_set(body,'{effectStatus}','\"FALSELY_OBSERVED\"'::jsonb)
                WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*SCOPE.key, review_proof.feedback_command_id))
            conn.commit()
        try:
            with pytest.raises(Exception):
                improvement_worker.run_one(SCOPE, review_proof.feedback_command_id)
            with connect(SCOPE) as conn:
                assert conn.execute("""SELECT count(*) AS n
                    FROM ecommerce_growth_improvement_target WHERE org_id=%s AND project_id=%s""",
                    SCOPE.key).fetchone()["n"] == 0
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE ecommerce_growth_daily_review_target
                    SET body=jsonb_set(body,'{effectStatus}','\"AWAITING_OBSERVATION\"'::jsonb)
                    WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                    (*SCOPE.key, review_proof.feedback_command_id))
                conn.commit()
        assert improvement.run_once(SCOPE) == [{"commandId": review_proof.feedback_command_id,
            "status": "IMPROVEMENT_PENDING_ACKED"}]
        assert improvement_read_connections == [SCOPE]
        assert improvement.list_pending(SCOPE) == []
        with runtime_connect(SCOPE) as conn:
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
            assert conn.execute("""SELECT count(*) AS n FROM ecommerce_growth_improvement_target""").fetchone()["n"] == 0
        with connect(SCOPE) as conn:
            acl = conn.execute("""SELECT
                has_table_privilege('aos_runtime','public.ecommerce_growth_improvement_target','SELECT') AS can_read,
                has_table_privilege('aos_runtime','public.ecommerce_growth_improvement_target','INSERT') AS can_insert,
                has_table_privilege('aos_runtime','public.ecommerce_growth_improvement_target','UPDATE') AS can_update,
                has_function_privilege('aos_runtime',
                  'public.ecommerce_growth_improvement_put_a0v_106(text,text,uuid,bigint,jsonb,jsonb,jsonb,jsonb,jsonb,jsonb)',
                  'EXECUTE') AS can_put""").fetchone()
            acl_source = conn.execute("""SELECT pg_get_userbyid(c.relowner) AS owner,
                c.relacl::text AS acl, pg_has_role('aos_runtime',c.relowner,'USAGE') AS inherits_owner
                FROM pg_class c WHERE c.oid='public.ecommerce_growth_improvement_target'::regclass""").fetchone()
            assert acl == {"can_read": True, "can_insert": False,
                "can_update": False, "can_put": True}, acl_source
            daily_acl = conn.execute("""SELECT
                has_table_privilege('aos_runtime','public.ecommerce_growth_daily_review_target','SELECT') AS can_read,
                has_table_privilege('aos_runtime','public.ecommerce_growth_daily_review_target','INSERT') AS can_insert,
                has_table_privilege('aos_runtime','public.ecommerce_growth_daily_review_target','UPDATE') AS can_update""").fetchone()
            assert daily_acl == {"can_read": True, "can_insert": False, "can_update": False}
            target = conn.execute("""SELECT command_id,receipt_ref,body,
                'sha256:'||encode(digest(convert_to(body::text,'UTF8'),'sha256'),'hex') AS computed_hash
                FROM ecommerce_growth_improvement_target WHERE org_id=%s AND project_id=%s""",
                SCOPE.key).fetchall()
            assert len(target) == 1
            assert target[0]["command_id"] == review_proof.feedback_command_id
            assert target[0]["receipt_ref"]["contentHash"] == target[0]["computed_hash"]
            assert target[0]["body"]["effectStatus"] == "AWAITING_COMPARABLE_EVIDENCE"
            segments = conn.execute("""SELECT sequence,state,attempt,target_receipt_ref
                FROM ecommerce_growth_feedback_segment WHERE org_id=%s AND project_id=%s
                  AND command_id=%s ORDER BY sequence""",
                (*SCOPE.key, review_proof.feedback_command_id)).fetchall()
            assert [(row["sequence"], row["state"], row["attempt"]) for row in segments] == [
                (1, "acked", 1), (2, "acked", 1), (3, "pending", 0)]
            assert segments[1]["target_receipt_ref"] == target[0]["receipt_ref"]
            assert segments[2]["target_receipt_ref"] is None
            assert conn.execute("""SELECT completed_sequence FROM ecommerce_growth_feedback_checkpoint
                WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*SCOPE.key, review_proof.feedback_command_id)).fetchone()["completed_sequence"] == 2
        assert ImprovementFeedbackWorker(connect=runtime_connect).run_one(
            SCOPE, review_proof.feedback_command_id)["status"] == "ALREADY_ACKED"
        partial_feedback = EcommerceWorkshopFeedbackReadModel(connect=connect).read(SCOPE).items[0]
        assert [segment.state for segment in partial_feedback.segments] == [
            "acknowledged", "acknowledged", "pending"]
        assert partial_feedback.effect_status == "待观察"
        assert partial_feedback.candidate_status == "尚未形成"
        effect_subject = "content-effect-" + target[0]["receipt_ref"]["contentHash"][7:47]
        effect_request = CreateEffectReviewRequest(
            subject_id=effect_subject,
            subject_ref=ResourceRef(resource_type="ImprovementPendingReceipt",
                resource_id=target[0]["receipt_ref"]["resourceId"], revision="1",
                authority="ecommerce-growth"),
            observation_refs=[], metric_keys=[], sample_count=0, min_sample=1,
            cutoff_at=datetime.now(UTC), event_time_at=datetime.now(UTC) - timedelta(seconds=1),
            accepted=False, expected_revision=0,
            reason_code="content_accepted_effect_evidence_pending")
        with runtime_connect(SCOPE) as conn:
            effect = AipEffectReviewStore().create_review_in_transaction(
                SCOPE, effect_request, "ecommerce-effect-review", now=datetime.now(UTC),
                transaction=HostTransaction(conn))
            assert effect.accepted is False
            assert effect.effect_completed is False
            assert effect.maturity_status is EffectMaturityStatus.INSUFFICIENT
            conn.rollback()
        with connect(SCOPE) as conn:
            assert conn.execute("""SELECT count(*) AS n FROM aip_effect_review_revision
                WHERE org_id=%s AND project_id=%s AND subject_id=%s""",
                (*SCOPE.key, effect_subject)).fetchone()["n"] == 0
        effect_owner = EffectReviewOwner(connect=runtime_connect)
        effect_consumer = CurrentEffectReviewConsumer(connect=runtime_connect, owner=effect_owner)
        memory_worker = MemoryCandidateFeedbackWorker(connect=runtime_connect)
        with pytest.raises(Exception, match="formal effect review is missing"):
            memory_worker.run_one(SCOPE, review_proof.feedback_command_id)
        with connect(SCOPE) as conn:
            assert conn.execute("""SELECT count(*) AS n FROM aip_memory_candidate
                WHERE org_id=%s AND project_id=%s""", SCOPE.key).fetchone()["n"] == 0
        assert effect_consumer.list_pending(SCOPE) == [review_proof.feedback_command_id]
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE ecommerce_growth_improvement_target
                SET body=jsonb_set(body,'{effectStatus}','\"FALSELY_MATURE\"'::jsonb)
                WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*SCOPE.key, review_proof.feedback_command_id))
            conn.commit()
        try:
            with pytest.raises(Exception):
                effect_owner.run_one(SCOPE, review_proof.feedback_command_id)
            with connect(SCOPE) as conn:
                assert conn.execute("""SELECT count(*) AS n FROM aip_effect_review_revision
                    WHERE org_id=%s AND project_id=%s AND subject_id=%s""",
                    (*SCOPE.key, effect_subject)).fetchone()["n"] == 0
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE ecommerce_growth_improvement_target
                    SET body=jsonb_set(body,'{effectStatus}','\"AWAITING_COMPARABLE_EVIDENCE\"'::jsonb)
                    WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                    (*SCOPE.key, review_proof.feedback_command_id))
                conn.commit()
        assert effect_consumer.run_once(SCOPE) == [{"commandId": review_proof.feedback_command_id,
            "status": "EFFECT_REVIEW_INSUFFICIENT"}]
        assert effect_consumer.list_pending(SCOPE) == []
        with connect(SCOPE) as conn:
            rows = conn.execute("""SELECT subject_ref,accepted,effect_completed,
                maturity_status,sample_count,min_sample,reason_code
                FROM aip_effect_review_revision WHERE org_id=%s AND project_id=%s
                  AND subject_id=%s""", (*SCOPE.key, effect_subject)).fetchall()
            assert len(rows) == 1
            assert rows[0]["subject_ref"]["resourceId"] == target[0]["receipt_ref"]["resourceId"]
            assert rows[0]["accepted"] is False
            assert rows[0]["effect_completed"] is False
            assert rows[0]["maturity_status"] == "insufficient"
            assert rows[0]["sample_count"] == 0 and rows[0]["min_sample"] == 1
            assert rows[0]["reason_code"] == "content_accepted_effect_evidence_pending"
        assert effect_owner.run_one(SCOPE, review_proof.feedback_command_id)["status"] == "ALREADY_REVIEWED"
        reviewed_feedback = EcommerceWorkshopFeedbackReadModel(connect=connect).read(SCOPE).items[0]
        assert reviewed_feedback.effect_status == "证据不足"
        assert reviewed_feedback.candidate_status == "尚未形成"
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE aip_effect_review_revision SET accepted=true
                WHERE org_id=%s AND project_id=%s AND subject_id=%s""",
                (*SCOPE.key, effect_subject))
            conn.commit()
        try:
            with pytest.raises(Exception, match="lineage or maturity drifted"):
                effect_owner.run_one(SCOPE, review_proof.feedback_command_id)
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE aip_effect_review_revision SET accepted=false
                    WHERE org_id=%s AND project_id=%s AND subject_id=%s""",
                    (*SCOPE.key, effect_subject))
                conn.commit()
        memory_consumer = CurrentMemoryCandidateConsumer(
            connect=runtime_connect, worker=memory_worker)
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE aip_effect_review_revision SET accepted=true
                WHERE org_id=%s AND project_id=%s AND subject_id=%s""",
                (*SCOPE.key, effect_subject))
            conn.commit()
        try:
            assert memory_consumer.list_pending(SCOPE) == []
            with pytest.raises(Exception, match="lineage or maturity drifted"):
                memory_worker.run_one(SCOPE, review_proof.feedback_command_id)
            with connect(SCOPE) as conn:
                assert conn.execute("""SELECT count(*) AS n FROM aip_memory_candidate
                    WHERE org_id=%s AND project_id=%s""", SCOPE.key).fetchone()["n"] == 0
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE aip_effect_review_revision SET accepted=false
                    WHERE org_id=%s AND project_id=%s AND subject_id=%s""",
                    (*SCOPE.key, effect_subject))
                conn.commit()
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE extension_operation_dispatch_binding SET operation_fence=true
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_review'""", SCOPE.key)
            conn.commit()
        try:
            assert memory_consumer.list_pending(SCOPE) == []
            with pytest.raises(Exception):
                memory_worker.run_one(SCOPE, review_proof.feedback_command_id)
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE extension_operation_dispatch_binding SET operation_fence=false
                    WHERE org_id=%s AND project_id=%s
                      AND operation_id='ecommerce_growth_content_review'""", SCOPE.key)
                conn.commit()
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE aip_task_run SET status='running'
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*SCOPE.key, proof["run_id"]))
            conn.commit()
        try:
            with pytest.raises(Exception):
                memory_worker.run_one(SCOPE, review_proof.feedback_command_id)
            with connect(SCOPE) as conn:
                assert conn.execute("""SELECT count(*) AS n FROM aip_memory_candidate
                    WHERE org_id=%s AND project_id=%s""", SCOPE.key).fetchone()["n"] == 0
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE aip_task_run SET status='succeeded'
                    WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                    (*SCOPE.key, proof["run_id"]))
                conn.commit()
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE ecommerce_growth_improvement_target
                SET body=jsonb_set(body,'{effectStatus}','\"FALSELY_MATURE\"'::jsonb)
                WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*SCOPE.key, review_proof.feedback_command_id))
            conn.commit()
        try:
            with pytest.raises(Exception):
                memory_worker.run_one(SCOPE, review_proof.feedback_command_id)
            with connect(SCOPE) as conn:
                assert conn.execute("""SELECT count(*) AS n FROM aip_memory_candidate
                    WHERE org_id=%s AND project_id=%s""", SCOPE.key).fetchone()["n"] == 0
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE ecommerce_growth_improvement_target
                    SET body=jsonb_set(body,'{effectStatus}','\"AWAITING_COMPARABLE_EVIDENCE\"'::jsonb)
                    WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                    (*SCOPE.key, review_proof.feedback_command_id))
                conn.commit()
        with connect(SCOPE) as conn:
            pristine = conn.execute("""SELECT state,attempt,target_receipt_ref
                FROM ecommerce_growth_feedback_segment WHERE org_id=%s AND project_id=%s
                  AND command_id=%s AND sequence=3""",
                (*SCOPE.key, review_proof.feedback_command_id)).fetchone()
            assert pristine == {"state": "pending", "attempt": 0, "target_receipt_ref": None}
        assert memory_consumer.list_pending(SCOPE) == [review_proof.feedback_command_id]
        assert memory_consumer.run_once(SCOPE) == [{
            "commandId": review_proof.feedback_command_id,
            "status": "MEMORY_CANDIDATE_ACKED",
        }]
        assert memory_consumer.list_pending(SCOPE) == []
        with connect(SCOPE) as conn:
            rows = conn.execute("""SELECT candidate_id,status,memory_layer,scope,
                payload_ref,source_id,source_revision,markings
                FROM aip_memory_candidate WHERE org_id=%s AND project_id=%s""",
                SCOPE.key).fetchall()
            assert len(rows) == 1
            assert rows[0]["status"] == "pending"
            assert rows[0]["memory_layer"] == "episodic"
            assert rows[0]["scope"] == "workspace"
            assert "insufficient_evidence" in rows[0]["markings"]
            assert rows[0]["payload_ref"]["artifactId"] == settled.artifact_id
            assert rows[0]["payload_ref"]["contentHash"] == settled.artifact_hash
            assert conn.execute("""SELECT count(*) AS n FROM aip_memory_candidate_event
                WHERE org_id=%s AND project_id=%s AND candidate_id=%s""",
                (*SCOPE.key, rows[0]["candidate_id"])).fetchone()["n"] == 1
            assert conn.execute("""SELECT count(*) AS n FROM aip_memory_item
                WHERE org_id=%s AND project_id=%s""", SCOPE.key).fetchone()["n"] == 0
            source = conn.execute("""SELECT source_ref,content_hash FROM aip_memory_source_revision
                WHERE org_id=%s AND project_id=%s AND source_id=%s AND revision=%s""",
                (*SCOPE.key, rows[0]["source_id"], rows[0]["source_revision"])).fetchone()
            formal_review_id = conn.execute("""SELECT review_id FROM aip_effect_review_revision
                WHERE org_id=%s AND project_id=%s AND subject_id=%s AND revision=1""",
                (*SCOPE.key, effect_subject)).fetchone()["review_id"]
            assert source["source_ref"]["resourceId"] == formal_review_id
            assert len(source["content_hash"]) == 64
            segment = conn.execute("""SELECT state,attempt,target_receipt_ref FROM
                ecommerce_growth_feedback_segment WHERE org_id=%s AND project_id=%s
                  AND command_id=%s AND sequence=3""",
                (*SCOPE.key, review_proof.feedback_command_id)).fetchone()
            assert segment["state"] == "acked" and segment["attempt"] == 1
            assert segment["target_receipt_ref"]["resourceId"] == rows[0]["candidate_id"]
            assert conn.execute("""SELECT completed_sequence FROM ecommerce_growth_feedback_checkpoint
                WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*SCOPE.key, review_proof.feedback_command_id)).fetchone()["completed_sequence"] == 3
        assert memory_worker.run_one(SCOPE, review_proof.feedback_command_id)["status"] == "ALREADY_ACKED"
        with runtime_connect(SCOPE) as conn:
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
            assert conn.execute("SELECT count(*) AS n FROM aip_memory_candidate").fetchone()["n"] == 0
        feedback_view = EcommerceWorkshopFeedbackReadModel(connect=connect).read(SCOPE)
        assert feedback_view.tenant.org_id == SCOPE.org_id
        assert len(feedback_view.items) == 1
        item = feedback_view.items[0]
        assert item.effect_status == "证据不足"
        assert item.candidate_status == "待治理"
        assert [segment.state for segment in item.segments] == ["acknowledged"] * 3
        assert item.execution_authorized is False
        assert item.audit_details.effect_review_ref is not None
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE aip_task_run SET status='running'
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*SCOPE.key, proof["run_id"]))
            conn.commit()
        try:
            with pytest.raises(Exception):
                EcommerceWorkshopFeedbackReadModel(connect=connect).read(SCOPE)
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE aip_task_run SET status='succeeded'
                    WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                    (*SCOPE.key, proof["run_id"]))
                conn.commit()
        with connect(SCOPE) as conn:
            conn.execute("""UPDATE ecommerce_growth_improvement_target
                SET body=jsonb_set(body,'{effectStatus}','\"FALSELY_MATURE\"'::jsonb)
                WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*SCOPE.key, review_proof.feedback_command_id))
            conn.commit()
        try:
            with pytest.raises(Exception):
                EcommerceWorkshopFeedbackReadModel(connect=connect).read(SCOPE)
        finally:
            with connect(SCOPE) as conn:
                conn.execute("""UPDATE ecommerce_growth_improvement_target
                    SET body=jsonb_set(body,'{effectStatus}',
                    '\"AWAITING_COMPARABLE_EVIDENCE\"'::jsonb)
                    WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                    (*SCOPE.key, review_proof.feedback_command_id))
                conn.commit()
        @contextmanager
        def canary_connect(scope):
            assert scope == TenantScope("dev-org", "dev-project")
            with connect(SCOPE) as conn:
                conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
                yield conn

        assert EcommerceWorkshopFeedbackReadModel(connect=canary_connect).read(
            TenantScope("dev-org", "dev-project")).items == []
