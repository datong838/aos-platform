"""Real Action persistence/current ACL with a substituted source preparation.

This proves the binding composition, NOT a natural current-source business chain.
No approval row or binding hash is inserted by the fixture.
"""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
from aos_api.ecommerce_growth_host_ports import HostTransaction
import aos_api.ecommerce_content_first_action_binding as binding
from aos_api.openfga import user_key, marking_key
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner
from tests.aip.test_network_consumer_signed_https_pg import https_signer


@pytest.fixture
def prepared(monkeypatch):
    key = uuid4().hex
    maker, checker = "content-maker-" + key, "content-checker-" + key
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_org(id,name) VALUES(%s,'isolated org') ON CONFLICT DO NOTHING", (SCOPE.org_id,))
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES(%s,%s,'isolated workspace') ON CONFLICT DO NOTHING", SCOPE.key)
        old_object = conn.execute("SELECT * FROM meta_object_type WHERE id='Task'").fetchone()
        old_action = conn.execute("SELECT * FROM meta_action_type WHERE id=%s", (binding.ACTION,)).fetchone()
        conn.execute("""INSERT INTO meta_object_type(id,name,published,properties,required_markings)
            VALUES('Task','Task',true,'[]','[]') ON CONFLICT(id) DO UPDATE SET published=true""")
        conn.execute("""INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria)
            VALUES(%s,'Content','Task','[]','[]','[]') ON CONFLICT(id) DO UPDATE
            SET name='Content',object_type='Task',parameters='[]',required_markings='[]',submission_criteria='[]'""",
            (binding.ACTION,))
        for actor, role in [(maker, "member"), (checker, "approver")]:
            conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s)",
                         (*SCOPE.key, actor, role))
            conn.execute("""INSERT INTO authz_tuple(org_id,project_id,user_key,relation,object_key)
                VALUES(%s,%s,%s,'bearer',%s) ON CONFLICT DO NOTHING""",
                (*SCOPE.key, user_key(actor), marking_key("internal")))
        conn.commit()
    tasks = AipTaskStore()
    task = tasks.create_task(SCOPE, maker, key, CreateTaskRequest(type="analysis", title="Isolated binding"))
    plan = tasks.create_plan(SCOPE, maker, task.id, key, CreatePlanRevisionRequest(
        expected_task_version=task.version, steps=[PlanStep(step_key="content_generate", title="Content")]))
    task = tasks.get_task(SCOPE, task.id)
    tasks.approve_plan(SCOPE, maker, task.id, plan.revision, task.version, plan.content_hash)
    run = tasks.create_run(SCOPE, maker, task.id, key, CreateTaskRunRequest(
        plan_revision_id=plan.id, expected_task_version=tasks.get_task(SCOPE, task.id).version))
    now = datetime.now(timezone.utc)
    sources = SimpleNamespace(task_ref=BudgetExactRef(resourceType="Task", resourceId=task.id,
        revision=1, contentHash="sha256:" + "a" * 64), snapshot=SimpleNamespace(checked_at=now),
        action_context=SimpleNamespace(request=SimpleNamespace(task_run_ref=SimpleNamespace(resource_id=run.id)),
            capacity={"expires_at": now + timedelta(minutes=3)},
            budget_policy=SimpleNamespace(effective_until=now + timedelta(hours=1))),
        quota=SimpleNamespace(effective_until=now + timedelta(hours=1), max_input_tokens=100, max_output_tokens=100),
        price=SimpleNamespace(development_cost_authorization=None, input_token_price=1,
                              output_token_price=1, token_unit=1000), cost_context={})
    # These two source substitutes are explicit. Identity, metadata, marking,
    # risk, amount, binding, Store SQL, maker/checker and replay run unchanged.
    envelope = {"isolatedSource": key}
    monkeypatch.setattr(ContentBudgetCommandOwner, "_prepare_sources", classmethod(lambda *a, **kw: sources))
    monkeypatch.setattr(binding, "source_envelope", lambda *a: dict(envelope))
    principal = lambda actor: Principal(actor, *SCOPE.key, token_kind="oidc")
    with connect(SCOPE) as conn:
        snapshot = binding._metadata(conn)
        body = binding._request(HostTransaction(conn), SCOPE, key, 500, now + timedelta(minutes=2), sources)
    store = AipActionStore(first_content_guard=binding.FirstContentActionGuard(principal(maker)))
    checker_store = AipActionStore(first_content_guard=binding.FirstContentActionGuard(principal(checker)))
    risk = classify_action_risk(binding.ACTION, snapshot, body.payload, None)
    try:
        yield SimpleNamespace(key=key, maker=maker, checker=checker, body=body, snapshot=snapshot,
            risk=risk, store=store, checker_store=checker_store, sources=sources, envelope=envelope)
    finally:
        # Restore only shared metadata touched in this disposable database.
        with isolated_owner() as conn:
            if old_action:
                conn.execute("""UPDATE meta_action_type SET name=%s,object_type=%s,parameters=%s::jsonb,
                    required_markings=%s::jsonb,submission_criteria=%s::jsonb WHERE id=%s""",
                    (old_action["name"], old_action["object_type"], json.dumps(old_action["parameters"]),
                     json.dumps(old_action["required_markings"]), json.dumps(old_action["submission_criteria"]), binding.ACTION))
            else:
                conn.execute("DELETE FROM meta_action_type WHERE id=%s", (binding.ACTION,))
            if old_object:
                conn.execute("UPDATE meta_object_type SET published=%s WHERE id='Task'", (old_object["published"],))
            conn.commit()


def _propose(p, **changes):
    body = p.body.model_copy(update=changes) if changes else p.body
    return p.store.create_proposal(SCOPE, p.maker, p.key, body, p.snapshot, p.risk)


def test_real_draft_approval_binding_and_replay(prepared):
    p = prepared
    proposal = _propose(p)
    assert _propose(p) == proposal
    assert proposal.proposal.action_binding_hash
    decision = DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash, decision="approved")
    with pytest.raises(AipActionTransitionBlocked, match="INDEPENDENT_CHECKER"):
        p.store.decide(SCOPE, p.maker, proposal.proposal.id, p.key + "-self", decision)
    with pytest.raises(AipActionTransitionBlocked, match="PRODUCER_REQUIRED"):
        AipActionStore().decide(SCOPE, p.checker, proposal.proposal.id, p.key, decision)
    approved = p.checker_store.decide(SCOPE, p.checker, proposal.proposal.id, p.key, decision)
    assert approved.proposal.status.value == "approved" and len(approved.approvals) == 1
    assert approved.approvals[0].action_binding_hash == proposal.proposal.action_binding_hash
    assert p.checker_store.decide(SCOPE, p.checker, proposal.proposal.id, p.key, decision) == approved
    with connect(SCOPE) as conn:
        event = conn.execute("SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s",
            (*SCOPE.key, approved.approvals[0].id)).fetchone()
        binding.revalidate_first_content_approval(HostTransaction(conn), SCOPE, event, p.sources, p.key)
        # Even a Store-produced binding cannot bypass the natural intent gate
        # through the generic budget API. No natural intent was manufactured.
        from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, BudgetReservationBlocked, canonical_hash
        event_fields = {k: event[k] for k in ("approval_event_id", "proposal_id", "proposal_version",
            "proposal_hash", "decision", "actor_id", "reason", "expires_at", "created_at", "action_binding_hash")}
        approval_ref = BudgetExactRef(resourceType="ActionApprovalEvent", resourceId=event["approval_event_id"],
            revision=event["proposal_version"], contentHash=canonical_hash(event_fields, prefixed=True))
        with pytest.raises(BudgetReservationBlocked, match="first content current source"):
            AipBudgetReservationStore()._approval_authority(conn, SCOPE, approval_ref,
                datetime.now(timezone.utc), task_ref=p.sources.task_ref,
                operation_id=binding.ACTION, upper_bound_minor=500)
        p.envelope["isolatedSource"] = "changed"
        with pytest.raises(AipActionTransitionBlocked, match="BINDING_DRIFTED"):
            binding.revalidate_first_content_approval(HostTransaction(conn), SCOPE, event, p.sources, p.key)


@pytest.mark.parametrize("drift", ["source", "member", "marking", "metadata", "expiry", "amount"])
def test_drift_prevents_new_approval_and_replay(prepared, drift):
    p = prepared
    proposal = _propose(p)
    if drift == "source": p.envelope["isolatedSource"] = "changed"
    elif drift == "expiry": p.sources.snapshot.checked_at = p.body.expires_at + timedelta(seconds=1)
    elif drift == "amount": p.sources.price.input_token_price = 100000
    else:
        with isolated_owner() as conn:
            if drift == "member":
                conn.execute("UPDATE meta_membership SET role='member' WHERE org_id=%s AND project_id=%s AND subject=%s",
                             (*SCOPE.key, p.checker))
            elif drift == "marking":
                conn.execute("DELETE FROM authz_tuple WHERE org_id=%s AND project_id=%s AND user_key=%s",
                             (*SCOPE.key, user_key(p.checker)))
            else:
                conn.execute("UPDATE meta_action_type SET name='Changed' WHERE id=%s", (binding.ACTION,))
            conn.commit()
    decision = DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash, decision="approved")
    with pytest.raises((AipActionTransitionBlocked, ValueError)):
        p.checker_store.decide(SCOPE, p.checker, proposal.proposal.id, p.key, decision)
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                            (*SCOPE.key, proposal.proposal.id)).fetchone()["n"] == 0


def test_request_tampering_is_rejected_before_proposal_insert(prepared):
    p = prepared
    payload = {**p.body.payload, "firstContentSources": {"isolatedSource": "forged"}}
    with pytest.raises(AipActionTransitionBlocked, match="REQUEST_OR_RISK"):
        _propose(p, payload=payload)
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                            (*SCOPE.key, p.key)).fetchone()["n"] == 0


def test_signed_identity_is_reverified_and_cross_scope_rejected(https_signer):
    sign, fetched = https_signer
    principal = binding._identity(SCOPE, "Bearer " + sign("isolated-content-maker"))
    assert principal.subject == "isolated-content-maker" and principal.token_kind == "oidc"
    assert fetched
    with pytest.raises(AipActionTransitionBlocked, match="EXTERNAL_IDENTITY_REQUIRED"):
        binding._identity(SCOPE, "Bearer " + sign("isolated-content-maker", changes={"org_id": "dev-org"}))
    with pytest.raises(AipActionTransitionBlocked, match="EXTERNAL_IDENTITY_REQUIRED"):
        binding._identity(SCOPE, "Bearer " + sign("isolated-content-maker", wrong_key=True))


@pytest.mark.parametrize("drift", ["budget", "price", "invocation"])
def test_generic_budget_checks_exact_source_pair_and_natural_key(prepared, monkeypatch, drift):
    p = prepared
    proposed = _propose(p)
    approved = p.checker_store.decide(SCOPE, p.checker, proposed.proposal.id, p.key,
        DecideActionProposalRequest(expectedProposalVersion=proposed.proposal.version,
            expectedProposalHash=proposed.proposal.proposal_hash, decision="approved"))
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, BudgetReservationBlocked, canonical_hash
    budget = BudgetExactRef(resourceType="BudgetRevision", resourceId="test-budget", revision=1, contentHash="sha256:" + "b" * 64)
    price = BudgetExactRef(resourceType="ModelPriceSnapshotRevision", resourceId="test-price", revision=1, contentHash="sha256:" + "c" * 64)
    # Test only the final pair/key comparison after source admission. This does
    # not grant a real source or call reserve/produce a held reservation.
    admitted = SimpleNamespace(authorities={"budget": budget.model_dump(mode="json", by_alias=True),
                                            "pricing": price.model_dump(mode="json", by_alias=True)})
    monkeypatch.setattr(binding, "require_first_content_budget_source", lambda *a: admitted)
    with connect(SCOPE) as conn:
        event = conn.execute("""SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
            actor_id,reason,expires_at,created_at,action_binding_hash FROM aip_action_approval_event
            WHERE org_id=%s AND project_id=%s AND approval_event_id=%s""",
            (*SCOPE.key, approved.approvals[0].id)).fetchone()
        ref = BudgetExactRef(resourceType="ActionApprovalEvent", resourceId=event["approval_event_id"],
            revision=event["proposal_version"], contentHash=canonical_hash(dict(event), prefixed=True))
        args = dict(task_ref=p.sources.task_ref, operation_id=binding.ACTION, upper_bound_minor=500,
                    policy_ref=budget, pricing_ref=price, invocation_key=p.key)
        store = AipBudgetReservationStore()
        store._approval_authority(conn, SCOPE, ref, datetime.now(timezone.utc), **args)
        if drift == "budget": args["policy_ref"] = budget.model_copy(update={"resource_id": "other"})
        elif drift == "price": args["pricing_ref"] = price.model_copy(update={"resource_id": "other"})
        else: args["invocation_key"] = "other"
        with pytest.raises(BudgetReservationBlocked, match="current source authority"):
            store._approval_authority(conn, SCOPE, ref, datetime.now(timezone.utc), **args)
