"""Store-produced first Action and GE sources; missing binding still blocks reserve.

Disposable full-schema PG only. No Provider execution or live business authority.
"""
from uuid import uuid4

import pytest

from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.aip_budget_reservation_contracts import BudgetExactRef, ReserveBudgetRequest
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, BudgetReservationBlocked, canonical_hash
from aos_api.aip_contracts import ActionRiskLevel, PlanStep
from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect
from tests.aip.test_budget_configuration_runtime_pg import configured_pair
from tests.aip.test_budget_cost_consumer_pg import caller
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE


def test_first_action_uses_public_stores_but_unbound_approval_cannot_reserve(configured_pair):
    maker, basis, _, _, _, budget, price = configured_pair
    key = uuid4().hex
    tasks = AipTaskStore()
    task = tasks.create_task(SCOPE, maker.subject, key, CreateTaskRequest(
        type="analysis", title="Isolated first content approval"))
    plan = tasks.create_plan(SCOPE, maker.subject, task.id, key, CreatePlanRevisionRequest(
        expected_task_version=task.version,
        steps=[PlanStep(step_key="content_generate", title="Generate"),
               PlanStep(step_key="content_review", title="Review")],
        dependencies=[{"fromStepKey": "content_generate", "toStepKey": "content_review"}]))
    task = tasks.get_task(SCOPE, task.id)
    tasks.approve_plan(SCOPE, maker.subject, task.id, plan.revision, task.version, plan.content_hash)
    task = tasks.get_task(SCOPE, task.id)
    run = tasks.create_run(SCOPE, maker.subject, task.id, key, CreateTaskRunRequest(
        plan_revision_id=plan.id, expected_task_version=task.version))
    tasks.start_run(SCOPE, run.id, expected_run_version=run.version,
        expected_task_version=tasks.timeline(SCOPE, run.id).task.version,
        actor=maker.subject, idempotency_key=key)
    # Action metadata is a scoped test input, not a production registry claim.
    action = {"id": "ecommerce_growth_content_generate", "name": "content generate",
              "objectType": "Task", "parameters": [], "requiredMarkings": [],
              "submissionCriteria": [], "revisionHash": "a" * 64}
    request = CreateActionProposalRequest(action_type_id=action["id"], task_id=task.id,
        run_id=run.id, purpose="First generation cost approval", risk_hint=ActionRiskLevel.R2,
        payload={"budgetUpperBoundMinor": basis.basis.per_request_risk_minor})
    risk = classify_action_risk(action["id"], action, request.payload, request.risk_hint)
    actions = AipActionStore()
    proposed = actions.create_proposal(SCOPE, maker.subject, key, request, action, risk)
    assert actions.create_proposal(SCOPE, maker.subject, key, request, action, risk) == proposed
    decision = DecideActionProposalRequest(expected_proposal_version=proposed.proposal.version,
        expected_proposal_hash=proposed.proposal.proposal_hash, decision="approved")
    with pytest.raises(AipActionTransitionBlocked, match="maker cannot"):
        actions.decide(SCOPE, maker.subject, proposed.proposal.id, key + "-self", decision)
    approved = actions.decide(SCOPE, "isolated-content-checker", proposed.proposal.id, key, decision)
    assert approved.proposal.status.value == "approved"
    assert actions.decide(SCOPE, "isolated-content-checker", proposed.proposal.id, key, decision) == approved
    assert len(approved.approvals) == 1 and approved.proposal.action_binding_hash is None
    with connect(SCOPE) as conn:
        task_hash = conn.execute("SELECT request_hash FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s",
            (*SCOPE.key, task.id)).fetchone()["request_hash"]
        event = conn.execute("""SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,
            decision,actor_id,reason,expires_at,created_at,action_binding_hash
            FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s""",
            (*SCOPE.key, approved.approvals[0].id)).fetchone()
    reserve = ReserveBudgetRequest(operation_id=action["id"], invocation_key=key,
        task_ref=BudgetExactRef(resource_type="Task", resource_id=task.id, revision=1,
                               content_hash="sha256:" + task_hash),
        policy_ref=budget, pricing_ref=price,
        approval_ref=BudgetExactRef(resource_type="ActionApprovalEvent", resource_id=event["approval_event_id"],
            revision=event["proposal_version"], content_hash=canonical_hash(dict(event), prefixed=True)),
        upper_bound_minor=basis.basis.per_request_risk_minor)
    with pytest.raises(BudgetReservationBlocked, match="approval must bind this Task"):
        AipBudgetReservationStore().reserve(SCOPE, reserve, actor=maker.subject)
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_budget_reservation WHERE org_id=%s AND project_id=%s AND invocation_key=%s",
            (*SCOPE.key, key)).fetchone()["n"] == 0
