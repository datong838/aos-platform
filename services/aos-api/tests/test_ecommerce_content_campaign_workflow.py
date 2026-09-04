from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contracts import BriefLifecycle, TaskBriefRevision
from aos_api.ecommerce_content_campaign_workflow import (
    ContentCampaignWorkflowConflict,
    EcommerceContentCampaignWorkflow,
)
from aos_api.ecommerce_content_campaign_workflow_contracts import (
    ContentCampaignApprovalPreviewRequest,
    ContentCampaignWorkflowCommandRequest,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 4, 8, 30, tzinfo=UTC)


def brief(*, revision: int = 1, version: int = 1, content_hash: str = "a" * 64, spec=None):
    return TaskBriefRevision(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        brief_id="brief-1",
        task_id="task-1",
        revision=revision,
        version=version,
        brief_type="content_campaign",
        schema_ref=ResourceRef(
            resource_type="ContentCampaignBriefSchema",
            resource_id="schema://aos/ecommerce/content-campaign-brief/v1",
            revision="1",
            authority="aos://ecommerce-workshop/content-campaign",
        ),
        spec=spec or {"objective": "策划秋季会员回访活动", "channels": ["微信小店"], "constraints": []},
        content_hash=content_hash,
        lifecycle=BriefLifecycle.DRAFT,
        created_by="user:operator",
        created_at=NOW,
    )


class Tasks:
    def __init__(self):
        self.calls = []

    def create_task(self, scope, actor, key, body):
        self.calls.append((scope, actor, key, body))
        return SimpleNamespace(id="task-1", title=body.title)


class Briefs:
    def __init__(self):
        self.current = brief()
        self.created = []
        self.revised = []
        self.history = {1: self.current}

    def create_brief(self, scope, actor, key, body):
        self.created.append((scope, actor, key, body))
        return self.current

    def revise_brief(self, scope, actor, brief_id, key, body):
        self.revised.append((scope, actor, brief_id, key, body))
        self.current = brief(revision=self.current.revision + 1, version=self.current.version + 1, content_hash=chr(97 + self.current.revision) * 64, spec=body.spec)
        self.history[self.current.revision] = self.current
        return self.current

    def get_brief(self, scope, brief_id, revision=None):
        return self.history.get(revision, self.current)


class CampaignReader:
    def __init__(self, *, eligible=0, blockers=0):
        self.eligible = eligible
        self.blockers = blockers

    def read(self, *, org_id, project_id):
        slice_item = lambda name: SimpleNamespace(
            slice_id=name,
            status="ready",
            blockers=[object()] * self.blockers,
            count_ledger=SimpleNamespace(eligible=self.eligible),
        )
        return SimpleNamespace(
            evaluated_at=NOW,
            data_cutoff=NOW,
            slices=[slice_item("plan"), slice_item("calendar"), slice_item("content")],
        )


def workflow(*, reader=None):
    return EcommerceContentCampaignWorkflow(
        task_store=Tasks(),
        brief_store=Briefs(),
        campaign_reader=reader or CampaignReader(),
        receipt_reader=lambda scope, operation, key: "w2r-receipt-1",
    )


def command(**changes):
    payload = {
        "command": "generate",
        "objective": "策划秋季会员回访活动",
        "channels": ["微信小店"],
        "audience": "近九十天成交会员",
        "timeWindow": "九月第二周",
        "constraints": ["不降低会员权益"],
    }
    payload.update(changes)
    return ContentCampaignWorkflowCommandRequest.model_validate(payload)


def test_generate_creates_chinese_business_task_and_versioned_brief_with_receipt():
    service = workflow()
    result = service.execute(SCOPE, actor="user:operator", idempotency_key="campaign-1", body=command())

    assert result.task.title == "制定秋季会员回访活动方案"
    assert result.draft.resource_id == "brief-1"
    assert result.draft.revision == 1
    assert result.receipt.receipt_id == "w2r-receipt-1"
    assert result.receipt.operation == "task_brief.create"
    assert result.side_effects.external_business_mutation_count == 0
    assert result.side_effects.provider_invocation_count == 0


def test_regenerate_requires_exact_current_ref_and_uses_cas_successor():
    service = workflow()
    result = service.execute(
        SCOPE,
        actor="user:operator",
        idempotency_key="campaign-2",
        body=command(
            command="regenerate",
            draftRef={
                "resourceType": "TaskBriefRevision",
                "resourceId": "brief-1",
                "revision": 1,
                "contentHash": "a" * 64,
            },
            expectedVersion=1,
        ),
    )
    assert result.draft.revision == 2
    assert result.draft.version == 2
    assert result.receipt.operation == "task_brief.revise"

    with pytest.raises(ContentCampaignWorkflowConflict):
        service.execute(
            SCOPE,
            actor="user:operator",
            idempotency_key="campaign-3",
            body=command(
                command="save",
                draftRef={
                    "resourceType": "TaskBriefRevision",
                    "resourceId": "brief-1",
                    "revision": 1,
                    "contentHash": "c" * 64,
                },
                expectedVersion=1,
            ),
        )


def test_approval_preview_is_read_only_and_explains_missing_canonical_inputs():
    service = workflow(reader=CampaignReader(eligible=0))
    result = service.preview_approval(
        SCOPE,
        ContentCampaignApprovalPreviewRequest.model_validate(
            {
                "draftRef": {
                    "resourceType": "TaskBriefRevision",
                    "resourceId": "brief-1",
                    "revision": 1,
                    "contentHash": "a" * 64,
                }
            }
        ),
    )
    assert result.status == "needs_input"
    assert result.approval_allowed is False
    assert "补充正式经营目标与预算版本" in result.next_actions
    assert result.side_effects.approval_created_count == 0
    assert result.side_effects.external_publication_count == 0


def test_approval_preview_can_be_reviewed_but_never_publishes():
    result = workflow(reader=CampaignReader(eligible=1)).preview_approval(
        SCOPE,
        ContentCampaignApprovalPreviewRequest.model_validate(
            {
                "draftRef": {
                    "resourceType": "TaskBriefRevision",
                    "resourceId": "brief-1",
                    "revision": 1,
                    "contentHash": "a" * 64,
                }
            }
        ),
    )
    assert result.status == "reviewable"
    assert result.approval_allowed is True
    assert result.side_effects.external_publication_count == 0


def test_apply_risk_decision_creates_receipted_successor_without_external_effect():
    service = workflow()
    result = service.execute(
        SCOPE,
        actor="user:operator",
        idempotency_key="campaign-risk-1",
        body=command(
            command="apply_risk_decision",
            draftRef={"resourceType": "TaskBriefRevision", "resourceId": "brief-1", "revision": 1, "contentHash": "a" * 64},
            expectedVersion=1,
            riskDecision={"category": "discount_margin", "disposition": "keep_current", "constraint": "毛利率不得低于已审批边界"},
        ),
    )
    assert result.draft.version == 2
    assert result.draft.risk_decisions[0].category == "discount_margin"
    assert result.draft.risk_decisions[0].applied_from_revision == 1
    assert "毛利率不得低于已审批边界" in result.draft.constraints
    assert result.receipt.operation == "task_brief.revise"
    assert result.side_effects.external_business_mutation_count == 0


def test_undo_risk_decision_uses_previous_revision_and_keeps_audit_history():
    service = workflow()
    applied = service.execute(
        SCOPE,
        actor="user:operator",
        idempotency_key="campaign-risk-2",
        body=command(
            command="apply_risk_decision",
            draftRef={"resourceType": "TaskBriefRevision", "resourceId": "brief-1", "revision": 1, "contentHash": "a" * 64},
            expectedVersion=1,
            riskDecision={"category": "inventory_supply", "disposition": "defer", "constraint": "库存承诺必须以正式可售量为准"},
        ),
    )
    undone = service.execute(
        SCOPE,
        actor="user:operator",
        idempotency_key="campaign-risk-3",
        body=command(
            command="undo_risk_decision",
            draftRef={"resourceType": "TaskBriefRevision", "resourceId": "brief-1", "revision": applied.draft.revision, "contentHash": applied.draft.content_hash},
            expectedVersion=applied.draft.version,
        ),
    )
    assert undone.draft.version == 3
    assert undone.draft.risk_decisions == []
    assert undone.draft.last_action == "risk_decision_undone"
    assert undone.side_effects.external_publication_count == 0
