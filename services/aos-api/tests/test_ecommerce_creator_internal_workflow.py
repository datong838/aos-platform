from dataclasses import dataclass

import pytest

from aos_api.ecommerce_creator_internal_workflow import EcommerceCreatorInternalWorkflow, CreatorInternalWorkflowConflict
from aos_api.ecommerce_creator_internal_workflow_contracts import CreatorInternalWorkflowCommandRequest
from aos_api.tenant_scope import TenantScope

HASH = "a" * 64
SCOPE = TenantScope("org-org", "dev-project")


@dataclass
class Task:
    id: str = "creator-task-1"


@dataclass
class Brief:
    brief_id: str
    task_id: str
    revision: int
    version: int
    content_hash: str
    spec: dict
    brief_type: str
    schema_ref: object


class Tasks:
    def create_task(self, scope, actor, key, body):
        assert scope == SCOPE and actor == "operator" and body.goal["externalEffectsAllowed"] is False
        return Task()


class Briefs:
    def __init__(self):
        self.items = {}

    def create_brief(self, scope, actor, key, body):
        item = Brief("creator-brief-1", body.task_id, 1, 1, HASH, body.spec, body.brief_type, body.schema_ref)
        self.items[1] = item
        return item

    def revise_brief(self, scope, actor, brief_id, key, body):
        current = self.items[max(self.items)]
        if body.expected_version != current.version:
            raise ValueError("stale")
        revision = current.revision + 1
        item = Brief(brief_id, current.task_id, revision, current.version + 1, chr(97 + revision) * 64, body.spec, body.brief_type, body.schema_ref)
        self.items[revision] = item
        return item

    def get_brief(self, scope, brief_id, revision=None):
        return self.items[revision or max(self.items)]

    def list_briefs(self, scope):
        return type("BriefList", (), {"items": [self.items[max(self.items)]]})()


def request(command="create", **changes):
    payload = {"command": command, "purpose": "outreach_batch", "title": "七夕达人邀约", "summary": "整理候选范围和邀约目标", "details": {"channel": "站内邀约"}}
    payload.update(changes)
    return CreatorInternalWorkflowCommandRequest.model_validate(payload)


def test_create_revise_review_and_history_are_internal_only():
    briefs = Briefs()
    receipts = lambda scope, operation, key: "receipt-1"
    workflow = EcommerceCreatorInternalWorkflow(task_store=Tasks(), brief_store=briefs, receipt_reader=receipts)
    created = workflow.execute(SCOPE, "operator", "create-1", request())
    assert created.draft.status == "draft"
    assert created.side_effects.model_dump() == {"provider_invocation_count": 0, "external_outreach_count": 0, "contract_signature_count": 0, "business_mutation_count": 0}
    submitted = workflow.execute(SCOPE, "operator", "submit-1", request("submit_review", draftRef=created.draft, expectedVersion=1))
    assert submitted.draft.status == "in_review" and submitted.draft.version == 2
    approved = workflow.execute(SCOPE, "operator", "approve-1", request("approve", draftRef=submitted.draft, expectedVersion=2))
    assert approved.draft.status == "approved"
    history = workflow.history(SCOPE, created.draft.resource_id)
    assert history.count == 3 and [item.status for item in history.items] == ["draft", "in_review", "approved"]


def test_restore_creates_new_draft_and_preserves_history():
    briefs = Briefs(); workflow = EcommerceCreatorInternalWorkflow(task_store=Tasks(), brief_store=briefs, receipt_reader=lambda *_: "receipt-1")
    created = workflow.execute(SCOPE, "operator", "create-2", request())
    saved = workflow.execute(SCOPE, "operator", "save-2", request("save", title="第二版", draftRef=created.draft, expectedVersion=1))
    restored = workflow.execute(SCOPE, "operator", "restore-2", request("restore", draftRef=saved.draft, expectedVersion=2, restoreRevision=1))
    assert restored.draft.status == "draft" and restored.draft.title == "七夕达人邀约"
    assert workflow.history(SCOPE, created.draft.resource_id).count == 3


def test_exact_version_drift_fails_closed():
    briefs = Briefs(); workflow = EcommerceCreatorInternalWorkflow(task_store=Tasks(), brief_store=briefs, receipt_reader=lambda *_: "receipt-1")
    created = workflow.execute(SCOPE, "operator", "create-3", request())
    with pytest.raises(CreatorInternalWorkflowConflict):
        workflow.execute(SCOPE, "operator", "save-3", request("save", draftRef=created.draft.model_copy(update={"content_hash": "b" * 64}), expectedVersion=1))


def test_command_validation_requires_revision_contract():
    with pytest.raises(ValueError):
        request("approve")


def test_review_transition_fails_closed_when_draft_is_approved_directly():
    briefs = Briefs(); workflow = EcommerceCreatorInternalWorkflow(task_store=Tasks(), brief_store=briefs, receipt_reader=lambda *_: "receipt-1")
    created = workflow.execute(SCOPE, "operator", "create-4", request())
    with pytest.raises(CreatorInternalWorkflowConflict, match="not allowed"):
        workflow.execute(SCOPE, "operator", "approve-4", request("approve", draftRef=created.draft, expectedVersion=1))


def test_non_creator_brief_and_purpose_drift_fail_closed():
    briefs = Briefs(); workflow = EcommerceCreatorInternalWorkflow(task_store=Tasks(), brief_store=briefs, receipt_reader=lambda *_: "receipt-1")
    created = workflow.execute(SCOPE, "operator", "create-5", request())
    briefs.items[1].brief_type = "content_campaign"
    with pytest.raises(CreatorInternalWorkflowConflict, match="not a creator"):
        workflow.history(SCOPE, created.draft.resource_id)
    briefs.items[1].brief_type = "creator_internal_workflow"
    with pytest.raises(CreatorInternalWorkflowConflict, match="purpose is immutable"):
        workflow.execute(SCOPE, "operator", "save-5", request("save", purpose="collaboration", draftRef=created.draft, expectedVersion=1))


def test_list_returns_only_valid_creator_workflows():
    briefs = Briefs(); workflow = EcommerceCreatorInternalWorkflow(task_store=Tasks(), brief_store=briefs, receipt_reader=lambda *_: "receipt-1")
    workflow.execute(SCOPE, "operator", "create-6", request())
    result = workflow.list(SCOPE)
    assert result.count == 1 and result.items[0].purpose == "outreach_batch"


def test_list_returns_only_latest_workflow_for_each_purpose():
    briefs = Briefs()
    workflow = EcommerceCreatorInternalWorkflow(
        task_store=Tasks(),
        brief_store=briefs,
        receipt_reader=lambda *_: "receipt-1",
    )
    workflow.execute(SCOPE, "operator", "create-7", request())
    older = briefs.items[1]
    latest = Brief(
        "creator-brief-2", older.task_id, 1, 1, "c" * 64,
        {**older.spec, "title": "最新邀约批次"}, older.brief_type, older.schema_ref,
    )
    briefs.list_briefs = lambda scope: type(
        "BriefList", (), {"items": [latest, older]}
    )()
    result = workflow.list(SCOPE)
    assert result.count == 1
    assert result.items[0].title == "最新邀约批次"


def test_review_transition_and_restore_revision_fail_closed():
    briefs = Briefs()
    workflow = EcommerceCreatorInternalWorkflow(
        task_store=Tasks(),
        brief_store=briefs,
        receipt_reader=lambda *_: "receipt-1",
    )
    created = workflow.execute(SCOPE, "operator", "create-4", request())
    with pytest.raises(CreatorInternalWorkflowConflict):
        workflow.execute(
            SCOPE,
            "operator",
            "approve-4",
            request("approve", draftRef=created.draft, expectedVersion=1),
        )
    with pytest.raises(CreatorInternalWorkflowConflict):
        workflow.execute(
            SCOPE,
            "operator",
            "restore-4",
            request(
                "restore",
                draftRef=created.draft,
                expectedVersion=1,
                restoreRevision=1,
            ),
        )
