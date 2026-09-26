"""Only content generation may budget against an immutable Task creation Ref."""

import pytest

from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_store import (
    AipBudgetReservationStore, BudgetReservationBlocked, canonical_hash,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
TASK = {
    "task_type": "ecommerce.workshop.business_task",
    "title": "内容任务", "description": "生成销售说明", "priority": 1,
    "goal": {"objective": "有来源"}, "selection_ref": None,
    "policy_revision": "v1", "version": 4, "status": "executing",
    "current_plan_revision_id": "plan-1",
}
CREATION = {
    "type": TASK["task_type"], "title": TASK["title"],
    "description": TASK["description"], "priority": TASK["priority"],
    "goal": TASK["goal"], "selectionRef": TASK["selection_ref"],
    "policyRevision": TASK["policy_revision"],
}


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Conn:
    def __init__(self, *, status="executing", hash_drift=False, running=True):
        self.task = {**TASK, "status": status,
                     "request_hash": "f" * 64 if hash_drift else canonical_hash(CREATION)}
        self.running = running

    def execute(self, query, params):
        assert params[:2] == SCOPE.key
        if "FROM public.aip_task" in query and "aip_task_run" not in query:
            return Cursor([self.task])
        if "aip_task_run" in query:
            return Cursor([{"run_id": "run-1"}] if self.running else [])
        raise AssertionError(query)


def test_content_task_creation_ref_survives_plan_run_version_change():
    ref = BudgetExactRef(resource_type="Task", resource_id="task-1", revision=1,
                         content_hash=canonical_hash(CREATION, prefixed=True))
    AipBudgetReservationStore()._task_authority(
        Conn(), SCOPE, ref, operation_id="ecommerce_growth_content_generate")
    with pytest.raises(BudgetReservationBlocked):
        AipBudgetReservationStore()._task_authority(
            Conn(status="completed"), SCOPE, ref,
            operation_id="ecommerce_growth_content_generate")
    with pytest.raises(BudgetReservationBlocked):
        AipBudgetReservationStore()._task_authority(
            Conn(hash_drift=True), SCOPE, ref,
            operation_id="ecommerce_growth_content_generate")
    with pytest.raises(BudgetReservationBlocked):
        AipBudgetReservationStore()._task_authority(
            Conn(running=False), SCOPE, ref,
            operation_id="ecommerce_growth_content_generate")


def test_other_budget_operations_still_require_current_task_version():
    ref = BudgetExactRef(resource_type="Task", resource_id="task-1", revision=1,
                         content_hash=canonical_hash(CREATION, prefixed=True))
    with pytest.raises(BudgetReservationBlocked):
        AipBudgetReservationStore()._task_authority(
            Conn(), SCOPE, ref, operation_id="another.operation")
