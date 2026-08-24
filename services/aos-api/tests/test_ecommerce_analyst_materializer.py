from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, GrowthPlanRevision
from aos_api.ecommerce_analyst_materializer import AnalystMaterializationBlocked, EcommerceAnalystMaterializer
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 25, tzinfo=UTC)
HASH = "a" * 64
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")


def ref(kind: str, identity: str) -> AnalystExactRef:
    return AnalystExactRef(resourceType=kind, resourceId=identity, revision=1, contentHash=HASH)


def plan(lifecycle: str = "approved") -> GrowthPlanRevision:
    return GrowthPlanRevision.model_validate({"tenant": {"orgId": "org-org", "projectId": "dev-project"}, "planId": "plan-1", "revision": 1, "version": 1, "lifecycle": lifecycle, "decisionRef": ref("DecisionSummaryRevision", "decision-1"), "objective": "grow", "constraints": [], "budget": "10", "expectedEffect": "+1%", "confidence": 0.5, "stopConditions": ["stale"], "items": [{"itemId": "a", "taskType": "analysis", "title": "A", "objective": "A", "eligible": True}, {"itemId": "b", "taskType": "analysis", "title": "B", "objective": "B", "eligible": False}], "approvedAt": NOW if lifecycle == "approved" else None, "contentHash": HASH, "createdBy": "user:operator", "createdAt": NOW})


class Store:
    def __init__(self, item: GrowthPlanRevision, current: bool = True) -> None:
        self.item = item; self.current = current; self.graphs = []
    def get_plan_exact(self, scope, exact): return self.item
    def is_current_plan(self, scope, exact): return self.current
    def publish_task_graph(self, scope, actor, key, item, *, expected_version):
        self.graphs.append(item); return ref("TaskGraphRevision", item.graph_id)


class Tasks:
    def __init__(self, result): self.result = result; self.calls = []
    def materialize_exact_tasks(self, scope, actor, key, requests): self.calls.append(requests); return self.result


def test_materializes_only_eligible_items_and_commits_graph_after_full_mapping() -> None:
    store = Store(plan()); tasks = Tasks({"a": ref("Task", "task-a")})
    result = EcommerceAnalystMaterializer(store, tasks).materialize(SCOPE, "user:operator", "idem", ref("GrowthPlanRevision", "plan-1"), graph_id="graph-1", now=NOW)
    assert result.resource_type == "TaskGraphRevision"
    assert [request.plan_item_id for request in tasks.calls[0]] == ["a"]
    assert store.graphs[0].eligible_plan_item_count == store.graphs[0].canonical_task_count == 1


def test_partial_mapping_does_not_persist_task_graph() -> None:
    store = Store(plan()); tasks = Tasks({})
    with pytest.raises(AnalystMaterializationBlocked, match="partial"):
        EcommerceAnalystMaterializer(store, tasks).materialize(SCOPE, "user:operator", "idem", ref("GrowthPlanRevision", "plan-1"), graph_id="graph-1", now=NOW)
    assert store.graphs == []


@pytest.mark.parametrize("item,current", [(plan("draft"), True), (plan(), False)])
def test_unapproved_or_stale_plan_fails_before_task_creation(item, current) -> None:
    store = Store(item, current); tasks = Tasks({"a": ref("Task", "task-a")})
    with pytest.raises(AnalystMaterializationBlocked):
        EcommerceAnalystMaterializer(store, tasks).materialize(SCOPE, "user:operator", "idem", ref("GrowthPlanRevision", "plan-1"), graph_id="graph-1", now=NOW)
    assert tasks.calls == [] and store.graphs == []
