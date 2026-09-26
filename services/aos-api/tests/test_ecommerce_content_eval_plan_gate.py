"""The content Eval contract is owned by the original approved TaskRun Plan."""

from copy import deepcopy

import pytest

from aos_api.ecommerce_content_eval_plan_gate import require_original_content_eval_gate
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
REF = {"resourceType": "EvalContractRevision", "resourceId": "content-contract-1",
       "revision": 2, "contentHash": "a" * 64}


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class PlanTransaction:
    def __init__(self, row):
        self.row = row

    def execute(self, query, params):
        assert "JOIN public.aip_plan_revision" in query
        assert "JOIN public.aip_task" in query
        return Result(self.row if params == (*SCOPE.key, "content-run-1") else None)


def current_plan():
    return {"run_plan_revision_id": "plan-1", "plan_revision_id": "plan-1",
            "current_plan_revision_id": "plan-1", "approval_status": "approved",
            "steps": [{"stepKey": "content_generate", "gateRefs": []},
                      {"stepKey": "content_review", "gateRefs": [deepcopy(REF)]}]}


def test_exact_original_content_review_gate_is_accepted():
    require_original_content_eval_gate(PlanTransaction(current_plan()),
                                      SCOPE, "content-run-1", REF)


@pytest.mark.parametrize("fault", [
    "missing", "duplicate", "wrong_hash", "wrong_kind", "draft",
    "superseded", "missing_row", "missing_review_step",
])
def test_content_review_plan_gate_fails_closed(fault):
    plan = current_plan()
    if fault == "missing":
        plan["steps"][1]["gateRefs"] = []
    elif fault == "duplicate":
        plan["steps"][1]["gateRefs"].append(deepcopy(REF))
    elif fault == "wrong_hash":
        plan["steps"][1]["gateRefs"][0]["contentHash"] = "b" * 64
    elif fault == "wrong_kind":
        plan["steps"][1]["gateRefs"][0]["resourceType"] = "MediaGatePolicyRevision"
    elif fault == "draft":
        plan["approval_status"] = "draft"
    elif fault == "superseded":
        plan["current_plan_revision_id"] = "plan-2"
    elif fault == "missing_row":
        plan = None
    elif fault == "missing_review_step":
        plan["steps"].pop()
    with pytest.raises(ValueError, match="Plan"):
        require_original_content_eval_gate(PlanTransaction(plan), SCOPE,
                                          "content-run-1", REF)


def test_content_review_plan_gate_rejects_cross_tenant_scope():
    with pytest.raises(ValueError, match="Plan"):
        require_original_content_eval_gate(PlanTransaction(current_plan()),
                                          TenantScope("dev-org", "dev-project"),
                                          "content-run-1", REF)
