"""A new timestamp alone cannot authorize a returned content generation."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from aos_api.aip_action_store import canonical_hash as action_hash
from aos_api.aip_budget_reservation_store import canonical_hash as budget_hash
from aos_api.ecommerce_content_repair_approval_authority import (
    require_repair_approval_binding,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
BASE = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)


def _ref(kind, identity, digest="a" * 64):
    return {"resourceType": kind, "resourceId": identity, "revision": 1,
            "contentHash": "sha256:" + digest}


def _case():
    dispatch = SimpleNamespace(installation_id="installation-1", generation="generation-1",
        execution_epoch=3, cutover_group_id="group-1", cutover_group_revision=2,
        dispatch_revision=5, checked_at=BASE + timedelta(minutes=2))
    expected = {
        "returnDecisionRef": _ref("ReturnDecision", "decision-1"),
        "briefRef": _ref("TaskBriefRevision", "brief-1"),
        "priorArtifactRef": {"resourceType": "Artifact", "resourceId": "artifact-1",
                             "contentHash": "b" * 64},
        "installationBindingRef": {"installationId": "installation-1",
            "generation": "generation-1", "executionEpoch": 3,
            "cutoverGroupId": "group-1", "cutoverGroupRevision": 2,
            "dispatchRevision": 5},
        "capabilityRef": _ref("CapabilityRevision", "capability-1"),
        "budgetUpperBoundMinor": 1000,
    }
    stable = {"tenantScope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
              "taskId": "task-1", "runId": "run-1", "payload": expected,
              "createdBy": "maker-1",
              "actionType": {"id": "ecommerce_growth_content_generate"},
              "actionBindingHash": "c" * 64}
    event = {"approval_event_id": "approval-1", "proposal_id": "proposal-1",
             "proposal_version": 1, "proposal_hash": action_hash(stable),
             "decision": "approved", "actor_id": "reviewer-1",
             "reason": "批准返工", "expires_at": BASE + timedelta(hours=1),
             "created_at": BASE + timedelta(minutes=1),
             "action_binding_hash": "c" * 64}
    row = {**event, "approval_ref": _ref("ActionApprovalEvent", "approval-1",
                budget_hash(event)), "proposal_status": "approved",
           "action_type_id": "ecommerce_growth_content_generate",
           "task_id": "task-1", "run_id": "run-1",
           "proposal_payload": expected, "proposal_hash_saved": action_hash(stable),
           "proposal_expires_at": BASE + timedelta(hours=1),
           "proposal_created_by": "maker-1",
           "proposal_binding_hash": "c" * 64,
           "draft_hash": action_hash(stable), "draft_status": "approved",
           "draft_snapshot": stable}
    return dispatch, row


class _Transaction:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, params):
        assert "aip_action_approval_event" in sql and "aip_action_draft" in sql
        assert params == ("org-org", "dev-project", "approval-1")
        return SimpleNamespace(fetchall=lambda: [self.row])


def _check(row, dispatch):
    expected = _case()[1]["proposal_payload"]
    require_repair_approval_binding(_Transaction(row), SCOPE, row["approval_ref"],
        task_id="task-1", run_id="run-1", decision_ref=expected["returnDecisionRef"],
        brief_ref=expected["briefRef"],
        prior_artifact_ref=expected["priorArtifactRef"],
        capability_ref=expected["capabilityRef"],
        upper_bound_minor=1000, dispatch=dispatch)


def test_repair_approval_binds_exact_new_input_and_installation():
    dispatch, row = _case()
    _check(row, dispatch)
    for key in ("returnDecisionRef", "briefRef", "priorArtifactRef",
                "installationBindingRef", "capabilityRef", "budgetUpperBoundMinor"):
        drift = deepcopy(row)
        drift["proposal_payload"].pop(key)
        drift["draft_snapshot"]["payload"] = drift["proposal_payload"]
        with pytest.raises(ValueError):
            _check(drift, dispatch)
    for drift in (
        {"proposal_status": "draft"}, {"decision": "rejected"},
        {"run_id": "other-run"}, {"proposal_hash_saved": "d" * 64},
        {"draft_hash": "d" * 64},
    ):
        with pytest.raises(ValueError):
            _check({**row, **drift}, dispatch)
    with pytest.raises(ValueError):
        _check(row, SimpleNamespace(**{**vars(dispatch), "execution_epoch": 4}))
