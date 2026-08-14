from __future__ import annotations

import uuid

import pytest

from aos_api.aip_action_models import (
    AcquireExecutionLeaseRequest,
    CreateActionProposalRequest,
    DecideActionProposalRequest,
)
from aos_api.aip_action_adapters import ACTION_ADAPTERS
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_policy import RiskDecision
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.aip_contracts import ActionRiskLevel, ApprovalDecision
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.auth import Principal
from aos_api.db import connect

from test_w2d_store import SCOPE, _seed


def _risk() -> RiskDecision:
    return RiskDecision(
        level=ActionRiskLevel.R2,
        floor=ActionRiskLevel.R2,
        reasons=("single_external_effect",),
        approval_policy={
            "makerChecker": True,
            "minimumApprovals": 1,
            "executionAllowed": True,
            "draftOnly": False,
        },
    )


def _action_snapshot(action_id: str) -> dict[str, object]:
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO meta_action_type
               (id,name,object_type,parameters,required_markings,submission_criteria)
               VALUES (%s,'W2-D 受控启动通知','WorkOrder','[]'::jsonb,'[]'::jsonb,'[]'::jsonb)""",
            (action_id,),
        )
        conn.commit()
    return AipActionStore().action_type_snapshot(SCOPE, action_id)


def _frozen_preview() -> tuple[ExactRevisionRef, str, str]:
    request, instance_id = _seed()
    preview = AipProductionContractStore().create_impact_preview(
        SCOPE,
        "test:w2d-action",
        f"preview-{uuid.uuid4().hex}",
        request,
    )
    frozen = AipProductionContractStore().freeze_impact_preview(
        SCOPE,
        "test:w2d-action",
        preview.preview_id,
        preview.version,
        f"freeze-{uuid.uuid4().hex}",
    )
    return (
        ExactRevisionRef(
            resource_type="ImpactPreviewRevision",
            resource_id=frozen.preview_id,
            revision=frozen.revision,
            content_hash=frozen.content_hash,
        ),
        request.task_id,
        instance_id,
    )


def test_proposal_hash_and_snapshot_bind_exact_impact_preview() -> None:
    preview_ref, task_id, _ = _frozen_preview()
    action_id = f"send_w2d_{uuid.uuid4().hex}"
    store = AipActionStore()
    body = CreateActionProposalRequest(
        action_type_id=action_id,
        task_id=task_id,
        purpose="绑定冻结影响预览",
        payload={"message": "受控启动"},
        impact_preview_ref=preview_ref,
    )
    bundle = store.create_proposal(
        SCOPE,
        "maker:w2d",
        f"proposal-{uuid.uuid4().hex}",
        body,
        _action_snapshot(action_id),
        _risk(),
    )
    assert bundle.proposal.impact_preview_ref == preview_ref
    with connect(SCOPE) as conn:
        row = conn.execute(
            """SELECT impact_preview_id,impact_preview_revision,impact_preview_hash
               FROM aip_action_proposal
               WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*SCOPE.key, bundle.proposal.id),
        ).fetchone()
    assert dict(row) == {
        "impact_preview_id": preview_ref.resource_id,
        "impact_preview_revision": preview_ref.revision,
        "impact_preview_hash": preview_ref.content_hash,
    }


def test_preview_binding_drift_blocks_approval() -> None:
    preview_ref, task_id, instance_id = _frozen_preview()
    action_id = f"send_w2d_{uuid.uuid4().hex}"
    store = AipActionStore()
    proposal = store.create_proposal(
        SCOPE,
        "maker:w2d",
        f"proposal-{uuid.uuid4().hex}",
        CreateActionProposalRequest(
            action_type_id=action_id,
            task_id=task_id,
            purpose="漂移后必须失败关闭",
            impact_preview_ref=preview_ref,
        ),
        _action_snapshot(action_id),
        _risk(),
    ).proposal
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_agent_instance SET version=version+1
               WHERE org_id=%s AND project_id=%s AND instance_id=%s""",
            (*SCOPE.key, instance_id),
        )
        conn.commit()
    with pytest.raises(AipActionTransitionBlocked, match="DRIFTED"):
        store.decide(
            SCOPE,
            "checker:w2d",
            proposal.id,
            f"approve-{uuid.uuid4().hex}",
            DecideActionProposalRequest(
                expected_proposal_version=proposal.version,
                expected_proposal_hash=proposal.proposal_hash,
                decision=ApprovalDecision.APPROVED,
            ),
        )


def test_legacy_proposal_without_preview_remains_compatible() -> None:
    action_id = f"send_legacy_{uuid.uuid4().hex}"
    store = AipActionStore()
    proposal = store.create_proposal(
        SCOPE,
        "maker:legacy",
        f"proposal-{uuid.uuid4().hex}",
        CreateActionProposalRequest(
            action_type_id=action_id,
            purpose="历史提案 NULL 兼容",
        ),
        _action_snapshot(action_id),
        _risk(),
    ).proposal
    assert proposal.impact_preview_ref is None
    approved = store.decide(
        SCOPE,
        "checker:legacy",
        proposal.id,
        f"approve-{uuid.uuid4().hex}",
        DecideActionProposalRequest(
            expected_proposal_version=proposal.version,
            expected_proposal_hash=proposal.proposal_hash,
            decision=ApprovalDecision.APPROVED,
        ),
    )
    assert approved.proposal.status.value == "approved"


def test_preview_binding_drift_blocks_execution_lease() -> None:
    preview_ref, task_id, instance_id = _frozen_preview()
    action_id = f"send_w2d_{uuid.uuid4().hex}"
    store = AipActionStore()
    proposal = store.create_proposal(
        SCOPE,
        "maker:w2d",
        f"proposal-{uuid.uuid4().hex}",
        CreateActionProposalRequest(
            action_type_id=action_id,
            task_id=task_id,
            purpose="执行前再次校验影响预览",
            impact_preview_ref=preview_ref,
        ),
        _action_snapshot(action_id),
        _risk(),
    ).proposal
    approved = store.decide(
        SCOPE,
        "checker:w2d",
        proposal.id,
        f"approve-{uuid.uuid4().hex}",
        DecideActionProposalRequest(
            expected_proposal_version=proposal.version,
            expected_proposal_hash=proposal.proposal_hash,
            decision=ApprovalDecision.APPROVED,
        ),
    ).proposal
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_agent_instance SET version=version+1
               WHERE org_id=%s AND project_id=%s AND instance_id=%s""",
            (*SCOPE.key, instance_id),
        )
        conn.commit()
    executor = Principal(
        subject="executor:w2d",
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["aip_executor"],
        markings=["public", "restricted"],
    )
    with pytest.raises(AipActionTransitionBlocked, match="DRIFTED"):
        AipActionExecutionService(store, ACTION_ADAPTERS).acquire_lease(
            executor,
            approved.id,
            f"lease-{uuid.uuid4().hex}",
            AcquireExecutionLeaseRequest(
                expected_proposal_version=approved.version,
                expected_proposal_hash=approved.proposal_hash,
            ),
        )
