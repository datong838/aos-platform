"""Full-migration, disposable-DB composition for a content review candidate.

Each assertion below is only a staged subproof; no test Provider is a live call.
"""

from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_reservation_contracts import BudgetExactRef, ReserveBudgetRequest
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, canonical_hash
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.ecommerce_content_execution_journal import (
    ContentExecutionConflict, ContentExecutionJournal, _payload,
)
from aos_api.ecommerce_content_review_pending import (
    ContentReviewPendingBlocked, ContentReviewPendingReader,
)
from aos_api.ecommerce_content_execution_composition import CurrentContentPreparation
from aos_api.ecommerce_content_execution_composition import CurrentContentStatusReader
from aos_api.ecommerce_content_execution_worker import ContentExecutionWorker, PreparedContentInvocation
from aos_api.ecommerce_content_result_consumer import ContentResultConsumer
from aos_api.ecommerce_content_step_owner import (
    ContentGenerationStepOwner, ContentGenerationStepSource, ContentStepConflict,
)
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthDispatchSnapshot, HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
from aos_api.ecommerce_growth_runtime_store import BoundEcommerceGrowthRuntimeStore
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
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "a0v_105"
        assert conn.execute("SELECT to_regprocedure(%s) AS procedure",
            ("public.extension_dispatch_lock_group_a0v_028(uuid)",)).fetchone()["procedure"] is not None


def _seed_original_run_and_budget(connect):
    """Seed only external authorities in the owned clone; use public Task/Budget APIs."""
    now = datetime.now(UTC)
    store = AipTaskStore(connect)
    task = store.create_task(SCOPE, "fixture", "content-p2g-task", CreateTaskRequest(
        type="analysis", title="Content review composition"))
    plan = store.create_plan(SCOPE, "fixture", task.id, "content-p2g-plan",
        CreatePlanRevisionRequest(expected_task_version=task.version, steps=[
            PlanStep(step_key="content_generate", title="Generate"),
            PlanStep(step_key="content_review", title="Review"),
        ]))
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
        insert(conn, "aip_budget_head", budget_id="content-p2g-budget", current_revision=1)
        insert(conn, "aip_budget_revision", budget_id="content-p2g-budget", revision=1,
            content_hash=budget_hash, lifecycle="active", environment="development",
            currency="CNY", daily_limit_minor=500, monthly_limit_minor=900,
            alert_threshold_pct=80, hard_stop=True, unknown_usage_behavior="block",
            effective_from=now - timedelta(days=1), effective_until=now + timedelta(days=7),
            owner="fixture", over_budget_approver="reviewer", payload={}, created_by="fixture")
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


def _seed_current_command_receipt(connect, proof):
    """Only an isolated installation; use the formal immutable Receipt owner."""
    fixture_path = Path(__file__).resolve().parents[1] / "aip/test_aip_budget_reservation_pg.py"
    spec = importlib.util.spec_from_file_location("content_budget_command_fixture", fixture_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    command = module.content_generate_command(proof["request"])
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
