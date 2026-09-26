"""Read the original approved content Plan's exact Eval gate; never pick a new one."""

from __future__ import annotations

import json
from typing import Any

from aos_api.aip_contracts import ExactContractRef
from aos_api.tenant_scope import TenantScope


def require_original_content_eval_gate(
    transaction: Any, scope: TenantScope, run_id: str, contract_ref: Any,
) -> None:
    if type(scope) is not TenantScope or type(run_id) is not str or not run_id:
        raise ValueError("content review Plan scope or Run is invalid")
    try:
        expected = ExactContractRef.model_validate(contract_ref)
    except Exception as exc:
        raise ValueError("content review Plan EvalContract ref is invalid") from exc
    if expected.resource_type != "EvalContractRevision":
        raise ValueError("content review Plan requires EvalContractRevision")
    row = transaction.execute(
        """SELECT r.plan_revision_id AS run_plan_revision_id,
                  p.plan_revision_id,p.approval_status,p.steps,
                  t.current_plan_revision_id
             FROM public.aip_task_run r
             JOIN public.aip_plan_revision p
               ON p.org_id=r.org_id AND p.project_id=r.project_id
              AND p.plan_revision_id=r.plan_revision_id AND p.task_id=r.task_id
             JOIN public.aip_task t
               ON t.org_id=r.org_id AND t.project_id=r.project_id
              AND t.task_id=r.task_id
            WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s""",
        (*scope.key, run_id),
    ).fetchone()
    if row is None or row["approval_status"] != "approved" or (
        row["run_plan_revision_id"] != row["plan_revision_id"]
        or row["current_plan_revision_id"] != row["plan_revision_id"]
    ):
        raise ValueError("content review original Plan is not current and approved")
    steps = json.loads(row["steps"]) if isinstance(row["steps"], str) else row["steps"]
    if type(steps) is not list:
        raise ValueError("content review original Plan steps are invalid")
    reviews = [step for step in steps if type(step) is dict and step.get("stepKey") == "content_review"]
    if len(reviews) != 1 or type(reviews[0].get("gateRefs")) is not list:
        raise ValueError("content review original Plan needs one review step")
    gate_refs = [ref for ref in reviews[0]["gateRefs"]
                 if type(ref) is dict and ref.get("resourceType") == "EvalContractRevision"]
    if len(gate_refs) != 1 or gate_refs[0] != expected.model_dump(mode="json", by_alias=True):
        raise ValueError("content review original Plan exact EvalContract gate drifted")
