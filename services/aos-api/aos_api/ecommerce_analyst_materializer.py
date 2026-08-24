"""Fail-closed GrowthPlan to canonical AIP TaskGraph orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Protocol

from pydantic import Field

from aos_api.aip_contracts import AipContractModel
from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef,
    GrowthPlanLifecycle,
    GrowthPlanRevision,
    TaskGraphMapping,
    TaskGraphRevision,
)
from aos_api.tenant_scope import TenantScope


class CanonicalTaskRequest(AipContractModel):
    plan_item_id: str
    task_type: str
    title: str
    priority: int = Field(ge=0, le=100)
    goal: dict[str, str]


class CanonicalTaskMaterializer(Protocol):
    def materialize_exact_tasks(
        self, scope: TenantScope, actor: str, key: str, requests: list[CanonicalTaskRequest]
    ) -> dict[str, AnalystExactRef]: ...


class AnalystPlanStore(Protocol):
    def get_plan_exact(self, scope: TenantScope, ref: AnalystExactRef) -> GrowthPlanRevision: ...
    def is_current_plan(self, scope: TenantScope, ref: AnalystExactRef) -> bool: ...
    def publish_task_graph(
        self, scope: TenantScope, actor: str, key: str, item: TaskGraphRevision, *, expected_version: int
    ) -> AnalystExactRef: ...


class AnalystMaterializationBlocked(RuntimeError):
    code = "ANALYST_TASKGRAPH_MATERIALIZATION_BLOCKED"


def _hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class EcommerceAnalystMaterializer:
    def __init__(self, store: AnalystPlanStore, task_materializer: CanonicalTaskMaterializer) -> None:
        self._store = store
        self._tasks = task_materializer

    def materialize(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        plan_ref: AnalystExactRef,
        *,
        graph_id: str,
        now: datetime,
    ) -> AnalystExactRef:
        plan = self._store.get_plan_exact(scope, plan_ref)
        if plan.lifecycle is not GrowthPlanLifecycle.APPROVED:
            raise AnalystMaterializationBlocked("only an approved exact GrowthPlanRevision can materialize")
        if not self._store.is_current_plan(scope, plan_ref):
            raise AnalystMaterializationBlocked("GrowthPlanRevision is stale; approve a successor")
        eligible = [item for item in plan.items if item.eligible]
        requests = [
            CanonicalTaskRequest(
                plan_item_id=item.item_id,
                task_type=item.task_type,
                title=item.title,
                priority=item.priority,
                goal={"objective": item.objective, "growthPlanId": plan.plan_id},
            )
            for item in eligible
        ]
        exact_tasks = self._tasks.materialize_exact_tasks(scope, actor, f"{key}:tasks", requests)
        expected_ids = {item.item_id for item in eligible}
        if set(exact_tasks) != expected_ids:
            raise AnalystMaterializationBlocked("canonical Task materializer returned a partial or extra mapping")
        for task_ref in exact_tasks.values():
            if task_ref.resource_type != "Task":
                raise AnalystMaterializationBlocked("canonical Task materializer returned a non-Task ref")
        mappings = [TaskGraphMapping(plan_item_id=item.item_id, task_ref=exact_tasks[item.item_id]) for item in eligible]
        graph_payload = {
            "graphId": graph_id,
            "planRef": plan_ref.model_dump(mode="json", by_alias=True),
            "mappings": [item.model_dump(mode="json", by_alias=True) for item in mappings],
        }
        graph = TaskGraphRevision(
            tenant=plan.tenant,
            graph_id=graph_id,
            revision=1,
            version=1,
            plan_ref=plan_ref,
            eligible_plan_item_count=len(eligible),
            canonical_task_count=len(exact_tasks),
            mappings=mappings,
            materialized_at=now,
            content_hash=_hash(graph_payload),
            created_by=actor,
            created_at=now,
        )
        return self._store.publish_task_graph(scope, actor, f"{key}:graph", graph, expected_version=0)
