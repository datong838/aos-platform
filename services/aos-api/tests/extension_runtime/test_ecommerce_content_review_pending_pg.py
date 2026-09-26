"""Full-migration, disposable-DB composition for a content review candidate.

Each assertion below is only a staged subproof; no test Provider is a live call.
"""

from datetime import UTC, datetime, timedelta

from aos_api.aip_budget_reservation_contracts import BudgetExactRef, ReserveBudgetRequest
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, canonical_hash
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from test_ecommerce_analyst_growth_plan_full_graph import SCOPE, disposable_database, insert
from test_ecommerce_analyst_method_authority import apply_migrations


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


def test_original_content_run_can_hold_formal_budget_in_one_full_database():
    with disposable_database() as connect:
        apply_migrations(connect)
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
