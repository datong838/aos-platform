from __future__ import annotations

import json
import uuid

import pytest

from aos_api.aip_action_models import (
    CreateActionProposalRequest,
    DecideActionProposalRequest,
)
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_contracts import ApprovalDecision
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractIdempotencyConflict,
)
from aos_api.aip_production_contracts import (
    ActionProposalExactRef,
    ExactRevisionRef,
    FreezeProductionContextRequest,
    ProductionStartDecisionStatus,
    ProductionStartRequest,
)
from aos_api.aip_production_start_service import AipProductionStartService
from aos_api.db import connect

from test_w2d_action_binding import _action_snapshot, _risk
from test_w2d_store import SCOPE, _seed


def _seed_start_candidate() -> tuple[ProductionStartRequest, AipActionStore]:
    preview_body, _ = _seed()
    contracts = AipProductionContractStore()
    preview = contracts.create_impact_preview(
        SCOPE,
        "maker:w2d-start",
        f"preview-{uuid.uuid4().hex}",
        preview_body,
    )
    preview = contracts.freeze_impact_preview(
        SCOPE,
        "maker:w2d-start",
        preview.preview_id,
        preview.version,
        f"freeze-{uuid.uuid4().hex}",
    )
    context = contracts.freeze_production_context(
        SCOPE,
        "maker:w2d-start",
        f"ctx-{uuid.uuid4().hex}",
        FreezeProductionContextRequest(
            task_id=preview_body.task_id,
            brief_ref=preview_body.brief_ref,
            evidence_bundle_ref=preview_body.evidence_bundle_ref,
            eval_contract_ref=preview_body.eval_contract_ref,
            responsibility_plan_ref=preview_body.responsibility_plan_ref,
        ),
    )
    preview_ref = ExactRevisionRef(
        resource_type="ImpactPreviewRevision",
        resource_id=preview.preview_id,
        revision=preview.revision,
        content_hash=preview.content_hash,
    )
    context_ref = ExactRevisionRef(
        resource_type="ProductionContextRevision",
        resource_id=context.context_id,
        revision=context.revision,
        content_hash=context.content_hash,
    )
    action_store = AipActionStore()
    action_id = f"send_w2d_start_{uuid.uuid4().hex}"
    proposal = action_store.create_proposal(
        SCOPE,
        "maker:w2d-start",
        f"proposal-{uuid.uuid4().hex}",
        CreateActionProposalRequest(
            action_type_id=action_id,
            task_id=preview_body.task_id,
            purpose="W2-D 组合门受控启动",
            impact_preview_ref=preview_ref,
        ),
        _action_snapshot(action_id),
        _risk(),
    ).proposal
    graph_id = f"logic-w2d-{uuid.uuid4().hex[:16]}"
    graph_hash = "7" * 64
    graph_snapshot = {
        "nodes": [{"id": "n1", "kind": "input"}],
        "edges": [],
    }
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_logic_graph
               (org_id,project_id,graph_id,name,status,revision,published_version,
                graph_hash,payload)
               VALUES(%s,%s,%s,'W2-D start','published',1,1,%s,%s::jsonb)""",
            (*SCOPE.key, graph_id, graph_hash, json.dumps(graph_snapshot)),
        )
        conn.execute(
            """INSERT INTO aip_logic_graph_revision
               (org_id,project_id,graph_id,revision,graph_hash,snapshot,actor)
               VALUES(%s,%s,%s,1,%s,%s::jsonb,'test:w2d')""",
            (*SCOPE.key, graph_id, graph_hash, json.dumps(graph_snapshot)),
        )
        task = conn.execute(
            """SELECT version FROM aip_task
               WHERE org_id=%s AND project_id=%s AND task_id=%s""",
            (*SCOPE.key, preview_body.task_id),
        ).fetchone()
        conn.commit()
    return (
        ProductionStartRequest(
            task_id=preview_body.task_id,
            expected_task_version=int(task["version"]),
            production_context_ref=context_ref,
            plan_ref=preview_body.plan_ref,
            preview_ref=preview_ref,
            action_proposal_ref=ActionProposalExactRef(
                proposal_id=proposal.id,
                version=proposal.version,
                proposal_hash=proposal.proposal_hash,
            ),
            logic_graph_id=graph_id,
            logic_revision=1,
            logic_graph_hash=graph_hash,
        ),
        action_store,
    )


def _runtime_counts(task_id: str) -> tuple[int, int]:
    with connect(SCOPE) as conn:
        task_runs = conn.execute(
            """SELECT COUNT(*) AS n FROM aip_task_run
               WHERE org_id=%s AND project_id=%s AND task_id=%s""",
            (*SCOPE.key, task_id),
        ).fetchone()["n"]
        agent_runs = conn.execute(
            """SELECT COUNT(*) AS n FROM aip_agent_run
               WHERE org_id=%s AND project_id=%s AND task_id=%s""",
            (*SCOPE.key, task_id),
        ).fetchone()["n"]
    return int(task_runs), int(agent_runs)


def test_blocked_start_is_append_only_and_has_zero_runtime_side_effects() -> None:
    request, _ = _seed_start_candidate()
    before = _runtime_counts(request.task_id)
    decision = AipProductionStartService().start(
        SCOPE, "approver:w2d", f"blocked-{uuid.uuid4().hex}", request
    )
    assert decision.status is ProductionStartDecisionStatus.BLOCKED
    assert {item.code for item in decision.blockers} == {
        "ACTION_PROPOSAL_NOT_APPROVED",
        "ACTION_APPROVAL_QUORUM_LOST",
    }
    assert decision.task_run_ref is None
    assert _runtime_counts(request.task_id) == before
    with connect(SCOPE) as conn:
        plan = conn.execute(
            """SELECT approval_status FROM aip_plan_revision
               WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
            (*SCOPE.key, request.plan_ref.resource_id),
        ).fetchone()
    assert plan["approval_status"] == "draft"


def test_ready_start_atomically_creates_one_canonical_task_run_and_replays() -> None:
    request, action_store = _seed_start_candidate()
    proposal = action_store.decide(
        SCOPE,
        "checker:w2d-start",
        request.action_proposal_ref.proposal_id,
        f"approval-{uuid.uuid4().hex}",
        DecideActionProposalRequest(
            expected_proposal_version=request.action_proposal_ref.version,
            expected_proposal_hash=request.action_proposal_ref.proposal_hash,
            decision=ApprovalDecision.APPROVED,
        ),
    ).proposal
    request = request.model_copy(
        update={
            "action_proposal_ref": ActionProposalExactRef(
                proposal_id=proposal.id,
                version=proposal.version,
                proposal_hash=proposal.proposal_hash,
            )
        }
    )
    key = f"start-{uuid.uuid4().hex}"
    service = AipProductionStartService()
    started = service.start(SCOPE, "approver:w2d", key, request)
    replay = service.start(SCOPE, "approver:w2d", key, request)
    assert started.status is ProductionStartDecisionStatus.STARTED
    assert replay.decision_id == started.decision_id
    assert replay.task_run_ref == started.task_run_ref
    assert _runtime_counts(request.task_id) == (1, 0)
    with connect(SCOPE) as conn:
        plan = conn.execute(
            """SELECT approval_status FROM aip_plan_revision
               WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
            (*SCOPE.key, request.plan_ref.resource_id),
        ).fetchone()
    assert plan["approval_status"] == "approved"
    drifted = request.model_copy(
        update={"expected_task_version": request.expected_task_version + 1}
    )
    with pytest.raises(ProductionContractIdempotencyConflict):
        service.start(SCOPE, "approver:w2d", key, drifted)


def test_empty_or_mismatched_logic_blocks_start_without_runtime() -> None:
    request, _ = _seed_start_candidate()
    empty_hash = "8" * 64
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_logic_graph_revision
               SET snapshot=%s::jsonb, graph_hash=%s
               WHERE org_id=%s AND project_id=%s AND graph_id=%s AND revision=%s""",
            (
                json.dumps({"nodes": [], "edges": []}),
                empty_hash,
                *SCOPE.key,
                request.logic_graph_id,
                request.logic_revision,
            ),
        )
        conn.execute(
            """UPDATE aip_logic_graph
               SET graph_hash=%s
               WHERE org_id=%s AND project_id=%s AND graph_id=%s""",
            (empty_hash, *SCOPE.key, request.logic_graph_id),
        )
        conn.commit()
    before = _runtime_counts(request.task_id)
    empty_decision = AipProductionStartService().start(
        SCOPE,
        "approver:w2d",
        f"empty-{uuid.uuid4().hex}",
        request.model_copy(update={"logic_graph_hash": empty_hash}),
    )
    assert empty_decision.status is ProductionStartDecisionStatus.BLOCKED
    assert "LOGIC_GRAPH_EMPTY" in {item.code for item in empty_decision.blockers}
    assert empty_decision.task_run_ref is None
    mismatch = AipProductionStartService().start(
        SCOPE,
        "approver:w2d",
        f"hash-{uuid.uuid4().hex}",
        request.model_copy(update={"logic_graph_hash": "9" * 64}),
    )
    assert mismatch.status is ProductionStartDecisionStatus.BLOCKED
    assert "LOGIC_GRAPH_HASH_MISMATCH" in {item.code for item in mismatch.blockers}
    assert _runtime_counts(request.task_id) == before


def test_action_binding_hash_mismatch_blocks_start_without_runtime() -> None:
    request, action_store = _seed_start_candidate()
    proposal = action_store.decide(
        SCOPE,
        "checker:w2d-start",
        request.action_proposal_ref.proposal_id,
        f"approval-{uuid.uuid4().hex}",
        DecideActionProposalRequest(
            expected_proposal_version=request.action_proposal_ref.version,
            expected_proposal_hash=request.action_proposal_ref.proposal_hash,
            decision=ApprovalDecision.APPROVED,
        ),
    ).proposal
    request = request.model_copy(
        update={
            "action_proposal_ref": ActionProposalExactRef(
                proposal_id=proposal.id,
                version=proposal.version,
                proposal_hash=proposal.proposal_hash,
            )
        }
    )
    with connect(SCOPE) as conn:
        draft = conn.execute(
            """SELECT snapshot FROM aip_action_draft
               WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*SCOPE.key, proposal.id),
        ).fetchone()
        snapshot = draft["snapshot"]
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        snapshot["actionBindingHash"] = "a" * 64
        conn.execute(
            """UPDATE aip_action_draft SET snapshot=%s::jsonb
               WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (json.dumps(snapshot), *SCOPE.key, proposal.id),
        )
        conn.commit()
    before = _runtime_counts(request.task_id)
    decision = AipProductionStartService().start(
        SCOPE, "approver:w2d", f"bind-hash-{uuid.uuid4().hex}", request
    )
    assert decision.status is ProductionStartDecisionStatus.BLOCKED
    assert "ACTION_BINDING_HASH_MISMATCH" in {item.code for item in decision.blockers}
    assert decision.task_run_ref is None
    assert _runtime_counts(request.task_id) == before
