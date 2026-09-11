"""Package task expansion parity; canonical writes remain host-owned."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib
from pathlib import Path
import subprocess
import sys

import pytest

from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef as HostExactRef,
    GrowthPlanRevision as HostGrowthPlanRevision,
)
from aos_api.ecommerce_analyst_materializer import EcommerceAnalystMaterializer
from aos_api.tenant_scope import TenantScope


ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "bundles/solutions/ecommerce-growth/backend"
NOW = datetime(2026, 9, 12, 2, 0, tzinfo=UTC)
HASH = "a" * 64
SCOPE = TenantScope("org-org", "dev-project")


@pytest.fixture
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    contracts = importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_authority_contracts"
    )
    materializer = importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_materializer"
    )
    return contracts, materializer


def host_ref(kind: str, identity: str, *, digest: str = HASH) -> HostExactRef:
    return HostExactRef(
        resourceType=kind,
        resourceId=identity,
        revision=1,
        contentHash=digest,
    )


def host_plan(*, lifecycle: str = "approved") -> HostGrowthPlanRevision:
    return HostGrowthPlanRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "planId": "plan-1",
            "revision": 1,
            "version": 1,
            "lifecycle": lifecycle,
            "decisionRef": host_ref("DecisionSummaryRevision", "decision-1"),
            "objective": "形成内部内容任务",
            "constraints": ["禁止外部发布"],
            "budget": "100.00",
            "expectedEffect": "待真实窗口核验",
            "confidence": 0.5,
            "stopConditions": ["来源失效"],
            "items": [
                {
                    "itemId": "content-a",
                    "taskType": "content",
                    "title": "准备商品介绍",
                    "objective": "核对商品事实",
                    "priority": 80,
                    "eligible": True,
                },
                {
                    "itemId": "price-b",
                    "taskType": "price",
                    "title": "核查价格",
                    "objective": "形成影响预览",
                    "priority": 60,
                    "eligible": False,
                },
            ],
            "approvedAt": NOW if lifecycle == "approved" else None,
            "contentHash": HASH,
            "createdBy": "user:reviewer",
            "createdAt": NOW,
        }
    )


class HostStore:
    def __init__(self, plan: HostGrowthPlanRevision) -> None:
        self.plan = plan
        self.graph = None

    def get_plan_exact(self, scope, plan_ref):
        assert scope == SCOPE and plan_ref == host_ref("GrowthPlanRevision", "plan-1")
        return self.plan

    def is_current_plan(self, scope, plan_ref):
        return scope == SCOPE and plan_ref == host_ref("GrowthPlanRevision", "plan-1")

    def publish_task_graph(self, scope, actor, key, item, *, expected_version):
        assert scope == SCOPE and actor == "user:reviewer" and expected_version == 0
        self.graph = item
        return host_ref("TaskGraphRevision", item.graph_id, digest=item.content_hash)


class HostTasks:
    def __init__(self) -> None:
        self.requests = None

    def materialize_exact_tasks(self, scope, actor, key, requests):
        assert scope == SCOPE and actor == "user:reviewer"
        self.requests = requests
        return {"content-a": host_ref("Task", "task-content-a")}


def package_inputs(package, *, lifecycle: str = "approved"):
    contracts, _ = package
    plan = host_plan(lifecycle=lifecycle)
    return (
        contracts.GrowthPlanRevision.model_validate(
            plan.model_dump(mode="json", by_alias=True)
        ),
        contracts.AnalystExactRef.model_validate(
            host_ref("GrowthPlanRevision", "plan-1").model_dump(
                mode="json", by_alias=True
            )
        ),
    )


def test_package_requests_and_graph_match_existing_host_orchestration(package) -> None:
    store, tasks = HostStore(host_plan()), HostTasks()
    EcommerceAnalystMaterializer(store, tasks).materialize(
        SCOPE,
        "user:reviewer",
        "materialize-1",
        host_ref("GrowthPlanRevision", "plan-1"),
        graph_id="graph-1",
        now=NOW,
    )
    plan, plan_ref = package_inputs(package)
    contracts, materializer = package
    requests = materializer.build_canonical_task_requests(plan, plan_ref)
    exact_tasks = {
        "content-a": contracts.AnalystExactRef.model_validate(
            host_ref("Task", "task-content-a").model_dump(mode="json", by_alias=True)
        )
    }
    graph = materializer.assemble_task_graph(
        plan=plan,
        plan_ref=plan_ref,
        exact_tasks=exact_tasks,
        graph_id="graph-1",
        actor="user:reviewer",
        now=NOW,
    )
    assert [item.model_dump(mode="json", by_alias=True) for item in requests] == [
        item.model_dump(mode="json", by_alias=True) for item in tasks.requests
    ]
    assert graph.model_dump(mode="json", by_alias=True) == store.graph.model_dump(
        mode="json", by_alias=True
    )
    assert [item.plan_item_id for item in graph.mappings] == ["content-a"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("partial", "partial or extra"),
        ("extra", "partial or extra"),
        ("non_task", "non-Task"),
        ("naive", "timezone"),
        ("blank_actor", "actor"),
        ("wrong_plan_ref", "exact reference"),
        ("draft", "only an approved"),
    ],
)
def test_package_materialization_fails_closed(package, change: str, message: str) -> None:
    contracts, materializer = package
    plan, plan_ref = package_inputs(
        package, lifecycle="draft" if change == "draft" else "approved"
    )
    exact_tasks = {
        "content-a": contracts.AnalystExactRef.model_validate(
            host_ref("Task", "task-content-a").model_dump(mode="json", by_alias=True)
        )
    }
    actor, now = "user:reviewer", NOW
    if change == "partial":
        exact_tasks = {}
    elif change == "extra":
        exact_tasks["extra"] = exact_tasks["content-a"]
    elif change == "non_task":
        exact_tasks["content-a"] = contracts.AnalystExactRef(
            resourceType="Artifact", resourceId="artifact-1", revision=1, contentHash=HASH
        )
    elif change == "naive":
        now = datetime(2026, 9, 12)
    elif change == "blank_actor":
        actor = " "
    elif change == "wrong_plan_ref":
        plan_ref = contracts.AnalystExactRef(
            resourceType="GrowthPlanRevision",
            resourceId="plan-1",
            revision=1,
            contentHash="b" * 64,
        )
    with pytest.raises((ValueError, RuntimeError), match=message):
        materializer.assemble_task_graph(
            plan=plan,
            plan_ref=plan_ref,
            exact_tasks=exact_tasks,
            graph_id="graph-1",
            actor=actor,
            now=now,
        )


def test_standalone_import_never_loads_platform_modules() -> None:
    program = """
import sys
class DenyPlatform:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aos_api" or fullname.startswith("aos_api."):
            raise AssertionError("platform import forbidden: " + fullname)
sys.meta_path.insert(0, DenyPlatform())
sys.path.insert(0, sys.argv[1])
from ecommerce_growth.ecommerce_analyst_materializer import assemble_task_graph
assert callable(assemble_task_graph)
assert not any(name.startswith("aos_api") for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-I", "-c", program, str(BACKEND)],
        check=True,
        capture_output=True,
        text=True,
    )
