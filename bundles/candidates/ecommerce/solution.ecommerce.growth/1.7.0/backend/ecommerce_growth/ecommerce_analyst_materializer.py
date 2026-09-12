"""Pure GrowthPlan task expansion; canonical Task and graph writes stay host-owned."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Mapping

from pydantic import Field

from .ecommerce_analyst_authority_contracts import (
    AipContractModel,
    AnalystExactRef,
    GrowthPlanLifecycle,
    GrowthPlanRevision,
    TaskGraphMapping,
    TaskGraphRevision,
)


class AnalystMaterializationBlocked(RuntimeError):
    code = "ANALYST_TASKGRAPH_MATERIALIZATION_BLOCKED"


class CanonicalTaskRequest(AipContractModel):
    plan_item_id: str
    task_type: str
    title: str
    priority: int = Field(ge=0, le=100)
    goal: dict[str, str]


def _hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _verified_plan(
    plan: GrowthPlanRevision,
    plan_ref: AnalystExactRef,
) -> tuple[GrowthPlanRevision, AnalystExactRef]:
    plan = GrowthPlanRevision.model_validate(plan.model_dump(mode="python"))
    plan_ref = AnalystExactRef.model_validate(plan_ref.model_dump(mode="python"))
    if (
        plan_ref.resource_type != "GrowthPlanRevision"
        or plan_ref.resource_id != plan.plan_id
        or plan_ref.revision != plan.revision
        or plan_ref.content_hash != plan.content_hash
    ):
        raise AnalystMaterializationBlocked("GrowthPlan exact reference drifted")
    if plan.lifecycle is not GrowthPlanLifecycle.APPROVED:
        raise AnalystMaterializationBlocked(
            "only an approved exact GrowthPlanRevision can materialize"
        )
    return plan, plan_ref


def build_canonical_task_requests(
    plan: GrowthPlanRevision,
    plan_ref: AnalystExactRef,
) -> list[CanonicalTaskRequest]:
    """Expand only eligible plan items without creating canonical Tasks."""

    plan, _ = _verified_plan(plan, plan_ref)
    return [
        CanonicalTaskRequest(
            plan_item_id=item.item_id,
            task_type=item.task_type,
            title=item.title,
            priority=item.priority,
            goal={"objective": item.objective, "growthPlanId": plan.plan_id},
        )
        for item in plan.items
        if item.eligible
    ]


def assemble_task_graph(
    *,
    plan: GrowthPlanRevision,
    plan_ref: AnalystExactRef,
    exact_tasks: Mapping[str, AnalystExactRef],
    graph_id: str,
    actor: str,
    now: datetime,
) -> TaskGraphRevision:
    """Assemble a graph only after the host returns a complete exact Task mapping."""

    plan, plan_ref = _verified_plan(plan, plan_ref)
    if type(exact_tasks) is not dict:
        raise AnalystMaterializationBlocked("canonical Task mapping must be a strict object")
    eligible = [item for item in plan.items if item.eligible]
    expected_ids = {item.item_id for item in eligible}
    if set(exact_tasks) != expected_ids or any(type(key) is not str for key in exact_tasks):
        raise AnalystMaterializationBlocked(
            "canonical Task materializer returned a partial or extra mapping"
        )
    parsed_tasks = {
        key: AnalystExactRef.model_validate(value.model_dump(mode="python"))
        for key, value in exact_tasks.items()
    }
    if any(ref.resource_type != "Task" for ref in parsed_tasks.values()):
        raise AnalystMaterializationBlocked(
            "canonical Task materializer returned a non-Task ref"
        )
    if type(graph_id) is not str or not graph_id.strip() or graph_id.strip() != graph_id:
        raise ValueError("canonical graph identity is required")
    if type(actor) is not str or not actor.strip() or actor.strip() != actor:
        raise ValueError("canonical graph actor is required")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("graph time must include a timezone")

    mappings = [
        TaskGraphMapping(plan_item_id=item.item_id, task_ref=parsed_tasks[item.item_id])
        for item in eligible
    ]
    graph_payload = {
        "graphId": graph_id,
        "planRef": plan_ref.model_dump(mode="json", by_alias=True),
        "mappings": [item.model_dump(mode="json", by_alias=True) for item in mappings],
    }
    return TaskGraphRevision(
        tenant=plan.tenant,
        graph_id=graph_id,
        revision=1,
        version=1,
        plan_ref=plan_ref,
        eligible_plan_item_count=len(eligible),
        canonical_task_count=len(parsed_tasks),
        mappings=mappings,
        materialized_at=now,
        content_hash=_hash(graph_payload),
        created_by=actor,
        created_at=now,
    )


__all__ = [
    "AnalystMaterializationBlocked",
    "CanonicalTaskRequest",
    "assemble_task_graph",
    "build_canonical_task_requests",
]
