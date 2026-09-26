"""A revised brief is evidence of preparation, never permission to invoke Provider."""

from types import SimpleNamespace

import pytest

from aos_api.aip_production_contract_store import canonical_hash
from aos_api.ecommerce_content_repair_brief_authority import (
    require_repair_brief, require_frozen_repair_brief,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
HASH_A = "a" * 64


def _ref(kind, identity, revision, digest):
    return {"resourceType": kind, "resourceId": identity, "revision": revision,
            "contentHash": "sha256:" + digest}


def _authority():
    previous = {"sourceHandoffRef": _ref("HandoffReceipt", "handoff-1", 1, HASH_A),
                "taskRef": _ref("Task", "task-1", 1, HASH_A),
                "growthPlanRef": _ref("GrowthPlanRevision", "plan-1", 1, HASH_A),
                "artifactRefs": [_ref("ArtifactRevision", f"source-{n}", 1, HASH_A)
                                 for n in range(4)],
                "externalPublicationRequested": False}
    decision = _ref("ReturnDecision", "return-1", 1, HASH_A)
    artifact = {"resourceType": "Artifact", "resourceId": "artifact-1",
                "contentHash": HASH_A}
    repair = {"returnDecisionRef": decision, "priorArtifactRef": artifact,
              "humanReason": "核对商品事实"}
    current = {**previous, "repair": repair}
    schema = {"resourceType": "ContentCampaignBriefSchema",
              "resourceId": "schema://aos/ecommerce/content-campaign-brief/v1",
              "revision": "1", "authority": "aos://ecommerce-workshop/content-campaign"}
    digest = canonical_hash({"briefType": "content_campaign", "schemaRef": schema,
                             "spec": current})
    brief = _ref("TaskBriefRevision", "brief-1", 2, digest)
    receipt_ref = dict(brief, contentHash=digest)
    receipt_hash = canonical_hash({"briefId": "brief-1", "expectedVersion": 1,
                                   "briefType": "content_campaign", "schemaRef": schema,
                                   "spec": current})
    row = {"task_id": "task-1", "current_revision": 2, "version": 2,
           "brief_type": "content_campaign", "schema_ref": schema,
           "spec": current, "content_hash": digest, "lifecycle": "draft",
           "created_by": "repair-reviewer", "previous_spec": previous,
           "previous_content_hash": canonical_hash({"briefType": "content_campaign",
                                                    "schemaRef": schema, "spec": previous}),
           "previous_schema_ref": schema, "previous_brief_type": "content_campaign",
           "receipt_request_hash": receipt_hash, "receipt_result_ref": receipt_ref,
           "receipt_created_by": "repair-reviewer"}
    return brief, _ref("TaskBriefRevision", "brief-1", 1,
                       row["previous_content_hash"]), decision, artifact, row


class _Transaction:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, params):
        assert "aip_task_brief_head" in sql and "task_brief.revise" in sql
        assert params == (2, 2, 2, "org-org", "dev-project", "brief-1")
        return SimpleNamespace(fetchall=lambda: [self.row])


def test_repair_brief_requires_formal_revision_and_receipt():
    brief, prior, decision, artifact, row = _authority()
    require_repair_brief(_Transaction(row), SCOPE, brief, prior, decision, artifact,
                         task_id="task-1", reason="核对商品事实")
    for changes in (
        {"current_revision": 1}, {"receipt_request_hash": HASH_A},
        {"receipt_result_ref": {**row["receipt_result_ref"], "contentHash": HASH_A}},
        {"task_id": "other-task"}, {"lifecycle": "frozen"},
        {"previous_content_hash": HASH_A},
        {"spec": {**row["spec"], "repair": {**row["spec"]["repair"],
                                       "humanReason": "另一句话"}}},
        {"spec": {**row["spec"], "externalPublicationRequested": True}},
    ):
        with pytest.raises(ValueError):
            require_repair_brief(_Transaction({**row, **changes}), SCOPE, brief,
                                 prior, decision, artifact, task_id="task-1",
                                 reason="核对商品事实")
    with pytest.raises(ValueError):
        require_repair_brief(_Transaction(row), SCOPE, prior, prior, decision,
                             artifact, task_id="task-1", reason="核对商品事实")
    with pytest.raises(ValueError):
        require_repair_brief(_Transaction(row), SCOPE, brief, prior,
                             {**decision, "contentHash": "sha256:" + "b" * 64},
                             artifact, task_id="task-1", reason="核对商品事实")


class _FrozenTransaction:
    def __init__(self, frozen_row, revised_row):
        self.frozen_row = frozen_row
        self.revised_row = revised_row

    def execute(self, sql, _params):
        if "task_brief.freeze" in sql:
            return SimpleNamespace(fetchall=lambda: [self.frozen_row])
        assert "task_brief.revise" in sql
        return SimpleNamespace(fetchall=lambda: [self.revised_row])


def test_frozen_repair_brief_requires_both_public_receipts():
    draft, prior, decision, artifact, revised_row = _authority()
    frozen = {**draft, "revision": 3}
    frozen_row = {
        "task_id": "task-1", "current_revision": 3, "version": 3,
        "brief_type": "content_campaign", "schema_ref": revised_row["schema_ref"],
        "spec": revised_row["spec"], "content_hash": revised_row["content_hash"],
        "lifecycle": "frozen", "created_by": "reviewer",
        "draft_brief_type": "content_campaign",
        "draft_schema_ref": revised_row["schema_ref"],
        "draft_spec": revised_row["spec"],
        "draft_content_hash": revised_row["content_hash"],
        "draft_lifecycle": "draft",
        "receipt_request_hash": canonical_hash({"briefId": "brief-1", "expectedVersion": 2}),
        "receipt_result_ref": {**frozen, "contentHash": revised_row["content_hash"]},
        "receipt_created_by": "reviewer",
    }
    active_revised = {**revised_row, "current_revision": 3, "version": 3}
    require_frozen_repair_brief(_FrozenTransaction(frozen_row, active_revised),
        SCOPE, frozen, prior, decision, artifact, task_id="task-1", reason="核对商品事实")
    for drift in (
        {"draft_lifecycle": "unknown"},
        {"draft_content_hash": HASH_A},
        {"receipt_request_hash": HASH_A},
        {"receipt_result_ref": {**frozen_row["receipt_result_ref"], "contentHash": HASH_A}},
        {"current_revision": 2},
    ):
        with pytest.raises(ValueError):
            require_frozen_repair_brief(
                _FrozenTransaction({**frozen_row, **drift}, active_revised),
                SCOPE, frozen, prior, decision, artifact, task_id="task-1",
                reason="核对商品事实")
