from __future__ import annotations

import uuid

import pytest

from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "test:w2c"


def _key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _step() -> PlanStep:
    return PlanStep(step_key="draft", title="生成草稿")


def test_compiled_production_plan_requires_exact_start_gate_before_approval() -> None:
    store = AipTaskStore()
    task = store.create_task(
        SCOPE,
        ACTOR,
        _key("task"),
        CreateTaskRequest(title="W2-C production approval guard"),
    )
    plan = store.create_plan(
        SCOPE,
        ACTOR,
        task.id,
        _key("plan"),
        CreatePlanRevisionRequest(
            expected_task_version=task.version,
            steps=[_step()],
            risk={
                "productionContract": {
                    "compilerVersion": "w2c.v1",
                    "productionStartGateRequired": True,
                    "productionStartGateRef": None,
                }
            },
        ),
    )

    with pytest.raises(
        AipTaskTransitionBlocked, match="production start gate"
    ):
        store.approve_plan(
            SCOPE,
            ACTOR,
            task.id,
            plan.revision,
            task.version + 1,
            plan.content_hash,
        )


def test_ordinary_plan_approval_is_unchanged() -> None:
    store = AipTaskStore()
    task = store.create_task(
        SCOPE,
        ACTOR,
        _key("task"),
        CreateTaskRequest(title="W2-C ordinary approval compatibility"),
    )
    plan = store.create_plan(
        SCOPE,
        ACTOR,
        task.id,
        _key("plan"),
        CreatePlanRevisionRequest(
            expected_task_version=task.version,
            steps=[_step()],
        ),
    )

    approved = store.approve_plan(
        SCOPE,
        ACTOR,
        task.id,
        plan.revision,
        task.version + 1,
        plan.content_hash,
    )

    assert approved.approval_status == "approved"
